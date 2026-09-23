"""Unit tests for the dlc_work_group_membership write module (run_module flows).

``run_module()`` is driven end to end against an in-memory fake DLC client
whose add/delete-member operations mutate the work-group user store, so the
post-write ``DescribeWorkGroups`` refetch and the reconciliation waiter
converge immediately. The module reconciles (no create/delete lifecycle): the
work group must already exist and the run converges its exact member set.

Scenario matrix:

* missing work group fails before any write
* idempotent no-op when the member set already matches (order independent)
* check-mode dry run for adds / removes
* add, remove and combined add+remove runs (SDK request fields captured)
* ``allow_empty`` guard for removing every member
* argument-validation failure (missing required params) before any SDK call
* the blanket ``sdk_error_payload`` failure path
* legacy helper regression tests (folded from test_dlc_work_group_membership.py)
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import dlc_work_group_membership as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

GROUP_ID = 10042


def _group(**overrides):
    item = {"WorkGroupId": GROUP_ID, "UserSet": []}
    item.update(overrides)
    return item


def _base(**overrides):
    params = {"work_group_id": GROUP_ID, "user_ids": ["u1"]}
    params.update(overrides)
    return module_args(**params)


class FakeDlcClient(object):
    """In-memory DLC client mutating each work group's member store."""

    def __init__(self, groups=None):
        self.groups = [copy.deepcopy(g) for g in (groups or [])]
        self.calls = []

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def DescribeWorkGroups(self, request):
        self._record("DescribeWorkGroups", request)
        wgid = getattr(request, "WorkGroupId", None)
        matches = [g for g in self.groups if g.get("WorkGroupId") == wgid]
        return SimpleNamespace(
            WorkGroupSet=[
                FakeResource(dict(g, UserSet=[FakeResource({"UserId": user}) for user in g.get("UserSet", [])]))
                for g in matches
            ],
            RequestId="req-fake",
        )

    def AddUsersToWorkGroup(self, request):
        self._record("AddUsersToWorkGroup", request)
        info = request.AddInfo
        for group in self.groups:
            if group.get("WorkGroupId") == info.WorkGroupId:
                store = group.setdefault("UserSet", [])
                for user in info.UserIds:
                    if user not in store:
                        store.append(user)
        return SimpleNamespace(RequestId="req-fake")

    def DeleteUsersFromWorkGroup(self, request):
        self._record("DeleteUsersFromWorkGroup", request)
        info = request.AddInfo
        for group in self.groups:
            if group.get("WorkGroupId") == info.WorkGroupId:
                group["UserSet"] = [user for user in group.get("UserSet", []) if user not in info.UserIds]
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake, models=None):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (models or FakeModels(), SimpleNamespace(DlcClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


def _find_call(fake, operation):
    return next(request for name, request in fake.calls if name == operation)


# ---------------------------------------------------------------------------
# precondition failures
# ---------------------------------------------------------------------------


def test_missing_work_group_fails(monkeypatch):
    fake = FakeDlcClient(groups=[])
    _make_module(monkeypatch, fake)
    _base()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "DLC work group not found" in exc.value.args[0]["msg"]


# ---------------------------------------------------------------------------
# idempotent no-op
# ---------------------------------------------------------------------------


def test_members_already_match_is_idempotent(monkeypatch):
    fake = FakeDlcClient(groups=[_group(UserSet=["u1", "u2"])])
    _make_module(monkeypatch, fake)
    _base(user_ids=["u2", "u1"])  # order must not matter
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["user_ids"] == ["u1", "u2"]
    assert result["added"] == []
    assert result["removed"] == []
    assert [name for name, unused in fake.calls] == ["DescribeWorkGroups"]


# ---------------------------------------------------------------------------
# add flows
# ---------------------------------------------------------------------------


def test_add_check_mode_is_dry_run(monkeypatch):
    fake = FakeDlcClient(groups=[_group(UserSet=["u1"])])
    _make_module(monkeypatch, fake)
    _base(_ansible_check_mode=True, user_ids=["u1", "u2"])
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["user_ids"] == ["u1", "u2"]
    assert fake.groups[0]["UserSet"] == ["u1"]
    assert "AddUsersToWorkGroup" not in [name for name, unused in fake.calls]


def test_add_joins_new_members(monkeypatch):
    fake = FakeDlcClient(groups=[_group(UserSet=["u1"])])
    _make_module(monkeypatch, fake)
    _base(user_ids=["u1", "u2", "u3"])
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["user_ids"] == ["u1", "u2", "u3"]
    assert result["added"] == ["u2", "u3"]
    request = _find_call(fake, "AddUsersToWorkGroup")
    assert request.AddInfo.WorkGroupId == GROUP_ID
    assert sorted(request.AddInfo.UserIds) == ["u2", "u3"]
    ops = [name for name, unused in fake.calls]
    assert ops[0] == "DescribeWorkGroups"
    assert ops[-1] == "DescribeWorkGroups"  # waiter + final refetch converge


# ---------------------------------------------------------------------------
# remove flows
# ---------------------------------------------------------------------------


def test_remove_empty_set_requires_allow_empty(monkeypatch):
    fake = FakeDlcClient(groups=[_group(UserSet=["u1"])])
    _make_module(monkeypatch, fake)
    _base(user_ids=[])
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "allow_empty=true" in exc.value.args[0]["msg"]
    assert fake.groups[0]["UserSet"] == ["u1"]


def test_allow_empty_removes_all_members(monkeypatch):
    fake = FakeDlcClient(groups=[_group(UserSet=["u1", "u2"])])
    _make_module(monkeypatch, fake)
    _base(user_ids=[], allow_empty=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["user_ids"] == []
    assert result["removed"] == ["u1", "u2"]
    assert fake.groups[0]["UserSet"] == []
    request = _find_call(fake, "DeleteUsersFromWorkGroup")
    assert request.AddInfo.WorkGroupId == GROUP_ID
    assert sorted(request.AddInfo.UserIds) == ["u1", "u2"]


def test_remove_stale_members_reconciles(monkeypatch):
    fake = FakeDlcClient(groups=[_group(UserSet=["u1", "u2"])])
    _make_module(monkeypatch, fake)
    _base(user_ids=["u2"])
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["user_ids"] == ["u2"]
    assert result["removed"] == ["u1"]
    ops = [name for name, unused in fake.calls]
    assert "AddUsersToWorkGroup" not in ops
    assert "DeleteUsersFromWorkGroup" in ops


def test_add_and_remove_combined(monkeypatch):
    fake = FakeDlcClient(groups=[_group(UserSet=["u1", "u2"])])
    _make_module(monkeypatch, fake)
    _base(user_ids=["u2", "u3"])
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["user_ids"] == ["u2", "u3"]
    assert result["added"] == ["u3"]
    assert result["removed"] == ["u1"]
    ops = [name for name, unused in fake.calls]
    assert "AddUsersToWorkGroup" in ops
    assert "DeleteUsersFromWorkGroup" in ops


# ---------------------------------------------------------------------------
# argument validation and failure paths
# ---------------------------------------------------------------------------


def test_missing_required_arguments_fail(monkeypatch):
    fake = FakeDlcClient(groups=[_group()])
    _make_module(monkeypatch, fake)
    module_args(user_ids=["u1"])  # work_group_id omitted
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "work_group_id" in exc.value.args[0]["msg"]
    assert fake.calls == []


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeWorkGroups(self, request):
            raise Boom("connection dropped")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    _base()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]


# ---------------------------------------------------------------------------
# legacy helper regression tests (folded from test_dlc_work_group_membership.py)
# ---------------------------------------------------------------------------


class _Info(object):
    pass


class _Request(object):
    pass


_Models = type(
    "Models",
    (),
    {
        "UserIdSetOfWorkGroupId": _Info,
        "AddUsersToWorkGroupRequest": _Request,
        "DeleteUsersFromWorkGroupRequest": _Request,
    },
)


def test_delta_is_exact_and_order_independent():
    assert mod.delta(["u2", "u1"], ["u2", "u3"]) == (["u3"], ["u1"])
    assert mod.delta(["u1"], ["u1"]) == ([], [])


def test_membership_request_scopes_group_and_users():
    request = mod.membership_request(_Models, 42, ["u1", "u2"], True)
    assert request.AddInfo.WorkGroupId == 42
    assert request.AddInfo.UserIds == ["u1", "u2"]
    remove = mod.membership_request(_Models, 7, ["u9"], False)
    assert isinstance(remove, _Request)
    assert remove.AddInfo.WorkGroupId == 7
