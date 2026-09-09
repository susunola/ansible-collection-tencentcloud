"""Unit tests for the cos_bucket_origin write module (run_module flows).

Drives ``run_module()`` against an in-memory fake COS client whose
``get/put/delete_bucket_origin`` operations mutate an origin-config store.
The module reaches ``qcloud_cos`` via ``module_utils/cos.py``, so
``cos.require_cos_sdk`` and ``cos.create_cos_client`` are monkeypatched.

Scenario matrix:

* absent on a missing rule (idempotent no-op) and on an existing rule
  (check-mode dry run, real delete)
* creation when missing (happy path, check mode)
* no-op when rules already match; rule drift triggers ``put``
* blanket COS SDK failure maps to the error payload
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils import cos
from ansible_collections.susunola.tencentcloud.plugins.modules import cos_bucket_origin as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    module_args,
    run,
)

RULES = [
    {"RulePriority": 1, "OriginType": "COS", "OriginValue": "source-1250000000.cos.ap-guangzhou.myqcloud.com"},
    {"RulePriority": 2, "OriginType": "COS", "OriginValue": "backup-1250000000.cos.ap-guangzhou.myqcloud.com"},
]

NORMALIZED = {"OriginRule": copy.deepcopy(RULES)}


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
    """In-memory COS client mutating an origin-configuration store."""

    def __init__(self, origin=None):
        self.origin = copy.deepcopy(origin)
        self.calls = []

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def get_bucket_origin(self, Bucket, **kwargs):
        self._record("get_bucket_origin", Bucket)
        if self.origin is None:
            raise FakeCosError("NoSuchBucket")
        return {"OriginConfiguration": copy.deepcopy(self.origin)}

    def put_bucket_origin(self, Bucket, OriginConfiguration, **kwargs):
        self._record("put_bucket_origin", OriginConfiguration)
        self.origin = copy.deepcopy(OriginConfiguration)

    def delete_bucket_origin(self, Bucket, **kwargs):
        self._record("delete_bucket_origin", Bucket)
        self.origin = None


def _make_module(monkeypatch, fake, appid="1250000000"):
    monkeypatch.setattr(cos, "require_cos_sdk", lambda module: None)
    monkeypatch.setattr(cos, "create_cos_client", lambda module: fake)
    monkeypatch.setattr(cos, "resolve_appid", lambda module: appid)
    return fake


def _rules():
    return copy.deepcopy(RULES)


def _config(**overrides):
    params = {"name": "application-data", "appid": "1250000000"}
    params.update(overrides)
    return module_args(**params)


def test_absent_missing_is_idempotent(monkeypatch):
    fake = FakeCosClient(origin=None)
    _make_module(monkeypatch, fake)
    _config(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["origin"] is None
    assert [c for c, unused in fake.calls] == ["get_bucket_origin"]


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeCosClient(origin=NORMALIZED)
    _make_module(monkeypatch, fake)
    _config(_ansible_check_mode=True, state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert fake.origin is not None
    assert "delete_bucket_origin" not in [c for c, unused in fake.calls]


def test_absent_deletes_configuration(monkeypatch):
    fake = FakeCosClient(origin=NORMALIZED)
    _make_module(monkeypatch, fake)
    _config(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert fake.origin is None
    ops = [c for c, unused in fake.calls]
    assert "delete_bucket_origin" in ops


def test_create_configuration(monkeypatch):
    fake = FakeCosClient(origin=None)
    _make_module(monkeypatch, fake)
    _config(state="present", rules=_rules())
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["origin"] == NORMALIZED
    assert fake.origin == NORMALIZED
    ops = [c for c, unused in fake.calls]
    assert ops[0] == "get_bucket_origin"
    assert "put_bucket_origin" in ops


def test_create_check_mode_is_dry_run(monkeypatch):
    fake = FakeCosClient(origin=None)
    _make_module(monkeypatch, fake)
    _config(_ansible_check_mode=True, state="present", rules=_rules())
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["origin"] == NORMALIZED
    assert fake.origin is None
    assert "put_bucket_origin" not in [c for c, unused in fake.calls]


def test_existing_no_drift_is_idempotent(monkeypatch):
    fake = FakeCosClient(origin=NORMALIZED)
    _make_module(monkeypatch, fake)
    _config(state="present", rules=_rules())
    result = run(mod.run_module)
    assert result["changed"] is False
    assert "put_bucket_origin" not in [c for c, unused in fake.calls]


def test_rule_drift_triggers_update(monkeypatch):
    updated = [
        {"RulePriority": 1, "OriginType": "COS", "OriginValue": "replaced-1250000000.cos.ap-guangzhou.myqcloud.com"}
    ]
    fake = FakeCosClient(origin=NORMALIZED)
    _make_module(monkeypatch, fake)
    _config(state="present", rules=updated)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert len(result["origin"]["OriginRule"]) == 1
    ops = [c for c, unused in fake.calls]
    assert "put_bucket_origin" in ops


def test_rule_order_normalized_by_priority(monkeypatch):
    # Input order differs from priority order; normalize sorts by RulePriority.
    shuffled = [
        {"RulePriority": 2, "OriginType": "COS", "OriginValue": "backup-1250000000.cos.ap-guangzhou.myqcloud.com"},
        {"RulePriority": 1, "OriginType": "COS", "OriginValue": "source-1250000000.cos.ap-guangzhou.myqcloud.com"},
    ]
    fake = FakeCosClient(origin=None)
    _make_module(monkeypatch, fake)
    _config(state="present", rules=shuffled)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["origin"]["OriginRule"][0]["RulePriority"] == 1
    assert fake.origin["OriginRule"][0]["RulePriority"] == 1


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def get_bucket_origin(self, Bucket, **kwargs):
            raise Boom("connection dropped")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    _config(state="present", rules=_rules())
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud COS request failed"
    assert "connection dropped" in payload["error"]
