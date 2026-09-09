"""Deep harness tests for tse_gateway_runtime_info.

Covers the runtime request builder (optional group scoping guarded by a
hasattr check), the fetch_nodes pagination loop, and run_module() end to
end: happy-path network/ports/addresses/nodes collection, nodes skipped
when no group is selected, page_size validation and the
sdk_error_payload fail contract.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import sys
import types

import pytest

from ansible_collections.susunola.tencentcloud.plugins.modules import tse_gateway_runtime_info


class GroupedRequest:
    GroupId = None


class PlainRequest:
    pass


class FakeModels:
    DescribeCloudNativeAPIGatewayConfigRequest = GroupedRequest
    DescribeCloudNativeAPIGatewayPortsRequest = PlainRequest
    DescribePublicAddressConfigRequest = GroupedRequest
    DescribeCloudNativeAPIGatewayNodesRequest = PlainRequest


def test_request_maps_gateway_and_optional_group():
    value = tse_gateway_runtime_info.request(GroupedRequest, "gateway-1", "group-1")
    assert value.GatewayId == "gateway-1"
    assert value.GroupId == "group-1"


def test_request_skips_group_when_model_lacks_attribute():
    value = tse_gateway_runtime_info.request(PlainRequest, "gateway-1", "group-1")
    assert value.GatewayId == "gateway-1"
    assert not hasattr(value, "GroupId")


class FakeItem:
    def __init__(self, marker):
        self.marker = marker

    def _serialize(self, allow_none=True):
        return {"Marker": self.marker}


class FakeNodeResult:
    def __init__(self, items, total):
        self.NodeList = items
        self.TotalCount = total


class FakeNodeResponse:
    def __init__(self, items, total_count, request_id):
        self.Result = FakeNodeResult(items, total_count)
        self.RequestId = request_id


class FakeResultResponse:
    def __init__(self, result, request_id):
        self.Result = result
        self.RequestId = request_id


class FakeAddressResult:
    def __init__(self, items):
        self.ConfigList = items


class FakeClient:
    def __init__(self):
        self.node_pages = []
        self.node_requests = []
        self.config_response = None
        self.ports_response = None
        self.address_response = None

    def DescribeCloudNativeAPIGatewayNodes(self, request):
        self.node_requests.append(request)
        return self.node_pages.pop(0)

    def DescribeCloudNativeAPIGatewayConfig(self, request):
        return self.config_response

    def DescribeCloudNativeAPIGatewayPorts(self, request):
        return self.ports_response

    def DescribePublicAddressConfig(self, request):
        return self.address_response


class ModuleExit(BaseException):
    pass


class ModuleFail(BaseException):
    def __init__(self, payload):
        self.payload = payload
        super(ModuleFail, self).__init__("module failed: %r" % (payload,))


class FakeModule:
    def __init__(self, params):
        self.params = params
        self.exit_payload = None
        self.fail_payload = None

    def require_sdk(self):
        pass

    def create_client(self, client_class, endpoint):
        return self._client

    def sdk_call(self, operation, request=None):
        if request is not None:
            return operation(request)
        return operation()

    def exit_json(self, **kwargs):
        self.exit_payload = kwargs
        raise ModuleExit()

    def fail_json(self, **kwargs):
        self.fail_payload = kwargs
        raise ModuleFail(kwargs)


def _inject_sdk(monkeypatch, client):
    service = types.ModuleType("tencentcloud.tse.v20201207")
    service.models = FakeModels
    service.tse_client = types.SimpleNamespace(TseClient=lambda *args: object())
    monkeypatch.setitem(sys.modules, "tencentcloud", types.ModuleType("tencentcloud"))
    monkeypatch.setitem(sys.modules, "tencentcloud.tse",
                        types.ModuleType("tencentcloud.tse"))
    monkeypatch.setitem(sys.modules, "tencentcloud.tse.v20201207", service)


def _run(monkeypatch, client, **params):
    _inject_sdk(monkeypatch, client)
    fake = FakeModule(params)
    fake._client = client
    monkeypatch.setattr(tse_gateway_runtime_info, "TencentCloudModule", lambda **kwargs: fake)
    with pytest.raises(ModuleExit):
        tse_gateway_runtime_info.run_module()
    return fake


def _expect_fail(monkeypatch, fake):
    monkeypatch.setattr(tse_gateway_runtime_info, "TencentCloudModule", lambda **kwargs: fake)
    with pytest.raises(ModuleFail) as excinfo:
        tse_gateway_runtime_info.run_module()
    return excinfo.value.payload


def _runtime_client():
    client = FakeClient()
    client.config_response = FakeResultResponse(FakeItem("net-cfg"), "req-config")
    client.ports_response = FakeResultResponse(FakeItem("ports"), "req-ports")
    client.address_response = FakeResultResponse(
        FakeAddressResult([FakeItem("addr-1")]), "req-address")
    return client


def test_run_module_collects_runtime_with_group_nodes(monkeypatch):
    client = _runtime_client()
    client.node_pages = [
        FakeNodeResponse([FakeItem("n1"), FakeItem("n2")], 3, "req-node-1"),
        FakeNodeResponse([FakeItem("n3")], 3, "req-node-2"),
    ]
    fake = _run(monkeypatch, client, gateway_id="gateway-1", group_id="group-1", page_size=2)
    payload = fake.exit_payload
    assert payload["changed"] is False
    assert payload["network_config"] == {"Marker": "net-cfg"}
    assert payload["ports"] == {"Marker": "ports"}
    assert payload["public_addresses"] == [{"Marker": "addr-1"}]
    assert [item["Marker"] for item in payload["nodes"]] == ["n1", "n2", "n3"]
    assert payload["node_count"] == 3
    assert payload["request_ids"] == {"network_config": "req-config", "ports": "req-ports",
                                      "public_addresses": "req-address", "nodes": "req-node-2"}
    assert [request.Offset for request in client.node_requests] == [0, 2]


def test_run_module_skips_nodes_without_group(monkeypatch):
    client = _runtime_client()
    fake = _run(monkeypatch, client, gateway_id="gateway-1", group_id=None, page_size=2)
    payload = fake.exit_payload
    assert payload["nodes"] == []
    assert payload["node_count"] == 0
    assert payload["request_ids"]["nodes"] is None
    assert client.node_requests == []


@pytest.mark.parametrize("page_size,message", [
    (0, "page_size must be between 1 and 100"),
    (101, "page_size must be between 1 and 100"),
])
def test_run_module_validates_page_size_bounds(monkeypatch, page_size, message):
    p = {"gateway_id": "gateway-1", "group_id": None, "page_size": page_size}
    payload = _expect_fail(monkeypatch, FakeModule(p))
    assert payload["msg"] == message


class SdkError(Exception):
    def __init__(self, code, request_id):
        self._code = code
        self._request_id = request_id
        super(SdkError, self).__init__("api exploded")

    def get_code(self):
        return self._code

    def get_request_id(self):
        return self._request_id


def test_run_module_fails_cleanly_on_sdk_error(monkeypatch):
    class FailingClient:
        def DescribeCloudNativeAPIGatewayConfig(self, request):
            raise SdkError("FailedOperation", "req-err")

    failing = FailingClient()
    _inject_sdk(monkeypatch, failing)
    fake = FakeModule({"gateway_id": "gateway-1", "group_id": None, "page_size": 2})
    fake._client = failing
    monkeypatch.setattr(tse_gateway_runtime_info, "TencentCloudModule", lambda **kwargs: fake)
    with pytest.raises(ModuleFail) as excinfo:
        tse_gateway_runtime_info.run_module()
    payload = excinfo.value.payload
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert payload["error"] == "api exploded"
    assert payload["error_code"] == "FailedOperation"
    assert payload["request_id"] == "req-err"
