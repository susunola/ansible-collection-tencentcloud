"""Unit tests for the dcdb_account write module (run_module flows).

The module creates and deletes DCDB accounts, updates descriptions and
explicitly rotates passwords; creation-time routing properties are immutable
after creation. The fake DCDB client mutates an account store so post-write
``find`` refetches converge immediately.

Scenario matrix:

* argument validation (missing required args, rotate without password,
  create without password)
* no-op when every managed property already matches
* creation flows (real and check-mode dry run)
* description drift and explicit password rotation
* immutable creation-time property drift fails
* deletion flows (present, absent no-op, check-mode dry run)
* the blanket SDK failure path
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import dcdb_account as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

INSTANCE_ID = "tdsqlshard-xxxxxxxx"

ACCOUNT = {
    "UserName": "app",
    "Host": "%",
    "Description": "application",
    "ReadOnly": 0,
    "DelayThresh": 10,
    "SlaveConst": 0,
    "MaxUserConnections": 0,
}


def _args(**overrides):
    params = {
        "instance_id": INSTANCE_ID,
        "username": "app",
        "host": "%",
        "password": "S3cret!",
        "description": "application",
        "read_only": 0,
        "delay_threshold": 10,
        "sticky_replica": False,
        "max_user_connections": 0,
    }
    params.update(overrides)
    return module_args(**params)


class FakeDcdbClient(object):
    """In-memory DCDB client mutating an account store."""

    def __init__(self, accounts=None):
        self.accounts = [copy.deepcopy(a) for a in (accounts or [])]
        self.calls = []

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def DescribeAccounts(self, request):
        self._record("DescribeAccounts", request)
        return SimpleNamespace(Users=[FakeResource(a) for a in self.accounts])

    def CreateAccount(self, request):
        self._record("CreateAccount", request)
        self.accounts.append(
            {
                "UserName": request.UserName,
                "Host": request.Host,
                "Description": getattr(request, "Description", ""),
                "ReadOnly": getattr(request, "ReadOnly", 0),
                "DelayThresh": getattr(request, "DelayThresh", 10),
                "SlaveConst": getattr(request, "SlaveConst", 0),
                "MaxUserConnections": getattr(request, "MaxUserConnections", 0),
            }
        )
        return SimpleNamespace(RequestId="req-fake")

    def ModifyAccountDescription(self, request):
        self._record("ModifyAccountDescription", request)
        for account in self.accounts:
            if account["UserName"] == request.UserName and (account.get("Host") or "%") == request.Host:
                account["Description"] = request.Description
        return SimpleNamespace(RequestId="req-fake")

    def ResetAccountPassword(self, request):
        self._record("ResetAccountPassword", request)
        return SimpleNamespace(RequestId="req-fake")

    def DeleteAccount(self, request):
        self._record("DeleteAccount", request)
        self.accounts = [
            a for a in self.accounts
            if not (a["UserName"] == request.UserName and (a.get("Host") or "%") == request.Host)
        ]
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake, models=None):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (models or FakeModels(), SimpleNamespace(DcdbClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


def test_missing_required_args_fails(monkeypatch):
    fake = FakeDcdbClient()
    _make_module(monkeypatch, fake)
    module_args()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "missing required arguments" in exc.value.args[0]["msg"]
    assert fake.calls == []


def test_rotate_password_without_password_fails(monkeypatch):
    fake = FakeDcdbClient()
    _make_module(monkeypatch, fake)
    _args(rotate_password=True, password=None)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "password is required when rotate_password=true" in exc.value.args[0]["msg"]
    assert fake.calls == []


def test_idempotent_when_account_matches(monkeypatch):
    fake = FakeDcdbClient(accounts=[ACCOUNT])
    _make_module(monkeypatch, fake)
    _args()
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["account"]["UserName"] == "app"
    assert [c for c, unused in fake.calls] == ["DescribeAccounts"]


def test_create_account(monkeypatch):
    fake = FakeDcdbClient()
    _make_module(monkeypatch, fake)
    _args(password="S3cret!")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["account"]["Description"] == "application"
    assert len(fake.accounts) == 1
    create_call = next((c, r) for c, r in fake.calls if c == "CreateAccount")
    assert create_call[1].UserName == "app"
    assert create_call[1].Host == "%"
    assert create_call[1].Password == "S3cret!"
    assert create_call[1].ReadOnly == 0


def test_create_without_password_fails(monkeypatch):
    fake = FakeDcdbClient()
    _make_module(monkeypatch, fake)
    _args(password=None)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "password is required when creating" in exc.value.args[0]["msg"]
    assert fake.accounts == []


def test_create_check_mode_is_dry_run(monkeypatch):
    fake = FakeDcdbClient()
    _make_module(monkeypatch, fake)
    _args(_ansible_check_mode=True, password="S3cret!")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert "CreateAccount" not in [c for c, unused in fake.calls]
    assert fake.accounts == []


def test_description_drift_updates_account(monkeypatch):
    stored = dict(ACCOUNT)
    stored["Description"] = "old text"
    fake = FakeDcdbClient(accounts=[stored])
    _make_module(monkeypatch, fake)
    _args(description="application")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["account"]["Description"] == "application"
    update_call = next((c, r) for c, r in fake.calls if c == "ModifyAccountDescription")
    assert update_call[1].Description == "application"
    assert "ResetAccountPassword" not in [c for c, unused in fake.calls]


def test_rotate_password_on_existing_account(monkeypatch):
    fake = FakeDcdbClient(accounts=[ACCOUNT])
    _make_module(monkeypatch, fake)
    _args(rotate_password=True, password="newpass")
    result = run(mod.run_module)
    assert result["changed"] is True
    rotate_call = next((c, r) for c, r in fake.calls if c == "ResetAccountPassword")
    assert rotate_call[1].Password == "newpass"


def test_immutable_read_only_drift_fails(monkeypatch):
    stored = dict(ACCOUNT)
    stored["ReadOnly"] = 1
    fake = FakeDcdbClient(accounts=[stored])
    _make_module(monkeypatch, fake)
    _args(read_only=0)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "Immutable fields cannot be changed" in payload["msg"]
    assert "ReadOnly" in payload["immutable_changes"]


def test_delete_account(monkeypatch):
    fake = FakeDcdbClient(accounts=[ACCOUNT])
    _make_module(monkeypatch, fake)
    _args(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["account"] is None
    assert fake.accounts == []
    delete_call = next((c, r) for c, r in fake.calls if c == "DeleteAccount")
    assert delete_call[1].UserName == "app"


def test_delete_missing_account_is_idempotent(monkeypatch):
    fake = FakeDcdbClient()
    _make_module(monkeypatch, fake)
    _args(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["account"] is None
    assert "DeleteAccount" not in [c for c, unused in fake.calls]


def test_delete_check_mode_is_dry_run(monkeypatch):
    fake = FakeDcdbClient(accounts=[ACCOUNT])
    _make_module(monkeypatch, fake)
    _args(_ansible_check_mode=True, state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert len(fake.accounts) == 1
    assert "DeleteAccount" not in [c for c, unused in fake.calls]


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeAccounts(self, request):
            raise Boom("connection dropped")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    _args()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]


# ---------------------------------------------------------------------------
# legacy helper regression tests (folded from test_dcdb_account.py)
# ---------------------------------------------------------------------------


def legacy_params():
    return {
        "username": "app",
        "host": "%",
        "description": "application",
        "read_only": 0,
        "delay_threshold": 10,
        "sticky_replica": False,
        "max_user_connections": 0,
    }


def test_desired_maps_account_properties():
    assert mod.desired(legacy_params()) == {
        "UserName": "app",
        "Host": "%",
        "Description": "application",
        "ReadOnly": 0,
        "DelayThresh": 10,
        "SlaveConst": 0,
        "MaxUserConnections": 0,
    }


def test_comparable_ignores_server_only_fields():
    value = mod.desired(legacy_params())
    value["CreateTime"] = "now"
    assert mod.comparable(value) == mod.desired(legacy_params())
