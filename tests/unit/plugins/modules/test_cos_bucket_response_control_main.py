"""Unit tests for the cos_bucket_response_control write module (run_module flows).

Drives ``run_module()`` against an in-memory fake COS client whose
``get/put/delete_bucket_response_control`` operations mutate a
response-control store. The module reaches ``qcloud_cos`` via
``module_utils/cos.py``, so ``cos.require_cos_sdk`` and
``cos.create_cos_client`` are monkeypatched.

Scenario matrix:

* absent on a missing rule (idempotent no-op) and on an existing rule
  (check-mode dry run, real delete)
* creation when missing (happy path, check mode)
* no-op when parameters already match; parameter drift triggers put
* blanket COS SDK failure maps to the error payload
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils import cos
from ansible_collections.susunola.tencentcloud.plugins.modules import cos_bucket_response_control as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    module_args,
    run,
)

NORMALIZED = {
    "ControlParamList": {
        "Param": [
            "response-cache-control",
            "response-content-disposition",
            "response-content-encoding",
            "response-expires",
        ]
    }
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
    """In-memory COS client mutating a response-control store."""

    def __init__(self, control=None):
        self.control = copy.deepcopy(control)
        self.calls = []

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def get_bucket_response_control(self, Bucket, **kwargs):
        self._record("get_bucket_response_control", Bucket)
        if self.control is None:
            raise FakeCosError("NoSuchBucket")
        return {"ResponseControlConfiguration": copy.deepcopy(self.control)}

    def put_bucket_response_control(self, Bucket, ResponseControlConfiguration, **kwargs):
        self._record("put_bucket_response_control", ResponseControlConfiguration)
        self.control = copy.deepcopy(ResponseControlConfiguration)

    def delete_bucket_response_control(self, Bucket, **kwargs):
        self._record("delete_bucket_response_control", Bucket)
        self.control = None


def _make_module(monkeypatch, fake, appid="1250000000"):
    monkeypatch.setattr(cos, "require_cos_sdk", lambda module: None)
    monkeypatch.setattr(cos, "create_cos_client", lambda module: fake)
    monkeypatch.setattr(cos, "resolve_appid", lambda module: appid)
    return fake


def _config(**overrides):
    params = {"name": "application-data", "appid": "1250000000"}
    params.update(overrides)
    return module_args(**params)


def _control_args(**overrides):
    params = {
        "state": "present",
        "parameters": [
            "response-cache-control",
            "response-content-disposition",
            "response-content-encoding",
            "response-expires",
        ],
    }
    params.update(overrides)
    return params


def test_absent_missing_is_idempotent(monkeypatch):
    fake = FakeCosClient(control=None)
    _make_module(monkeypatch, fake)
    _config(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["response_control"] is None
    assert [c for c, unused in fake.calls] == ["get_bucket_response_control"]


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeCosClient(control=NORMALIZED)
    _make_module(monkeypatch, fake)
    _config(_ansible_check_mode=True, state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert fake.control is not None
    assert "delete_bucket_response_control" not in [c for c, unused in fake.calls]


def test_absent_deletes_configuration(monkeypatch):
    fake = FakeCosClient(control=NORMALIZED)
    _make_module(monkeypatch, fake)
    _config(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert fake.control is None
    ops = [c for c, unused in fake.calls]
    assert "delete_bucket_response_control" in ops


def test_create_configuration(monkeypatch):
    fake = FakeCosClient(control=None)
    _make_module(monkeypatch, fake)
    _config(**_control_args())
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["response_control"] == NORMALIZED
    assert fake.control == NORMALIZED
    ops = [c for c, unused in fake.calls]
    assert ops[0] == "get_bucket_response_control"
    assert "put_bucket_response_control" in ops


def test_create_check_mode_is_dry_run(monkeypatch):
    fake = FakeCosClient(control=None)
    _make_module(monkeypatch, fake)
    _config(_ansible_check_mode=True, **_control_args())
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["response_control"] == NORMALIZED
    assert fake.control is None
    assert "put_bucket_response_control" not in [c for c, unused in fake.calls]


def test_existing_no_drift_is_idempotent(monkeypatch):
    fake = FakeCosClient(control=NORMALIZED)
    _make_module(monkeypatch, fake)
    _config(**_control_args())
    result = run(mod.run_module)
    assert result["changed"] is False
    assert "put_bucket_response_control" not in [c for c, unused in fake.calls]


def test_parameter_drift_triggers_update(monkeypatch):
    fake = FakeCosClient(control=NORMALIZED)
    _make_module(monkeypatch, fake)
    _config(
        **_control_args(
            parameters=["response-content-type", "response-content-language", "response-expires"]
        )
    )
    result = run(mod.run_module)
    expected = ["response-content-language", "response-content-type", "response-expires"]
    assert result["changed"] is True
    assert result["response_control"]["ControlParamList"]["Param"] == expected
    assert fake.control["ControlParamList"]["Param"] == expected
    ops = [c for c, unused in fake.calls]
    assert "put_bucket_response_control" in ops


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def get_bucket_response_control(self, Bucket, **kwargs):
            raise Boom("connection dropped")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    _config(**_control_args())
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud COS request failed"
    assert "connection dropped" in payload["error"]
