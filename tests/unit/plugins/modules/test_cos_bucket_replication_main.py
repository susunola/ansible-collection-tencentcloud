"""Unit tests for the cos_bucket_replication write module (run_module flows).

Drives ``run_module()`` against an in-memory fake COS client whose
``get/put/delete_bucket_replication`` operations mutate a replication store.
The module reaches ``qcloud_cos`` via ``module_utils/cos.py``, so
``cos.require_cos_sdk`` and ``cos.create_cos_client`` are monkeypatched.

Scenario matrix:

* absent on a missing rule (idempotent no-op) and on an existing rule
  (check-mode dry run, real delete)
* creation when missing (happy path, check mode)
* no-op when the configuration already matches; rule/role drift triggers put
* blanket COS SDK failure maps to the error payload
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils import cos
from ansible_collections.susunola.tencentcloud.plugins.modules import cos_bucket_replication as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    module_args,
    run,
)

ROLE = "qcs::cam::uin/100000000001:uin/100000000001"
RULES = [
    {
        "ID": "rule-1",
        "Prefix": "docs/",
        "Status": "Enabled",
        "Destination": {
            "Bucket": "backup-1250000000",
            "StorageClass": "STANDARD",
        },
    }
]

NORMALIZED = {"Role": ROLE, "Rule": copy.deepcopy(RULES)}


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
    """In-memory COS client mutating a replication store."""

    def __init__(self, replication=None):
        self.replication = copy.deepcopy(replication)
        self.calls = []

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def get_bucket_replication(self, Bucket, **kwargs):
        self._record("get_bucket_replication", Bucket)
        if self.replication is None:
            raise FakeCosError("NoSuchBucket")
        return {"ReplicationConfiguration": copy.deepcopy(self.replication)}

    def put_bucket_replication(self, Bucket, ReplicationConfiguration, **kwargs):
        self._record("put_bucket_replication", ReplicationConfiguration)
        self.replication = copy.deepcopy(ReplicationConfiguration)

    def delete_bucket_replication(self, Bucket, **kwargs):
        self._record("delete_bucket_replication", Bucket)
        self.replication = None


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


def _replication_args(**overrides):
    params = {"state": "present", "role": ROLE, "rules": _rules()}
    params.update(overrides)
    return params


def test_absent_missing_is_idempotent(monkeypatch):
    fake = FakeCosClient(replication=None)
    _make_module(monkeypatch, fake)
    _config(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["replication"] is None
    assert [c for c, unused in fake.calls] == ["get_bucket_replication"]


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeCosClient(replication=NORMALIZED)
    _make_module(monkeypatch, fake)
    _config(_ansible_check_mode=True, state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["replication"] == NORMALIZED
    assert fake.replication is not None
    assert "delete_bucket_replication" not in [c for c, unused in fake.calls]


def test_absent_deletes_configuration(monkeypatch):
    fake = FakeCosClient(replication=NORMALIZED)
    _make_module(monkeypatch, fake)
    _config(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["replication"] is None
    assert fake.replication is None
    ops = [c for c, unused in fake.calls]
    assert "delete_bucket_replication" in ops


def test_create_configuration(monkeypatch):
    fake = FakeCosClient(replication=None)
    _make_module(monkeypatch, fake)
    _config(**_replication_args())
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["replication"] == NORMALIZED
    assert fake.replication == NORMALIZED
    ops = [c for c, unused in fake.calls]
    assert ops[0] == "get_bucket_replication"
    assert "put_bucket_replication" in ops


def test_create_check_mode_is_dry_run(monkeypatch):
    fake = FakeCosClient(replication=None)
    _make_module(monkeypatch, fake)
    _config(_ansible_check_mode=True, **_replication_args())
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["replication"] == NORMALIZED
    assert fake.replication is None
    assert "put_bucket_replication" not in [c for c, unused in fake.calls]


def test_existing_no_drift_is_idempotent(monkeypatch):
    fake = FakeCosClient(replication=NORMALIZED)
    _make_module(monkeypatch, fake)
    _config(**_replication_args())
    result = run(mod.run_module)
    assert result["changed"] is False
    assert "put_bucket_replication" not in [c for c, unused in fake.calls]


def test_rule_drift_triggers_update(monkeypatch):
    updated = [
        {
            "ID": "rule-1",
            "Prefix": "docs/",
            "Status": "Enabled",
            "Destination": {"Bucket": "backup-1250000000", "StorageClass": "STANDARD_IA"},
        }
    ]
    fake = FakeCosClient(replication=NORMALIZED)
    _make_module(monkeypatch, fake)
    _config(**_replication_args(rules=updated))
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["replication"]["Rule"][0]["Destination"]["StorageClass"] == "STANDARD_IA"
    ops = [c for c, unused in fake.calls]
    assert "put_bucket_replication" in ops


def test_role_drift_triggers_update(monkeypatch):
    fake = FakeCosClient(replication=NORMALIZED)
    _make_module(monkeypatch, fake)
    _config(**_replication_args(role="qcs::cam::uin/200000000002:uin/200000000002"))
    result = run(mod.run_module)
    assert result["changed"] is True
    ops = [c for c, unused in fake.calls]
    assert "put_bucket_replication" in ops


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def get_bucket_replication(self, Bucket, **kwargs):
            raise Boom("connection dropped")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    _config(**_replication_args())
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud COS request failed"
    assert "connection dropped" in payload["error"]
