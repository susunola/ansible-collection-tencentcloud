"""Unit tests for the cdb_account write module (helpers + run_module).

Creates, updates, rotates and deletes a TencentDB for MySQL account
identified by the (user, host) pair. Lookup pages through
DescribeAccounts (Limit 100) and matches on both ``User`` and ``Host``.
There are no immutable fields: drift is decomposed into per-attribute
Modify* calls (description, max connections) and password changes are
only applied when ``rotate_password`` is explicitly requested. Creating
an account without a password fails before any API call.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import cdb_account as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)


def _account(**overrides):
    """API-shaped CDB account dict; fresh copy per call."""
    item = {
        "User": "app",
        "Host": "%",
        "Notes": "",
        "MaxUserConnections": 10240,
    }
    item.update(overrides)
    return item


def _params(**overrides):
    """Module parameters pre-filled from the argument spec defaults."""
    params = {
        "state": "present",
        "instance_id": "cdb-abc123",
        "username": "app",
        "host": "%",
        "password": None,
        "rotate_password": False,
        "description": "",
        "max_user_connections": 10240,
    }
    params.update(overrides)
    return params


def _run_args(**extra):
    """module_args() pre-filled with every module parameter."""
    return module_args(**{k: v for k, v in _params(**extra).items() if v is not None})


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


class FakeCdbClient(object):
    """In-memory CdbClient stand-in storing CDB account dicts.

    DescribeAccounts filters by InstanceId and pages with the request's
    Offset/Limit; the module applies its own (User, Host) identity match.
    Create appends the account from the request's Account model; the
    per-attribute Modify* operations update only their own field so the
    module's decomposed drift handling is observable.
    """

    def __init__(self, accounts=None):
        self.accounts = [dict(a) for a in (accounts or [])]
        self.calls = []

    def _record(self, name, request):
        self.calls.append((name, request))
        return request

    def _instance_items(self, instance_id):
        return [a for a in self.accounts if a.get("_instance") == instance_id]

    @staticmethod
    def _serializable(account):
        return {k: v for k, v in account.items() if not k.startswith("_")}

    @staticmethod
    def _identity(account):
        return account.get("User"), account.get("Host")

    def DescribeAccounts(self, request):
        self._record("DescribeAccounts", request)
        items = self._instance_items(request.InstanceId)
        offset = getattr(request, "Offset", 0) or 0
        limit = getattr(request, "Limit", 100) or 100
        page = items[offset:offset + limit]
        return SimpleNamespace(
            Items=[FakeResource(self._serializable(a)) for a in page],
            TotalCount=len(items),
            RequestId="req-fake",
        )

    def CreateAccounts(self, request):
        self._record("CreateAccounts", request)
        first = request.Accounts[0]
        self.accounts.append({
            "_instance": request.InstanceId,
            "User": first.User,
            "Host": first.Host,
            "Notes": request.Description,
            "MaxUserConnections": request.MaxUserConnections,
        })
        return SimpleNamespace(RequestId="req-fake")

    def DeleteAccounts(self, request):
        self._record("DeleteAccounts", request)
        instance_id = request.InstanceId
        user, host = request.Accounts[0].User, request.Accounts[0].Host
        self.accounts = [
            a for a in self.accounts
            if a.get("_instance") != instance_id or self._identity(a) != (user, host)
        ]
        return SimpleNamespace(RequestId="req-fake")

    def ModifyAccountDescription(self, request):
        self._record("ModifyAccountDescription", request)
        for account in self._instance_items(request.InstanceId):
            if self._identity(account) == (request.Accounts[0].User, request.Accounts[0].Host):
                account["Notes"] = request.Description
        return SimpleNamespace(RequestId="req-fake")

    def ModifyAccountMaxUserConnections(self, request):
        self._record("ModifyAccountMaxUserConnections", request)
        for account in self._instance_items(request.InstanceId):
            if self._identity(account) == (request.Accounts[0].User, request.Accounts[0].Host):
                account["MaxUserConnections"] = request.MaxUserConnections
        return SimpleNamespace(RequestId="req-fake")

    def ModifyAccountPassword(self, request):
        self._record("ModifyAccountPassword", request)
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake):
    """Wire the shared monkeypatches and return the fake client."""
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(
        mod,
        "_load",
        lambda: (FakeModels(), SimpleNamespace(CdbClient=object)),
    )
    monkeypatch.setattr(
        TencentCloudModule,
        "create_client",
        lambda self, client_class, endpoint: fake,
    )
    return fake


def _store(fake, account, instance="cdb-abc123"):
    """Store an API-shaped account dict under an instance identity."""
    record = dict(account)
    record["_instance"] = instance
    fake.accounts.append(record)


class _BoomClient(object):
    """Every SDK call raises, so the module's wrapped error path is hit."""

    def __getattr__(self, name):
        def boom(*args, **kwargs):
            raise RuntimeError("service exploded")

        return boom


# ---------------------------------------------------------------------------
# request-builder / comparable / desired tests
# ---------------------------------------------------------------------------


def test_account_model_fields():
    value = mod.account(FakeModels(), "app", "10.%")
    assert value.User == "app"
    assert value.Host == "10.%"


def test_describe_request_fields():
    request = mod.describe(FakeModels(), _params(), offset=50)
    assert request.InstanceId == "cdb-abc123"
    assert request.Offset == 50
    assert request.Limit == 100


def test_describe_request_default_offset_is_zero():
    request = mod.describe(FakeModels(), _params())
    assert request.Offset == 0


def test_create_request_fields():
    request = mod.create(FakeModels(), _params(password="s3cret", description="App account", max_user_connections=500))
    assert request.InstanceId == "cdb-abc123"
    assert request.Password == "s3cret"
    assert request.Description == "App account"
    assert request.MaxUserConnections == 500
    assert request.Accounts[0].User == "app"
    assert request.Accounts[0].Host == "%"


def test_simple_request_builds_any_kind():
    models = FakeModels()
    for kind in ("DeleteAccounts", "ModifyAccountDescription", "ModifyAccountPassword", "ModifyAccountMaxUserConnections"):
        request = mod.simple(models, kind, _params())
        assert type(request).__name__ == kind + "Request"
        assert request.InstanceId == "cdb-abc123"
        assert request.Accounts[0].User == "app"
        assert request.Accounts[0].Host == "%"


def test_desired_matches_params():
    assert mod.desired(_params(description="App account", max_user_connections=500)) == {
        "User": "app",
        "Host": "%",
        "Notes": "App account",
        "MaxUserConnections": 500,
    }


def test_comparable_reads_same_keys():
    value = mod.comparable({"User": "app", "Host": "%", "Notes": "x", "MaxUserConnections": 7, "CreateTime": "ignored"})
    assert value == {"User": "app", "Host": "%", "Notes": "x", "MaxUserConnections": 7}


def test_comparable_missing_keys_become_none():
    value = mod.comparable({"User": "app", "Host": "%"})
    assert value == {"User": "app", "Host": "%", "Notes": None, "MaxUserConnections": None}


# ---------------------------------------------------------------------------
# find tests
# ---------------------------------------------------------------------------


def test_find_matches_user_and_host(monkeypatch):
    fake = FakeCdbClient()
    _store(fake, _account(User="root"))
    _store(fake, _account())
    _make_module(monkeypatch, fake)
    module = FakeModule(_params())
    value = mod.find(module, fake, FakeModels(), module.params)
    assert value["User"] == "app"
    assert value["Host"] == "%"


def test_find_requires_both_user_and_host(monkeypatch):
    fake = FakeCdbClient()
    _store(fake, _account(User="app", Host="10.%"))
    _make_module(monkeypatch, fake)
    module = FakeModule(_params())
    assert mod.find(module, fake, FakeModels(), module.params) is None


def test_find_no_match_returns_none(monkeypatch):
    fake = FakeCdbClient()
    _store(fake, _account(User="root"))
    _make_module(monkeypatch, fake)
    module = FakeModule(_params(username="ghost"))
    assert mod.find(module, fake, FakeModels(), module.params) is None


def test_find_other_instance_is_isolated(monkeypatch):
    fake = FakeCdbClient()
    _store(fake, _account(), instance="cdb-other")
    _make_module(monkeypatch, fake)
    module = FakeModule(_params())
    assert mod.find(module, fake, FakeModels(), module.params) is None


def test_find_paginates_across_pages(monkeypatch):
    fake = FakeCdbClient()
    for i in range(150):
        _store(fake, _account(User="user-%03d" % i))
    _store(fake, _account(User="app", Notes="found"))
    _make_module(monkeypatch, fake)
    module = FakeModule(_params())
    value = mod.find(module, fake, FakeModels(), module.params)
    assert value["User"] == "app"
    assert value["Notes"] == "found"
    assert [c[0] for c in fake.calls].count("DescribeAccounts") == 2  # pages 0/100


def test_find_page_exhaustion_stops(monkeypatch):
    fake = FakeCdbClient()
    for i in range(250):
        _store(fake, _account(User="user-%03d" % i))
    _make_module(monkeypatch, fake)
    module = FakeModule(_params(username="ghost"))
    assert mod.find(module, fake, FakeModels(), module.params) is None
    assert [c[0] for c in fake.calls].count("DescribeAccounts") == 3


# ---------------------------------------------------------------------------
# run_module main-path tests
# ---------------------------------------------------------------------------


def test_rotate_password_requires_password():
    _run_args(rotate_password=True, password=None)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "password is required when rotate_password=true" in exc.value.args[0]["msg"]


def test_present_creates_account(monkeypatch):
    fake = FakeCdbClient()
    _make_module(monkeypatch, fake)
    _run_args(password="s3cret", description="App account", max_user_connections=500)
    result = run(mod.run_module)
    assert result["changed"] is True
    account = result["account"]
    assert account["User"] == "app"
    assert account["Host"] == "%"
    assert account["Notes"] == "App account"
    assert account["MaxUserConnections"] == 500
    assert [c[0] for c in fake.calls].count("DescribeAccounts") == 2  # find + refetch
    create = [c for c in fake.calls if c[0] == "CreateAccounts"][0][1]
    assert create.Password == "s3cret"
    assert create.Accounts[0].User == "app"


def test_present_create_requires_password(monkeypatch):
    fake = FakeCdbClient()
    _make_module(monkeypatch, fake)
    _run_args(password=None)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "password is required when creating a CDB account" in exc.value.args[0]["msg"]
    assert not any(c[0] == "CreateAccounts" for c in fake.calls)


def test_present_noop_returns_unchanged(monkeypatch):
    fake = FakeCdbClient()
    _store(fake, _account())
    _make_module(monkeypatch, fake)
    _run_args()
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["account"]["User"] == "app"
    assert not any(c[0].startswith("Create") or c[0].startswith("Modify") for c in fake.calls)


def test_present_description_drift_updates_notes(monkeypatch):
    fake = FakeCdbClient()
    _store(fake, _account(Notes="old"))
    _make_module(monkeypatch, fake)
    _run_args(description="new")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["account"]["Notes"] == "new"
    update = [c for c in fake.calls if c[0] == "ModifyAccountDescription"][0][1]
    assert update.Description == "new"
    assert update.Accounts[0].User == "app"
    assert not any(c[0] == "ModifyAccountMaxUserConnections" for c in fake.calls)


def test_present_max_connections_drift_updates(monkeypatch):
    fake = FakeCdbClient()
    _store(fake, _account(MaxUserConnections=500))
    _make_module(monkeypatch, fake)
    _run_args()
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["account"]["MaxUserConnections"] == 10240
    update = [c for c in fake.calls if c[0] == "ModifyAccountMaxUserConnections"][0][1]
    assert update.MaxUserConnections == 10240
    assert not any(c[0] == "ModifyAccountDescription" for c in fake.calls)


def test_present_both_drifts_issue_both_updates(monkeypatch):
    fake = FakeCdbClient()
    _store(fake, _account(Notes="old", MaxUserConnections=500))
    _make_module(monkeypatch, fake)
    _run_args(description="new")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["account"]["Notes"] == "new"
    assert result["account"]["MaxUserConnections"] == 10240
    assert [c[0] for c in fake.calls].count("ModifyAccountDescription") == 1
    assert [c[0] for c in fake.calls].count("ModifyAccountMaxUserConnections") == 1


def test_present_rotate_password_issues_password_update(monkeypatch):
    fake = FakeCdbClient()
    _store(fake, _account())
    _make_module(monkeypatch, fake)
    _run_args(rotate_password=True, password="newpass")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["account"]["User"] == "app"
    update = [c for c in fake.calls if c[0] == "ModifyAccountPassword"][0][1]
    assert update.NewPassword == "newpass"
    assert not any(c[0] in ("ModifyAccountDescription", "ModifyAccountMaxUserConnections") for c in fake.calls)


def test_present_password_without_rotate_is_noop(monkeypatch):
    fake = FakeCdbClient()
    _store(fake, _account())
    _make_module(monkeypatch, fake)
    _run_args(password="newpass")  # rotate_password defaults false
    result = run(mod.run_module)
    assert result["changed"] is False
    assert not any(c[0].startswith("Create") or c[0].startswith("Modify") for c in fake.calls)


def test_present_rotate_password_check_mode_is_dry_run(monkeypatch):
    fake = FakeCdbClient()
    _store(fake, _account())
    _make_module(monkeypatch, fake)
    _run_args(_ansible_check_mode=True, rotate_password=True, password="newpass")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["account"]["User"] == "app"
    assert not any(c[0].startswith("Create") or c[0].startswith("Modify") for c in fake.calls)


def test_present_check_mode_update_is_dry_run(monkeypatch):
    fake = FakeCdbClient()
    _store(fake, _account(Notes="old"))
    _make_module(monkeypatch, fake)
    _run_args(_ansible_check_mode=True, description="new")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["account"]["Notes"] == "old"  # pre-change state reported
    assert result["diff"]["after"]["Notes"] == "new"
    assert not any(c[0].startswith("Create") or c[0].startswith("Modify") for c in fake.calls)


def test_present_check_mode_create_is_dry_run(monkeypatch):
    fake = FakeCdbClient()
    _make_module(monkeypatch, fake)
    _run_args(_ansible_check_mode=True, password="s3cret")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["account"] is None  # nothing was created to report
    assert result["diff"]["before"] is None
    assert result["diff"]["after"]["User"] == "app"
    assert not any(c[0] == "CreateAccounts" for c in fake.calls)
    assert fake.accounts == []


def test_absent_not_found_is_noop(monkeypatch):
    fake = FakeCdbClient()
    _store(fake, _account(User="root"))
    _make_module(monkeypatch, fake)
    _run_args(state="absent", username="ghost")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["account"] is None
    assert not any(c[0] == "DeleteAccounts" for c in fake.calls)


def test_absent_deletes_account(monkeypatch):
    fake = FakeCdbClient()
    _store(fake, _account())
    _store(fake, _account(User="root"))
    _make_module(monkeypatch, fake)
    _run_args(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["account"] is None
    delete = [c for c in fake.calls if c[0] == "DeleteAccounts"][0][1]
    assert delete.Accounts[0].User == "app"
    assert delete.Accounts[0].Host == "%"
    assert [a["User"] for a in fake.accounts] == ["root"]


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeCdbClient()
    _store(fake, _account())
    _make_module(monkeypatch, fake)
    _run_args(_ansible_check_mode=True, state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["account"]["User"] == "app"  # pre-delete state reported
    assert result["diff"]["after"] is None
    assert not any(c[0] == "DeleteAccounts" for c in fake.calls)
    assert len(fake.accounts) == 1


def test_sdk_error_is_reported(monkeypatch):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(
        mod,
        "_load",
        lambda: (FakeModels(), SimpleNamespace(CdbClient=object)),
    )
    monkeypatch.setattr(
        TencentCloudModule,
        "create_client",
        lambda self, client_class, endpoint: _BoomClient(),
    )
    _run_args(password="s3cret")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert payload["error"] == "service exploded"


def test_main_entrypoint_runs_module(monkeypatch):
    fake = FakeCdbClient()
    _store(fake, _account())
    _make_module(monkeypatch, fake)
    _run_args()
    result = run(mod.main)
    assert result["changed"] is False
    assert result["account"]["User"] == "app"
