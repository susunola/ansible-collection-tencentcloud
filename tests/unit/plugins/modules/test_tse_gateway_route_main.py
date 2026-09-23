"""Unit tests for the tse_gateway_route write module.

Drives ``run_module()`` against an in-memory fake TSE client whose create /
modify / delete route calls mutate a route list so post-write describes
converge immediately.

Scenario matrix:

* argument guards (service_id required for present, at least one matcher)
* lookup: matching by name vs. by route_id, ambiguity guard
* present: create, idempotent no-op, drift-driven modify, check mode
* absent: no-op, delete, check mode
* the blanket SDK failure path
* legacy pure-helper assertions folded from the shallow test file
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import tse_gateway_route as mod
from ansible_collections.susunola.tencentcloud.plugins.modules.tse_gateway_route import (
    contains,
    desired,
    write_request,
)
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

GATEWAY_ID = "gateway-1001"
SERVICE_ID = "service-2001"

_WRITE_KEYS = (
    "Methods",
    "Hosts",
    "Paths",
    "Protocols",
    "PreserveHost",
    "HttpsRedirectStatusCode",
    "StripPath",
    "ForceHttps",
    "DestinationPorts",
    "Headers",
    "RequestBuffering",
    "ResponseBuffering",
    "RegexPriority",
    "QueryStringParameters",
)


def _route(rid, name, **extra):
    value = {"ID": rid, "Name": name}
    value.update(extra)
    return value


def _route_args(**overrides):
    params = {
        "gateway_id": GATEWAY_ID,
        "service_id": SERVICE_ID,
        "name": "orders",
        "methods": ["GET", "POST"],
        "paths": ["/orders"],
        "state": "present",
    }
    params.update(overrides)
    return module_args(**params)


class FakeTseClient(object):
    """In-memory TSE gateway-route client backed by a mutable route list."""

    def __init__(self, routes=None):
        self.routes = [dict(r) for r in routes or []]
        self.calls = []
        self._next_id = 1001

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def _copy_fields(self, source, target):
        for key in _WRITE_KEYS:
            if hasattr(source, key):
                target[key] = getattr(source, key)
        return target

    def DescribeCloudNativeAPIGatewayRoutes(self, request):
        self._record("DescribeCloudNativeAPIGatewayRoutes", request)
        payload = [SimpleNamespace(Routes=[FakeResource(dict(r)) for r in self.routes])]
        result = SimpleNamespace(RouteList=payload, RequestId="req-fake")
        return SimpleNamespace(Result=result, RequestId="req-fake")

    def CreateCloudNativeAPIGatewayRoute(self, request):
        self._record("CreateCloudNativeAPIGatewayRoute", request)
        rid = "route-%d" % self._next_id
        self._next_id += 1
        route = _route(rid, request.RouteName, ServiceID=request.ServiceID)
        self._copy_fields(request, route)
        self.routes.append(route)
        return SimpleNamespace(RequestId="req-fake")

    def ModifyCloudNativeAPIGatewayRoute(self, request):
        self._record("ModifyCloudNativeAPIGatewayRoute", request)
        for route in self.routes:
            if route["ID"] == getattr(request, "RouteID", None):
                route["Name"] = getattr(request, "RouteName", route["Name"])
                route["ServiceID"] = getattr(request, "ServiceID", route["ServiceID"])
                self._copy_fields(request, route)
        return SimpleNamespace(RequestId="req-fake")

    def DeleteCloudNativeAPIGatewayRoute(self, request):
        self._record("DeleteCloudNativeAPIGatewayRoute", request)
        marker = getattr(request, "Name", None)
        self.routes = [r for r in self.routes if r["ID"] != marker and r["Name"] != marker]
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake, models=None):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (models or FakeModels(), SimpleNamespace(TseClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


def _names(fake):
    return [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# argument guards
# ---------------------------------------------------------------------------


def test_present_without_service_id_fails(monkeypatch):
    fake = FakeTseClient()
    _make_module(monkeypatch, fake)
    module_args(
        gateway_id=GATEWAY_ID,
        name="orders",
        methods=["GET"],
        paths=["/orders"],
        state="present",
    )
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "service_id" in exc.value.args[0]["msg"]


def test_present_without_matcher_fails(monkeypatch):
    fake = FakeTseClient()
    _make_module(monkeypatch, fake)
    _route_args(methods=None, hosts=None, paths=None, destination_ports=None)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "At least one route matcher is required" in exc.value.args[0]["msg"]


# ---------------------------------------------------------------------------
# lookup semantics
# ---------------------------------------------------------------------------


def test_multiple_name_matches_fail_without_route_id(monkeypatch):
    fake = FakeTseClient(routes=[_route("route-1", "orders"), _route("route-2", "orders")])
    _make_module(monkeypatch, fake)
    _route_args()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "Multiple TSE gateway routes matched" in exc.value.args[0]["msg"]


def test_route_id_selects_single_route(monkeypatch):
    duplicate = _route("route-1", "orders", ServiceID=SERVICE_ID, Methods=["PUT"], Paths=["/other"])
    wanted = _route("route-2", "orders", ServiceID=SERVICE_ID, Methods=["GET", "POST"], Paths=["/orders"])
    fake = FakeTseClient(routes=[duplicate, wanted])
    _make_module(monkeypatch, fake)
    _route_args(route_id="route-2")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["route"]["ID"] == "route-2"


# ---------------------------------------------------------------------------
# present flows
# ---------------------------------------------------------------------------


def test_present_creates_new_route(monkeypatch):
    fake = FakeTseClient()
    _make_module(monkeypatch, fake)
    _route_args(hosts=["orders.example.com"], protocols=["https"], strip_path=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["route"]["ID"] == "route-1001"
    assert result["route"]["Name"] == "orders"
    assert result["route"]["Methods"] == ["GET", "POST"]
    assert result["route"]["Paths"] == ["/orders"]
    assert result["route"]["Hosts"] == ["orders.example.com"]
    assert result["route"]["StripPath"] is True
    assert "CreateCloudNativeAPIGatewayRoute" in _names(fake)
    assert fake.routes == [result["route"]]


def test_present_no_drift_is_idempotent(monkeypatch):
    route = _route("route-77", "orders", ServiceID=SERVICE_ID, Methods=["GET", "POST"], Paths=["/orders"])
    fake = FakeTseClient(routes=[route])
    _make_module(monkeypatch, fake)
    _route_args()
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["route"]["ID"] == "route-77"
    assert "CreateCloudNativeAPIGatewayRoute" not in _names(fake)
    assert "ModifyCloudNativeAPIGatewayRoute" not in _names(fake)


def test_present_drift_triggers_modify(monkeypatch):
    route = _route("route-77", "orders", ServiceID=SERVICE_ID, Methods=["GET", "POST"], Paths=["/legacy"])
    fake = FakeTseClient(routes=[route])
    _make_module(monkeypatch, fake)
    _route_args(paths=["/orders"])
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["route"]["Paths"] == ["/orders"]
    assert result["route"]["ID"] == "route-77"
    assert "ModifyCloudNativeAPIGatewayRoute" in _names(fake)


def test_present_check_mode_is_dry_run_for_create(monkeypatch):
    fake = FakeTseClient()
    _make_module(monkeypatch, fake)
    _route_args(_ansible_check_mode=True, paths=["/orders"])
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["route"]["Name"] == "orders"
    assert result["route"]["Paths"] == ["/orders"]
    assert "ID" not in result["route"]
    assert "CreateCloudNativeAPIGatewayRoute" not in _names(fake)
    assert fake.routes == []


def test_present_check_mode_is_dry_run_for_modify(monkeypatch):
    route = _route("route-77", "orders", ServiceID=SERVICE_ID, Methods=["GET", "POST"], Paths=["/legacy"])
    fake = FakeTseClient(routes=[route])
    _make_module(monkeypatch, fake)
    _route_args(_ansible_check_mode=True, paths=["/orders"])
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["route"]["Paths"] == ["/orders"]
    assert "ModifyCloudNativeAPIGatewayRoute" not in _names(fake)
    assert fake.routes[0]["Paths"] == ["/legacy"]


# ---------------------------------------------------------------------------
# absent flows
# ---------------------------------------------------------------------------


def test_absent_unregistered_is_idempotent(monkeypatch):
    fake = FakeTseClient()
    _make_module(monkeypatch, fake)
    _route_args(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["route"] is None
    assert "DeleteCloudNativeAPIGatewayRoute" not in _names(fake)


def test_absent_deletes_existing_route(monkeypatch):
    route = _route("route-77", "orders", ServiceID=SERVICE_ID, Methods=["GET"], Paths=["/orders"])
    fake = FakeTseClient(routes=[route])
    _make_module(monkeypatch, fake)
    _route_args(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["route"] is None
    assert "DeleteCloudNativeAPIGatewayRoute" in _names(fake)
    assert fake.routes == []


def test_absent_check_mode_is_dry_run(monkeypatch):
    route = _route("route-77", "orders", ServiceID=SERVICE_ID, Methods=["GET"], Paths=["/orders"])
    fake = FakeTseClient(routes=[route])
    _make_module(monkeypatch, fake)
    _route_args(_ansible_check_mode=True, state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["route"] is None
    assert "DeleteCloudNativeAPIGatewayRoute" not in _names(fake)
    assert fake.routes == [route]


# ---------------------------------------------------------------------------
# failure paths
# ---------------------------------------------------------------------------


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeCloudNativeAPIGatewayRoutes(self, request):
            raise Boom("connection dropped")

    _make_module(monkeypatch, ExplodingClient())
    _route_args()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]


# ---------------------------------------------------------------------------
# legacy pure-helper assertions (folded from the shallow test file)
# ---------------------------------------------------------------------------


class _RawCapture(object):
    def from_json_string(self, raw):
        self.raw = raw


def test_legacy_payload_and_subset_comparison_assertions():
    params = {
        "name": "orders",
        "service_id": "s1",
        "methods": ["GET"],
        "hosts": None,
        "paths": ["/orders"],
        "protocols": ["https"],
        "preserve_host": None,
        "https_redirect_status_code": None,
        "strip_path": True,
        "force_https": None,
        "destination_ports": None,
        "headers": None,
        "request_buffering": None,
        "response_buffering": None,
        "regex_priority": None,
        "query_string_parameters": None,
    }
    target = desired(params)
    assert contains(dict(target, ID="r1"), target)
    assert '"RouteName": "orders"' in write_request(_RawCapture, {"GatewayId": "g1", "RouteName": "orders"}).raw
