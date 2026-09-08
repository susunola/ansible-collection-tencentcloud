"""Unit tests for the postgresql_account write module (run_module flows).

Drives ``run_module()`` against an in-memory fake PostgreSQL client whose
create/remark/password/delete operations mutate an account store so the
post-write ``find_account`` waiter converges on the first poll.

Scenario matrix:

* absent on a missing account (idempotent no-op)
* absent with a matching account (check-mode dry run, real delete)
* creation when missing (password required guard, happy path, check mode)
* no-op when the account is up to date
* remark drift and explicit password rotation
* ``rotate_password`` validation guard
* the blanket SDK failure path
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import postgresql_account as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

INSTANCE = "postgres-8b0a1c2d"

ACCOUNT = {
    "UserName": "app_user",
    "Remark": "Application account",
    "UserType": "normal",
    "OpenCam": False,
}


def _account(**overrides):
    item = copy.deepcopy(ACCOUNT)
    item.update(overrides)
    return item


def _base(**overrides):
    params = {"instance_id": INSTANCE, "username": "app_user"}
    params.update(overrides)
    return module_args(**params)


class FakePostgresClient(object):
    """In-memory PostgreSQL client mutating an account store."""

    def __init__(self, accounts=None):
        self.accounts = [copy.deepcopy(t) for t in (accounts or [])]
        self.calls = []

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def _find(self, username):
        for item in self.accounts:
            if item.get("UserName") == username:
                return item
        return None

    def DescribeAccounts(self, request):
        self._record("DescribeAccounts", request)
        return SimpleNamespace(
            Details=[FakeResource(t) for t in self.accounts],
            TotalCount=len(self.accounts),
        )

    def CreateAccount(self, request):
        self._record("CreateAccount", request)
        self.accounts.append({
            "UserName": getattr(request, "UserName", None),
            "Remark": getattr(request, "Remark", None),
            "UserType": getattr(request, "Type", None),
            "OpenCam": getattr(request, "OpenCam", None),
        })
        return SimpleNamespace(RequestId="req-fake")

    def ModifyAccountRemark(self, request):
        self._record("ModifyAccountRemark", request)
        item = self._find(getattr(request, "UserName", None))
        if item is not None:
            item["Remark"] = getattr(request, "Remark", None)
        return SimpleNamespace(RequestId="req-fake")

    def ResetAccountPassword(self, request):
        self._record("ResetAccountPassword", request)
        return SimpleNamespace(RequestId="req-fake")

    def DeleteAccount(self, request):
        self._record("DeleteAccount", request)
        username = getattr(request, "UserName", None)
        self.accounts = [t for t in self.accounts if t.get("UserName") != username]
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake, models=None):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load_postgres", lambda: (models or FakeModels(), SimpleNamespace(PostgresClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


# ---------------------------------------------------------------------------
# absent flows
# ---------------------------------------------------------------------------


def test_absent_missing_account_is_idempotent(monkeypatch):
    fake = FakePostgresClient(accounts=[])
    _make_module(monkeypatch, fake)
    _base(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["account"] is None
    assert result["msg"] == "PostgreSQL account is absent"
    assert [c for c, unused in fake.calls] == ["DescribeAccounts"]


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakePostgresClient(accounts=[_account()])
    _make_module(monkeypatch, fake)
    _base(_ansible_check_mode=True, state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["msg"] == "Would delete PostgreSQL account"
    assert len(fake.accounts) == 1
    assert "DeleteAccount" not in [c for c, unused in fake.calls]


def test_absent_deletes_account(monkeypatch):
    fake = FakePostgresClient(accounts=[_account()])
    _make_module(monkeypatch, fake)
    _base(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["account"] is None
    assert fake.accounts == []
    ops = [c for c, unused in fake.calls]
    assert "DeleteAccount" in ops


# ---------------------------------------------------------------------------
# creation flows
# ---------------------------------------------------------------------------


def test_create_requires_password(monkeypatch):
    fake = FakePostgresClient(accounts=[])
    _make_module(monkeypatch, fake)
    _base(state="present")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "password is required when creating" in exc.value.args[0]["msg"]


def test_create_account(monkeypatch):
    fake = FakePostgresClient(accounts=[])
    _make_module(monkeypatch, fake)
    _base(state="present", password="s3cret", remark="Application account")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["account"]["UserName"] == "app_user"
    assert result["account"]["Remark"] == "Application account"
    assert len(fake.accounts) == 1
    ops = [c for c, unused in fake.calls]
    assert ops[0] == "DescribeAccounts"
    assert "CreateAccount" in ops


def test_create_check_mode_is_dry_run(monkeypatch):
    fake = FakePostgresClient(accounts=[])
    _make_module(monkeypatch, fake)
    _base(_ansible_check_mode=True, state="present", password="s3cret", remark="Application account")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["msg"] == "Would create PostgreSQL account"
    assert result["account"] is None
    assert fake.accounts == []
    assert "CreateAccount" not in [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# existing-account flows
# ---------------------------------------------------------------------------


def test_existing_account_no_drift_is_idempotent(monkeypatch):
    fake = FakePostgresClient(accounts=[_account()])
    _make_module(monkeypatch, fake)
    _base(state="present", remark="Application account")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["account"]["UserName"] == "app_user"
    assert result["msg"] == "PostgreSQL account is up to date"


def test_remark_drift_updates(monkeypatch):
    fake = FakePostgresClient(accounts=[_account()])
    _make_module(monkeypatch, fake)
    _base(state="present", remark="New remark")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["account"]["Remark"] == "New remark"
    assert result["msg"] == "PostgreSQL account updated"
    ops = [c for c, unused in fake.calls]
    assert "ModifyAccountRemark" in ops
    assert "ResetAccountPassword" not in ops


def test_password_rotation(monkeypatch):
    fake = FakePostgresClient(accounts=[_account()])
    _make_module(monkeypatch, fake)
    _base(state="present", password="new-s3cret", rotate_password=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    ops = [c for c, unused in fake.calls]
    assert "ResetAccountPassword" in ops


def test_rotate_password_requires_password(monkeypatch):
    fake = FakePostgresClient(accounts=[_account()])
    _make_module(monkeypatch, fake)
    _base(state="present", rotate_password=True)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "password is required when rotate_password=true" in exc.value.args[0]["msg"]


def test_rotate_and_remark_drift_both_apply(monkeypatch):
    fake = FakePostgresClient(accounts=[_account()])
    _make_module(monkeypatch, fake)
    _base(state="present", password="new-s3cret", rotate_password=True, remark="Changed remark")
    result = run(mod.run_module)
    assert result["changed"] is True
    ops = [c for c, unused in fake.calls]
    assert "ModifyAccountRemark" in ops
    assert "ResetAccountPassword" in ops


# ---------------------------------------------------------------------------
# failure paths
# ---------------------------------------------------------------------------


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeAccounts(self, request):
            raise Boom("connection dropped")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    _base(state="present")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]
