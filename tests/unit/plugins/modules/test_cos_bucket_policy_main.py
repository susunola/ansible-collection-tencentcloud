"""Unit tests for the cos_bucket_policy write module (run_module flows).

Drives ``run_module()`` against an in-memory fake COS client whose
``get/put/delete_bucket_policy`` operations mutate a bucket-policy store.
The module reaches ``qcloud_cos`` via ``module_utils/cos.py``, so
``cos.require_cos_sdk`` and ``cos.create_cos_client`` are monkeypatched.

Scenario matrix:

* absent on a missing policy (idempotent no-op) and on an existing policy
  (check-mode dry run, real delete)
* creation when missing (happy path, check mode; put receives a compact
  JSON document)
* no-op when the policy already matches; policy drift triggers put
* blanket COS SDK failure maps to the error payload
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
import json

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils import cos
from ansible_collections.susunola.tencentcloud.plugins.modules import cos_bucket_policy as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    module_args,
    run,
)

POLICY = {
    "version": "2.0",
    "statement": [
        {
            "effect": "allow",
            "principal": {"qcs": ["qcs::cam::uin/100000000001:uin/100000000001"]},
            "action": ["name/cos:GetObject"],
            "resource": ["qcs::cos:ap-guangzhou:uid/1250000000:application-data-1250000000/*"],
        }
    ],
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
    """In-memory COS client mutating a bucket-policy store."""

    def __init__(self, policy=None):
        self.policy = copy.deepcopy(policy)
        self.calls = []

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def get_bucket_policy(self, Bucket, **kwargs):
        self._record("get_bucket_policy", Bucket)
        if self.policy is None:
            raise FakeCosError("NoSuchBucketPolicy")
        return {"Policy": json.dumps(self.policy)}

    def put_bucket_policy(self, Bucket, Policy, **kwargs):
        self._record("put_bucket_policy", Policy)
        self.policy = json.loads(Policy)

    def delete_bucket_policy(self, Bucket, **kwargs):
        self._record("delete_bucket_policy", Bucket)
        self.policy = None


def _make_module(monkeypatch, fake, appid="1250000000"):
    monkeypatch.setattr(cos, "require_cos_sdk", lambda module: None)
    monkeypatch.setattr(cos, "create_cos_client", lambda module: fake)
    monkeypatch.setattr(cos, "resolve_appid", lambda module: appid)
    return fake


def _config(**overrides):
    params = {"name": "application-data", "appid": "1250000000"}
    params.update(overrides)
    return module_args(**params)


def _present_args(**overrides):
    params = {"state": "present", "policy": copy.deepcopy(POLICY)}
    params.update(overrides)
    return params


def test_absent_missing_is_idempotent(monkeypatch):
    fake = FakeCosClient(policy=None)
    _make_module(monkeypatch, fake)
    _config(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["policy"] is None
    assert [c for c, unused in fake.calls] == ["get_bucket_policy"]


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeCosClient(policy=copy.deepcopy(POLICY))
    _make_module(monkeypatch, fake)
    _config(_ansible_check_mode=True, state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert fake.policy is not None
    assert "delete_bucket_policy" not in [c for c, unused in fake.calls]


def test_absent_deletes_policy(monkeypatch):
    fake = FakeCosClient(policy=copy.deepcopy(POLICY))
    _make_module(monkeypatch, fake)
    _config(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert fake.policy is None
    ops = [c for c, unused in fake.calls]
    assert "delete_bucket_policy" in ops


def test_create_policy(monkeypatch):
    fake = FakeCosClient(policy=None)
    _make_module(monkeypatch, fake)
    _config(**_present_args())
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["policy"] == POLICY
    assert fake.policy == POLICY
    ops = [c for c, unused in fake.calls]
    assert ops[0] == "get_bucket_policy"
    puts = [req for name, req in fake.calls if name == "put_bucket_policy"]
    assert len(puts) == 1
    # put receives a compact JSON document (no insignificant whitespace)
    assert puts[0] == json.dumps(POLICY, sort_keys=True, separators=(",", ":"))


def test_create_check_mode_is_dry_run(monkeypatch):
    fake = FakeCosClient(policy=None)
    _make_module(monkeypatch, fake)
    _config(_ansible_check_mode=True, **_present_args())
    result = run(mod.run_module)
    assert result["changed"] is True
    assert fake.policy is None
    assert "put_bucket_policy" not in [c for c, unused in fake.calls]


def test_existing_no_drift_is_idempotent(monkeypatch):
    fake = FakeCosClient(policy=copy.deepcopy(POLICY))
    _make_module(monkeypatch, fake)
    _config(**_present_args())
    result = run(mod.run_module)
    assert result["changed"] is False
    assert "put_bucket_policy" not in [c for c, unused in fake.calls]


def test_policy_drift_triggers_update(monkeypatch):
    stale = copy.deepcopy(POLICY)
    stale["statement"][0]["action"] = ["name/cos:GetBucket"]
    fake = FakeCosClient(policy=stale)
    _make_module(monkeypatch, fake)
    _config(**_present_args())
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["policy"]["statement"][0]["action"] == ["name/cos:GetObject"]
    assert fake.policy == POLICY
    ops = [c for c, unused in fake.calls]
    assert "put_bucket_policy" in ops


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def get_bucket_policy(self, Bucket, **kwargs):
            raise Boom("connection dropped")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    _config(**_present_args())
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud COS request failed"
    assert "connection dropped" in payload["error"]
