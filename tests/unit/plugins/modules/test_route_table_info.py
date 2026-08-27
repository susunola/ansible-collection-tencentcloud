from __future__ import absolute_import, division, print_function
__metaclass__ = type

from ansible_collections.susunola.tencentcloud.plugins.modules.route_table_info import build_request


class FakeFilter:
    pass


class FakeRequest:
    pass


class FakeModels:
    Filter = FakeFilter
    DescribeRouteTablesRequest = FakeRequest


def test_build_request_maps_ids_and_string_pagination():
    request = build_request(FakeModels, ["rtb-123"], {}, 20, 100)
    assert request.RouteTableIds == ["rtb-123"]
    assert request.Offset == "20"
    assert request.Limit == "100"


def test_build_request_sorts_filters():
    request = build_request(FakeModels, [], {"vpc-id": ["vpc-1"], "route-table-name": ["app"]}, 0, 100)
    assert [(item.Name, item.Values) for item in request.Filters] == [
        ("route-table-name", ["app"]), ("vpc-id", ["vpc-1"]),
    ]


def test_build_request_wraps_scalar_filter_values():
    request = build_request(FakeModels, [], {"association.main": "true"}, 0, 100)
    assert [(item.Name, item.Values) for item in request.Filters] == [
        ("association.main", ["true"]),
    ]
