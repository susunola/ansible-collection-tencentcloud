from ansible_collections.tencentcloud.cloud.plugins.modules.security_group_info import build_request


class FakeFilter:
    pass


class FakeRequest:
    pass


class FakeModels:
    Filter = FakeFilter
    DescribeSecurityGroupsRequest = FakeRequest


def test_build_request_maps_security_group_ids():
    request = build_request(FakeModels, ["sg-123"], {}, 0, 50)
    assert request.SecurityGroupIds == ["sg-123"]
    assert request.Offset == "0"
    assert request.Limit == "50"


def test_build_request_accepts_scalar_filter_values():
    request = build_request(FakeModels, [], {"security-group-name": "web"}, 0, 100)
    assert request.Filters[0].Name == "security-group-name"
    assert request.Filters[0].Values == ["web"]
