"""Unit tests for the organization_member write module (helpers + run_module).

Creates, updates, moves and deletes organization-created members. Members
are looked up by MemberUin or by display name through a paginated
DescribeOrganizationMembers walk (50 per page, first match wins). A
missing member needs name/account_name/node_id to be created; existing
members are updated in place (name/remark/allow_quit) and moved between
nodes (node_id drift). Creation applies the financial permission and
access-identity defaults through sorted request lists.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import organization_member as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)


class _SdkError(Exception):
    """Stand-in for TencentCloudSDKException carrying a code/request id."""

    def __init__(self, code, message="", request_id=None):
        super(_SdkError, self).__init__(message)
        self._code = code
        self._request_id = request_id

    def get_code(self):
        return self._code

    def get_request_id(self):
        return self._request_id


def _member(**overrides):
    """API-shaped member dict; fresh copy per call."""
    item = {
        "MemberUin": 100000000001,
        "Name": "prod-team",
        "AccountName": "prod-team",
        "NodeId": 1001,
        "Remark": "",
        "IsAllowQuit": "Denied",
    }
    item.update(overrides)
    return item


def _params(**overrides):
    """Module parameters pre-filled from the argument spec defaults."""
    params = {
        "state": "present",
        "member_uin": None,
        "name": "prod-team",
        "account_name": "prod-team",
        "node_id": 1001,
        "remark": "",
        "permission_ids": [1, 2],
        "identity_role_ids": [1],
        "allow_quit": "Denied",
    }
    params.update(overrides)
    return params


def _run_args(**extra):
    """module_args() pre-filled with every non-None module parameter."""
    params = _params(**extra)
    args = {k: v for k, v in params.items() if v is not None}
    for key, value in extra.items():
        if key.startswith("_"):
            args[key] = value
    return module_args(**args)


class FakeModule(object):
    """Minimal stand-in for helpers that need sdk_call / fail_json."""

    def __init__(self, params=None):
        self.params = params or _params()
        self.sdk_calls = []

    def sdk_call(self, operation, request):
        self.sdk_calls.append((operation, request))
        return operation(request)

    def fail_json(self, **kwargs):
        raise AnsibleFailJson(kwargs)


class FakeOrgClient(object):
    """In-memory OrganizationClient stand-in storing member dicts.

    DescribeOrganizationMembers returns one page of Items (Limit 50) with
    a Total count so the module can walk additional pages.
    CreateOrganizationMember synthesizes sequential UINs,
    UpdateOrganizationMember rewrites Name/Remark/IsAllowQuit (skipping
    None-valued Name so omitted names stay untouched),
    MoveOrganizationNodeMembers reassigns NodeId and
    DeleteOrganizationMembers removes by UIN list.
    """

    def __init__(self, members=None):
        self.members = [dict(m) for m in (members or [])]
        self.calls = []
        self._seq = 100000000101

    def _record(self, name, request):
        self.calls.append((name, request))
        return request

    def DescribeOrganizationMembers(self, request):
        self._record("DescribeOrganizationMembers", request)
        offset = request.Offset
        limit = request.Limit
        page = self.members[offset:offset + limit]
        return SimpleNamespace(
            Items=[FakeResource(dict(m)) for m in page],
            Total=len(self.members),
            RequestId="req-fake",
        )

    def CreateOrganizationMember(self, request):
        self._record("CreateOrganizationMember", request)
        uin = self._seq
        self._seq += 1
        stored = {
            "MemberUin": uin,
            "Name": request.Name,
            "AccountName": request.AccountName,
            "NodeId": request.NodeId,
            "Remark": request.Remark,
            "IsAllowQuit": "Denied",
        }
        self.members.append(stored)
        return SimpleNamespace(Uin=uin, RequestId="req-fake")

    def UpdateOrganizationMember(self, request):
        self._record("UpdateOrganizationMember", request)
        for member in self.members:
            if member["MemberUin"] == request.MemberUin:
                if request.Name is not None:
                    member["Name"] = request.Name
                member["Remark"] = request.Remark
                member["IsAllowQuit"] = request.IsAllowQuit
        return SimpleNamespace(RequestId="req-fake")

    def MoveOrganizationNodeMembers(self, request):
        self._record("MoveOrganizationNodeMembers", request)
        for member in self.members:
            if member["MemberUin"] in request.MemberUin:
                member["NodeId"] = request.NodeId
        return SimpleNamespace(RequestId="req-fake")

    def DeleteOrganizationMembers(self, request):
        self._record("DeleteOrganizationMembers", request)
        uins = request.MemberUin
        self.members = [m for m in self.members if m["MemberUin"] not in uins]
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake):
    """Wire the shared monkeypatches and return the fake client."""
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(
        mod,
        "_load",
        lambda: (FakeModels(), SimpleNamespace(OrganizationClient=object)),
    )
    monkeypatch.setattr(
        TencentCloudModule,
        "create_client",
        lambda self, client_class, endpoint: fake,
    )
    return fake


class _BoomClient(object):
    """Every SDK call raises, so the module's wrapped error path is hit."""

    def __getattr__(self, name):
        def boom(*args, **kwargs):
            raise _SdkError("AuthFailure", "auth rejected", request_id="req-err")

        return boom


# ---------------------------------------------------------------------------
# request-builder / helper tests
# ---------------------------------------------------------------------------


def test_describe_builds_paged_request():
    request = mod.describe(FakeModels(), offset=0)
    assert request.Offset == 0
    assert request.Limit == 50
    request = mod.describe(FakeModels(), offset=60)
    assert request.Offset == 60


def test_create_request_carries_fields_and_sorts_lists():
    request = mod.create(
        FakeModels(),
        _params(permission_ids=[2, 1], identity_role_ids=[3, 1], remark="prod"),
    )
    assert request.Name == "prod-team"
    assert request.AccountName == "prod-team"
    assert request.NodeId == 1001
    assert request.Remark == "prod"
    assert request.PolicyType == "Financial"
    assert request.PermissionIds == [1, 2]
    assert request.IdentityRoleID == [1, 3]


def test_update_request_carries_fields():
    request = mod.update(
        FakeModels(),
        _params(name="renamed", remark="tuned", allow_quit="Allow"),
        100000000001,
    )
    assert request.MemberUin == 100000000001
    assert request.Name == "renamed"
    assert request.Remark == "tuned"
    assert request.IsAllowQuit == "Allow"


def test_move_request_carries_node_and_uin():
    request = mod.move(FakeModels(), 2002, 100000000001)
    assert request.NodeId == 2002
    assert request.MemberUin == [100000000001]


def test_delete_request_carries_uin():
    request = mod.delete(FakeModels(), 100000000001)
    assert request.MemberUin == [100000000001]


def test_desired_uses_params_when_given():
    value = mod.desired(
        _params(name="new-name", node_id=2002, remark="r", allow_quit="Allow")
    )
    assert value == {
        "Name": "new-name",
        "NodeId": 2002,
        "Remark": "r",
        "IsAllowQuit": "Allow",
    }


def test_desired_falls_back_to_current():
    current = _member(Name="existing", NodeId=999)
    value = mod.desired(_params(name=None, node_id=None, allow_quit="Denied"), current)
    assert value == {
        "Name": "existing",
        "NodeId": 999,
        "Remark": "",
        "IsAllowQuit": "Denied",
    }


def test_comparable_selects_four_keys():
    value = mod.comparable(_member(Remark="x"))
    assert value == {
        "Name": "prod-team",
        "NodeId": 1001,
        "Remark": "x",
        "IsAllowQuit": "Denied",
    }


def test_find_by_member_uin(monkeypatch):
    fake = FakeOrgClient([_member(), _member(MemberUin=100000000002, Name="other")])
    module = FakeModule(_params(member_uin=100000000002))
    value = mod.find(module, fake, FakeModels(), module.params)
    assert value["MemberUin"] == 100000000002


def test_find_by_name(monkeypatch):
    fake = FakeOrgClient([_member(Name="other"), _member()])
    module = FakeModule(_params())
    value = mod.find(module, fake, FakeModels(), module.params)
    assert value["Name"] == "prod-team"


def test_find_no_match_returns_none(monkeypatch):
    fake = FakeOrgClient([_member(Name="other")])
    module = FakeModule(_params())
    assert mod.find(module, fake, FakeModels(), module.params) is None


def test_find_paginates_until_match(monkeypatch):
    members = [_member(MemberUin=100000000000 + i, Name="bulk-%d" % i) for i in range(60)]
    fake = FakeOrgClient(members)
    module = FakeModule(_params(name="bulk-55"))
    value = mod.find(module, fake, FakeModels(), module.params)
    assert value["Name"] == "bulk-55"
    assert len(module.sdk_calls) == 2


def test_find_paginates_and_returns_none(monkeypatch):
    members = [_member(MemberUin=100000000000 + i, Name="bulk-%d" % i) for i in range(60)]
    fake = FakeOrgClient(members)
    module = FakeModule(_params(name="absent"))
    assert mod.find(module, fake, FakeModels(), module.params) is None
    assert len(module.sdk_calls) == 2


# ---------------------------------------------------------------------------
# run_module main-path tests
# ---------------------------------------------------------------------------


def test_present_requires_create_fields(monkeypatch):
    fake = FakeOrgClient()
    _make_module(monkeypatch, fake)
    _run_args(member_uin=100000000001, name=None, account_name=None, node_id=None)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "name, account_name and node_id are required" in exc.value.args[0]["msg"]
    assert [c[0] for c in fake.calls] == ["DescribeOrganizationMembers"]


def test_absent_noop_when_missing(monkeypatch):
    fake = FakeOrgClient()
    _make_module(monkeypatch, fake)
    _run_args(state="absent", name="ghost")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["member"] is None
    assert [c[0] for c in fake.calls] == ["DescribeOrganizationMembers"]


def test_absent_check_mode_delete_is_dry_run(monkeypatch):
    fake = FakeOrgClient([_member()])
    _make_module(monkeypatch, fake)
    _run_args(state="absent", _ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["member"]["MemberUin"] == 100000000001
    assert result["diff"]["before"]["Name"] == "prod-team"
    assert result["diff"]["after"] is None
    assert [c[0] for c in fake.calls] == ["DescribeOrganizationMembers"]
    assert len(fake.members) == 1


def test_absent_deletes_member(monkeypatch):
    fake = FakeOrgClient([_member()])
    _make_module(monkeypatch, fake)
    _run_args(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["member"] is None
    assert [c[0] for c in fake.calls] == [
        "DescribeOrganizationMembers",
        "DeleteOrganizationMembers",
    ]
    assert fake.calls[1][1].MemberUin == [100000000001]
    assert fake.members == []


def test_present_noop_when_member_matches(monkeypatch):
    fake = FakeOrgClient([_member()])
    _make_module(monkeypatch, fake)
    _run_args()
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["member"]["MemberUin"] == 100000000001
    assert [c[0] for c in fake.calls] == ["DescribeOrganizationMembers"]


def test_present_noop_via_member_uin(monkeypatch):
    fake = FakeOrgClient([_member()])
    _make_module(monkeypatch, fake)
    _run_args(member_uin=100000000001)
    result = run(mod.run_module)
    assert result["changed"] is False
    assert [c[0] for c in fake.calls] == ["DescribeOrganizationMembers"]


def test_present_creates_member(monkeypatch):
    fake = FakeOrgClient()
    _make_module(monkeypatch, fake)
    _run_args()
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["member"]["MemberUin"] == 100000000101
    assert result["member"]["Name"] == "prod-team"
    assert [c[0] for c in fake.calls] == [
        "DescribeOrganizationMembers",
        "CreateOrganizationMember",
        "DescribeOrganizationMembers",
    ]
    created = fake.calls[1][1]
    assert created.Name == "prod-team"
    assert created.AccountName == "prod-team"
    assert created.NodeId == 1001
    assert created.Remark == ""
    assert created.PolicyType == "Financial"
    assert created.PermissionIds == [1, 2]
    assert created.IdentityRoleID == [1]
    assert len(fake.members) == 1


def test_present_check_mode_create_is_dry_run(monkeypatch):
    fake = FakeOrgClient()
    _make_module(monkeypatch, fake)
    _run_args(_ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["member"] is None
    assert result["diff"]["before"] is None
    assert result["diff"]["after"]["Name"] == "prod-team"
    assert result["diff"]["after"]["NodeId"] == 1001
    assert [c[0] for c in fake.calls] == ["DescribeOrganizationMembers"]
    assert fake.members == []


def test_present_renames_via_member_uin(monkeypatch):
    fake = FakeOrgClient([_member()])
    _make_module(monkeypatch, fake)
    _run_args(member_uin=100000000001, name="renamed")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["member"]["Name"] == "renamed"
    assert [c[0] for c in fake.calls] == [
        "DescribeOrganizationMembers",
        "UpdateOrganizationMember",
        "DescribeOrganizationMembers",
    ]
    updated = fake.calls[1][1]
    assert updated.MemberUin == 100000000001
    assert updated.Name == "renamed"


def test_present_remark_drift_updates_without_name(monkeypatch):
    fake = FakeOrgClient([_member()])
    _make_module(monkeypatch, fake)
    _run_args(member_uin=100000000001, name=None, remark="tuned")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["member"]["Name"] == "prod-team"
    assert result["member"]["Remark"] == "tuned"
    assert fake.calls[1][0] == "UpdateOrganizationMember"
    assert fake.calls[1][1].Name is None
    assert fake.calls[1][1].Remark == "tuned"


def test_present_check_mode_update_is_dry_run(monkeypatch):
    fake = FakeOrgClient([_member()])
    _make_module(monkeypatch, fake)
    _run_args(remark="tuned", _ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["member"]["Remark"] == ""
    assert result["diff"]["after"]["Remark"] == "tuned"
    assert [c[0] for c in fake.calls] == ["DescribeOrganizationMembers"]


def test_present_moves_between_nodes(monkeypatch):
    fake = FakeOrgClient([_member()])
    _make_module(monkeypatch, fake)
    _run_args(node_id=2002)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["member"]["NodeId"] == 2002
    assert [c[0] for c in fake.calls] == [
        "DescribeOrganizationMembers",
        "MoveOrganizationNodeMembers",
        "DescribeOrganizationMembers",
    ]
    moved = fake.calls[1][1]
    assert moved.NodeId == 2002
    assert moved.MemberUin == [100000000001]


def test_present_updates_then_moves(monkeypatch):
    fake = FakeOrgClient([_member()])
    _make_module(monkeypatch, fake)
    _run_args(remark="tuned", node_id=2002)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["member"]["Remark"] == "tuned"
    assert result["member"]["NodeId"] == 2002
    assert [c[0] for c in fake.calls] == [
        "DescribeOrganizationMembers",
        "UpdateOrganizationMember",
        "MoveOrganizationNodeMembers",
        "DescribeOrganizationMembers",
    ]


def test_sdk_failure_reports_error_payload(monkeypatch):
    fake = _BoomClient()
    _make_module(monkeypatch, fake)
    _run_args(state="absent", name="ghost")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert payload["error"] == "auth rejected"
    assert payload["error_code"] == "AuthFailure"
    assert payload["request_id"] == "req-err"


def test_main_entrypoint_runs_module(monkeypatch):
    fake = FakeOrgClient()
    _make_module(monkeypatch, fake)
    _run_args(state="absent", name="ghost")
    result = run(mod.main)
    assert result["changed"] is False
    assert result["member"] is None
