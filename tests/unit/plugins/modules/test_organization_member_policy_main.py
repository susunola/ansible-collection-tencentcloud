"""Unit tests for the organization_member_policy write module.

``organization_member_policy`` grants or revokes an organization access
policy on a member. Policies are identified either by an explicit
``policy_id`` or by their ``name``; ``name`` is immutable once a policy
exists and drift on it fails through ``require_immutable_unchanged``.

Scenario matrix:

* absent on a missing policy / present create (real, check mode)
* missing create-time parameters failure
* present no-drift idempotence and description/identity update
* PolicyName immutability guard
* absent on an existing policy (check-mode dry run, real delete)
* blanket SDK failure path
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import organization_member_policy as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

MEMBER_UIN = 100000000001

POLICY = {
    "PolicyId": 201,
    "PolicyName": "operations-access",
    "IdentityId": 12,
    "Description": "Operations access policy",
}


def _policy(**overrides):
    item = copy.deepcopy(POLICY)
    item.update(overrides)
    return item


def _p_args(**overrides):
    params = {"member_uin": MEMBER_UIN}
    params.update(overrides)
    return module_args(**params)


class FakeOrganizationClient(object):
    """In-memory Organization client storing member access policies."""

    def __init__(self, policies=None):
        self.policies = [copy.deepcopy(p) for p in (policies or [])]
        self.calls = []
        self._next = 300

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def DescribeOrganizationMemberPolicies(self, request):
        self._record("DescribeOrganizationMemberPolicies", request)
        items = [FakeResource(dict(p)) for p in self.policies]
        return SimpleNamespace(Items=items, Total=len(items))

    def CreateOrganizationMemberPolicy(self, request):
        self._record("CreateOrganizationMemberPolicy", request)
        self._next += 1
        policy = {
            "PolicyId": self._next,
            "PolicyName": request.PolicyName,
            "IdentityId": request.IdentityId,
            "Description": request.Description,
        }
        self.policies.append(policy)
        return SimpleNamespace(PolicyId=self._next)

    def UpdateOrganizationMembersPolicy(self, request):
        self._record("UpdateOrganizationMembersPolicy", request)
        for policy in self.policies:
            if policy["PolicyId"] == request.PolicyId:
                policy["IdentityId"] = request.IdentityId
                policy["Description"] = request.Description
        return SimpleNamespace()

    def DeleteOrganizationMembersPolicy(self, request):
        self._record("DeleteOrganizationMembersPolicy", request)
        self.policies = [p for p in self.policies if p["PolicyId"] != request.PolicyId]
        return SimpleNamespace()


def _make_module(monkeypatch, fake):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (FakeModels(), SimpleNamespace(OrganizationClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


# ---------------------------------------------------------------------------
# absent flows
# ---------------------------------------------------------------------------


def test_absent_on_missing_policy_is_idempotent(monkeypatch):
    fake = FakeOrganizationClient(policies=[])
    _make_module(monkeypatch, fake)
    _p_args(state="absent", name="operations-access")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["policy"] is None
    assert [c for c, unused in fake.calls] == ["DescribeOrganizationMemberPolicies"]


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeOrganizationClient(policies=[_policy()])
    _make_module(monkeypatch, fake)
    _p_args(_ansible_check_mode=True, state="absent", name="operations-access")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["policy"]["PolicyId"] == 201
    assert len(fake.policies) == 1
    assert "DeleteOrganizationMembersPolicy" not in [c for c, unused in fake.calls]


def test_absent_deletes_policy_by_id(monkeypatch):
    fake = FakeOrganizationClient(policies=[_policy()])
    _make_module(monkeypatch, fake)
    _p_args(state="absent", policy_id=201)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["policy"] is None
    assert fake.policies == []
    ops = [c for c, unused in fake.calls]
    assert "DeleteOrganizationMembersPolicy" in ops


# ---------------------------------------------------------------------------
# present flows
# ---------------------------------------------------------------------------


def test_present_requires_name_and_identity_when_creating(monkeypatch):
    fake = FakeOrganizationClient(policies=[])
    _make_module(monkeypatch, fake)
    _p_args(state="present", name="operations-access")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "name and identity_id are required" in exc.value.args[0]["msg"]


def test_present_creates_policy(monkeypatch):
    fake = FakeOrganizationClient(policies=[])
    _make_module(monkeypatch, fake)
    _p_args(
        state="present",
        name="operations-access",
        identity_id=12,
        description="Operations access policy",
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["policy"]["PolicyName"] == "operations-access"
    assert result["policy"]["PolicyId"] > 201
    assert len(fake.policies) == 1
    ops = [c for c, unused in fake.calls]
    assert ops[0] == "DescribeOrganizationMemberPolicies"
    assert "CreateOrganizationMemberPolicy" in ops


def test_present_create_check_mode_is_dry_run(monkeypatch):
    fake = FakeOrganizationClient(policies=[])
    _make_module(monkeypatch, fake)
    _p_args(_ansible_check_mode=True, state="present", name="operations-access", identity_id=12)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert fake.policies == []
    assert "CreateOrganizationMemberPolicy" not in [c for c, unused in fake.calls]


def test_present_no_drift_is_idempotent(monkeypatch):
    fake = FakeOrganizationClient(policies=[_policy()])
    _make_module(monkeypatch, fake)
    _p_args(
        state="present",
        name="operations-access",
        identity_id=12,
        description="Operations access policy",
    )
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["policy"]["PolicyId"] == 201
    assert "UpdateOrganizationMembersPolicy" not in [c for c, unused in fake.calls]


def test_description_drift_updates_policy(monkeypatch):
    fake = FakeOrganizationClient(policies=[_policy()])
    _make_module(monkeypatch, fake)
    _p_args(state="present", name="operations-access", identity_id=12, description="Renamed policy")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["policy"]["Description"] == "Renamed policy"
    assert fake.policies[0]["Description"] == "Renamed policy"
    ops = [c for c, unused in fake.calls]
    assert "UpdateOrganizationMembersPolicy" in ops


def test_identity_drift_updates_policy(monkeypatch):
    fake = FakeOrganizationClient(policies=[_policy()])
    _make_module(monkeypatch, fake)
    _p_args(
        state="present",
        name="operations-access",
        identity_id=30,
        description="Operations access policy",
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["policy"]["IdentityId"] == 30
    assert fake.policies[0]["IdentityId"] == 30


def test_policy_name_is_immutable(monkeypatch):
    fake = FakeOrganizationClient(policies=[_policy()])
    _make_module(monkeypatch, fake)
    _p_args(state="present", policy_id=201, name="renamed-policy", identity_id=12)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "Immutable fields cannot be changed" in payload["msg"]
    assert payload["replacement_required"] is True


# ---------------------------------------------------------------------------
# failure paths
# ---------------------------------------------------------------------------


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeOrganizationMemberPolicies(self, request):
            raise Boom("connection dropped")

    _make_module(monkeypatch, ExplodingClient())
    _p_args(state="present", name="operations-access", identity_id=12)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]
