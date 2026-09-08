"""Unit tests for the cynosdb_account write module (run_module flows).

Complements ``test_cynosdb_account.py`` (request-builder level) by driving
``run_module()`` end to end against an in-memory fake CynosDB client whose
write operations mutate the account store so post-write ``find_account``
refetches converge immediately.

Scenario matrix:

* absent on a missing account (idempotent no-op)
* absent with a matching account (check-mode dry run and real delete)
* creation when missing (with/without the required password, check mode)
* no-op when nothing drifts
* description drift updates
* explicit password rotation (and the rotate-password guard)
* the blanket ``Tencent Cloud API request failed`` failure path
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import cynosdb_account as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

ACCOUNT = {
    "AccountName": "app_user",
    "Host": "%",
    "Description": "application account",
    "MaxUserConnections": 100,
    "PasswordRotation": 0,
}


def _account(**overrides):
    item = copy.deepcopy(ACCOUNT)
    item.update(overrides)
    return item


def _base(**overrides):
    # cluster_id / account_name / host form the identity; optional keys
    # (password, description, max_user_connections, password_rotation, ...)
    # are only added when a scenario needs them.
    params = {"cluster_id": "cynosdbmysql-abc12345", "account_name": "app_user"}
    params.update(overrides)
    return module_args(**params)


class FakeCynosdbClient(object):
    """In-memory CynosDB client mutating a small account store."""

    def __init__(self, accounts=None):
        self.accounts = [copy.deepcopy(t) for t in (accounts or [])]
        self.calls = []

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def _find(self, cluster_id, account_name, host):
        for item in self.accounts:
            if (
                item.get("AccountName") == account_name
                and item.get("Host") == host
                and item.get("ClusterId", "cynosdbmysql-abc12345") == cluster_id
            ):
                return item
        return None

    def DescribeAccounts(self, request):
        self._record("DescribeAccounts", request)
        names = list(getattr(request, "AccountNames", None) or [])
        hosts = list(getattr(request, "Hosts", None) or [])
        matches = [
            t for t in self.accounts
            if (not names or t.get("AccountName") in names)
            and (not hosts or t.get("Host") in hosts)
            and t.get("ClusterId", "cynosdbmysql-abc12345") == request.ClusterId
        ]
        return SimpleNamespace(
            AccountSet=[FakeResource(t) for t in matches],
            TotalCount=len(matches),
        )

    def CreateAccounts(self, request):
        self._record("CreateAccounts", request)
        for account in list(getattr(request, "Accounts", None) or []):
            item = {
                "ClusterId": request.ClusterId,
                "AccountName": getattr(account, "AccountName", None),
                "Host": getattr(account, "Host", None),
                "Description": getattr(account, "Description", None) or "",
            }
            for attr in ("MaxUserConnections", "PasswordRotation"):
                value = getattr(account, attr, None)
                if value is not None:
                    item[attr] = value
            self.accounts.append(item)
        return SimpleNamespace(RequestId="req-fake")

    def DeleteAccounts(self, request):
        self._record("DeleteAccounts", request)
        cluster_id = request.ClusterId
        removed = []
        for account in list(getattr(request, "Accounts", None) or []):
            item = self._find(cluster_id, getattr(account, "AccountName", None), getattr(account, "Host", None))
            if item is not None:
                removed.append(item)
        for item in removed:
            self.accounts.remove(item)
        return SimpleNamespace(RequestId="req-fake")

    def ModifyAccountDescription(self, request):
        self._record("ModifyAccountDescription", request)
        item = self._find(request.ClusterId, request.AccountName, request.Host)
        if item is not None:
            item["Description"] = request.Description
        return SimpleNamespace(RequestId="req-fake")

    def ResetAccountPassword(self, request):
        self._record("ResetAccountPassword", request)
        item = self._find(request.ClusterId, request.AccountName, request.Host)
        if item is not None:
            item["AccountPassword"] = request.AccountPassword
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake, models=None):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load_cynosdb", lambda: (models or FakeModels(), SimpleNamespace(CynosdbClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


# ---------------------------------------------------------------------------
# absent flows
# ---------------------------------------------------------------------------


def test_absent_missing_account_is_idempotent(monkeypatch):
    fake = FakeCynosdbClient(accounts=[])
    _make_module(monkeypatch, fake)
    _base(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["account"] is None
    assert [c for c, unused in fake.calls] == ["DescribeAccounts"]


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeCynosdbClient(accounts=[_account()])
    _make_module(monkeypatch, fake)
    _base(_ansible_check_mode=True, state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["account"]["AccountName"] == "app_user"
    assert "DeleteAccounts" not in [c for c, unused in fake.calls]


def test_absent_deletes_account(monkeypatch):
    fake = FakeCynosdbClient(accounts=[_account()])
    _make_module(monkeypatch, fake)
    _base(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["account"] is None
    assert fake.accounts == []
    ops = [c for c, unused in fake.calls]
    assert "DeleteAccounts" in ops


def test_absent_missing_waits_for_convergence(monkeypatch):
    fake = FakeCynosdbClient(accounts=[_account()])
    _make_module(monkeypatch, fake)
    _base(state="absent", waiter_delay=5)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert fake.accounts == []


# ---------------------------------------------------------------------------
# creation flows
# ---------------------------------------------------------------------------


def test_create_requires_password(monkeypatch):
    fake = FakeCynosdbClient(accounts=[])
    _make_module(monkeypatch, fake)
    _base(state="present", description="new account")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "password is required when creating" in exc.value.args[0]["msg"]


def test_create_account(monkeypatch):
    fake = FakeCynosdbClient(accounts=[])
    _make_module(monkeypatch, fake)
    _base(
        state="present",
        password="S3cret!",
        description="application account",
        max_user_connections=50,
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["account"]["AccountName"] == "app_user"
    assert result["account"]["Description"] == "application account"
    assert result["account"]["MaxUserConnections"] == 50
    assert len(fake.accounts) == 1
    ops = [c for c, unused in fake.calls]
    assert ops[0] == "DescribeAccounts"
    assert "CreateAccounts" in ops


def test_create_check_mode_is_dry_run(monkeypatch):
    fake = FakeCynosdbClient(accounts=[])
    _make_module(monkeypatch, fake)
    _base(_ansible_check_mode=True, state="present", password="S3cret!", description="x")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["account"] is None
    assert fake.accounts == []
    assert "CreateAccounts" not in [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# existing-account flows
# ---------------------------------------------------------------------------


def test_existing_account_no_drift_is_idempotent(monkeypatch):
    fake = FakeCynosdbClient(accounts=[_account()])
    _make_module(monkeypatch, fake)
    _base(state="present", description="application account")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["account"]["Description"] == "application account"


def test_update_description_drift(monkeypatch):
    fake = FakeCynosdbClient(accounts=[_account()])
    _make_module(monkeypatch, fake)
    _base(state="present", description="renamed description")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["account"]["Description"] == "renamed description"
    ops = [c for c, unused in fake.calls]
    assert "ModifyAccountDescription" in ops


def test_update_description_check_mode_is_dry_run(monkeypatch):
    fake = FakeCynosdbClient(accounts=[_account()])
    _make_module(monkeypatch, fake)
    _base(_ansible_check_mode=True, state="present", description="renamed description")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["account"]["Description"] == "application account"
    assert "ModifyAccountDescription" not in [c for c, unused in fake.calls]


def test_rotate_password_requires_password(monkeypatch):
    fake = FakeCynosdbClient(accounts=[_account()])
    _make_module(monkeypatch, fake)
    _base(state="present", rotate_password=True)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "password is required when rotate_password=true" in exc.value.args[0]["msg"]


def test_rotate_password_applies(monkeypatch):
    fake = FakeCynosdbClient(accounts=[_account()])
    _make_module(monkeypatch, fake)
    _base(state="present", description="application account", password="NewP@ss", rotate_password=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["account"]["Description"] == "application account"
    ops = [c for c, unused in fake.calls]
    assert "ResetAccountPassword" in ops
    assert "ModifyAccountDescription" not in ops


# ---------------------------------------------------------------------------
# guard / failure paths
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
