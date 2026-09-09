"""Unit tests for the tse_gateway_rate_limit write module (run_module flows).

``run_module()`` creates, updates and deletes a rate-limit plugin bound to one
gateway service (addressed by name) or route (addressed by id). It is driven
end to end against an in-memory fake client whose create/modify/delete
operations mutate a per-(scope, resource) policy store so the post-write
describe refetch converges immediately.

Scenario matrix:

* absent without a live policy (idempotent) / check-mode delete / real delete
* creation when missing (service-by-name and route-by-id, check mode and real)
* idempotent no-op when the live policy already satisfies the desired config
* drift through the modify API (check mode and real)
* a describe that raises a not-found error is treated as absent and the
  policy is then created
* create-time config requirement enforced by ``required_if``
* blanket ``sdk_error_payload`` failure path
* legacy helper regression tests (folded from test_tse_gateway_rate_limit.py)
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import tse_gateway_rate_limit as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

GATEWAY_ID = "gateway-abc"
ROUTE_ID = "route-1001"
SERVICE = "service-orders"
CONFIG = {"Enabled": True, "QpsThresholds": [{"Unit": "second", "Max": 100}], "LimitBy": "service"}


def _base(**overrides):
    params = {
        "gateway_id": GATEWAY_ID,
        "scope": "route",
        "resource": ROUTE_ID,
        "config": copy.deepcopy(CONFIG),
    }
    params.update(overrides)
    return module_args(**params)


class FakeRateLimitClient(object):
    """In-memory TSE rate-limit client keyed by (scope, resource)."""

    def __init__(self, policies=None):
        self.policies = {}
        for (scope, resource), value in (policies or {}).items():
            self.policies[(scope, resource)] = copy.deepcopy(value)
        self.calls = []

    def _record(self, name, request=None):
        self.calls.append((name, request))

    @staticmethod
    def _identity(request):
        return getattr(request, "Name", None) or getattr(request, "Id", None)

    def _describe(self, scope, name, request):
        self._record(name, request)
        assert request.GatewayId == GATEWAY_ID
        policy = self.policies.get((scope, self._identity(request)))
        return SimpleNamespace(Result=FakeResource(copy.deepcopy(policy)) if policy else None, RequestId="req-fake")

    def _mutate(self, scope, name, request):
        self._record(name, request)
        self.policies[(scope, self._identity(request))] = copy.deepcopy(request.LimitDetail)
        return SimpleNamespace(RequestId="req-fake")

    def _delete(self, scope, name, request):
        self._record(name, request)
        self.policies.pop((scope, self._identity(request)), None)
        return SimpleNamespace(RequestId="req-fake")

    def DescribeCloudNativeAPIGatewayServiceRateLimit(self, request):
        return self._describe("service", "DescribeCloudNativeAPIGatewayServiceRateLimit", request)

    def CreateCloudNativeAPIGatewayServiceRateLimit(self, request):
        return self._mutate("service", "CreateCloudNativeAPIGatewayServiceRateLimit", request)

    def ModifyCloudNativeAPIGatewayServiceRateLimit(self, request):
        return self._mutate("service", "ModifyCloudNativeAPIGatewayServiceRateLimit", request)

    def DeleteCloudNativeAPIGatewayServiceRateLimit(self, request):
        return self._delete("service", "DeleteCloudNativeAPIGatewayServiceRateLimit", request)

    def DescribeCloudNativeAPIGatewayRouteRateLimit(self, request):
        return self._describe("route", "DescribeCloudNativeAPIGatewayRouteRateLimit", request)

    def CreateCloudNativeAPIGatewayRouteRateLimit(self, request):
        return self._mutate("route", "CreateCloudNativeAPIGatewayRouteRateLimit", request)

    def ModifyCloudNativeAPIGatewayRouteRateLimit(self, request):
        return self._mutate("route", "ModifyCloudNativeAPIGatewayRouteRateLimit", request)

    def DeleteCloudNativeAPIGatewayRouteRateLimit(self, request):
        return self._delete("route", "DeleteCloudNativeAPIGatewayRouteRateLimit", request)


def _make_module(monkeypatch, fake):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (FakeModels(), SimpleNamespace(TseClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


def _ops(fake):
    return [name for name, unused in fake.calls]


# ---------------------------------------------------------------------------
# absent flows
# ---------------------------------------------------------------------------


def test_absent_without_rate_limit_is_idempotent(monkeypatch):
    fake = _make_module(monkeypatch, FakeRateLimitClient())
    _base(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["rate_limit"] is None
    assert _ops(fake) == ["DescribeCloudNativeAPIGatewayRouteRateLimit"]


def test_absent_deletes_existing_service_policy(monkeypatch):
    fake = _make_module(monkeypatch, FakeRateLimitClient(policies={("service", SERVICE): CONFIG}))
    _base(scope="service", resource=SERVICE, state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["rate_limit"] is None
    assert fake.policies == {}
    assert _ops(fake) == [
        "DescribeCloudNativeAPIGatewayServiceRateLimit",
        "DeleteCloudNativeAPIGatewayServiceRateLimit",
    ]


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = _make_module(monkeypatch, FakeRateLimitClient(policies={("route", ROUTE_ID): CONFIG}))
    _base(state="absent", _ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert len(fake.policies) == 1
    assert "DeleteCloudNativeAPIGatewayRouteRateLimit" not in _ops(fake)


# ---------------------------------------------------------------------------
# creation flows
# ---------------------------------------------------------------------------


def test_present_creates_service_rate_limit_by_name(monkeypatch):
    fake = _make_module(monkeypatch, FakeRateLimitClient())
    _base(scope="service", resource=SERVICE)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["rate_limit"]["Enabled"] is True
    assert result["rate_limit"]["LimitBy"] == "service"
    assert result["rate_limit"]["QpsThresholds"] == [{"Unit": "second", "Max": 100}]
    assert fake.policies[("service", SERVICE)] == CONFIG
    assert _ops(fake) == [
        "DescribeCloudNativeAPIGatewayServiceRateLimit",
        "CreateCloudNativeAPIGatewayServiceRateLimit",
        "DescribeCloudNativeAPIGatewayServiceRateLimit",
    ]


def test_present_creates_route_rate_limit_by_id(monkeypatch):
    fake = _make_module(monkeypatch, FakeRateLimitClient())
    _base()
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["rate_limit"]["Enabled"] is True
    assert fake.policies[("route", ROUTE_ID)] == CONFIG
    assert _ops(fake) == [
        "DescribeCloudNativeAPIGatewayRouteRateLimit",
        "CreateCloudNativeAPIGatewayRouteRateLimit",
        "DescribeCloudNativeAPIGatewayRouteRateLimit",
    ]


def test_present_create_check_mode_is_dry_run(monkeypatch):
    fake = _make_module(monkeypatch, FakeRateLimitClient())
    _base(_ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["rate_limit"] == CONFIG
    assert "diff" in result
    assert fake.policies == {}
    assert "CreateCloudNativeAPIGatewayRouteRateLimit" not in _ops(fake)


def test_present_create_requires_config(monkeypatch):
    fake = _make_module(monkeypatch, FakeRateLimitClient())
    module_args(gateway_id=GATEWAY_ID, scope="route", resource=ROUTE_ID, state="present")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "config" in payload["msg"]
    assert fake.policies == {}


# ---------------------------------------------------------------------------
# idempotent and drift flows
# ---------------------------------------------------------------------------


def test_converged_policy_is_idempotent(monkeypatch):
    live = dict(CONFIG, Policy="local", UpdateTime="2026-01-01")
    fake = _make_module(monkeypatch, FakeRateLimitClient(policies={("service", SERVICE): live}))
    _base(scope="service", resource=SERVICE)
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["rate_limit"]["UpdateTime"] == "2026-01-01"
    assert "ModifyCloudNativeAPIGatewayServiceRateLimit" not in _ops(fake)


def test_threshold_drift_updates_policy(monkeypatch):
    drift = copy.deepcopy(CONFIG)
    drift["QpsThresholds"] = [{"Unit": "second", "Max": 50}]
    fake = _make_module(monkeypatch, FakeRateLimitClient(policies={("service", SERVICE): drift}))
    _base(scope="service", resource=SERVICE)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["rate_limit"]["QpsThresholds"] == [{"Unit": "second", "Max": 100}]
    assert fake.policies[("service", SERVICE)]["QpsThresholds"] == [{"Unit": "second", "Max": 100}]
    assert _ops(fake) == [
        "DescribeCloudNativeAPIGatewayServiceRateLimit",
        "ModifyCloudNativeAPIGatewayServiceRateLimit",
        "DescribeCloudNativeAPIGatewayServiceRateLimit",
    ]


def test_drift_check_mode_is_dry_run(monkeypatch):
    drift = dict(CONFIG, Enabled=False)
    fake = _make_module(monkeypatch, FakeRateLimitClient(policies={("route", ROUTE_ID): drift}))
    _base(_ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["rate_limit"] == CONFIG
    assert "diff" in result
    assert fake.policies[("route", ROUTE_ID)]["Enabled"] is False
    assert "ModifyCloudNativeAPIGatewayRouteRateLimit" not in _ops(fake)


# ---------------------------------------------------------------------------
# not-found tolerance and failure paths
# ---------------------------------------------------------------------------


def test_describe_not_found_is_absent_then_created(monkeypatch):
    class NotFound(Exception):
        def get_code(self):
            return "ResourceNotFound"

    class NotFoundClient(object):
        def __init__(self):
            self.policies = {}
            self.calls = []

        def _not_found(self, request):
            identity = getattr(request, "Name", None) or getattr(request, "Id", None)
            if identity not in self.policies:
                raise NotFound("rate limit plugin is not configured")
            return identity

        def DescribeCloudNativeAPIGatewayServiceRateLimit(self, request):
            self.calls.append("DescribeCloudNativeAPIGatewayServiceRateLimit")
            identity = self._not_found(request)
            return SimpleNamespace(Result=FakeResource(copy.deepcopy(self.policies[identity])), RequestId="req-fake")

        def CreateCloudNativeAPIGatewayServiceRateLimit(self, request):
            self.calls.append("CreateCloudNativeAPIGatewayServiceRateLimit")
            self.policies[request.Name] = copy.deepcopy(request.LimitDetail)
            return SimpleNamespace(RequestId="req-fake")

        def ModifyCloudNativeAPIGatewayServiceRateLimit(self, request):
            self.calls.append("ModifyCloudNativeAPIGatewayServiceRateLimit")
            self.policies[request.Name] = copy.deepcopy(request.LimitDetail)
            return SimpleNamespace(RequestId="req-fake")

        def DeleteCloudNativeAPIGatewayServiceRateLimit(self, request):
            self.calls.append("DeleteCloudNativeAPIGatewayServiceRateLimit")
            self.policies.pop(request.Name, None)
            return SimpleNamespace(RequestId="req-fake")

    fake = _make_module(monkeypatch, NotFoundClient())
    _base(scope="service", resource=SERVICE)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["rate_limit"]["Enabled"] is True
    assert fake.policies[SERVICE] == CONFIG
    assert fake.calls.count("DescribeCloudNativeAPIGatewayServiceRateLimit") == 2
    assert fake.calls.count("CreateCloudNativeAPIGatewayServiceRateLimit") == 1


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeCloudNativeAPIGatewayRouteRateLimit(self, request):
            raise Boom("tse endpoint unreachable")

        def CreateCloudNativeAPIGatewayRouteRateLimit(self, request):
            raise AssertionError("must not be reached")

        def ModifyCloudNativeAPIGatewayRouteRateLimit(self, request):
            raise AssertionError("must not be reached")

        def DeleteCloudNativeAPIGatewayRouteRateLimit(self, request):
            raise AssertionError("must not be reached")

    fake = _make_module(monkeypatch, ExplodingClient())
    _base()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "tse endpoint unreachable" in payload["error"]


# ---------------------------------------------------------------------------
# legacy helper regression tests (folded from test_tse_gateway_rate_limit.py)
# ---------------------------------------------------------------------------


class _RawRequest(object):
    def from_json_string(self, raw):
        self.raw = raw


def test_rate_limit_request_maps_scope_specific_resource_key():
    config = {"Enabled": True, "QpsThresholds": [{"Unit": "second", "Max": 100}]}
    route = mod.request(_RawRequest, None, {"gateway_id": "g1", "scope": "route", "resource": "r1"}, config)
    service = mod.request(_RawRequest, None, {"gateway_id": "g1", "scope": "service", "resource": "s1"}, config)
    assert '"Id": "r1"' in route.raw
    assert '"Name": "s1"' in service.raw
    assert '"GatewayId": "g1"' in route.raw
    assert '"LimitDetail"' in route.raw
    assert mod.contains(dict(config, Policy="local"), config)


def test_rate_limit_delete_request_maps_identity_only():
    route = mod.request(_RawRequest, None, {"gateway_id": "g1", "scope": "route", "resource": "r1"})
    service = mod.request(_RawRequest, None, {"gateway_id": "g1", "scope": "service", "resource": "s1"})
    assert '"Id": "r1"' in route.raw
    assert '"Name": "s1"' in service.raw
    assert '"LimitDetail"' not in route.raw


def test_contains_allows_server_enriched_policy():
    actual = {"Enabled": True, "LimitBy": "service", "UpdateTime": "2026-01-01"}
    expected = {"Enabled": True, "LimitBy": "service"}
    assert mod.contains(actual, expected)


def test_contains_rejects_drifted_values():
    actual = {"Enabled": False, "LimitBy": "service"}
    expected = {"Enabled": True, "LimitBy": "service"}
    assert not mod.contains(actual, expected)
