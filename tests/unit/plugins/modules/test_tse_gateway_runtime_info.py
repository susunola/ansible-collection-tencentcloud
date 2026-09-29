"""Deep harness tests for tse_gateway_runtime_info.

Covers the runtime request builder (optional group scoping guarded by a
hasattr check), the fetch_nodes pagination loop, and run_module() end to
end: happy-path network/ports/addresses/nodes collection, nodes skipped
when no group is selected, page_size validation and the
sdk_error_payload fail contract.

The module subclasses ``TencentCloudModule`` and loads its models and
client in its own ``_load()``, so the migration patches that helper and
the base class's ``create_client``, and lets ``module_args()`` supply the
credentials the base class validates. Every fake result serialises a real
field of its own model instead of a generic ``Marker``: ``GatewayId`` for
``DescribeCloudNativeAPIGatewayConfigResult``, ``GatewayInstancePortList``
for ``DescribeGatewayInstancePortResult``, ``Vip`` for
``PublicAddressConfig`` and ``NodeId`` for ``CloudNativeAPIGatewayNode``,
because that payload is what ``add_return_samples.py`` captures as the
module's documented sample.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import types

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import tse_gateway_runtime_info
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    module_args,
    run,
)


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
    """SDK-shaped item serialising one real field of its response model."""

    def __init__(self, field, value):
        self.field = field
        self.value = value

    def _serialize(self, allow_none=True):
        return {self.field: self.value}


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


def _patch_sdk(monkeypatch, client):
    """Hand the module its models/client class and the client itself."""
    monkeypatch.setattr(tse_gateway_runtime_info, "_load", lambda: (
        FakeModels, types.SimpleNamespace(TseClient=lambda *args: client)))
    monkeypatch.setattr(TencentCloudModule, "create_client",
                        lambda self, client_class, endpoint: client)


def _run(monkeypatch, client, **module_params):
    _patch_sdk(monkeypatch, client)
    module_args(**module_params)
    return run(tse_gateway_runtime_info.run_module)


def _expect_fail(monkeypatch, module_params):
    _patch_sdk(monkeypatch, FakeClient())
    module_args(**module_params)
    with pytest.raises(AnsibleFailJson) as failure:
        run(tse_gateway_runtime_info.run_module)
    return failure.value.args[0]


def _runtime_client():
    client = FakeClient()
    client.config_response = FakeResultResponse(FakeItem("GatewayId", "gateway-1"), "req-config")
    client.ports_response = FakeResultResponse(
        FakeItem("GatewayInstancePortList", [{"Scheme": "HTTPS", "PortList": [443]}]), "req-ports")
    client.address_response = FakeResultResponse(
        FakeAddressResult([FakeItem("Vip", "203.0.113.10")]), "req-address")
    return client


def test_run_module_collects_runtime_with_group_nodes(monkeypatch):
    client = _runtime_client()
    client.node_pages = [
        FakeNodeResponse([FakeItem("NodeId", "n1"), FakeItem("NodeId", "n2")], 3, "req-node-1"),
        FakeNodeResponse([FakeItem("NodeId", "n3")], 3, "req-node-2"),
    ]

    payload = _run(monkeypatch, client, gateway_id="gateway-1", group_id="group-1", page_size=2)

    assert payload["changed"] is False
    assert payload["network_config"] == {"GatewayId": "gateway-1"}
    assert payload["ports"] == {"GatewayInstancePortList": [{"Scheme": "HTTPS", "PortList": [443]}]}
    assert payload["public_addresses"] == [{"Vip": "203.0.113.10"}]
    assert [item["NodeId"] for item in payload["nodes"]] == ["n1", "n2", "n3"]
    assert payload["node_count"] == 3
    assert payload["request_ids"] == {"network_config": "req-config", "ports": "req-ports",
                                      "public_addresses": "req-address", "nodes": "req-node-2"}
    assert [request.Offset for request in client.node_requests] == [0, 2]


def test_run_module_skips_nodes_without_group(monkeypatch):
    client = _runtime_client()

    payload = _run(monkeypatch, client, gateway_id="gateway-1", page_size=2)

    assert payload["nodes"] == []
    assert payload["node_count"] == 0
    assert payload["request_ids"]["nodes"] is None
    assert client.node_requests == []


@pytest.mark.parametrize("page_size,message", [
    (0, "page_size must be between 1 and 100"),
    (101, "page_size must be between 1 and 100"),
])
def test_run_module_validates_page_size_bounds(monkeypatch, page_size, message):
    payload = _expect_fail(monkeypatch, {"gateway_id": "gateway-1", "page_size": page_size})
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

    _patch_sdk(monkeypatch, FailingClient())
    module_args(gateway_id="gateway-1", page_size=2)

    with pytest.raises(AnsibleFailJson) as failure:
        run(tse_gateway_runtime_info.run_module)

    payload = failure.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert payload["error"] == "api exploded"
    assert payload["error_code"] == "FailedOperation"
    assert payload["request_id"] == "req-err"
