"""Main-path (run_module) unit tests for the dlc_user write module.

Complements ``test_dlc_user.py`` (request-builder level) by driving
``run_module()`` end to end against an in-memory fake DLC client whose write
operations mutate a user store so post-write ``find`` and waiters converge.

Scenario matrix:
* pre-SDK validation (alias length, ADMIN with initial bindings)
* absent flows (missing, owner guard, allow_delete, bound guard, check mode,
  real delete)
* creation flows (check mode and real create with wait)
* no-op when nothing drifts
* description/user_type updates and the immutable alias guard
* multiple-match and SDK failure paths
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import dlc_user as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

USER = {
    "UserId": "100012345678",
    "UserDescription": "Analytics engineering account",
    "UserType": "COMMON",
    "UserAlias": "analytics-engineer",
    "AccountType": "UserAccount",
    "PolicySet": [],
    "WorkGroupSet": [],
    "IsOwner": False,
}


def _user(**overrides):
    item = copy.deepcopy(USER)
    item.update(overrides)
    return item


def _base(**overrides):
    params = {"user_id": "100012345678"}
    params.update(overrides)
    return module_args(**params)


class FakeDlcClient(object):
    """In-memory DLC client mutating a user store."""

    def __init__(self, users=None):
        self.users = [copy.deepcopy(u) for u in (users or [])]
        self.calls = []

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def DescribeUsers(self, request):
        self._record("DescribeUsers", request)
        uid = getattr(request, "UserId", None)
        matches = [copy.deepcopy(u) for u in self.users if u.get("UserId") == uid]
        return SimpleNamespace(UserSet=[FakeResource(u) for u in matches], TotalCount=len(matches))

    def CreateUser(self, request):
        self._record("CreateUser", request)
        item = {k: copy.deepcopy(v) for k, v in vars(request).items() if not k.startswith("_")}
        item.setdefault("PolicySet", [])
        item.setdefault("WorkGroupSet", [])
        item.setdefault("IsOwner", False)
        self.users.append(item)
        return SimpleNamespace(RequestId="req-fake")

    def ModifyUser(self, request):
        self._record("ModifyUser", request)
        for user in self.users:
            if user.get("UserId") == getattr(request, "UserId", None):
                user["UserDescription"] = getattr(request, "UserDescription", None)
        return SimpleNamespace(RequestId="req-fake")

    def ModifyUserType(self, request):
        self._record("ModifyUserType", request)
        for user in self.users:
            if user.get("UserId") == getattr(request, "UserId", None):
                user["UserType"] = getattr(request, "UserType", None)
        return SimpleNamespace(RequestId="req-fake")

    def DeleteUser(self, request):
        self._record("DeleteUser", request)
        ids = list(getattr(request, "UserIds", None) or [])
        self.users = [u for u in self.users if u.get("UserId") not in ids]
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake, models=None):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (models or FakeModels(), SimpleNamespace(DlcClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


# ---------------------------------------------------------------------------
# validation guards
# ---------------------------------------------------------------------------


def test_alias_too_long_fails(monkeypatch):
    fake = FakeDlcClient(users=[])
    _make_module(monkeypatch, fake)
    _base(alias="x" * 50)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "shorter than 50 characters" in exc.value.args[0]["msg"]


def test_admin_user_cannot_declare_bindings(monkeypatch):
    fake = FakeDlcClient(users=[])
    _make_module(monkeypatch, fake)
    _base(user_type="ADMIN", initial_work_group_ids=[1])
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "ADMIN users cannot declare initial policies or work groups" in exc.value.args[0]["msg"]


# ---------------------------------------------------------------------------
# absent flows
# ---------------------------------------------------------------------------


def test_absent_missing_user_is_idempotent(monkeypatch):
    fake = FakeDlcClient(users=[])
    _make_module(monkeypatch, fake)
    _base(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["user"] is None
    assert [c for c, unused in fake.calls] == ["DescribeUsers"]


def test_absent_owner_cannot_delete(monkeypatch):
    fake = FakeDlcClient(users=[_user(IsOwner=True)])
    _make_module(monkeypatch, fake)
    _base(state="absent")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "owner account cannot be deleted" in exc.value.args[0]["msg"]


def test_absent_requires_allow_delete(monkeypatch):
    fake = FakeDlcClient(users=[_user()])
    _make_module(monkeypatch, fake)
    _base(state="absent")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "allow_delete=true" in exc.value.args[0]["msg"]


def test_absent_bound_user_requires_allow_delete_bound(monkeypatch):
    fake = FakeDlcClient(users=[_user(PolicySet=[{"PolicyName": "DLCFullAccess"}])])
    _make_module(monkeypatch, fake)
    _base(state="absent", allow_delete=True)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "allow_delete_bound=true" in exc.value.args[0]["msg"]


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeDlcClient(users=[_user()])
    _make_module(monkeypatch, fake)
    _base(_ansible_check_mode=True, state="absent", allow_delete=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert len(fake.users) == 1
    assert "DeleteUser" not in [c for c, unused in fake.calls]


def test_absent_deletes_user(monkeypatch):
    fake = FakeDlcClient(users=[_user()])
    _make_module(monkeypatch, fake)
    _base(state="absent", allow_delete=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert fake.users == []
    ops = [c for c, unused in fake.calls]
    assert "DeleteUser" in ops


# ---------------------------------------------------------------------------
# creation flows
# ---------------------------------------------------------------------------


def test_create_user(monkeypatch):
    fake = FakeDlcClient(users=[])
    _make_module(monkeypatch, fake)
    _base(state="present", description="Analytics engineering account", user_type="COMMON", alias="analytics-engineer", wait=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["user"]["UserId"] == "100012345678"
    assert result["user"]["UserDescription"] == "Analytics engineering account"
    assert len(fake.users) == 1
    ops = [c for c, unused in fake.calls]
    assert "CreateUser" in ops


def test_create_check_mode_is_dry_run(monkeypatch):
    fake = FakeDlcClient(users=[])
    _make_module(monkeypatch, fake)
    _base(_ansible_check_mode=True, state="present", description="brand new", alias="fresh-alias")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert fake.users == []
    assert "CreateUser" not in [c for c, unused in fake.calls]
    assert result["user"]["UserAlias"] == "fresh-alias"


# ---------------------------------------------------------------------------
# existing-user flows
# ---------------------------------------------------------------------------


def test_existing_user_no_drift_is_idempotent(monkeypatch):
    fake = FakeDlcClient(users=[_user()])
    _make_module(monkeypatch, fake)
    _base(state="present", description="Analytics engineering account", user_type="COMMON")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["user"]["UserAlias"] == "analytics-engineer"


def test_description_drift_updates_user(monkeypatch):
    fake = FakeDlcClient(users=[_user()])
    _make_module(monkeypatch, fake)
    _base(state="present", description="Updated description", wait=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["user"]["UserDescription"] == "Updated description"
    ops = [c for c, unused in fake.calls]
    assert "ModifyUser" in ops


def test_user_type_drift_updates_type(monkeypatch):
    fake = FakeDlcClient(users=[_user()])
    _make_module(monkeypatch, fake)
    _base(state="present", user_type="ADMIN", wait=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["user"]["UserType"] == "ADMIN"
    ops = [c for c, unused in fake.calls]
    assert "ModifyUserType" in ops


def test_alias_immutable_drift_fails(monkeypatch):
    fake = FakeDlcClient(users=[_user()])
    _make_module(monkeypatch, fake)
    _base(state="present", alias="renamed-alias")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "immutable" in payload["msg"]
    assert "UserAlias" in payload["immutable_drift"]


def test_update_check_mode_is_dry_run(monkeypatch):
    fake = FakeDlcClient(users=[_user()])
    _make_module(monkeypatch, fake)
    _base(_ansible_check_mode=True, state="present", description="preview text")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert fake.users[0]["UserDescription"] == "Analytics engineering account"
    assert "ModifyUser" not in [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# failure paths
# ---------------------------------------------------------------------------


def test_multiple_matches_fail(monkeypatch):
    class DupClient(object):
        def DescribeUsers(self, request):
            return SimpleNamespace(
                UserSet=[FakeResource(_user()), FakeResource(_user(WorkGroupSet=[{"WorkGroupId": 1}]))],
                TotalCount=2,
            )

    fake = DupClient()
    _make_module(monkeypatch, fake)
    _base(state="present")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "Multiple DLC users matched" in exc.value.args[0]["msg"]


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeUsers(self, request):
            raise Boom("connection dropped")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    _base(state="present")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]


# ---------------------------------------------------------------------------
# legacy helper regression tests (folded from test_dlc_user.py)
# ---------------------------------------------------------------------------


class LegacyObject(object):
    def from_json_string(self, value):
        import json

        for key, item in json.loads(value).items():
            setattr(self, key, item)


class LegacyModels(object):
    DescribeUsersRequest = LegacyObject
    CreateUserRequest = LegacyObject
    ModifyUserRequest = LegacyObject
    ModifyUserTypeRequest = LegacyObject
    DeleteUserRequest = LegacyObject


def legacy_params():
    return {
        "user_id": "10001",
        "description": "analytics",
        "user_type": "COMMON",
        "alias": "analyst",
        "principal_type": "UserAccount",
        "account_source": "TencentAccount",
        "initial_policies": None,
        "initial_work_group_ids": [42],
    }


def test_describe_uses_exact_identity_and_pagination():
    request = mod.describe_request(LegacyModels, legacy_params(), 100)
    assert request.UserId == "10001" and request.Offset == 100 and request.Limit == 100
    assert request.AccountType == "TencentAccount"


def test_create_maps_initial_access_contract():
    request = mod.create_request(LegacyModels, legacy_params())
    assert request.UserId == "10001" and request.UserType == "COMMON" and request.WorkGroupIds == [42]
    assert request.AccountType == "UserAccount"


def test_mutation_requests_keep_account_identity():
    p = legacy_params()
    assert mod.modify_request(LegacyModels, p).UserDescription == "analytics"
    assert mod.type_request(LegacyModels, p).UserType == "COMMON"
    assert mod.delete_request(LegacyModels, p).UserIds == ["10001"]
