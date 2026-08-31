from ansible_collections.susunola.tencentcloud.plugins.modules.tse_gateway_runtime_info import request, fetch_nodes


class Request(object):
    GroupId = None


class Item(object):
    def __init__(self, value): self.value = value
    def _serialize(self, allow_none=False): return {"Value": self.value}


class Result(object):
    def __init__(self, values, total): self.NodeList, self.TotalCount = [Item(v) for v in values], total


class Response(object):
    def __init__(self, values, total, request_id): self.Result, self.RequestId = Result(values, total), request_id


class Models(object):
    DescribeCloudNativeAPIGatewayNodesRequest = Request


class Client(object):
    def __init__(self): self.offsets = []
    def DescribeCloudNativeAPIGatewayNodes(self, value):
        self.offsets.append(value.Offset)
        return Response([1, 2] if value.Offset == 0 else [3], 3, "request-%s" % value.Offset)


class Module(object):
    def sdk_call(self, operation, value): return operation(value)


def test_request_maps_gateway_and_optional_group():
    value = request(Request, "gateway-1", "group-1")
    assert (value.GatewayId, value.GroupId) == ("gateway-1", "group-1")


def test_fetch_nodes_paginates():
    client = Client()
    nodes, total, request_id = fetch_nodes(Module(), client, Models, "gateway-1", "group-1", 2)
    assert nodes == [{"Value": 1}, {"Value": 2}, {"Value": 3}]
    assert (total, request_id, client.offsets) == (3, "request-2", [0, 2])
