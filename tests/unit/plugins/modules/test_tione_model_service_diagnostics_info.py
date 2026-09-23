"""Deep harness tests for tione_model_service_diagnostics_info.

Covers call_request / preflight_request builders, serialize_call_info
gateway-variant serialization and run_module() end to end in both
mutually exclusive modes (service_group_id call info vs hot-update
preflight), mode validation, and the sdk_error_payload fail contract.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import json
import sys
import types

import pytest

from ansible_collections.susunola.tencentcloud.plugins.modules import tione_model_service_diagnostics_info


class FakeRequest:
    pass


class FakeJsonModel:
    def from_json_string(self, value):
        self.payload = json.loads(value)


class FakeModels:
    DescribeModelServiceCallInfoRequest = FakeRequest
    DescribeModelServiceHotUpdatedRequest = FakeRequest
    ImageInfo = FakeJsonModel
    ModelInfo = FakeJsonModel
    VolumeMount = FakeJsonModel


def call_params():
    return {"service_group_id": "msg-1", "project_id": "p1",
            "image_info": None, "model_info": None, "volume_mount": None}


def preflight_params():
    return {"service_group_id": None, "project_id": None,
            "image_info": {"ImageType": "TCR", "ImageUrl": "ccr.ccs.tencentyun.com/team/infer:v2"},
            "model_info": None, "volume_mount": {"Type": "CFS"}}


def test_call_request_uses_group_and_workspace_identity():
    request = tione_model_service_diagnostics_info.call_request(FakeModels, call_params())
    assert (request.ServiceGroupId, request.TiProjectId) == ("msg-1", "p1")


def test_call_request_omits_workspace_when_absent():
    p = dict(call_params(), project_id=None)
    assert not hasattr(tione_model_service_diagnostics_info.call_request(FakeModels, p), "TiProjectId")


def test_preflight_request_builds_only_supplied_sdk_models():
    request = tione_model_service_diagnostics_info.preflight_request(FakeModels, preflight_params())
    assert request.ImageInfo.payload == preflight_params()["image_info"]
    assert request.VolumeMount.payload == {"Type": "CFS"}
    assert not hasattr(request, "ModelInfo")


class FakeItem:
    def __init__(self, marker):
        self.marker = marker

    def _serialize(self, allow_none=True):
        return {"Marker": self.marker}


def test_serialize_call_info_preserves_all_gateway_variants():
    response = types.SimpleNamespace(
        ServiceCallInfo=FakeItem("legacy"), InferGatewayCallInfo=None,
        DefaultNginxGatewayCallInfo=FakeItem("nginx"), TJCallInfo=None,
        IntranetCallInfo=FakeItem("private"), ServiceCallInfoV2=FakeItem("gateway-v2"))
    value = tione_model_service_diagnostics_info.serialize_call_info(response)
    assert value["ServiceCallInfo"] == {"Marker": "legacy"}
    assert value["InferGatewayCallInfo"] is None
    assert value["DefaultNginxGatewayCallInfo"] == {"Marker": "nginx"}
    assert value["IntranetCallInfo"] == {"Marker": "private"}
    assert value["ServiceCallInfoV2"] == {"Marker": "gateway-v2"}


class ModuleExit(BaseException):
    pass


class ModuleFail(BaseException):
    def __init__(self, payload):
        self.payload = payload
        super(ModuleFail, self).__init__("module failed: %r" % (payload,))


class FakeModule:
    def __init__(self, params):
        self.params = params
        self.exit_payload = None
        self.fail_payload = None

    def require_sdk(self):
        pass

    def create_client(self, client_class, endpoint):
        return self._client

    def sdk_call(self, operation, request=None):
        if request is not None:
            return operation(request)
        return operation()

    def exit_json(self, **kwargs):
        self.exit_payload = kwargs
        raise ModuleExit()

    def fail_json(self, **kwargs):
        self.fail_payload = kwargs
        raise ModuleFail(kwargs)


def _inject_sdk(monkeypatch, client):
    service = types.ModuleType("tencentcloud.tione.v20211111")
    service.models = FakeModels
    service.tione_client = types.SimpleNamespace(TioneClient=lambda *args: object())
    monkeypatch.setitem(sys.modules, "tencentcloud", types.ModuleType("tencentcloud"))
    monkeypatch.setitem(sys.modules, "tencentcloud.tione",
                        types.ModuleType("tencentcloud.tione"))
    monkeypatch.setitem(sys.modules, "tencentcloud.tione.v20211111", service)


class FakeClient:
    def __init__(self):
        self.call_response = None
        self.preflight_response = None
        self.requests = []

    def DescribeModelServiceCallInfo(self, request):
        self.requests.append(request)
        return self.call_response

    def DescribeModelServiceHotUpdated(self, request):
        self.requests.append(request)
        return self.preflight_response


def _run(monkeypatch, client, **params):
    _inject_sdk(monkeypatch, client)
    fake = FakeModule(params)
    fake._client = client
    monkeypatch.setattr(tione_model_service_diagnostics_info, "TencentCloudModule",
                        lambda **kwargs: fake)
    with pytest.raises(ModuleExit):
        tione_model_service_diagnostics_info.run_module()
    return fake


def test_run_module_returns_call_info_for_service_group(monkeypatch):
    client = FakeClient()
    client.call_response = types.SimpleNamespace(
        ServiceCallInfo=FakeItem("legacy"), InferGatewayCallInfo=None,
        DefaultNginxGatewayCallInfo=None, TJCallInfo=None,
        IntranetCallInfo=FakeItem("private"), ServiceCallInfoV2=None,
        RequestId="req-call")
    fake = _run(monkeypatch, client, **call_params())
    payload = fake.exit_payload
    assert payload["changed"] is False
    assert payload["call_info"]["ServiceCallInfo"] == {"Marker": "legacy"}
    assert payload["call_info"]["IntranetCallInfo"] == {"Marker": "private"}
    assert payload["request_id"] == "req-call"


def test_run_module_returns_preflight_flag_for_hot_update_inputs(monkeypatch):
    client = FakeClient()
    client.preflight_response = types.SimpleNamespace(ModelTurboFlag="Allowed", RequestId="req-hot")
    fake = _run(monkeypatch, client, **preflight_params())
    payload = fake.exit_payload
    assert payload["model_turbo_flag"] == "Allowed"
    assert payload["request_id"] == "req-hot"
    assert client.requests[0].ImageInfo.payload == preflight_params()["image_info"]


def test_run_module_rejects_mixing_modes_and_stray_project_id(monkeypatch):
    both = dict(call_params(), image_info={"ImageType": "TCR"})
    fake = FakeModule(both)
    monkeypatch.setattr(tione_model_service_diagnostics_info, "TencentCloudModule",
                        lambda **kwargs: fake)
    with pytest.raises(ModuleFail) as excinfo:
        tione_model_service_diagnostics_info.run_module()
    assert "but not both" in excinfo.value.payload["msg"]

    stray = dict(preflight_params(), project_id="p1")
    fake = FakeModule(stray)
    monkeypatch.setattr(tione_model_service_diagnostics_info, "TencentCloudModule",
                        lambda **kwargs: fake)
    with pytest.raises(ModuleFail) as excinfo:
        tione_model_service_diagnostics_info.run_module()
    assert excinfo.value.payload["msg"] == "project_id is only valid with service_group_id"


class SdkError(Exception):
    def __init__(self, code, request_id):
        self._code = code
        self._request_id = request_id
        super(SdkError, self).__init__("api exploded")

    def get_code(self):
        return self._code

    def get_request_id(self):
        return self._request_id


def test_run_module_fails_cleanly_on_sdk_error(monkeypatch):
    class FailingClient:
        def DescribeModelServiceHotUpdated(self, request):
            raise SdkError("FailedOperation", "req-err")

    failing = FailingClient()
    _inject_sdk(monkeypatch, failing)
    fake = FakeModule(preflight_params())
    fake._client = failing
    monkeypatch.setattr(tione_model_service_diagnostics_info, "TencentCloudModule",
                        lambda **kwargs: fake)
    with pytest.raises(ModuleFail) as excinfo:
        tione_model_service_diagnostics_info.run_module()
    payload = excinfo.value.payload
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert payload["error_code"] == "FailedOperation"
    assert payload["request_id"] == "req-err"
