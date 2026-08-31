from ansible_collections.susunola.tencentcloud.plugins.modules.tione_model_service_diagnostics_info import call_request, preflight_request, serialize_call_info


class Object:
    def from_json_string(self, value): self.value = value
class Models:
    DescribeModelServiceCallInfoRequest = DescribeModelServiceHotUpdatedRequest = ImageInfo = ModelInfo = VolumeMount = Object


def test_call_request_uses_group_and_workspace_identity():
    request = call_request(Models, {"service_group_id": "g1", "project_id": "p1"})
    assert (request.ServiceGroupId, request.TiProjectId) == ("g1", "p1")


def test_preflight_request_builds_only_supplied_sdk_models():
    request = preflight_request(Models, {"image_info": {"ImageType": "TCR"}, "model_info": None, "volume_mount": {"Type": "CFS"}})
    assert '"ImageType": "TCR"' in request.ImageInfo.value
    assert '"Type": "CFS"' in request.VolumeMount.value
    assert not hasattr(request, "ModelInfo")


class Item:
    def __init__(self, value): self.value = value
    def _serialize(self, allow_none=True): return {"value": self.value}
class Response:
    ServiceCallInfo = Item("legacy")
    InferGatewayCallInfo = None
    DefaultNginxGatewayCallInfo = Item("nginx")
    TJCallInfo = None
    IntranetCallInfo = Item("private")
    ServiceCallInfoV2 = Item("gateway-v2")


def test_serialize_call_info_preserves_all_gateway_variants():
    value = serialize_call_info(Response())
    assert value["InferGatewayCallInfo"] is None
    assert value["ServiceCallInfoV2"] == {"value": "gateway-v2"}
    assert value["IntranetCallInfo"] == {"value": "private"}
