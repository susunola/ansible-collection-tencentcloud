from __future__ import absolute_import, division, print_function
__metaclass__ = type

from ansible_collections.susunola.tencentcloud.plugins.modules.subnet_info import build_request


class FakeFilter:
    pass


class FakeRequest:
    pass


class FakeModels:
    Filter = FakeFilter
    DescribeSubnetsRequest = FakeRequest


def test_build_request_maps_ids_and_string_pagination():
    request = build_request(FakeModels, ["subnet-123"], {}, 20, 100)
    assert request.SubnetIds == ["subnet-123"]
    assert request.Offset == "20"
    assert request.Limit == "100"


def test_build_request_sorts_filters():
    request = build_request(FakeModels, [], {"subnet-name": ["web"], "vpc-id": ["vpc-1"]}, 0, 100)
    assert [(item.Name, item.Values) for item in request.Filters] == [
        ("subnet-name", ["web"]), ("vpc-id", ["vpc-1"]),
    ]


def test_build_request_wraps_scalar_filter_values():
    request = build_request(FakeModels, [], {"is-default": True}, 0, 100)
    assert request.Filters[0].Values == [True]
