"""Deep harness tests for the dlc_model_artifact_info module.

Covers build_request (strong model-version identity) and run_module
end-to-end over the config/files/readme artifact calls: request identity,
independent artifact selection, ConfigJson parsing, the "no artifact
selected" validation and the sdk_error_payload failure contract. This module
has no paginator; each artifact is a single describe call.
"""
from __future__ import absolute_import, division, print_function

__metaclass__ = type

import sys
import types

import pytest

from ansible_collections.susunola.tencentcloud.plugins.modules import dlc_model_artifact_info


class Request:
    pass


class FakeModels:
    GetModelConfigRequest = Request
    GetModelFilesRequest = Request
    GetModelReadmeRequest = Request


def params():
    return {"model_uid": "model-1", "model_version": "v2",
            "include_config": True, "include_files": True, "include_readme": True}


def test_build_request_uses_strong_model_version_identity():
    request = dlc_model_artifact_info.build_request(Request, params())
    assert request.ModelUid == "model-1"
    assert request.ModelVersion == "v2"


class FakeResponse:
    def __init__(self, value):
        self.value = dict(value)

    def _serialize(self, allow_none=True):
        return dict(self.value)


class FakeClient:
    def __init__(self, responses):
        self.responses = dict(responses)
        self.calls = []

    def _serve(self, name, request):
        self.calls.append((name, request.ModelUid, request.ModelVersion))
        return FakeResponse(self.responses[name])

    def GetModelConfig(self, request):
        return self._serve("config", request)

    def GetModelFiles(self, request):
        return self._serve("files", request)

    def GetModelReadme(self, request):
        return self._serve("readme", request)


class ModuleExit(BaseException):
    pass


class ModuleFail(BaseException):
    def __init__(self, payload):
        self.payload = payload
        super(ModuleFail, self).__init__("module failed: %r" % (payload,))


class SDKError(Exception):
    def get_code(self):
        return "UnauthorizedOperation"

    def get_request_id(self):
        return "req-err"


class FakeModule:
    def __init__(self, params, client):
        self.params = params
        self.client = client
        self.exit_payload = None
        self.fail_payload = None

    def exit_json(self, **kwargs):
        self.exit_payload = kwargs
        raise ModuleExit()

    def fail_json(self, **kwargs):
        self.fail_payload = kwargs
        raise ModuleFail(kwargs)

    def require_sdk(self):
        pass

    def create_client(self, client_class, endpoint):
        return self.client

    def sdk_call(self, operation, request=None, retry=True):
        if request is None:
            return operation()
        return operation(request)


def _inject_sdk(monkeypatch):
    service = types.ModuleType("tencentcloud.dlc.v20210125")
    service.models = FakeModels
    service.dlc_client = types.SimpleNamespace(DlcClient=object)
    monkeypatch.setitem(sys.modules, "tencentcloud", types.ModuleType("tencentcloud"))
    monkeypatch.setitem(sys.modules, "tencentcloud.dlc",
                        types.ModuleType("tencentcloud.dlc"))
    monkeypatch.setitem(sys.modules, "tencentcloud.dlc.v20210125", service)


def _run(monkeypatch, client, expect_fail=False, **p):
    _inject_sdk(monkeypatch)
    fake = FakeModule(p, client)
    monkeypatch.setattr(dlc_model_artifact_info, "TencentCloudModule", lambda **kwargs: fake)
    with pytest.raises(ModuleFail if expect_fail else ModuleExit):
        dlc_model_artifact_info.run_module()
    return fake


def test_run_module_combines_all_artifacts_and_parses_config_json(monkeypatch):
    client = FakeClient({
        "config": {"ModelName": "m", "ConfigJson": '{"layers": 12}', "RequestId": "rc"},
        "files": {"Files": [{"Name": "weights"}], "RequestId": "rf"},
        "readme": {"Readme": "# Model", "RequestId": "rr"},
    })
    fake = _run(monkeypatch, client, region="ap-guangzhou", **params())
    payload = fake.exit_payload
    assert payload["changed"] is False
    assert payload["request_ids"] == {"config": "rc", "files": "rf", "readme": "rr"}
    assert payload["config"]["Config"] == {"layers": 12}
    assert "RequestId" not in payload["config"]
    assert payload["files"]["Files"] == [{"Name": "weights"}]
    assert payload["readme"]["Readme"] == "# Model"
    assert all(call[1:] == ("model-1", "v2") for call in client.calls)
    assert [call[0] for call in client.calls] == ["config", "files", "readme"]


def test_run_module_honours_selection_and_tolerates_invalid_config_json(monkeypatch):
    p = dict(params(), include_files=False, include_readme=False)
    client = FakeClient({"config": {"ConfigJson": "not-json", "RequestId": "rc"}})
    fake = _run(monkeypatch, client, region="ap-guangzhou", **p)
    payload = fake.exit_payload
    assert payload == {
        "changed": False,
        "request_ids": {"config": "rc"},
        "config": {"ConfigJson": "not-json", "Config": None},
    }
    assert [call[0] for call in client.calls] == ["config"]


def test_run_module_rejects_no_selected_artifact(monkeypatch):
    p = dict(params(), include_config=False, include_files=False, include_readme=False)
    payload = _run(monkeypatch, None, expect_fail=True,
                   region="ap-guangzhou", **p).fail_payload
    assert payload["msg"] == "at least one model artifact must be selected"


def test_run_module_fails_cleanly_on_sdk_error(monkeypatch):
    class FailingClient:
        def _explode(self, request):
            raise SDKError("api exploded")

        GetModelConfig = _explode
        GetModelFiles = _explode
        GetModelReadme = _explode

    payload = _run(monkeypatch, FailingClient(), expect_fail=True,
                   region="ap-guangzhou", **params()).fail_payload
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert payload["error"] == "api exploded"
    assert payload["error_code"] == "UnauthorizedOperation"
    assert payload["request_id"] == "req-err"
