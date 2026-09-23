"""Unit tests for the api_gateway_usage_plan_binding write module.

Drives ``run_module()`` against an in-memory fake API Gateway client whose
bind / unbind operations mutate the usage plan's environment-binding list so
post-write describes converge immediately.

A binding matches when an ``EnvironmentList`` entry for the same service and
environment also carries the requested ``api_id`` (or no API for a
service-level binding), so an absent run removes exactly the requested
binding out of the plan's binding list.

Scenario matrix:

* absent on a plan with no matching binding (idempotent no-op, including
  when the plan has bindings elsewhere)
* absent removes a single service-level binding out of a multi-binding list
* absent with a live binding (check-mode dry run, real unbind)
* present bind on an unbound service (happy path, API-level variant,
  check mode)
* present on an already-bound service (idempotent no-op)
* the blanket SDK failure path
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import api_gateway_usage_plan_binding as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

BINDING = {
    "UsagePlanId": "usagePlan-1001",
    "ServiceId": "service-abc",
    "EnvironmentName": "release",
    "ApiId": None,
}


def _binding(**overrides):
    item = copy.deepcopy(BINDING)
    item.update(overrides)
    return item


def _bind_args(**overrides):
    params = {
        "usage_plan_id": "usagePlan-1001",
        "service_id": "service-abc",
        "environment": "release",
    }
    params.update(overrides)
    return module_args(**params)


class FakeApigatewayClient(object):
    """In-memory client mutating one usage plan's environment-binding list."""

    def __init__(self, bindings=None):
        self.bindings = [copy.deepcopy(t) for t in (bindings or [])]
        self.calls = []

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def DescribeUsagePlanEnvironments(self, request):
        self._record("DescribeUsagePlanEnvironments", request)
        plan_id = getattr(request, "UsagePlanId", None)
        return SimpleNamespace(
            Result=SimpleNamespace(EnvironmentList=[FakeResource(t) for t in self.bindings if t.get("UsagePlanId") == plan_id])
        )

    def BindEnvironment(self, request):
        self._record("BindEnvironment", request)
        api = (getattr(request, "ApiIds", None) or [None])[0]
        for plan_id in getattr(request, "UsagePlanIds", None) or []:
            self.bindings.append({
                "UsagePlanId": plan_id,
                "ServiceId": getattr(request, "ServiceId", None),
                "EnvironmentName": getattr(request, "Environment", None),
                "ApiId": api,
            })
        return SimpleNamespace(RequestId="req-fake")

    def UnBindEnvironment(self, request):
        self._record("UnBindEnvironment", request)
        api = (getattr(request, "ApiIds", None) or [None])[0]
        plans = set(getattr(request, "UsagePlanIds", None) or [])
        service_id = getattr(request, "ServiceId", None)
        environment = getattr(request, "Environment", None)
        kept = []
        for item in self.bindings:
            same = item.get("UsagePlanId") in plans
            same = same and item.get("ServiceId") == service_id
            same = same and item.get("EnvironmentName") == environment
            same = same and (item.get("ApiId") or None) == api
            if not same:
                kept.append(item)
        self.bindings = kept
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake, models=None):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (models or FakeModels(), SimpleNamespace(ApigatewayClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


def _names(fake):
    return [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# absent flows
# ---------------------------------------------------------------------------


def test_absent_missing_binding_is_idempotent(monkeypatch):
    fake = FakeApigatewayClient(bindings=[])
    _make_module(monkeypatch, fake)
    _bind_args(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["binding"] is None
    assert _names(fake) == ["DescribeUsagePlanEnvironments"]


def test_absent_when_bound_elsewhere_is_idempotent(monkeypatch):
    # The plan is bound to another environment/service, but not to the one
    # requested, so absent must not touch it.
    fake = FakeApigatewayClient(bindings=[_binding(ServiceId="service-other")])
    _make_module(monkeypatch, fake)
    _bind_args(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["binding"] is None
    assert len(fake.bindings) == 1


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeApigatewayClient(bindings=[_binding()])
    _make_module(monkeypatch, fake)
    _bind_args(_ansible_check_mode=True, state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert len(fake.bindings) == 1
    assert "UnBindEnvironment" not in _names(fake)


def test_absent_unbinds_service_binding(monkeypatch):
    fake = FakeApigatewayClient(bindings=[_binding()])
    _make_module(monkeypatch, fake)
    _bind_args(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["binding"] is None
    assert fake.bindings == []
    assert "UnBindEnvironment" in _names(fake)


def test_absent_removes_single_binding_from_list(monkeypatch):
    # Two services bound to the same plan in the same environment; absent
    # must remove only the requested service binding.
    fake = FakeApigatewayClient(
        bindings=[_binding(), _binding(ServiceId="service-xyz", ApiId="api-2")]
    )
    _make_module(monkeypatch, fake)
    _bind_args(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert [b["ServiceId"] for b in fake.bindings] == ["service-xyz"]
    assert "UnBindEnvironment" in _names(fake)


def test_absent_unbinds_api_level_binding(monkeypatch):
    fake = FakeApigatewayClient(bindings=[_binding(ApiId="api-9")])
    _make_module(monkeypatch, fake)
    _bind_args(state="absent", api_id="api-9")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert fake.bindings == []


# ---------------------------------------------------------------------------
# present (bind) flows
# ---------------------------------------------------------------------------


def test_present_binds_unbound_service(monkeypatch):
    fake = FakeApigatewayClient(bindings=[])
    _make_module(monkeypatch, fake)
    _bind_args(state="present")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["binding"] == {
        "UsagePlanId": "usagePlan-1001",
        "ServiceId": "service-abc",
        "Environment": "release",
        "ApiId": None,
    }
    assert len(fake.bindings) == 1
    assert "BindEnvironment" in _names(fake)


def test_present_binds_api_level(monkeypatch):
    # A service-level binding already exists; requesting an API-level
    # binding is a different entry, so a new API binding is added.
    fake = FakeApigatewayClient(bindings=[_binding()])
    _make_module(monkeypatch, fake)
    _bind_args(state="present", api_id="api-7")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["binding"]["ApiId"] == "api-7"
    assert [b.get("ApiId") for b in fake.bindings] == [None, "api-7"]


def test_present_bind_check_mode_is_dry_run(monkeypatch):
    fake = FakeApigatewayClient(bindings=[])
    _make_module(monkeypatch, fake)
    _bind_args(_ansible_check_mode=True, state="present")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["binding"]["ServiceId"] == "service-abc"
    assert fake.bindings == []
    assert "BindEnvironment" not in _names(fake)


def test_present_already_bound_is_idempotent(monkeypatch):
    fake = FakeApigatewayClient(bindings=[_binding()])
    _make_module(monkeypatch, fake)
    _bind_args(state="present")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["binding"]["Environment"] == "release"
    assert "BindEnvironment" not in _names(fake)


# ---------------------------------------------------------------------------
# failure paths
# ---------------------------------------------------------------------------


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeUsagePlanEnvironments(self, request):
            raise Boom("connection dropped")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    _bind_args(state="present")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]
