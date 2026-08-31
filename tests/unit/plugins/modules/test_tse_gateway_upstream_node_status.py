from ansible_collections.susunola.tencentcloud.plugins.modules.tse_gateway_upstream_node_status import (
    describe_request, find_node, modify_request,
)


class Request(object): pass
class Models(object):
    DescribeCloudNativeAPIGatewayUpstreamRequest = Request
    ModifyUpstreamNodeStatusRequest = Request


PARAMS = {"gateway_id": "gateway-1", "service_name": "orders", "host": "10.0.0.20", "port": 8080,
          "status": "UNHEALTHY"}


def test_requests_map_target_identity_and_status():
    describe = describe_request(Models, PARAMS)
    modify = modify_request(Models, PARAMS)
    assert (describe.GatewayId, describe.ServiceName) == ("gateway-1", "orders")
    assert (modify.Host, modify.Port, modify.Status) == ("10.0.0.20", 8080, "UNHEALTHY")


class Target(object):
    def _serialize(self, allow_none=False): return {"Host": "10.0.0.20", "Port": 8080, "Health": "HEALTHY"}
class Upstream(object): Target = [Target()]
class Result(object): UpstreamList = [Upstream()]
class Response(object): Result = Result()
class Client(object):
    def DescribeCloudNativeAPIGatewayUpstream(self, request): return Response()
class Module(object):
    def sdk_call(self, operation, request): return operation(request)
    def fail_json(self, **kwargs): raise AssertionError(kwargs)


def test_find_node_matches_host_and_port():
    assert find_node(Module(), Client(), Models, PARAMS)["Health"] == "HEALTHY"
