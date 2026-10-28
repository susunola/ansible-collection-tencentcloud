"""Unit tests for the cos_bucket_policy_info module (run_module level).

Drives ``run_module()`` against an in-memory fake COS client. The module
reaches ``qcloud_cos`` via ``module_utils/cos.py``, so ``cos.require_cos_sdk``
and ``cos.create_cos_client`` are monkeypatched.

Scenario matrix:

* existing policy as a dict is reported as a single-element ``policies`` list
* JSON-string payloads and the ``{"Policy": ...}`` wrapper are normalized
* a bucket without a policy (404) yields empty ``policies`` and ``policy: None``
* a non-404 COS SDK failure maps to ``fail_json``
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import json

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils import cos
from ansible_collections.susunola.tencentcloud.plugins.modules import cos_bucket_policy_info as mod
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
            "resource": ["qcs::cos:ap-guangzhou:uid/1300000000:application-data-1300000000/*"],
        }
    ],
}


class FakeCosError(Exception):
    """Stand-in for qcloud_cos.cos_exception.CosServiceError."""

    def __init__(self, code, status=404, request_id="req-fake"):
        super(FakeCosError, self).__init__(code)
        self._code = code
        self._status = status
        self._request_id = request_id

    def get_error_code(self):
        return self._code

    def get_status_code(self):
        return self._status

    def get_request_id(self):
        return self._request_id


class FakeCosClient(object):
    def __init__(self, policies=None):
        self.policies = dict(policies or {})

    def get_bucket_policy(self, Bucket, **kwargs):
        if Bucket not in self.policies:
            raise FakeCosError("NoSuchPolicy")
        return self.policies[Bucket]


@pytest.fixture
def client(monkeypatch):
    fake = FakeCosClient()
    monkeypatch.setattr(cos, "require_cos_sdk", lambda module: None)
    monkeypatch.setattr(cos, "create_cos_client", lambda module: fake)
    return fake


def test_existing_policy_is_returned(client):
    client.policies["application-data-1300000000"] = POLICY
    module_args(name="application-data", appid="1300000000")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["policies"] == [POLICY]
    assert result["policy"] == POLICY


def test_json_string_payload_is_normalized(client):
    client.policies["application-data-1300000000"] = json.dumps(POLICY)
    module_args(name="application-data", appid="1300000000")
    result = run(mod.run_module)
    assert result["policies"] == [POLICY]
    assert result["policy"] == POLICY


def test_policy_wrapper_is_unwrapped(client):
    client.policies["application-data-1300000000"] = {"Policy": POLICY}
    module_args(name="application-data", appid="1300000000")
    result = run(mod.run_module)
    assert result["policies"] == [POLICY]
    assert result["policy"] == POLICY


def test_missing_policy_yields_empty_result(client):
    module_args(name="application-data", appid="1300000000")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["policies"] == []
    assert result["policy"] is None


def test_sdk_error_maps_to_fail_json(client):
    def broken(Bucket, **kwargs):
        raise FakeCosError("AccessDenied", status=403)

    client.get_bucket_policy = broken
    module_args(name="application-data", appid="1300000000")
    with pytest.raises(AnsibleFailJson) as excinfo:
        run(mod.run_module)
    assert excinfo.value.args[0]["error_code"] == "AccessDenied"
