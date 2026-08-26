from __future__ import absolute_import, division, print_function

__metaclass__ = type

from ansible_collections.tencentcloud.cloud.plugins.modules.vpc_info import build_request


class FakeFilter:
    pass


class FakeRequest:
    pass


class FakeModels:
    Filter = FakeFilter
    DescribeVpcsRequest = FakeRequest


def test_build_request_maps_ids_and_string_pagination():
    request = build_request(FakeModels, ["vpc-123"], {}, 20, 100)
    assert request.VpcIds == ["vpc-123"]
    assert request.Offset == "20"
    assert request.Limit == "100"


def test_build_request_sorts_filters():
    request = build_request(FakeModels, [], {"vpc-name": ["prod"], "is-default": ["true"]}, 0, 100)
    assert [(item.Name, item.Values) for item in request.Filters] == [
        ("is-default", ["true"]), ("vpc-name", ["prod"]),
    ]
