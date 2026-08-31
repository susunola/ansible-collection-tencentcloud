from ansible_collections.susunola.tencentcloud.plugins.modules.tse_governance_host_retirement import (
    batches, delete_request, describe_request,
)


class Request(object): pass
class Instance(object):
    def from_json_string(self, value): self.json = value
class Models(object):
    DescribeGovernanceInstancesRequest = Request
    DeleteGovernanceInstancesByHostRequest = Request
    GovernanceInstanceUpdate = Instance


PARAMS = {"instance_id": "ins-1", "host": "10.0.0.30"}


def test_retirement_requests_map_host_and_instances():
    describe = describe_request(Models, PARAMS, 20)
    deletion = delete_request(Models, PARAMS, [{"Host": "10.0.0.30", "Port": 8080}])
    assert (describe.InstanceId, describe.Host, describe.Offset, describe.Limit) == ("ins-1", "10.0.0.30", 20, 100)
    assert len(deletion.GovernanceInstances) == 1


def test_batches_preserve_every_instance():
    assert list(batches([1, 2, 3, 4, 5], 2)) == [[1, 2], [3, 4], [5]]
