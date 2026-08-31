from ansible_collections.susunola.tencentcloud.plugins.modules.tcm_prometheus import converged, link_request, without_secrets


class Value(object):
    def from_json_string(self, raw): self.raw = raw
class Models(object):
    LinkPrometheusRequest = Value
    PrometheusConfig = Value


def test_prometheus_request_uses_sdk_mesh_id_spelling():
    value = link_request(Models, "mesh-1", {"InstanceId": "prom-1"})
    assert value.MeshID == "mesh-1"
    assert "prom-1" in value.Prometheus.raw


def test_prometheus_comparison_redacts_password_and_allows_returned_fields():
    current = {"InstanceId": "prom-1", "CustomProm": {"Username": "u", "Password": None}, "DisplayName": "managed"}
    desired = {"InstanceId": "prom-1", "CustomProm": {"Username": "u", "Password": "secret"}}
    assert converged(current, desired)
    assert "Password" not in without_secrets(desired)["CustomProm"]
