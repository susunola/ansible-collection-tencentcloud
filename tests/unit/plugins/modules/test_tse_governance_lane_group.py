import json

from ansible_collections.susunola.tencentcloud.plugins.modules.tse_governance_lane_group import contains, delete_request, desired, write_request


class Value(object):
    def from_json_string(self, raw):
        self.raw = raw


class Request(object):
    pass


class Models(object):
    GovernanceLaneGroup = Value
    DeleteGovernanceLaneGroup = Value
    CreateGovernanceLaneGroupsRequest = Request
    DeleteGovernanceLaneGroupsRequest = Request


def test_lane_group_requests_map_full_lifecycle():
    p = {
        "instance_id": "ins1",
        "name": "gray",
        "traffic_entries": [{"Service": "edge"}],
        "destinations": [{"Service": "orders"}],
        "description": "gray lane",
        "rules": [{"Name": "canary"}],
    }
    target = desired(p)
    create = write_request(Models.CreateGovernanceLaneGroupsRequest, Models, p, target)
    assert json.loads(create.LaneGroups[0].raw)["Rules"] == [{"Name": "canary"}]
    delete = delete_request(Models, p, {"ID": "lane-1", "Name": "gray"})
    assert json.loads(delete.LaneGroups[0].raw) == {"ID": "lane-1", "Name": "gray"}


def test_lane_group_comparison_is_order_independent_and_ignores_read_only_fields():
    desired_rules = [{"Name": "b", "Priority": 2}, {"Name": "a", "Priority": 1}]
    actual = [{"Name": "a", "Priority": 1, "Revision": "r1"}, {"Name": "b", "Priority": 2, "Revision": "r2"}]
    assert contains(actual, desired_rules)
    assert not contains(actual, desired_rules[:1])
    assert not contains([actual[0], actual[1]], [desired_rules[0], desired_rules[0]])
