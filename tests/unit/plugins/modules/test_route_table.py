"""Unit tests for the route_table write module helpers."""

from __future__ import absolute_import, division, print_function
__metaclass__ = type
from ansible_collections.tencentcloud.cloud.plugins.modules.route_table import (
    build_describe_request,
    diff_routes,
    find_route_table,
)


class FakeFilter(object):
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)


class FakeRequest(object):
    pass


class FakeRoute(object):
    pass


class FakeModels(object):
    Filter = FakeFilter
    Route = FakeRoute
    DescribeRouteTablesRequest = FakeRequest
    DeleteRoutesRequest = FakeRequest
    CreateRoutesRequest = FakeRequest


class FakeRouteTable(object):
    def __init__(self, table_id, name, vpc_id="vpc-1", routes=None, tags=None):
        self.RouteTableId = table_id
        self.RouteTableName = name
        self.VpcId = vpc_id
        self.RouteSet = routes or []
        self.TagSet = tags or []

    def _serialize(self, allow_none=True):
        return {
            "RouteTableId": self.RouteTableId,
            "RouteTableName": self.RouteTableName,
            "VpcId": self.VpcId,
            "RouteSet": list(self.RouteSet),
            "TagSet": [{"Key": t.Key, "Value": t.Value} for t in self.TagSet],
        }


class FakeResponse(object):
    def __init__(self, tables):
        self.RouteTableSet = tables


class FakeClient(object):
    def __init__(self, response=None, exc=None):
        self.response = response
        self.exc = exc
        self.calls = []

    def DescribeRouteTables(self, request):
        self.calls.append(request)
        if self.exc:
            raise self.exc
        return self.response


class FakeModule(object):
    def __init__(self):
        self.params = {"retries": 2}

    def sdk_call(self, operation, request):
        return operation(request)


def test_build_describe_request_by_id():
    request = build_describe_request(FakeModels, "rtb-123", "vpc-1", "app")
    assert request.RouteTableIds == ["rtb-123"]
    assert request.Limit == "100"
    assert not hasattr(request, "Filters")


def test_build_describe_request_by_vpc_and_name():
    request = build_describe_request(FakeModels, None, "vpc-1", "app")
    assert [(f.Name, f.Values) for f in request.Filters] == [
        ("vpc-id", ["vpc-1"]),
        ("route-table-name", ["app"]),
    ]
    assert not hasattr(request, "RouteTableIds")


def test_build_describe_request_by_name_only():
    request = build_describe_request(FakeModels, None, None, "app")
    assert [(f.Name, f.Values) for f in request.Filters] == [("route-table-name", ["app"])]


def test_find_route_table_returns_first_match():
    client = FakeClient(FakeResponse([FakeRouteTable("rtb-1", "app")]))
    module = FakeModule()
    table = find_route_table(module, client, FakeModels, None, "vpc-1", "app")
    assert table["RouteTableId"] == "rtb-1"
    assert len(client.calls) == 1


def test_find_route_table_returns_none_when_absent():
    client = FakeClient(FakeResponse([]))
    module = FakeModule()
    assert find_route_table(module, client, FakeModels, None, "vpc-1", "app") is None


def test_find_route_table_handles_none_set():
    client = FakeClient(FakeResponse(None))
    module = FakeModule()
    assert find_route_table(module, client, FakeModels, "rtb-1", None, None) is None


def test_find_route_table_surfaces_sdk_exceptions():
    class Boom(Exception):
        def get_code(self):
            return "ResourceNotFound"

    client = FakeClient(exc=Boom("gone"))
    module = FakeModule()
    try:
        find_route_table(module, client, FakeModels, "rtb-1", None, None)
        raise AssertionError("expected exception")
    except Boom:
        pass


def _desired(cidr, gateway_type="NAT", gateway_id="nat-1", description=None):
    return {
        "destination_cidr_block": cidr,
        "gateway_type": gateway_type,
        "gateway_id": gateway_id,
        "description": description,
    }


def _remote(cidr, gateway_type="NAT", gateway_id="nat-1", desc="", route_type="USER", route_id=1):
    return {
        "DestinationCidrBlock": cidr,
        "GatewayType": gateway_type,
        "GatewayId": gateway_id,
        "RouteDescription": desc,
        "RouteType": route_type,
        "RouteId": route_id,
        "RouteItemId": "rti-%d" % route_id,
    }


def test_diff_routes_adds_missing_routes():
    to_add, to_delete = diff_routes([_desired("10.1.0.0/16")], [])
    assert [r["destination_cidr_block"] for r in to_add] == ["10.1.0.0/16"]
    assert to_delete == []


def test_diff_routes_removes_unlisted_routes():
    to_add, to_delete = diff_routes([], [_remote("10.1.0.0/16")])
    assert to_add == []
    assert [r["DestinationCidrBlock"] for r in to_delete] == ["10.1.0.0/16"]


def test_diff_routes_keeps_matching_routes():
    to_add, to_delete = diff_routes([_desired("10.1.0.0/16")], [_remote("10.1.0.0/16")])
    assert to_add == []
    assert to_delete == []


def test_diff_routes_replaces_changed_gateway():
    to_add, to_delete = diff_routes(
        [_desired("10.1.0.0/16", gateway_id="nat-2")],
        [_remote("10.1.0.0/16", gateway_id="nat-1")],
    )
    assert [r["gateway_id"] for r in to_add] == ["nat-2"]
    assert [r["GatewayId"] for r in to_delete] == ["nat-1"]


def test_diff_routes_replaces_changed_description():
    to_add, to_delete = diff_routes(
        [_desired("10.1.0.0/16", description="egress")],
        [_remote("10.1.0.0/16", desc="")],
    )
    assert [r["description"] for r in to_add] == ["egress"]
    assert len(to_delete) == 1


def test_diff_routes_ignores_system_routes():
    current = [
        _remote("10.0.0.0/8", gateway_type="LOCAL", route_type="NETD", route_id=9),
        _remote("172.16.0.0/12", gateway_type="CCN", route_type="CCN", route_id=10),
    ]
    to_add, to_delete = diff_routes([], current)
    assert to_add == []
    assert to_delete == []


def test_diff_routes_none_description_matches_empty_remote():
    to_add, to_delete = diff_routes([_desired("10.1.0.0/16")], [_remote("10.1.0.0/16", desc=None)])
    assert to_add == []
    assert to_delete == []
