"""Deep harness tests for tione_model_service_diagnostics_info.

Covers call_request / preflight_request builders, serialize_call_info
gateway-variant serialization and run_module() end to end in both
mutually exclusive modes (service_group_id call info vs hot-update
preflight), mode validation, and the sdk_error_payload fail contract.

The module subclasses ``TencentCloudModule``, so the migration patches the
base class's ``create_client`` and the module's own ``_load`` (which is where
it imports its models and client class), and lets ``module_args()`` supply the
credentials the base class validates. The fixture serialises real fields of the
call-info models it stands in for -- ``ServiceGroupId`` on ``ServiceCallInfo``
and ``ServiceCallInfoV2``, ``Host`` on ``DefaultNginxGatewayCallInfo`` and
``PrivateLinkInfos`` on ``IntranetCallInfo`` -- rather than a generic
``Marker``, so the payload is what ``add_return_samples.py`` captures as the
module's documented sample.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import json
import types

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import tione_model_service_diagnostics_info
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    module_args,
    run,
)


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
    """SDK-shaped call-info resource carrying the real fields it serialises."""

    def __init__(self, data):
        self._data = dict(data)

    def _serialize(self, allow_none=True):
        return dict(self._data)


def test_serialize_call_info_preserves_all_gateway_variants():
    response = types.SimpleNamespace(
        ServiceCallInfo=FakeItem({"ServiceGroupId": "legacy"}), InferGatewayCallInfo=None,
        DefaultNginxGatewayCallInfo=FakeItem({"Host": "nginx"}), TJCallInfo=None,
        IntranetCallInfo=FakeItem({"PrivateLinkInfos": ["private"]}),
        ServiceCallInfoV2=FakeItem({"ServiceGroupId": "gateway-v2"}))
    value = tione_model_service_diagnostics_info.serialize_call_info(response)
    assert value["ServiceCallInfo"] == {"ServiceGroupId": "legacy"}
    assert value["InferGatewayCallInfo"] is None
    assert value["DefaultNginxGatewayCallInfo"] == {"Host": "nginx"}
    assert value["IntranetCallInfo"] == {"PrivateLinkInfos": ["private"]}
    assert value["ServiceCallInfoV2"] == {"ServiceGroupId": "gateway-v2"}


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


def _patch_sdk(monkeypatch, client):
    """Hand the module its models/client class and the client itself."""
    monkeypatch.setattr(tione_model_service_diagnostics_info, "_load", lambda: (
        FakeModels, types.SimpleNamespace(TioneClient=lambda *args: client)))
    monkeypatch.setattr(TencentCloudModule, "create_client",
                        lambda self, client_class, endpoint: client)


def test_run_module_returns_call_info_for_service_group(monkeypatch):
    client = FakeClient()
    client.call_response = types.SimpleNamespace(
        ServiceCallInfo=FakeItem({"ServiceGroupId": "legacy"}), InferGatewayCallInfo=None,
        DefaultNginxGatewayCallInfo=None, TJCallInfo=None,
        IntranetCallInfo=FakeItem({"PrivateLinkInfos": ["private"]}), ServiceCallInfoV2=None,
        RequestId="req-call")
    _patch_sdk(monkeypatch, client)
    module_args(**call_params())

    payload = run(tione_model_service_diagnostics_info.run_module)

    assert payload["changed"] is False
    assert payload["call_info"]["ServiceCallInfo"] == {"ServiceGroupId": "legacy"}
    assert payload["call_info"]["IntranetCallInfo"] == {"PrivateLinkInfos": ["private"]}
    assert payload["request_id"] == "req-call"


def test_run_module_returns_preflight_flag_for_hot_update_inputs(monkeypatch):
    client = FakeClient()
    client.preflight_response = types.SimpleNamespace(ModelTurboFlag="Allowed", RequestId="req-hot")
    _patch_sdk(monkeypatch, client)
    module_args(**preflight_params())

    payload = run(tione_model_service_diagnostics_info.run_module)

    assert payload["model_turbo_flag"] == "Allowed"
    assert payload["request_id"] == "req-hot"
    assert client.requests[0].ImageInfo.payload == preflight_params()["image_info"]


def test_run_module_rejects_mixing_modes_and_stray_project_id():
    both = call_params()
    both["image_info"] = {"ImageType": "TCR"}
    module_args(**both)

    with pytest.raises(AnsibleFailJson) as failure:
        run(tione_model_service_diagnostics_info.run_module)

    assert "but not both" in failure.value.args[0]["msg"]

    stray = preflight_params()
    stray["project_id"] = "p1"
    module_args(**stray)

    with pytest.raises(AnsibleFailJson) as failure:
        run(tione_model_service_diagnostics_info.run_module)

    assert failure.value.args[0]["msg"] == "project_id is only valid with service_group_id"


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

    _patch_sdk(monkeypatch, FailingClient())
    module_args(**preflight_params())

    with pytest.raises(AnsibleFailJson) as failure:
        run(tione_model_service_diagnostics_info.run_module)

    payload = failure.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert payload["error_code"] == "FailedOperation"
    assert payload["request_id"] == "req-err"
