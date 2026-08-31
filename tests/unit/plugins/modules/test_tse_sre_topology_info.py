from ansible_collections.susunola.tencentcloud.plugins.modules.tse_sre_topology_info import (
    build_request, fetch_all,
)


class Request(object):
    pass


class Item(object):
    def __init__(self, value): self.value = value
    def _serialize(self, allow_none=False): return {"Value": self.value}


class Response(object):
    def __init__(self, values, total, request_id, field):
        setattr(self, field, [Item(value) for value in values])
        self.TotalCount = total
        self.RequestId = request_id


class Module(object):
    def sdk_call(self, operation, request): return operation(request)


def test_build_request_maps_pagination():
    request = build_request(Request, "ins-1", 20, 10)
    assert (request.InstanceId, request.Offset, request.Limit) == ("ins-1", 20, 10)


def test_fetch_all_paginates_and_serializes():
    offsets = []
    def operation(request):
        offsets.append(request.Offset)
        values = [1, 2] if request.Offset == 0 else [3]
        return Response(values, 3, "request-%s" % request.Offset, "Replicas")
    values, total, request_id = fetch_all(
        Module(), operation, Request, "ins-1", 2, "Replicas"
    )
    assert values == [{"Value": 1}, {"Value": 2}, {"Value": 3}]
    assert (total, request_id, offsets) == (3, "request-2", [0, 2])
