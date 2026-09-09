"""Unit tests for the tse_gateway_cors write module.

Drives ``run_module()`` against an in-memory fake TSE client whose
create-or-modify / delete operations mutate a per-resource CORS policy store
so post-write describes converge immediately.

Scenario matrix:

* absent on a resource without a policy (idempotent no-op)
* absent with a live policy (check-mode dry run, real delete)
* creation when missing (full spec, defaults-filled minimal spec,
  check mode)
* existing policy without drift (idempotent no-op)
* drift (methods / origins / credentials) triggers create-or-modify
  (real update, check mode)
* the blanket SDK failure path
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import tse_gateway_cors as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

POLICY = {
    "Enabled": True,
    "Origins": ["https://app.example.com"],
    "Headers": ["Content-Type", "X-Custom"],
    "Methods": ["GET", "POST"],
    "ExposedHeaders": ["X-Request-Id"],
    "MaxAge": 600,
    "Credentials": True,
    "PreFlightContinue": False,
}

ROUTE_ID = "route-1001"


def _policy(**overrides):
    item = copy.deepcopy(POLICY)
    item.update(overrides)
    return item


def _cors_args(**overrides):
    params = {
        "state": "present",
        "gateway_id": "gateway-1001",
        "scope": "route",
        "resource_id": ROUTE_ID,
        "enabled": True,
        "origins": ["https://app.example.com"],
        "headers": ["Content-Type", "X-Custom"],
        "methods": ["GET", "POST"],
        "exposed_headers": ["X-Request-Id"],
        "max_age": 600,
        "credentials": True,
        "preflight_continue": False,
    }
    params.update(overrides)
    return module_args(**params)


def _key(scope, resource_id):
    return (scope, resource_id)


class FakeTseClient(object):
    """In-memory TSE client storing one CORS policy per (scope, resource)."""

    def __init__(self, policies=None):
        self.policies = {}
        for (scope, resource_id), value in (policies or {}).items():
            self.policies[_key(scope, resource_id)] = copy.deepcopy(value)
        self.calls = []

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def DescribeCloudNativeAPIGatewayCORS(self, request):
        self._record("DescribeCloudNativeAPIGatewayCORS", request)
        policy = self.policies.get(_key(getattr(request, "SourceType", None), getattr(request, "SourceId", None)))
        return SimpleNamespace(Result=FakeResource(policy) if policy else None, RequestId="req-fake")

    def CreateOrModifyCloudNativeAPIGatewayCORS(self, request):
        self._record("CreateOrModifyCloudNativeAPIGatewayCORS", request)
        self.policies[_key(getattr(request, "SourceType", None), getattr(request, "SourceId", None))] = {
            key: getattr(request, key, None)
            for key in (
                "Enabled", "Origins", "Headers", "Methods",
                "ExposedHeaders", "MaxAge", "Credentials", "PreFlightContinue",
            )
        }
        return SimpleNamespace(RequestId="req-fake")

    def DeleteCloudNativeAPIGatewayCORS(self, request):
        self._record("DeleteCloudNativeAPIGatewayCORS", request)
        self.policies.pop(_key(getattr(request, "SourceType", None), getattr(request, "SourceId", None)), None)
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake, models=None):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (models or FakeModels(), SimpleNamespace(TseClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


def _names(fake):
    return [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# absent flows
# ---------------------------------------------------------------------------


def test_absent_missing_policy_is_idempotent(monkeypatch):
    fake = FakeTseClient()
    _make_module(monkeypatch, fake)
    _cors_args(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["cors"] is None
    assert _names(fake) == ["DescribeCloudNativeAPIGatewayCORS"]


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeTseClient(policies={("route", ROUTE_ID): _policy()})
    _make_module(monkeypatch, fake)
    _cors_args(_ansible_check_mode=True, state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert len(fake.policies) == 1
    assert "DeleteCloudNativeAPIGatewayCORS" not in _names(fake)


def test_absent_deletes_policy(monkeypatch):
    fake = FakeTseClient(policies={("route", ROUTE_ID): _policy()})
    _make_module(monkeypatch, fake)
    _cors_args(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["cors"] is None
    assert fake.policies == {}
    assert "DeleteCloudNativeAPIGatewayCORS" in _names(fake)


# ---------------------------------------------------------------------------
# present / creation flows
# ---------------------------------------------------------------------------


def test_create_cors_with_full_spec(monkeypatch):
    fake = FakeTseClient()
    _make_module(monkeypatch, fake)
    _cors_args(state="present")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["cors"]["Methods"] == ["GET", "POST"]
    assert result["cors"]["Credentials"] is True
    assert result["cors"]["MaxAge"] == 600
    assert len(fake.policies) == 1
    assert "CreateOrModifyCloudNativeAPIGatewayCORS" in _names(fake)


def test_create_cors_uses_defaults_for_omitted_fields(monkeypatch):
    fake = FakeTseClient()
    _make_module(monkeypatch, fake)
    module_args(state="present", gateway_id="gateway-1001", scope="service", resource_id="svc-1001")
    result = run(mod.run_module)
    assert result["changed"] is True
    cors = result["cors"]
    assert cors["Enabled"] is True
    assert cors["Origins"] == []
    assert cors["Headers"] == []
    assert cors["Methods"] == []
    assert cors["ExposedHeaders"] == []
    assert cors["MaxAge"] == 0
    assert cors["Credentials"] is False
    assert cors["PreFlightContinue"] is False


def test_create_check_mode_is_dry_run(monkeypatch):
    fake = FakeTseClient()
    _make_module(monkeypatch, fake)
    _cors_args(_ansible_check_mode=True, state="present")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["cors"]["Origins"] == ["https://app.example.com"]
    assert fake.policies == {}
    assert "CreateOrModifyCloudNativeAPIGatewayCORS" not in _names(fake)


def test_existing_policy_no_drift_is_idempotent(monkeypatch):
    fake = FakeTseClient(policies={("route", ROUTE_ID): _policy()})
    _make_module(monkeypatch, fake)
    _cors_args(state="present")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["cors"]["Methods"] == ["GET", "POST"]
    assert "CreateOrModifyCloudNativeAPIGatewayCORS" not in _names(fake)


def test_methods_drift_updates_policy(monkeypatch):
    fake = FakeTseClient(policies={("route", ROUTE_ID): _policy()})
    _make_module(monkeypatch, fake)
    _cors_args(state="present", methods=["GET", "POST", "PUT"])
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["cors"]["Methods"] == ["GET", "POST", "PUT"]
    assert fake.policies[("route", ROUTE_ID)]["Methods"] == ["GET", "POST", "PUT"]
    assert "CreateOrModifyCloudNativeAPIGatewayCORS" in _names(fake)


def test_credentials_drift_updates_policy(monkeypatch):
    fake = FakeTseClient(policies={("route", ROUTE_ID): _policy()})
    _make_module(monkeypatch, fake)
    _cors_args(state="present", credentials=False)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["cors"]["Credentials"] is False


def test_partial_fields_merge_with_current(monkeypatch):
    fake = FakeTseClient(policies={("route", ROUTE_ID): _policy()})
    _make_module(monkeypatch, fake)
    _cors_args(state="present", max_age=120)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["cors"]["MaxAge"] == 120
    assert result["cors"]["Methods"] == ["GET", "POST"]


def test_update_check_mode_is_dry_run(monkeypatch):
    fake = FakeTseClient(policies={("route", ROUTE_ID): _policy()})
    _make_module(monkeypatch, fake)
    _cors_args(_ansible_check_mode=True, state="present", methods=["GET", "POST", "PUT"])
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["cors"]["Methods"] == ["GET", "POST", "PUT"]
    assert fake.policies[("route", ROUTE_ID)]["Methods"] == ["GET", "POST"]
    assert "CreateOrModifyCloudNativeAPIGatewayCORS" not in _names(fake)


# ---------------------------------------------------------------------------
# failure paths
# ---------------------------------------------------------------------------


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeCloudNativeAPIGatewayCORS(self, request):
            raise Boom("connection dropped")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    _cors_args(state="present")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]


# ---------------------------------------------------------------------------
# legacy helper regression tests (folded from test_tse_gateway_policies.py)
# ---------------------------------------------------------------------------


class _Value(object):
    pass


def test_cors_defaults_and_request_identity():
    p = {"gateway_id": "g1", "scope": "route", "resource_id": "r1"}
    target = mod.target_config(p, None)
    assert target["Enabled"] is True
    assert target["Origins"] == []
    assert target["Methods"] == []
    request = mod.request(_Value, p, target)
    assert request.GatewayId == "g1"
    assert request.SourceType == "route"
    assert request.SourceId == "r1"
    assert request.Enabled is True
    assert request.Origins == []


def test_cors_request_maps_identity_without_target():
    p = {"gateway_id": "g1", "scope": "service", "resource_id": "svc-1"}
    request = mod.request(_Value, p)
    assert request.GatewayId == "g1"
    assert request.SourceType == "service"
    assert request.SourceId == "svc-1"


def test_cors_target_supplied_fields_override_defaults():
    p = {"gateway_id": "g1", "scope": "route", "resource_id": "r1", "methods": ["GET"], "credentials": True}
    target = mod.target_config(p, None)
    assert target["Methods"] == ["GET"]
    assert target["Credentials"] is True
    assert target["Enabled"] is True


def test_cors_target_merges_unsupplied_fields_from_current():
    current = {"Enabled": True, "Origins": ["https://app.example.com"], "MaxAge": 600}
    p = {"gateway_id": "g1", "scope": "route", "resource_id": "r1", "methods": ["PUT"]}
    target = mod.target_config(p, current)
    assert target["Methods"] == ["PUT"]
    assert target["Origins"] == ["https://app.example.com"]
    assert target["MaxAge"] == 600
