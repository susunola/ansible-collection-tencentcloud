import json

from ansible_collections.susunola.tencentcloud.plugins.modules.tse_governance_instance import contains, delete_request, desired, request


class Value(object):
    def from_json_string(self, raw):
        self.raw = raw


class Request(object):
    pass


class Models(object):
    GovernanceInstanceInput = Value
    GovernanceInstanceUpdate = Value
    CreateGovernanceInstancesRequest = Request
    ModifyGovernanceInstancesRequest = Request
    DeleteGovernanceInstancesRequest = Request


def test_governance_instance_requests_map_create_update_and_delete():
    p = {
        "instance_id": "engine-1",
        "namespace": "production",
        "service": "orders",
        "host": "10.0.0.3",
        "port": 8080,
        "protocol": "http",
        "instance_version": "v1",
        "weight": 100,
        "healthy": True,
        "isolate": False,
        "enable_health_check": True,
        "ttl": 5,
        "metadata": [{"Key": "zone", "Value": "a"}],
    }
    target = desired(p)
    create = request(Models.CreateGovernanceInstancesRequest, Models, p, target)
    assert json.loads(create.GovernanceInstances[0].raw)["Host"] == "10.0.0.3"
    current = dict(target, Id="service-instance-1")
    delete = delete_request(Models, p, current)
    assert json.loads(delete.GovernanceInstances[0].raw)["Id"] == "service-instance-1"


def test_governance_instance_metadata_comparison_ignores_order_and_read_only_fields():
    expected = [{"Key": "zone", "Value": "a"}, {"Key": "stage", "Value": "prod"}]
    actual = [{"Key": "stage", "Value": "prod", "CreateTime": "now"}, {"Key": "zone", "Value": "a"}]
    assert contains(actual, expected)
