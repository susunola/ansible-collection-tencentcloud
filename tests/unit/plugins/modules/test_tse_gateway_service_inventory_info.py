"""Deep harness tests for tse_gateway_service_inventory_info.

Covers the inventory/upstream request builders (service filters coerced
to strings, upstream service-name scoping), the fetch_inventory
pagination loop, service-name extraction, and run_module() end to end:
paginated inventory with optional per-service upstream resolution,
empty results, unsupported-filter and page_size validation and the
sdk_error_payload fail contract.

The module subclasses ``TencentCloudModule`` and loads its models and
client in its own ``_load()``, so the migration patches that helper and
the base class's ``create_client``, and lets ``module_args()`` supply the
credentials the base class validates. The fake item carries the real
``KongServiceRoute`` shape the API returns — the service identity is
nested under ``Service`` (a ``KongServicePreview``) next to
``RouteTotalCount``/``Routes`` — and the upstream result carries the real
``KongUpstreamList`` shape, because that payload is what
``add_return_samples.py`` captures as the module's documented sample.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import types

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import tse_gateway_service_inventory_info
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    module_args,
    run,
)


class FakeRequest:
    pass


class FakeFilter:
    pass


class FakeModels:
    DescribeCNGWServicesWithRoutesRequest = FakeRequest
    DescribeCloudNativeAPIGatewayUpstreamRequest = FakeRequest
    ListFilter = FakeFilter


def params(**overrides):
    options = {
        "gateway_id": "gateway-1", "filters": {"name": "orders", "upstreamType": "NATIVE"},
        "include_upstreams": True, "page_size": 2,
    }
    options.update(overrides)
    return options


def test_inventory_request_maps_filters_and_pagination():
    inventory = tse_gateway_service_inventory_info.inventory_request(FakeModels, params(), 4)
    assert inventory.GatewayId == "gateway-1"
    assert inventory.Offset == 4 and inventory.Limit == 2
    assert [(item.Key, item.Value) for item in inventory.Filters] == [
        ("name", "orders"), ("upstreamType", "NATIVE")]


def test_inventory_request_always_builds_a_filter_list():
    p = params(filters={})
    inventory = tse_gateway_service_inventory_info.inventory_request(FakeModels, p, 0)
    assert inventory.Filters == []


def test_upstream_request_maps_service_name():
    upstream = tse_gateway_service_inventory_info.upstream_request(FakeModels, "gateway-1", "orders")
    assert upstream.GatewayId == "gateway-1"
    assert upstream.ServiceName == "orders"


class FakeItem:
    """Real ``KongServiceRoute``: the service name lives under ``Service``."""

    def __init__(self, name):
        self.name = name

    def _serialize(self, allow_none=True):
        return {
            "Service": {"ID": self.name + "-id", "Name": self.name},
            "RouteTotalCount": 1,
            "Routes": [{"Name": self.name + "-route"}],
        }


class FakeUpstreamResult:
    """Real ``KongUpstreamList``: upstreams live in ``UpstreamList``."""

    def __init__(self, name):
        self.name = name

    def _serialize(self, allow_none=True):
        return {"UpstreamList": [{"ID": self.name + "-id", "Name": self.name}]}


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


def _patch_sdk(monkeypatch, client):
    """Hand the module its models/client class and the client itself."""
    monkeypatch.setattr(tse_gateway_service_inventory_info, "_load", lambda: (
        FakeModels, types.SimpleNamespace(TseClient=lambda *args: client)))
    monkeypatch.setattr(TencentCloudModule, "create_client",
                        lambda self, client_class, endpoint: client)


def _run(monkeypatch, client, **module_params):
    _patch_sdk(monkeypatch, client)
    module_args(**module_params)
    return run(tse_gateway_service_inventory_info.run_module)


def _expect_fail(monkeypatch, module_params):
    _patch_sdk(monkeypatch, FakeClient([]))
    module_args(**module_params)
    with pytest.raises(AnsibleFailJson) as failure:
        run(tse_gateway_service_inventory_info.run_module)
    return failure.value.args[0]


def test_run_module_resolves_upstreams_for_each_service(monkeypatch):
    client = FakeClient([
        FakeInventoryResponse([FakeItem("svc-2"), FakeItem("svc-1")], 3, "req-inv-1"),
        FakeInventoryResponse([FakeItem("svc-3")], 3, "req-inv-2"),
    ])
    client.upstream_responses = {
        "svc-1": FakeUpstreamResponse(FakeUpstreamResult("upstream-1"), "req-up-1"),
        "svc-2": FakeUpstreamResponse(FakeUpstreamResult("upstream-2"), "req-up-2"),
        "svc-3": FakeUpstreamResponse(FakeUpstreamResult("upstream-3"), "req-up-3"),
    }

    payload = _run(monkeypatch, client, **params())

    assert payload["changed"] is False
    assert [item["Service"]["Name"] for item in payload["services"]] == ["svc-2", "svc-1", "svc-3"]
    assert sorted(payload["upstreams"].keys()) == ["svc-1", "svc-2", "svc-3"]
    assert payload["upstreams"]["svc-1"]["UpstreamList"][0]["Name"] == "upstream-1"
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

    payload = _run(monkeypatch, client, **p)

    assert payload["upstreams"] == {}
    assert payload["request_ids"]["upstreams"] == {}
    assert client.upstream_requests == []


def test_run_module_empty_inventory_stops_pagination(monkeypatch):
    client = FakeClient([FakeInventoryResponse([], 0, "req-inv-empty")])

    payload = _run(monkeypatch, client, **params())

    assert payload["services"] == [] and payload["upstreams"] == {}
    assert payload["total_count"] == 0


@pytest.mark.parametrize("page_size,message", [
    (0, "page_size must be between 1 and 100"),
    (101, "page_size must be between 1 and 100"),
])
def test_run_module_validates_page_size_bounds(monkeypatch, page_size, message):
    p = params()
    p["page_size"] = page_size
    payload = _expect_fail(monkeypatch, p)
    assert payload["msg"] == message


def test_run_module_rejects_unsupported_filters(monkeypatch):
    p = params()
    p["filters"] = {"name": "orders", "bogus": "x", "upstreamType": "NATIVE"}
    payload = _expect_fail(monkeypatch, p)
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

    _patch_sdk(monkeypatch, FailingClient())
    module_args(**params())

    with pytest.raises(AnsibleFailJson) as failure:
        run(tse_gateway_service_inventory_info.run_module)

    payload = failure.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert payload["error"] == "api exploded"
    assert payload["error_code"] == "FailedOperation"
    assert payload["request_id"] == "req-err"
