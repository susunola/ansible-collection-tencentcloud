import json

from ansible_collections.susunola.tencentcloud.plugins.modules.tse_gateway_service import (
    health_update_request,
    targets_match,
    targets_request,
    contains,
    desired,
    write_request,
)


class Value(object):
    def from_json_string(self, raw):
        self.raw = raw


class Models(object):
    UpdateUpstreamTargetsRequest = Value
    UpdateUpstreamHealthCheckConfigRequest = Value


def test_gateway_service_payload_and_subset_comparison():
    p = {
        "name": "orders",
        "protocol": "http",
        "timeout": 30000,
        "retries_count": 2,
        "upstream_type": "IPList",
        "upstream_info": {"Targets": [{"Host": "10.0.0.1", "Port": 80}]},
        "path": "/",
    }
    target = desired(p)
    assert contains(dict(target, ID="s1"), target)
    assert '"GatewayId": "g1"' in write_request(Value, p, {"GatewayId": "g1", **target}).raw


def test_gateway_upstream_requests_map_targets_and_health_checks():
    p = {"gateway_id": "g1"}
    targets = [{"Host": "10.0.0.1", "Port": 80, "Weight": 100}]
    health = {"EnableActiveHealthCheck": True}
    assert json.loads(targets_request(Models, p, "orders", targets).raw) == {"GatewayId": "g1", "Name": "orders", "Targets": targets}
    assert json.loads(health_update_request(Models, p, "orders", health).raw) == {"GatewayId": "g1", "Name": "orders", "HealthCheckConfig": health}


def test_gateway_targets_compare_authoritative_membership_and_ignore_read_only_fields():
    desired_targets = [{"Host": "10.0.0.2", "Port": 80, "Weight": 50}, {"Host": "10.0.0.1", "Port": 80, "Weight": 100}]
    actual = [{"Host": "10.0.0.1", "Port": 80, "Weight": 100, "Health": "HEALTHY"}, {"Host": "10.0.0.2", "Port": 80, "Weight": 50, "CreatedTime": "now"}]
    assert targets_match(actual, desired_targets)
    assert not targets_match(actual, desired_targets[:1])
