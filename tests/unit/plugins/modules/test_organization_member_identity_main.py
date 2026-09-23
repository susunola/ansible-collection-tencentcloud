"""Unit tests for the organization_member_identity write module.

``organization_member_identity`` reconciles the exact set of organization
access identities bound to a member: identities listed in
``identity_ids`` are added, identities outside it are revoked when
``purge`` is enabled.

Scenario matrix:

* exact-set no-drift idempotence
* additive grant (real, check mode)
* purge revocation of stale identities and purge=false keeping extras
* blanket SDK failure path
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import organization_member_identity as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

MEMBER_UIN = 100000000001


def _member_args(**overrides):
    params = {"member_uin": MEMBER_UIN}
    params.update(overrides)
    return module_args(**params)


class FakeOrganizationClient(object):
    """In-memory Organization client storing per-member identity sets."""

    def __init__(self, members=None):
        self.members = {uin: sorted(set(ids)) for uin, ids in (members or {}).items()}
        self.calls = []

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def DescribeOrganizationMemberAuthIdentities(self, request):
        self._record("DescribeOrganizationMemberAuthIdentities", request)
        ids = self.members.get(request.MemberUin, [])
        return SimpleNamespace(
            Items=[FakeResource({"IdentityId": i}) for i in ids],
            Total=len(ids),
        )

    def CreateOrganizationMemberAuthIdentity(self, request):
        self._record("CreateOrganizationMemberAuthIdentity", request)
        uin = request.MemberUins[0]
        current = set(self.members.get(uin, []))
        self.members[uin] = sorted(current | set(request.IdentityIds))
        return SimpleNamespace()

    def DeleteOrganizationMemberAuthIdentity(self, request):
        self._record("DeleteOrganizationMemberAuthIdentity", request)
        uin = request.MemberUin
        current = set(self.members.get(uin, []))
        self.members[uin] = sorted(current - {request.IdentityId})
        return SimpleNamespace()


def _make_module(monkeypatch, fake):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (FakeModels(), SimpleNamespace(OrganizationClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


# ---------------------------------------------------------------------------
# idempotence
# ---------------------------------------------------------------------------


def test_exact_set_no_drift_is_idempotent(monkeypatch):
    fake = FakeOrganizationClient(members={MEMBER_UIN: [1, 12]})
    _make_module(monkeypatch, fake)
    _member_args(identity_ids=[12, 1])
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["identity_ids"] == [1, 12]
    ops = [c for c, unused in fake.calls]
    assert "CreateOrganizationMemberAuthIdentity" not in ops
    assert "DeleteOrganizationMemberAuthIdentity" not in ops


# ---------------------------------------------------------------------------
# grant flows
# ---------------------------------------------------------------------------


def test_adds_missing_identities(monkeypatch):
    fake = FakeOrganizationClient(members={MEMBER_UIN: [1]})
    _make_module(monkeypatch, fake)
    _member_args(identity_ids=[1, 12])
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["identity_ids"] == [1, 12]
    assert fake.members[MEMBER_UIN] == [1, 12]
    ops = [c for c, unused in fake.calls]
    assert ops[0] == "DescribeOrganizationMemberAuthIdentities"
    assert "CreateOrganizationMemberAuthIdentity" in ops


def test_add_check_mode_is_dry_run(monkeypatch):
    fake = FakeOrganizationClient(members={MEMBER_UIN: [1]})
    _make_module(monkeypatch, fake)
    _member_args(_ansible_check_mode=True, identity_ids=[1, 12])
    result = run(mod.run_module)
    assert result["changed"] is True
    assert fake.members[MEMBER_UIN] == [1]
    assert "CreateOrganizationMemberAuthIdentity" not in [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# purge flows
# ---------------------------------------------------------------------------


def test_purge_revokes_stale_identities(monkeypatch):
    fake = FakeOrganizationClient(members={MEMBER_UIN: [1, 12, 30]})
    _make_module(monkeypatch, fake)
    _member_args(identity_ids=[1, 12])
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["identity_ids"] == [1, 12]
    assert fake.members[MEMBER_UIN] == [1, 12]
    ops = [c for c, unused in fake.calls]
    assert "DeleteOrganizationMemberAuthIdentity" in ops


def test_purge_false_keeps_stale_identities(monkeypatch):
    fake = FakeOrganizationClient(members={MEMBER_UIN: [1, 30]})
    _make_module(monkeypatch, fake)
    _member_args(identity_ids=[1], purge=False)
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["identity_ids"] == [1, 30]
    assert "DeleteOrganizationMemberAuthIdentity" not in [c for c, unused in fake.calls]


def test_purge_all_when_empty_desired(monkeypatch):
    fake = FakeOrganizationClient(members={MEMBER_UIN: [1, 12]})
    _make_module(monkeypatch, fake)
    _member_args(identity_ids=[])
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["identity_ids"] == []
    assert fake.members[MEMBER_UIN] == []


# ---------------------------------------------------------------------------
# failure paths
# ---------------------------------------------------------------------------


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeOrganizationMemberAuthIdentities(self, request):
            raise Boom("connection dropped")

    _make_module(monkeypatch, ExplodingClient())
    _member_args(identity_ids=[1, 12])
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]
