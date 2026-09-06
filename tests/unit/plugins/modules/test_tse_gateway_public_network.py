from ansible_collections.susunola.tencentcloud.plugins.modules.tse_gateway_public_network import contains, create_request, desired, group_request


class Value(object):
    def from_json_string(self, raw):
        self.raw = raw


class Filter(object):
    pass


class Models(object):
    CreateCloudNativeAPIGatewayPublicNetworkRequest = Value
    DescribeNativeGatewayServerGroupsRequest = Value
    Filter = Filter


def test_public_network_payload_and_access_control_comparison():
    p = {
        "gateway_id": "g1",
        "group_id": "grp1",
        "config": {"InternetMaxBandwidthOut": 20, "MultiZoneFlag": True},
        "access_control": {"Mode": "Whitelist", "CidrWhiteList": ["10.0.0.0/8"]},
    }
    assert '"GroupId": "grp1"' in create_request(Models, p).raw
    target = desired(p)
    assert contains(dict(target, Status="Open"), target)
    lookup = group_request(Models, {"gateway_id": "g1", "group_name": "workers"})
    assert lookup.Filters[0].Values == ["workers"]
