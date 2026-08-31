from ansible_collections.susunola.tencentcloud.plugins.modules.tcm_access_log import converged, desired, update_request


class Value(object):
    def from_json_string(self, raw): self.raw = raw
class Models(object):
    ModifyAccessLogConfigRequest = Value
    SelectedRange = Value
    CLS = Value


def params(): return {"mesh_id": "mesh-1", "enabled": True, "selected_range": {"All": True}, "template": "istio", "encoding": "JSON", "format": None, "cls": {"TopicId": "topic-1"}, "enable_stdout": True, "enable_server": False, "server_address": None}


def test_access_log_request_maps_destinations_and_encoding():
    value = update_request(Models, params())
    assert value.MeshId == "mesh-1"
    assert value.Encoding == "JSON"
    assert "topic-1" in value.CLS.raw
    assert desired(params())["EnableStdout"] is True


def test_access_log_convergence_allows_server_enriched_nested_fields():
    target = desired(params())
    current = dict(target, SelectedRange={"All": True, "Namespace": "default"})
    assert converged(current, target)
