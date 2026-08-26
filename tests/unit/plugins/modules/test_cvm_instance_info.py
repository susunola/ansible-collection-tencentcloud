from ansible_collections.tencentcloud.cloud.plugins.modules.cvm_instance_info import build_request


class FakeFilter:
    pass


class FakeRequest:
    pass


class FakeModels:
    Filter = FakeFilter
    DescribeInstancesRequest = FakeRequest


def test_build_request_maps_filters_and_pagination():
    request = build_request(FakeModels, ["ins-123"], {"zone": ["ap-guangzhou-3"], "instance-state": ["RUNNING"]}, 20, 100)
    assert request.InstanceIds == ["ins-123"]
    assert request.Offset == 20
    assert request.Limit == 100
    assert [(item.Name, item.Values) for item in request.Filters] == [
        ("instance-state", ["RUNNING"]), ("zone", ["ap-guangzhou-3"]),
    ]
