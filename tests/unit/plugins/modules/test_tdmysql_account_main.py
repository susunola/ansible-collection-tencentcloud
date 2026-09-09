"""Unit tests for the tdmysql_account write module (run_module flows).

Drives ``run_module()`` end to end against an in-memory fake TDSQL MySQL
client whose write operations mutate the user store so the post-write
``get`` refetch and the ``DescribeFlow`` waiter converge immediately.

Scenario matrix:

* absent on a missing account (idempotent no-op)
* absent with a matching account (requires ``allow_delete``, check-mode dry
  run, and the real delete path with and without ``wait``)
* creation when missing (password guard, check mode, privileges applied
  conditionally)
* no-op when nothing drifts
* global-privilege drift updates (with and without check mode)
* the create-only description immutable drift guard
* explicit password rotation (guard, real reset, combined privilege change)
* multiple-match ambiguity and the password/encrypted_password exclusivity
* the blanket ``sdk_error_payload`` failure path
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import tdmysql_account as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

INSTANCE_ID = "tdsql3-abcd1234"

ACCOUNT = {
    "InstanceId": INSTANCE_ID,
    "UserName": "reporting",
    "Host": "%",
    "Description": "Read-only reporting account",
    "GlobalPrivileges": ["SELECT"],
}


def _account(**overrides):
    item = dict(ACCOUNT)
    item.update(overrides)
    return item


def _base(**overrides):
    # ``state``/``rotate_password`` carry no choices for the identity keys;
    # host defaults to "%" and is only passed when a scenario needs a value.
    params = {
        "instance_id": INSTANCE_ID,
        "username": "reporting",
    }
    params.update(overrides)
    return module_args(**params)


class FakeTdmysqlClient(object):
    """In-memory TDSQL MySQL client mutating a small user store."""

    def __init__(self, users=None):
        self.users = [dict(t) for t in (users or [])]
        self.calls = []

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def _find(self, username, host):
        for item in self.users:
            if item.get("UserName") == username and item.get("Host") == host:
                return item
        return None

    def DescribeUsers(self, request):
        self._record("DescribeUsers", request)
        rows = [dict(t) for t in self.users if t.get("InstanceId") == getattr(request, "InstanceId", None)]
        return SimpleNamespace(Users=[FakeResource(t) for t in rows], RequestId="req-users")

    def DescribeUserPrivileges(self, request):
        self._record("DescribeUserPrivileges", request)
        item = self._find(getattr(request, "UserName", None), getattr(request, "Host", None))
        return SimpleNamespace(Privileges=list(item.get("GlobalPrivileges") or []) if item else [], RequestId="req-priv")

    def CreateUsers(self, request):
        self._record("CreateUsers", request)
        first = request.Users[0]
        self.users.append(
            {
                "InstanceId": getattr(request, "InstanceId", None),
                "UserName": first.UserName,
                "Host": first.Host,
                "Description": getattr(request, "Description", None),
            }
        )
        return SimpleNamespace(FlowId=101, RequestId="req-create")

    def DeleteUsers(self, request):
        self._record("DeleteUsers", request)
        first = request.Users[0]
        self.users = [t for t in self.users if not (t.get("UserName") == first.UserName and t.get("Host") == first.Host)]
        return SimpleNamespace(FlowId=102, RequestId="req-delete")

    def ModifyUserPrivileges(self, request):
        self._record("ModifyUserPrivileges", request)
        first = request.Users[0]
        item = self._find(first.UserName, first.Host)
        if item is not None:
            item["GlobalPrivileges"] = list(getattr(request, "GlobalPrivileges", None) or [])
        return SimpleNamespace(FlowId=103, RequestId="req-modify-priv")

    def ResetUsersPassword(self, request):
        self._record("ResetUsersPassword", request)
        return SimpleNamespace(FlowId=104, RequestId="req-reset")

    def DescribeFlow(self, request):
        self._record("DescribeFlow", request)
        return SimpleNamespace(Status="success", RequestId="req-flow")


def _make_module(monkeypatch, fake, models=None):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (models or FakeModels(), SimpleNamespace(TdmysqlClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)


# ---------------------------------------------------------------------------
# absent flows
# ---------------------------------------------------------------------------


def test_absent_missing_account_is_idempotent(monkeypatch):
    fake = FakeTdmysqlClient()
    _make_module(monkeypatch, fake)
    _base(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["account"] is None
    assert [c for c, unused in fake.calls] == ["DescribeUsers"]


def test_absent_requires_allow_delete(monkeypatch):
    fake = FakeTdmysqlClient(users=[_account()])
    _make_module(monkeypatch, fake)
    _base(state="absent")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "allow_delete=true is required to delete" in payload["msg"]
    assert payload["account"]["UserName"] == "reporting"


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeTdmysqlClient(users=[_account()])
    _make_module(monkeypatch, fake)
    _base(_ansible_check_mode=True, state="absent", allow_delete=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["account"] is None
    assert len(fake.users) == 1
    assert "DeleteUsers" not in [c for c, unused in fake.calls]


def test_absent_deletes_account_and_waits(monkeypatch):
    fake = FakeTdmysqlClient(users=[_account()])
    _make_module(monkeypatch, fake)
    _base(state="absent", allow_delete=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["account"] is None
    assert fake.users == []
    ops = [c for c, unused in fake.calls]
    assert "DeleteUsers" in ops
    assert "DescribeFlow" in ops


def test_absent_delete_without_wait_skips_flow(monkeypatch):
    fake = FakeTdmysqlClient(users=[_account()])
    _make_module(monkeypatch, fake)
    _base(state="absent", allow_delete=True, wait=False)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert fake.users == []
    ops = [c for c, unused in fake.calls]
    assert "DeleteUsers" in ops
    assert "DescribeFlow" not in ops


# ---------------------------------------------------------------------------
# creation flows
# ---------------------------------------------------------------------------


def test_create_requires_password(monkeypatch):
    fake = FakeTdmysqlClient()
    _make_module(monkeypatch, fake)
    _base(state="present")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "password or encrypted_password is required to create an account" in exc.value.args[0]["msg"]


def test_create_account_with_privileges(monkeypatch):
    fake = FakeTdmysqlClient()
    _make_module(monkeypatch, fake)
    _base(
        state="present",
        password="s3cret!",
        description="Reporting account",
        global_privileges=["SELECT", "INSERT"],
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["account"]["UserName"] == "reporting"
    assert result["account"]["GlobalPrivileges"] == ["INSERT", "SELECT"]
    assert len(fake.users) == 1
    ops = [c for c, unused in fake.calls]
    assert ops[0] == "DescribeUsers"
    assert "CreateUsers" in ops
    assert "ModifyUserPrivileges" in ops
    assert "DescribeFlow" in ops


def test_create_account_without_privileges_skips_modify(monkeypatch):
    fake = FakeTdmysqlClient()
    _make_module(monkeypatch, fake)
    _base(state="present", password="s3cret!", description="Reporting account")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["account"]["GlobalPrivileges"] == []
    ops = [c for c, unused in fake.calls]
    assert "CreateUsers" in ops
    assert "ModifyUserPrivileges" not in ops


def test_create_check_mode_is_dry_run(monkeypatch):
    fake = FakeTdmysqlClient()
    _make_module(monkeypatch, fake)
    _base(
        _ansible_check_mode=True,
        state="present",
        password="s3cret!",
        description="Reporting account",
        global_privileges=["SELECT", "INSERT"],
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["account"] == {
        "UserName": "reporting",
        "Host": "%",
        "Description": "Reporting account",
        "GlobalPrivileges": ["INSERT", "SELECT"],
    }
    assert fake.users == []
    assert "CreateUsers" not in [c for c, unused in fake.calls]


def test_create_no_wait_skips_flow(monkeypatch):
    fake = FakeTdmysqlClient()
    _make_module(monkeypatch, fake)
    _base(state="present", password="s3cret!", wait=False)
    result = run(mod.run_module)
    assert result["changed"] is True
    ops = [c for c, unused in fake.calls]
    assert "CreateUsers" in ops
    assert "DescribeFlow" not in ops


# ---------------------------------------------------------------------------
# existing-account flows
# ---------------------------------------------------------------------------


def test_existing_account_no_drift_is_idempotent(monkeypatch):
    fake = FakeTdmysqlClient(users=[_account()])
    _make_module(monkeypatch, fake)
    _base(state="present", description="Read-only reporting account", global_privileges=["SELECT"])
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["account"]["UserName"] == "reporting"
    ops = [c for c, unused in fake.calls]
    assert "ModifyUserPrivileges" not in ops
    assert "ResetUsersPassword" not in ops


def test_update_global_privileges(monkeypatch):
    fake = FakeTdmysqlClient(users=[_account()])
    _make_module(monkeypatch, fake)
    _base(state="present", description="Read-only reporting account", global_privileges=["SELECT", "UPDATE"])
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["account"]["GlobalPrivileges"] == ["SELECT", "UPDATE"]
    ops = [c for c, unused in fake.calls]
    assert "ModifyUserPrivileges" in ops
    assert "ResetUsersPassword" not in ops


def test_update_check_mode_is_dry_run(monkeypatch):
    fake = FakeTdmysqlClient(users=[_account()])
    _make_module(monkeypatch, fake)
    _base(
        _ansible_check_mode=True,
        state="present",
        description="Read-only reporting account",
        global_privileges=["SELECT", "UPDATE"],
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["account"]["GlobalPrivileges"] == ["SELECT", "UPDATE"]
    assert fake.users[0]["GlobalPrivileges"] == ["SELECT"]
    assert "ModifyUserPrivileges" not in [c for c, unused in fake.calls]


def test_description_drift_is_immutable(monkeypatch):
    fake = FakeTdmysqlClient(users=[_account()])
    _make_module(monkeypatch, fake)
    _base(state="present", description="changed description", global_privileges=["SELECT"])
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "create-only" in payload["msg"]
    assert "Description" in payload["immutable_drift"]


def test_rotate_password_requires_credentials(monkeypatch):
    fake = FakeTdmysqlClient()
    _make_module(monkeypatch, fake)
    _base(state="present", rotate_password=True)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "password or encrypted_password is required when rotate_password=true" in exc.value.args[0]["msg"]


def test_rotate_password_resets_and_waits(monkeypatch):
    fake = FakeTdmysqlClient(users=[_account()])
    _make_module(monkeypatch, fake)
    _base(
        state="present",
        description="Read-only reporting account",
        global_privileges=["SELECT"],
        rotate_password=True,
        password="new-s3cret!",
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    ops = [c for c, unused in fake.calls]
    assert "ResetUsersPassword" in ops
    assert "DescribeFlow" in ops
    assert "ModifyUserPrivileges" not in ops


def test_rotate_password_combines_with_privilege_change(monkeypatch):
    fake = FakeTdmysqlClient(users=[_account()])
    _make_module(monkeypatch, fake)
    _base(
        state="present",
        description="Read-only reporting account",
        global_privileges=["SELECT", "INSERT"],
        rotate_password=True,
        password="new-s3cret!",
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    ops = [c for c, unused in fake.calls]
    assert "ModifyUserPrivileges" in ops
    assert "ResetUsersPassword" in ops


# ---------------------------------------------------------------------------
# guards / failure paths
# ---------------------------------------------------------------------------


def test_password_and_encrypted_are_mutually_exclusive(monkeypatch):
    fake = FakeTdmysqlClient()
    _make_module(monkeypatch, fake)
    _base(state="present", password="plain", encrypted_password="cipher")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "mutually exclusive" in exc.value.args[0]["msg"]


def test_multiple_matching_accounts_fail(monkeypatch):
    fake = FakeTdmysqlClient(users=[_account(), _account(Description="duplicate")])
    _make_module(monkeypatch, fake)
    _base(state="present")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "Multiple TDSQL MySQL accounts matched" in exc.value.args[0]["msg"]


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeUsers(self, request):
            raise Boom("connection dropped")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    _base(state="present", password="s3cret!")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]


# ---------------------------------------------------------------------------
# legacy helper regression tests (folded from test_tdmysql_account.py)
# ---------------------------------------------------------------------------


class LegacyObject(object):
    pass


class LegacyModels(object):
    CreateUsersRequest = DeleteUsersRequest = ModifyUserPrivilegesRequest = ResetUsersPasswordRequest = ResetUserPasswordInfo = DescribeUsersRequest = (
        DescribeUserPrivilegesRequest
    ) = User = LegacyObject


LEGACY_PARAMS = {
    "instance_id": "db1",
    "username": "report",
    "host": "10.%",
    "password": "secret",
    "encrypted_password": None,
    "description": "reporting",
    "global_privileges": ["SELECT"],
}


def test_account_requests_keep_composite_identity():
    create = mod.create_request(LegacyModels, LEGACY_PARAMS)
    delete = mod.delete_request(LegacyModels, LEGACY_PARAMS)
    reset = mod.reset_request(LegacyModels, LEGACY_PARAMS)
    assert (create.Users[0].UserName, create.Users[0].Host) == ("report", "10.%")
    assert delete.Users[0].Host == "10.%" and reset.Users[0].Password == "secret"


def test_privilege_requests_use_global_scope_and_sorted_set():
    describe, modify = mod.privileges_request(LegacyModels, LEGACY_PARAMS), mod.privileges_modify_request(LegacyModels, LEGACY_PARAMS)
    assert (describe.DbName, describe.ObjectType, describe.Object, describe.ColName) == ("*", "*", "*", "*")
    assert modify.GlobalPrivileges == ["SELECT"]


class LegacyItem(object):
    def __init__(self, value):
        self.value = value

    def _serialize(self, allow_none=True):
        return self.value


class LegacyResponse(object):
    def __init__(self, users=None, privileges=None, request_id="r1"):
        self.Users, self.Privileges, self.RequestId = users, privileges, request_id


class LegacyClient(object):
    def DescribeUsers(self, request):
        return LegacyResponse([LegacyItem({"UserName": "report", "Host": "10.%"}), LegacyItem({"UserName": "report", "Host": "%"})])

    def DescribeUserPrivileges(self, request):
        return LegacyResponse(privileges=["UPDATE", "SELECT"], request_id="r2")


class LegacyModule(object):
    def sdk_call(self, fn, request):
        return fn(request)

    def fail_json(self, **kwargs):
        raise ValueError(kwargs["msg"])


def test_account_get_matches_username_and_host_and_enriches_privileges():
    value = mod.get(LegacyModule(), LegacyClient(), LegacyModels, dict(LEGACY_PARAMS, include_global_privileges=True))
    assert value["Host"] == "10.%"
    assert value["GlobalPrivileges"] == ["SELECT", "UPDATE"]
