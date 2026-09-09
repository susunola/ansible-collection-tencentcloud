"""Unit tests for the tse_gateway_ip_restriction write module.

Drives ``run_module()`` against an in-memory fake TSE client whose
create-or-modify / delete operations mutate a per-resource policy store so
post-write describes converge immediately.

Scenario matrix:

* absent on a resource without a policy (idempotent no-op)
* absent with a live policy (check-mode dry run, real delete)
* creation when missing (happy path, check mode, and the
  restriction_type/addresses required-on-create guard)
* existing policy without drift (idempotent no-op)
* address drift triggers create-or-modify (real update, check mode)
* the blanket SDK failure path
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import tse_gateway_ip_restriction as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

POLICY = {
    "Enabled": True,
    "RestrictionType": "whiteList",
    "AddressList": ["10.0.0.0/8", "192.0.2.10"],
}

SERVICE_ID = "svc-1001"


def _policy(**overrides):
    item = copy.deepcopy(POLICY)
    item.update(overrides)
    return item


def _restriction_args(**overrides):
    params = {
        "state": "present",
        "gateway_id": "gateway-1001",
        "scope": "service",
        "resource_id": SERVICE_ID,
        "restriction_type": "whiteList",
        "addresses": ["10.0.0.0/8", "192.0.2.10"],
    }
    params.update(overrides)
    return module_args(**params)


def _key(scope, resource_id):
    return (scope, resource_id)


class FakeTseClient(object):
    """In-memory TSE client storing one policy per (scope, resource)."""

    def __init__(self, policies=None):
        self.policies = {}
        for (scope, resource_id), value in (policies or {}).items():
            self.policies[_key(scope, resource_id)] = copy.deepcopy(value)
        self.calls = []

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def DescribeCloudNativeAPIGatewayIPRestriction(self, request):
        self._record("DescribeCloudNativeAPIGatewayIPRestriction", request)
        policy = self.policies.get(_key(getattr(request, "SourceType", None), getattr(request, "SourceId", None)))
        return SimpleNamespace(Result=FakeResource(policy) if policy else None, RequestId="req-fake")

    def CreateOrModifyCloudNativeAPIGatewayIPRestriction(self, request):
        self._record("CreateOrModifyCloudNativeAPIGatewayIPRestriction", request)
        self.policies[_key(getattr(request, "SourceType", None), getattr(request, "SourceId", None))] = {
            "Enabled": getattr(request, "Enabled", None),
            "RestrictionType": getattr(request, "RestrictionType", None),
            "AddressList": getattr(request, "AddressList", None),
        }
        return SimpleNamespace(RequestId="req-fake")

    def DeleteCloudNativeAPIGatewayIPRestriction(self, request):
        self._record("DeleteCloudNativeAPIGatewayIPRestriction", request)
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
    _restriction_args(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["ip_restriction"] is None
    assert _names(fake) == ["DescribeCloudNativeAPIGatewayIPRestriction"]


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeTseClient(policies={("service", SERVICE_ID): _policy()})
    _make_module(monkeypatch, fake)
    _restriction_args(_ansible_check_mode=True, state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert len(fake.policies) == 1
    assert "DeleteCloudNativeAPIGatewayIPRestriction" not in _names(fake)


def test_absent_deletes_policy(monkeypatch):
    fake = FakeTseClient(policies={("service", SERVICE_ID): _policy()})
    _make_module(monkeypatch, fake)
    _restriction_args(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["ip_restriction"] is None
    assert fake.policies == {}
    assert "DeleteCloudNativeAPIGatewayIPRestriction" in _names(fake)


# ---------------------------------------------------------------------------
# present / creation flows
# ---------------------------------------------------------------------------


def test_present_without_type_and_addresses_fails(monkeypatch):
    fake = FakeTseClient()
    _make_module(monkeypatch, fake)
    module_args(state="present", gateway_id="gateway-1001", scope="service", resource_id=SERVICE_ID)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "restriction_type and addresses are required when creating" in exc.value.args[0]["msg"]


def test_create_ip_restriction(monkeypatch):
    fake = FakeTseClient()
    _make_module(monkeypatch, fake)
    _restriction_args(state="present")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["ip_restriction"]["RestrictionType"] == "whiteList"
    assert result["ip_restriction"]["Enabled"] is True
    assert result["ip_restriction"]["AddressList"] == ["10.0.0.0/8", "192.0.2.10"]
    assert len(fake.policies) == 1
    assert "CreateOrModifyCloudNativeAPIGatewayIPRestriction" in _names(fake)


def test_create_check_mode_is_dry_run(monkeypatch):
    fake = FakeTseClient()
    _make_module(monkeypatch, fake)
    _restriction_args(_ansible_check_mode=True, state="present")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["ip_restriction"]["RestrictionType"] == "whiteList"
    assert result["ip_restriction"]["Enabled"] is True
    assert fake.policies == {}
    assert "CreateOrModifyCloudNativeAPIGatewayIPRestriction" not in _names(fake)


def test_existing_policy_no_drift_is_idempotent(monkeypatch):
    fake = FakeTseClient(policies={("service", SERVICE_ID): _policy()})
    _make_module(monkeypatch, fake)
    _restriction_args(state="present")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["ip_restriction"]["RestrictionType"] == "whiteList"
    assert "CreateOrModifyCloudNativeAPIGatewayIPRestriction" not in _names(fake)


def test_address_drift_updates_policy(monkeypatch):
    fake = FakeTseClient(policies={("service", SERVICE_ID): _policy()})
    _make_module(monkeypatch, fake)
    _restriction_args(state="present", addresses=["10.0.0.0/8"])
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["ip_restriction"]["AddressList"] == ["10.0.0.0/8"]
    assert fake.policies[("service", SERVICE_ID)]["AddressList"] == ["10.0.0.0/8"]
    assert "CreateOrModifyCloudNativeAPIGatewayIPRestriction" in _names(fake)


def test_restriction_type_drift_updates_policy(monkeypatch):
    fake = FakeTseClient(policies={("service", SERVICE_ID): _policy()})
    _make_module(monkeypatch, fake)
    _restriction_args(state="present", restriction_type="blackList")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["ip_restriction"]["RestrictionType"] == "blackList"


def test_disable_via_enabled_drift(monkeypatch):
    fake = FakeTseClient(policies={("service", SERVICE_ID): _policy()})
    _make_module(monkeypatch, fake)
    _restriction_args(state="present", enabled=False)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["ip_restriction"]["Enabled"] is False


def test_update_check_mode_is_dry_run(monkeypatch):
    fake = FakeTseClient(policies={("service", SERVICE_ID): _policy()})
    _make_module(monkeypatch, fake)
    _restriction_args(_ansible_check_mode=True, state="present", addresses=["10.0.0.0/8"])
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["ip_restriction"]["AddressList"] == ["10.0.0.0/8"]
    assert fake.policies[("service", SERVICE_ID)]["AddressList"] == ["10.0.0.0/8", "192.0.2.10"]
    assert "CreateOrModifyCloudNativeAPIGatewayIPRestriction" not in _names(fake)


# ---------------------------------------------------------------------------
# failure paths
# ---------------------------------------------------------------------------


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeCloudNativeAPIGatewayIPRestriction(self, request):
            raise Boom("connection dropped")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    _restriction_args(state="present")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]
