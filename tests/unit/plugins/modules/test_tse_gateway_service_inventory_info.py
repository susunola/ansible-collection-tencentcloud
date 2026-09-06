from ansible_collections.susunola.tencentcloud.plugins.modules.tse_gateway_service_inventory_info import (
    fetch_inventory,
    inventory_request,
    service_name,
    upstream_request,
)


class Request(object):
    pass


class Filter(object):
    pass


class Models(object):
    DescribeCNGWServicesWithRoutesRequest = Request
    DescribeCloudNativeAPIGatewayUpstreamRequest = Request
    ListFilter = Filter


PARAMS = {"gateway_id": "gateway-1", "filters": {"name": "orders"}, "page_size": 2}


def test_inventory_and_upstream_request_mapping():
    inventory = inventory_request(Models, PARAMS, 4)
    upstream = upstream_request(Models, "gateway-1", "orders")
    assert (inventory.GatewayId, inventory.Offset, inventory.Limit) == ("gateway-1", 4, 2)
    assert [(item.Key, item.Value) for item in inventory.Filters] == [("name", "orders")]
    assert (upstream.GatewayId, upstream.ServiceName) == ("gateway-1", "orders")


class Item(object):
    def __init__(self, value):
        self.value = value

    def _serialize(self, allow_none=False):
        return {"Name": self.value}


class Result(object):
    def __init__(self, values, total):
        self.ServiceList, self.TotalCount = [Item(v) for v in values], total


class Response(object):
    def __init__(self, values, total, request_id):
        self.Result, self.RequestId = Result(values, total), request_id


class Client(object):
    def __init__(self):
        self.offsets = []

    def DescribeCNGWServicesWithRoutes(self, request):
        self.offsets.append(request.Offset)
        return Response(["one", "two"] if request.Offset == 0 else ["three"], 3, "request-%s" % request.Offset)


class Module(object):
    def sdk_call(self, operation, request):
        return operation(request)


def test_fetch_inventory_paginates_and_extracts_names():
    client = Client()
    services, total, request_id = fetch_inventory(Module(), client, Models, PARAMS)
    assert [service_name(value) for value in services] == ["one", "two", "three"]
    assert (total, request_id, client.offsets) == (3, "request-2", [0, 2])
