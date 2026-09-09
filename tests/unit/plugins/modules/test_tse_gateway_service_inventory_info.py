"""Deep harness tests for tse_gateway_service_inventory_info.

Covers the inventory/upstream request builders (service filters coerced
to strings, upstream service-name scoping), the fetch_inventory
pagination loop, service-name extraction, and run_module() end to end:
paginated inventory with optional per-service upstream resolution,
empty results, unsupported-filter and page_size validation and the
sdk_error_payload fail contract.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import sys
import types

import pytest

from ansible_collections.susunola.tencentcloud.plugins.modules import tse_gateway_service_inventory_info


class FakeRequest:
    pass


class FakeFilter:
    pass


class FakeModels:
    DescribeCNGWServicesWithRoutesRequest = FakeRequest
    DescribeCloudNativeAPIGatewayUpstreamRequest = FakeRequest
    ListFilter = FakeFilter


def params():
    return {"gateway_id": "gateway-1", "filters": {"name": "orders", "upstreamType": "NATIVE"},
            "include_upstreams": True, "page_size": 2}


def test_inventory_request_maps_filters_and_pagination():
    inventory = tse_gateway_service_inventory_info.inventory_request(FakeModels, params(), 4)
    assert inventory.GatewayId == "gateway-1"
    assert inventory.Offset == 4 and inventory.Limit == 2
    assert [(item.Key, item.Value) for item in inventory.Filters] == [
        ("name", "orders"), ("upstreamType", "NATIVE")]


def test_inventory_request_always_builds_a_filter_list():
    p = dict(params(), filters={})
    inventory = tse_gateway_service_inventory_info.inventory_request(FakeModels, p, 0)
    assert inventory.Filters == []


def test_upstream_request_maps_service_name():
    upstream = tse_gateway_service_inventory_info.upstream_request(FakeModels, "gateway-1", "orders")
    assert upstream.GatewayId == "gateway-1"
    assert upstream.ServiceName == "orders"


class FakeItem:
    def __init__(self, marker):
        self.marker = marker

    def _serialize(self, allow_none=True):
        return {"Name": self.marker, "Routes": [self.marker + "-route"]}


class FakeInventoryResult:
    def __init__(self, items, total_count):
        self.ServiceList = items
        self.TotalCount = total_count


class FakeInventoryResponse:
    def __init__(self, items, total_count, request_id):
        self.Result = FakeInventoryResult(items, total_count)
        self.RequestId = request_id


class FakeUpstreamResponse:
    def __init__(self, result, request_id):
        self.Result = result
        self.RequestId = request_id


class FakeClient:
    def __init__(self, pages=None):
        self._pages = list(pages or [])
        self.inventory_requests = []
        self.upstream_requests = []
        self.upstream_responses = {}

    def DescribeCNGWServicesWithRoutes(self, request):
        self.inventory_requests.append(request)
        return self._pages.pop(0)

    def DescribeCloudNativeAPIGatewayUpstream(self, request):
        self.upstream_requests.append(request)
        return self.upstream_responses[request.ServiceName]


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
    monkeypatch.setattr(tse_gateway_service_inventory_info, "TencentCloudModule", lambda **kwargs: fake)
    with pytest.raises(ModuleExit):
        tse_gateway_service_inventory_info.run_module()
    return fake


def _expect_fail(monkeypatch, fake):
    monkeypatch.setattr(tse_gateway_service_inventory_info, "TencentCloudModule", lambda **kwargs: fake)
    with pytest.raises(ModuleFail) as excinfo:
        tse_gateway_service_inventory_info.run_module()
    return excinfo.value.payload


def test_run_module_resolves_upstreams_for_each_service(monkeypatch):
    client = FakeClient([
        FakeInventoryResponse([FakeItem("svc-2"), FakeItem("svc-1")], 3, "req-inv-1"),
        FakeInventoryResponse([FakeItem("svc-3")], 3, "req-inv-2"),
    ])
    client.upstream_responses = {
        "svc-1": FakeUpstreamResponse(FakeItem("upstream-1"), "req-up-1"),
        "svc-2": FakeUpstreamResponse(FakeItem("upstream-2"), "req-up-2"),
        "svc-3": FakeUpstreamResponse(FakeItem("upstream-3"), "req-up-3"),
    }
    fake = _run(monkeypatch, client, **params())
    payload = fake.exit_payload
    assert payload["changed"] is False
    assert [item["Name"] for item in payload["services"]] == ["svc-2", "svc-1", "svc-3"]
    assert sorted(payload["upstreams"].keys()) == ["svc-1", "svc-2", "svc-3"]
    assert payload["upstreams"]["svc-1"]["Name"] == "upstream-1"
    assert payload["total_count"] == 3
    assert payload["request_ids"]["inventory"] == "req-inv-2"
    assert sorted(payload["request_ids"]["upstreams"].items()) == [
        ("svc-1", "req-up-1"), ("svc-2", "req-up-2"), ("svc-3", "req-up-3")]
    assert [request.Offset for request in client.inventory_requests] == [0, 2]
    assert [request.ServiceName for request in client.upstream_requests] == ["svc-1", "svc-2", "svc-3"]


def test_run_module_skips_upstreams_when_not_requested(monkeypatch):
    p = params()
    p["include_upstreams"] = False
    client = FakeClient([FakeInventoryResponse([FakeItem("svc-1")], 1, "req-inv-1")])
    fake = _run(monkeypatch, client, **p)
    payload = fake.exit_payload
    assert payload["upstreams"] == {}
    assert payload["request_ids"]["upstreams"] == {}
    assert client.upstream_requests == []


def test_run_module_empty_inventory_stops_pagination(monkeypatch):
    client = FakeClient([FakeInventoryResponse([], 0, "req-inv-empty")])
    fake = _run(monkeypatch, client, **params())
    payload = fake.exit_payload
    assert payload["services"] == [] and payload["upstreams"] == {}
    assert payload["total_count"] == 0


@pytest.mark.parametrize("page_size,message", [
    (0, "page_size must be between 1 and 100"),
    (101, "page_size must be between 1 and 100"),
])
def test_run_module_validates_page_size_bounds(monkeypatch, page_size, message):
    p = params()
    p["page_size"] = page_size
    payload = _expect_fail(monkeypatch, FakeModule(p))
    assert payload["msg"] == message


def test_run_module_rejects_unsupported_filters(monkeypatch):
    p = params()
    p["filters"] = {"name": "orders", "bogus": "x", "upstreamType": "NATIVE"}
    payload = _expect_fail(monkeypatch, FakeModule(p))
    assert payload["msg"] == "unsupported TSE gateway service inventory filters"
    assert payload["unsupported_filters"] == ["bogus"]


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
        def DescribeCNGWServicesWithRoutes(self, request):
            raise SdkError("FailedOperation", "req-err")

    failing = FailingClient()
    _inject_sdk(monkeypatch, failing)
    fake = FakeModule(params())
    fake._client = failing
    monkeypatch.setattr(tse_gateway_service_inventory_info, "TencentCloudModule", lambda **kwargs: fake)
    with pytest.raises(ModuleFail) as excinfo:
        tse_gateway_service_inventory_info.run_module()
    payload = excinfo.value.payload
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert payload["error"] == "api exploded"
    assert payload["error_code"] == "FailedOperation"
    assert payload["request_id"] == "req-err"
