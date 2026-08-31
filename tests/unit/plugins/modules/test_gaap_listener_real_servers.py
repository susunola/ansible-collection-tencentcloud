"""Tests for GAAP listener binding normalization."""
from ansible_collections.susunola.tencentcloud.plugins.modules.gaap_listener_real_servers import canonical


def test_canonical_maps_and_sorts_desired_bindings():
    result = canonical([
        {"real_server_id": "rs-b", "address": "10.0.0.2", "port": 80},
        {"real_server_id": "rs-a", "address": "10.0.0.1", "port": 80, "weight": 10, "failover_role": "master"},
    ])
    assert [item["RealServerId"] for item in result] == ["rs-a", "rs-b"]
    assert result[0]["RealServerWeight"] == 10
    assert result[1]["RealServerWeight"] == 1


def test_canonical_ignores_health_status_fields():
    current = canonical([{"RealServerId": "rs-a", "RealServerIP": "10.0.0.1", "RealServerPort": 80,
                          "RealServerWeight": 1, "RealServerStatus": 0}])
    desired = canonical([{"real_server_id": "rs-a", "address": "10.0.0.1", "port": 80}])
    assert current == desired
