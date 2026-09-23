"""Unit tests for the cos_bucket_intelligent_tiering write module (run_module flows).

Drives ``run_module()`` against an in-memory fake COS client whose
``get/put_bucket_intelligenttiering_v2`` operations mutate an
intelligent-tiering store. The module reaches ``qcloud_cos`` via
``module_utils/cos.py``, so ``cos.require_cos_sdk`` and
``cos.create_cos_client`` are monkeypatched.

Scenario matrix:

* absent on a missing rule (idempotent no-op) and on an existing rule
  (hard failure -- the default rule cannot be disabled)
* enablement when missing (happy path, check mode)
* no-op when already enabled with matching days; transition_days drift
  triggers put
* request_frequent validation rejects non-positive values
* blanket COS SDK failure maps to the error payload
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils import cos
from ansible_collections.susunola.tencentcloud.plugins.modules import cos_bucket_intelligent_tiering as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    module_args,
    run,
)

NORMALIZED = {
    "Id": "default",
    "Status": "Enabled",
    "Tiering": {"AccessTier": "INFREQUENT", "Days": 30, "RequestFrequent": 1},
}


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
    """In-memory COS client mutating an intelligent-tiering store."""

    def __init__(self, rule=None):
        self.rule = copy.deepcopy(rule)
        self.calls = []

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def get_bucket_intelligenttiering_v2(self, Bucket, Id, **kwargs):
        self._record("get_bucket_intelligenttiering_v2", Id)
        if self.rule is None:
            raise FakeCosError("NoSuchBucket")
        return {"IntelligentTieringConfiguration": copy.deepcopy(self.rule)}

    def put_bucket_intelligenttiering_v2(self, Bucket, Id, IntelligentTieringConfiguration, **kwargs):
        self._record("put_bucket_intelligenttiering_v2", IntelligentTieringConfiguration)
        self.rule = copy.deepcopy(IntelligentTieringConfiguration)


def _make_module(monkeypatch, fake, appid="1250000000"):
    monkeypatch.setattr(cos, "require_cos_sdk", lambda module: None)
    monkeypatch.setattr(cos, "create_cos_client", lambda module: fake)
    monkeypatch.setattr(cos, "resolve_appid", lambda module: appid)
    return fake


def _config(**overrides):
    params = {"name": "application-data", "appid": "1250000000"}
    params.update(overrides)
    return module_args(**params)


def test_absent_missing_is_idempotent(monkeypatch):
    fake = FakeCosClient(rule=None)
    _make_module(monkeypatch, fake)
    _config(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["intelligent_tiering"] is None
    assert [c for c, unused in fake.calls] == ["get_bucket_intelligenttiering_v2"]


def test_absent_on_enabled_rule_fails(monkeypatch):
    fake = FakeCosClient(rule=NORMALIZED)
    _make_module(monkeypatch, fake)
    _config(state="absent")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "cannot be disabled" in payload["msg"]
    assert payload["intelligent_tiering"] == NORMALIZED


def test_create_rule(monkeypatch):
    fake = FakeCosClient(rule=None)
    _make_module(monkeypatch, fake)
    _config()
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["intelligent_tiering"] == NORMALIZED
    assert fake.rule == NORMALIZED
    ops = [c for c, unused in fake.calls]
    assert ops[0] == "get_bucket_intelligenttiering_v2"
    assert "put_bucket_intelligenttiering_v2" in ops


def test_create_check_mode_is_dry_run(monkeypatch):
    fake = FakeCosClient(rule=None)
    _make_module(monkeypatch, fake)
    _config(_ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["intelligent_tiering"] == NORMALIZED
    assert fake.rule is None
    assert "put_bucket_intelligenttiering_v2" not in [c for c, unused in fake.calls]


def test_existing_no_drift_is_idempotent(monkeypatch):
    fake = FakeCosClient(rule=NORMALIZED)
    _make_module(monkeypatch, fake)
    _config()
    result = run(mod.run_module)
    assert result["changed"] is False
    assert "put_bucket_intelligenttiering_v2" not in [c for c, unused in fake.calls]


def test_transition_days_drift_triggers_update(monkeypatch):
    fake = FakeCosClient(rule=copy.deepcopy(NORMALIZED))
    _make_module(monkeypatch, fake)
    _config(transition_days=60)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["intelligent_tiering"]["Tiering"]["Days"] == 60
    assert fake.rule["Tiering"]["Days"] == 60
    ops = [c for c, unused in fake.calls]
    assert "put_bucket_intelligenttiering_v2" in ops


def test_request_frequent_must_be_positive(monkeypatch):
    fake = FakeCosClient(rule=None)
    _make_module(monkeypatch, fake)
    _config(request_frequent=0)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "must be positive" in payload["msg"]


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def get_bucket_intelligenttiering_v2(self, Bucket, Id, **kwargs):
            raise Boom("connection dropped")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    _config()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud COS request failed"
    assert "connection dropped" in payload["error"]
