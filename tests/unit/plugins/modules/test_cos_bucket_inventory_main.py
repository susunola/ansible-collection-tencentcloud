"""Unit tests for the cos_bucket_inventory write module (run_module flows).

Drives ``run_module()`` against an in-memory fake COS client whose
``get/put/delete_bucket_inventory`` operations mutate a store of named
inventory rules. The module reaches ``qcloud_cos`` via
``module_utils/cos.py``, so ``cos.require_cos_sdk`` and
``cos.create_cos_client`` are monkeypatched.

Scenario matrix:

* absent on a missing rule (idempotent no-op) and on an existing rule
  (check-mode dry run, real delete)
* creation when missing (happy path, check mode)
* no-op when the configuration already matches; OptionalFields sorting is
  treated as idempotent; config drift triggers put
* blanket COS SDK failure maps to the error payload
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils import cos
from ansible_collections.susunola.tencentcloud.plugins.modules import cos_bucket_inventory as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    module_args,
    run,
)

INVENTORY_ID = "daily-objects"
BASE = {
    "IsEnabled": "True",
    "IncludedObjectVersions": "All",
    "Schedule": {"Frequency": "Daily"},
    "Destination": {
        "COSBucketDestination": {
            "AccountId": "1250000000",
            "Bucket": "qcs::cos:ap-guangzhou::inventory-1250000000",
            "Format": "CSV",
        }
    },
}
NORMALIZED = dict(BASE, Id=INVENTORY_ID)


class FakeCosError(Exception):
    """Stand-in for qcloud_cos.cos_exception.CosServiceError."""

    def __init__(self, code, status=404):
        super(FakeCosError, self).__init__(code)
        self._code = code
        self._status = status

    def get_error_code(self):
        return self._code

    def get_status_code(self):
        return self._status


class FakeCosClient(object):
    """In-memory COS client mutating a store of named inventory rules."""

    def __init__(self, rules=None):
        # rules: {inventory_id: raw InventoryConfiguration document}
        self.rules = copy.deepcopy(rules) if rules is not None else {}
        self.calls = []

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def get_bucket_inventory(self, Bucket, Id, **kwargs):
        self._record("get_bucket_inventory", Id)
        if Id not in self.rules:
            raise FakeCosError("NoSuchBucket")
        return {"InventoryConfiguration": copy.deepcopy(self.rules[Id])}

    def put_bucket_inventory(self, Bucket, Id, InventoryConfiguration, **kwargs):
        self._record("put_bucket_inventory", Id)
        self.rules[Id] = copy.deepcopy(InventoryConfiguration)

    def delete_bucket_inventory(self, Bucket, Id, **kwargs):
        self._record("delete_bucket_inventory", Id)
        self.rules.pop(Id, None)


def _make_module(monkeypatch, fake, appid="1250000000"):
    monkeypatch.setattr(cos, "require_cos_sdk", lambda module: None)
    monkeypatch.setattr(cos, "create_cos_client", lambda module: fake)
    monkeypatch.setattr(cos, "resolve_appid", lambda module: appid)
    return fake


def _config(**overrides):
    params = {"name": "application-data", "appid": "1250000000", "inventory_id": INVENTORY_ID}
    params.update(overrides)
    return module_args(**params)


def _present_args(**overrides):
    params = {"state": "present", "configuration": copy.deepcopy(BASE)}
    params.update(overrides)
    return params


def test_absent_missing_is_idempotent(monkeypatch):
    fake = FakeCosClient(rules={})
    _make_module(monkeypatch, fake)
    _config(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["inventory"] is None
    assert [c for c, unused in fake.calls] == ["get_bucket_inventory"]


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeCosClient(rules={INVENTORY_ID: copy.deepcopy(NORMALIZED)})
    _make_module(monkeypatch, fake)
    _config(_ansible_check_mode=True, state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert INVENTORY_ID in fake.rules
    assert "delete_bucket_inventory" not in [c for c, unused in fake.calls]


def test_absent_deletes_rule(monkeypatch):
    fake = FakeCosClient(rules={INVENTORY_ID: copy.deepcopy(NORMALIZED)})
    _make_module(monkeypatch, fake)
    _config(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert INVENTORY_ID not in fake.rules
    ops = [c for c, unused in fake.calls]
    assert "delete_bucket_inventory" in ops


def test_create_rule(monkeypatch):
    fake = FakeCosClient(rules={})
    _make_module(monkeypatch, fake)
    _config(**_present_args())
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["inventory"] == NORMALIZED
    assert fake.rules[INVENTORY_ID] == NORMALIZED
    ops = [c for c, unused in fake.calls]
    assert ops[0] == "get_bucket_inventory"
    assert "put_bucket_inventory" in ops


def test_create_check_mode_is_dry_run(monkeypatch):
    fake = FakeCosClient(rules={})
    _make_module(monkeypatch, fake)
    _config(_ansible_check_mode=True, **_present_args())
    result = run(mod.run_module)
    assert result["changed"] is True
    assert INVENTORY_ID not in fake.rules
    assert "put_bucket_inventory" not in [c for c, unused in fake.calls]


def test_existing_no_drift_is_idempotent(monkeypatch):
    fake = FakeCosClient(rules={INVENTORY_ID: copy.deepcopy(NORMALIZED)})
    _make_module(monkeypatch, fake)
    _config(**_present_args())
    result = run(mod.run_module)
    assert result["changed"] is False
    assert "put_bucket_inventory" not in [c for c, unused in fake.calls]


def test_optional_fields_order_is_idempotent(monkeypatch):
    """OptionalFields.Field lists are sorted during normalize, so a different
    stored order must not look like drift."""
    stored = copy.deepcopy(NORMALIZED)
    stored["OptionalFields"] = {"Field": ["Size", "ETag", "LastModifiedTime"]}
    target = copy.deepcopy(BASE)
    target["OptionalFields"] = {"Field": ["LastModifiedTime", "Size", "ETag"]}
    fake = FakeCosClient(rules={INVENTORY_ID: stored})
    _make_module(monkeypatch, fake)
    _config(**_present_args(configuration=target))
    result = run(mod.run_module)
    assert result["changed"] is False
    assert "put_bucket_inventory" not in [c for c, unused in fake.calls]


def test_configuration_drift_triggers_update(monkeypatch):
    drifted = copy.deepcopy(NORMALIZED)
    drifted["Schedule"] = {"Frequency": "Weekly"}
    fake = FakeCosClient(rules={INVENTORY_ID: drifted})
    _make_module(monkeypatch, fake)
    _config(**_present_args())
    result = run(mod.run_module)
    assert result["changed"] is True
    assert fake.rules[INVENTORY_ID]["Schedule"] == {"Frequency": "Daily"}
    ops = [c for c, unused in fake.calls]
    assert "put_bucket_inventory" in ops


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def get_bucket_inventory(self, Bucket, Id, **kwargs):
            raise Boom("connection dropped")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    _config(**_present_args())
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud COS request failed"
    assert "connection dropped" in payload["error"]
