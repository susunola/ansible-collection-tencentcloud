"""Unit tests for the tse_gateway_waf_protection write module.

Drives ``run_module()`` against an in-memory fake TSE client whose
open / close WAF calls flip status flags in a store that describes read
back, so reconciliation converges immediately.

The module has no ``state``; it reconciles ``enabled`` for a scope's
resources and reports which ones were affected.

Scenario matrix:

* argument guards (resource_ids on Global, missing ids on Service/Route,
  duplicate ids)
* Global scope: no-drift no-op, enable drift (real + check mode), disable
* Service scope: enabling only the drifted subset of resources
* Route scope: disabling a route
* the blanket SDK failure path
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import tse_gateway_waf_protection as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

STATUS = {
    "Global": {"Global": False},
    "Service": {"svc-1": True, "svc-2": False},
    "Route": {"rt-1": True},
}


def _status(**overrides):
    item = copy.deepcopy(STATUS)
    for key, value in overrides.items():
        item[key] = copy.deepcopy(value)
    return item


def _waf_args(**overrides):
    params = {"gateway_id": "gateway-1001", "scope": "Global", "enabled": True}
    params.update(overrides)
    return module_args(**params)


class FakeTseClient(object):
    """In-memory TSE client whose WAF status map feeds describes."""

    def __init__(self, status=None):
        self.status = _status()
        if status is not None:
            self.status = status
        self.calls = []

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def DescribeWafProtection(self, request):
        self._record("DescribeWafProtection", request)
        scope = getattr(request, "Type", None)
        if scope == "Global":
            result = {"GlobalStatus": self.status["Global"]["Global"]}
        elif scope == "Service":
            result = {"ServicesStatus": [{"Id": rid, "Status": st} for rid, st in sorted(self.status["Service"].items())]}
        else:
            result = {"RouteStatus": [{"Id": rid, "Status": st} for rid, st in sorted(self.status["Route"].items())]}
        return SimpleNamespace(Result=FakeResource(result), RequestId="req-fake")

    def _set(self, request, value):
        scope = getattr(request, "Type", None)
        if scope == "Global":
            self.status["Global"]["Global"] = value
            return
        for rid in getattr(request, "List", None) or []:
            self.status[scope][rid] = value

    def OpenWafProtection(self, request):
        self._record("OpenWafProtection", request)
        self._set(request, True)
        return SimpleNamespace(RequestId="req-fake")

    def CloseWafProtection(self, request):
        self._record("CloseWafProtection", request)
        self._set(request, False)
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


def test_global_scope_with_resource_ids_fails(monkeypatch):
    fake = FakeTseClient()
    _make_module(monkeypatch, fake)
    _waf_args(scope="Global", resource_ids=["svc-1"])
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "resource_ids must be empty for Global" in exc.value.args[0]["msg"]


def test_service_scope_without_resource_ids_fails(monkeypatch):
    fake = FakeTseClient()
    _make_module(monkeypatch, fake)
    _waf_args(scope="Service", enabled=False)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "resource_ids is required for Service or Route" in exc.value.args[0]["msg"]


def test_duplicate_resource_ids_fail(monkeypatch):
    fake = FakeTseClient()
    _make_module(monkeypatch, fake)
    _waf_args(scope="Service", resource_ids=["svc-1", "svc-1"])
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "resource_ids must not contain duplicates" in exc.value.args[0]["msg"]


# ---------------------------------------------------------------------------
# Global scope
# ---------------------------------------------------------------------------


def test_global_no_drift_is_idempotent(monkeypatch):
    fake = FakeTseClient()
    _make_module(monkeypatch, fake)
    _waf_args(scope="Global", enabled=False)
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["waf_protection"]["Scope"] == "Global"
    assert result["waf_protection"]["Status"] == {"Global": False}
    assert "OpenWafProtection" not in _names(fake)
    assert "CloseWafProtection" not in _names(fake)


def test_global_enable_drift_opens_protection(monkeypatch):
    fake = FakeTseClient()
    _make_module(monkeypatch, fake)
    _waf_args(scope="Global", enabled=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["waf_protection"]["Status"] == {"Global": True}
    assert result["waf_protection"]["AffectedResourceIds"] == ["Global"]
    assert fake.status["Global"]["Global"] is True
    assert "OpenWafProtection" in _names(fake)


def test_global_enable_check_mode_is_dry_run(monkeypatch):
    fake = FakeTseClient()
    _make_module(monkeypatch, fake)
    _waf_args(_ansible_check_mode=True, scope="Global", enabled=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert fake.status["Global"]["Global"] is False
    assert "OpenWafProtection" not in _names(fake)


def test_global_disable_closes_protection(monkeypatch):
    fake = FakeTseClient(status=_status(Global={"Global": True}))
    _make_module(monkeypatch, fake)
    _waf_args(scope="Global", enabled=False)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["waf_protection"]["Status"] == {"Global": False}
    assert fake.status["Global"]["Global"] is False
    assert "CloseWafProtection" in _names(fake)


# ---------------------------------------------------------------------------
# Service / Route scope
# ---------------------------------------------------------------------------


def test_service_scope_enables_only_drifted_resources(monkeypatch):
    fake = FakeTseClient()
    _make_module(monkeypatch, fake)
    _waf_args(scope="Service", resource_ids=["svc-1", "svc-2"], enabled=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["waf_protection"]["Status"] == {"svc-1": True, "svc-2": True}
    assert result["waf_protection"]["AffectedResourceIds"] == ["svc-2"]
    assert fake.status["Service"] == {"svc-1": True, "svc-2": True}


def test_service_scope_no_drift_is_idempotent(monkeypatch):
    fake = FakeTseClient()
    _make_module(monkeypatch, fake)
    _waf_args(scope="Service", resource_ids=["svc-1"], enabled=True)
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["waf_protection"]["Status"] == {"svc-1": True}


def test_route_scope_disable_closes_route(monkeypatch):
    fake = FakeTseClient()
    _make_module(monkeypatch, fake)
    _waf_args(scope="Route", resource_ids=["rt-1"], enabled=False)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["waf_protection"]["Status"] == {"rt-1": False}
    assert result["waf_protection"]["AffectedResourceIds"] == ["rt-1"]
    assert fake.status["Route"]["rt-1"] is False
    assert "CloseWafProtection" in _names(fake)


def test_route_scope_no_drift_is_idempotent(monkeypatch):
    fake = FakeTseClient()
    _make_module(monkeypatch, fake)
    _waf_args(scope="Route", resource_ids=["rt-1"], enabled=True)
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["waf_protection"]["Status"] == {"rt-1": True}


# ---------------------------------------------------------------------------
# failure paths
# ---------------------------------------------------------------------------


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeWafProtection(self, request):
            raise Boom("connection dropped")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    _waf_args(scope="Global", enabled=False)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]
