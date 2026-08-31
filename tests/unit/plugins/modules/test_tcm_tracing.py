from ansible_collections.susunola.tencentcloud.plugins.modules.tcm_tracing import converged, desired, update_request


class Value(object):
    def from_json_string(self, raw): self.raw = raw
class Models(object):
    ModifyTracingConfigRequest = Value
    APM = Value
    TracingZipkin = Value


def test_tracing_request_maps_sampling_and_destination():
    p = {"mesh_id": "mesh-1", "enabled": True, "sampling": 10.0, "apm": {"Enable": True}, "zipkin": None}
    value = update_request(Models, p)
    assert value.MeshId == "mesh-1"
    assert value.Sampling == 10.0
    assert "Enable" in value.APM.raw
    assert "Zipkin" not in desired(p)


def test_tracing_convergence_allows_server_fields_and_ignores_destinations_when_disabled():
    assert converged(
        {"Enable": True, "Sampling": 10, "APM": {"Enable": True, "InstanceId": "apm-1"}},
        {"Enable": True, "Sampling": 10.0, "APM": {"Enable": True}},
    )
    assert converged(
        {"Enable": False, "Sampling": 0, "Zipkin": {"Address": "old"}},
        {"Enable": False, "Sampling": 0.0},
    )
