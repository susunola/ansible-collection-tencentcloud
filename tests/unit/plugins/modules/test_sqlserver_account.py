"""Unit tests for the sqlserver_account write module (helpers + run_module).

Covers the create / privilege-reconcile / delete flows of
``plugins/modules/sqlserver_account.py`` with an in-memory fake SQL Server
client whose write operations mutate the account store, so the module's
post-write ``find`` refetch converges immediately. Accounts are matched by
``Name`` across the paged DescribeAccounts list; database privilege changes
are computed as an add/drop/update diff (``Delete`` privilege removes a
database binding) and remark / password / account-type changes each map to
their dedicated API call.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import sqlserver_account as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

ACCOUNT = {
    "Name": "app",
    "Remark": "",
    "AccountType": "L3",
    "Dbs": [{"DBName": "orders", "Privilege": "ReadWrite"}],
}


def _account(**overrides):
    """API-shaped account dict isolated from the shared constant."""
    item = copy.deepcopy(ACCOUNT)
    item.update(overrides)
    return item


def _params(**overrides):
    """Module parameters pre-filled from the argument spec (base included)."""
    params = {
        "state": "present",
        "instance_id": "mssql-abc123",
        "username": "app",
        "password": "S3cret!pass",
        "rotate_password": False,
        "remark": "",
        "account_type": "L3",
        "database_privileges": [],
        "retries": 5,
        "waiter_delay": 5,
        "waiter_timeout": 120,
    }
    params.update(overrides)
    return params


def _run_args(**extra):
    """module_args() pre-filled with every module parameter."""
    args = dict(_params())
    args.update(extra)
    return module_args(**args)


def _db(database, privilege):
    return {"database": database, "privilege": privilege}


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


class FakeSqlserverClient(object):
    """In-memory SqlserverClient stand-in.

    Stores API-shaped account dicts. DescribeAccounts pages over the store
    honouring Offset/Limit so find pagination is exercised; the write
    operations (CreateAccount / ModifyAccountPrivilege / ModifyAccountRemark /
    ResetAccountPassword / DeleteAccount) mutate the store so post-write
    refetches converge.
    """

    def __init__(self, accounts=None):
        self.accounts = [copy.deepcopy(a) for a in (accounts or [])]
        self.calls = []

    def _record(self, name, request):
        self.calls.append((name, request))
        return request

    @staticmethod
    def _plain(model):
        """Convert an attribute-bag request model back to a plain dict."""
        return {k: v for k, v in vars(model).items() if not k.startswith("_")}

    def DescribeAccounts(self, request):
        self._record("DescribeAccounts", request)
        page = self.accounts[request.Offset : request.Offset + request.Limit]
        return SimpleNamespace(
            Accounts=[FakeResource(dict(a)) for a in page],
            TotalCount=len(self.accounts),
            RequestId="req-fake",
        )

    def CreateAccount(self, request):
        self._record("CreateAccount", request)
        for account in request.Accounts:
            plain = self._plain(account)
            self.accounts.append(
                {
                    "Name": plain["UserName"],
                    "Remark": plain.get("Remark") or "",
                    "AccountType": plain.get("AccountType"),
                    "Dbs": [self._plain(d) for d in (plain.get("DBPrivileges") or [])],
                }
            )
        return SimpleNamespace(RequestId="req-fake")

    def ModifyAccountPrivilege(self, request):
        self._record("ModifyAccountPrivilege", request)
        account = request.Accounts[0]
        for stored in self.accounts:
            if stored.get("Name") != account.UserName:
                continue
            stored["AccountType"] = account.AccountType
            dbs = list(stored.get("Dbs") or [])
            for change in account.DBPrivileges or []:
                if change.Privilege == "Delete":
                    dbs = [d for d in dbs if d["DBName"] != change.DBName]
                    continue
                replaced = False
                for d in dbs:
                    if d["DBName"] == change.DBName:
                        d["Privilege"] = change.Privilege
                        replaced = True
                if not replaced:
                    dbs.append({"DBName": change.DBName, "Privilege": change.Privilege})
            stored["Dbs"] = dbs
        return SimpleNamespace(RequestId="req-fake")

    def ModifyAccountRemark(self, request):
        self._record("ModifyAccountRemark", request)
        account = request.Accounts[0]
        for stored in self.accounts:
            if stored.get("Name") == account.UserName:
                stored["Remark"] = account.Remark
        return SimpleNamespace(RequestId="req-fake")

    def ResetAccountPassword(self, request):
        self._record("ResetAccountPassword", request)
        return SimpleNamespace(RequestId="req-fake")

    def DeleteAccount(self, request):
        self._record("DeleteAccount", request)
        names = list(request.UserNames or [])
        self.accounts = [a for a in self.accounts if a.get("Name") not in names]
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake):
    """Wire the shared monkeypatches and return the fake client."""
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(
        mod,
        "_load",
        lambda: (FakeModels(), SimpleNamespace(SqlserverClient=object)),
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
            raise RuntimeError("service exploded")

        return boom


# ---------------------------------------------------------------------------
# request-builder helper tests
# ---------------------------------------------------------------------------


def test_db_privileges_plain():
    items = mod._db_privileges(FakeModels(), [_db("orders", "ReadWrite"), _db("hr", "ReadOnly")])
    assert len(items) == 2
    assert type(items[0]).__name__ == "DBPrivilege"
    assert items[0].DBName == "orders"
    assert items[0].Privilege == "ReadWrite"
    assert items[1].DBName == "hr"


def test_db_privileges_modify_uses_modify_info():
    items = mod._db_privileges(FakeModels(), [_db("orders", "ReadWrite")], modify=True)
    assert type(items[0]).__name__ == "DBPrivilegeModifyInfo"
    assert items[0].DBName == "orders"


def test_describe_request_fields():
    request = mod.describe_request(FakeModels(), _params(), offset=7)
    assert request.InstanceId == "mssql-abc123"
    assert request.Offset == 7
    assert request.Limit == 100
    assert request.Name == "app"


def test_create_request_fields():
    request = mod.create_request(
        FakeModels(),
        _params(password="pw", remark="ops", account_type="L2", database_privileges=[_db("orders", "ReadWrite")]),
    )
    assert request.InstanceId == "mssql-abc123"
    assert len(request.Accounts) == 1
    account = request.Accounts[0]
    assert account.UserName == "app"
    assert account.Password == "pw"
    assert account.Remark == "ops"
    assert account.AccountType == "L2"
    assert len(account.DBPrivileges) == 1
    assert account.DBPrivileges[0].DBName == "orders"


def test_privilege_request_fields():
    request = mod.privilege_request(FakeModels(), _params(account_type="L1"), [_db("orders", "ReadOnly"), _db("hr", "Delete")])
    assert request.InstanceId == "mssql-abc123"
    account = request.Accounts[0]
    assert account.UserName == "app"
    assert account.AccountType == "L1"
    assert len(account.DBPrivileges) == 2
    assert type(account.DBPrivileges[0]).__name__ == "DBPrivilegeModifyInfo"
    assert account.DBPrivileges[1].Privilege == "Delete"


def test_remark_request_fields():
    request = mod.remark_request(FakeModels(), _params(remark="ops account"))
    account = request.Accounts[0]
    assert account.UserName == "app"
    assert account.Remark == "ops account"


def test_password_request_fields():
    request = mod.password_request(FakeModels(), _params(password="new-pw"))
    account = request.Accounts[0]
    assert account.UserName == "app"
    assert account.Password == "new-pw"


def test_delete_request_fields():
    request = mod.delete_request(FakeModels(), _params())
    assert request.InstanceId == "mssql-abc123"
    assert request.UserNames == ["app"]


# ---------------------------------------------------------------------------
# privileges / comparable / desired tests
# ---------------------------------------------------------------------------


def test_privileges_normalises_and_sorts():
    value = mod.privileges([{"DBName": "z-db", "Privilege": "ReadOnly"}, {"DBName": "a-db", "Privilege": "ReadWrite"}])
    assert value == [_db("a-db", "ReadWrite"), _db("z-db", "ReadOnly")]


def test_privileges_normalises_serialisable_objects():
    value = mod.privileges([FakeResource({"DBName": "orders", "Privilege": "DBOwner"})])
    assert value == [_db("orders", "DBOwner")]


def test_privileges_none():
    assert mod.privileges(None) == []


def test_comparable_mapping():
    value = mod.comparable(
        {"Name": "app", "Remark": "ops", "AccountType": "L2", "Dbs": [{"DBName": "orders", "Privilege": "ReadWrite"}]}
    )
    assert value == {"Name": "app", "Remark": "ops", "AccountType": "L2", "Dbs": [_db("orders", "ReadWrite")]}


def test_comparable_defaults_remark():
    value = mod.comparable({"Name": "app", "AccountType": "L3", "Dbs": None})
    assert value == {"Name": "app", "Remark": "", "AccountType": "L3", "Dbs": []}


def test_desired_mapping():
    value = mod.desired(_params(remark="ops", account_type="L2", database_privileges=[_db("orders", "ReadWrite"), _db("hr", "DBOwner")]))
    assert value == {
        "Name": "app",
        "Remark": "ops",
        "AccountType": "L2",
        "Dbs": [_db("hr", "DBOwner"), _db("orders", "ReadWrite")],  # sorted by database
    }


def test_privilege_changes_add_drop_update():
    changes = mod.privilege_changes(
        [_db("a", "ReadWrite"), _db("b", "ReadOnly")],
        [_db("b", "DBOwner"), _db("c", "ReadOnly")],
    )
    assert changes == [_db("a", "Delete"), _db("b", "DBOwner"), _db("c", "ReadOnly")]


def test_privilege_changes_noop_when_identical():
    assert mod.privilege_changes([_db("a", "ReadWrite")], [_db("a", "ReadWrite")]) == []


def test_privilege_changes_all_added():
    assert mod.privilege_changes([], [_db("a", "ReadWrite"), _db("b", "ReadOnly")]) == [
        _db("a", "ReadWrite"),
        _db("b", "ReadOnly"),
    ]


def test_privilege_changes_all_removed():
    changes = mod.privilege_changes([_db("a", "ReadWrite")], [])
    assert changes == [_db("a", "Delete")]


# ---------------------------------------------------------------------------
# find tests
# ---------------------------------------------------------------------------


def test_find_no_match_returns_none(monkeypatch):
    fake = FakeSqlserverClient([_account(Name="other")])
    _make_module(monkeypatch, fake)
    module = FakeModule(_params(username="ghost"))
    assert mod.find(module, fake, FakeModels(), module.params) is None


def test_find_by_name(monkeypatch):
    fake = FakeSqlserverClient([_account(Name="other"), _account()])
    _make_module(monkeypatch, fake)
    module = FakeModule(_params(username="app"))
    value = mod.find(module, fake, FakeModels(), module.params)
    assert value["Name"] == "app"


def test_find_paginates_until_match(monkeypatch):
    accounts = [_account(Name="bulk-%04d" % i, Dbs=[]) for i in range(150)]
    accounts.append(_account(Name="app"))
    fake = FakeSqlserverClient(accounts)
    _make_module(monkeypatch, fake)
    module = FakeModule(_params(username="app"))
    value = mod.find(module, fake, FakeModels(), module.params)
    assert value["Name"] == "app"
    list_calls = [c for c in fake.calls if c[0] == "DescribeAccounts"]
    assert len(list_calls) == 2  # pages of 100
    assert [c[1].Offset for c in list_calls] == [0, 100]


# ---------------------------------------------------------------------------
# run_module main-path tests
# ---------------------------------------------------------------------------


def test_rotate_password_requires_password():
    module_args(state="present", instance_id="mssql-abc123", username="app", rotate_password=True)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert exc.value.args[0]["msg"] == "password is required when rotate_password=true"


def test_sdk_error_is_reported(monkeypatch):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(
        mod,
        "_load",
        lambda: (FakeModels(), SimpleNamespace(SqlserverClient=object)),
    )
    monkeypatch.setattr(
        TencentCloudModule,
        "create_client",
        lambda self, client_class, endpoint: _BoomClient(),
    )
    _run_args()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert payload["error"] == "service exploded"


def test_present_creates_account(monkeypatch):
    fake = FakeSqlserverClient()
    _make_module(monkeypatch, fake)
    _run_args(password="pw", remark="ops", account_type="L2", database_privileges=[_db("orders", "ReadWrite")])
    result = run(mod.run_module)
    assert result["changed"] is True
    account = result["account"]
    assert account["Name"] == "app"
    assert account["AccountType"] == "L2"
    assert account["Dbs"] == [{"DBName": "orders", "Privilege": "ReadWrite"}]
    names = [c[0] for c in fake.calls]
    assert names.count("DescribeAccounts") == 2  # find + refetch
    assert names.count("CreateAccount") == 1
    create = [c for c in fake.calls if c[0] == "CreateAccount"][0][1]
    assert create.Accounts[0].UserName == "app"
    assert create.Accounts[0].Password == "pw"
    assert create.Accounts[0].DBPrivileges[0].DBName == "orders"


def test_present_create_requires_password(monkeypatch):
    fake = FakeSqlserverClient()
    _make_module(monkeypatch, fake)
    _run_args(password=None)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert exc.value.args[0]["msg"] == "password is required when creating a SQL Server account"
    assert not any("CreateAccount" == c[0] for c in fake.calls)


def test_present_noop_returns_unchanged(monkeypatch):
    fake = FakeSqlserverClient([_account()])
    _make_module(monkeypatch, fake)
    _run_args(database_privileges=[_db("orders", "ReadWrite")])
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["account"]["Name"] == "app"
    names = [c[0] for c in fake.calls]
    assert not any(name in names for name in ("CreateAccount", "ModifyAccountPrivilege", "ModifyAccountRemark"))


def test_present_db_privilege_change_triggers_update(monkeypatch):
    fake = FakeSqlserverClient([_account()])
    _make_module(monkeypatch, fake)
    _run_args(database_privileges=[_db("orders", "ReadOnly")])
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["account"]["Dbs"] == [{"DBName": "orders", "Privilege": "ReadOnly"}]
    update = [c for c in fake.calls if c[0] == "ModifyAccountPrivilege"][0][1]
    assert update.Accounts[0].UserName == "app"
    assert update.Accounts[0].DBPrivileges[0].DBName == "orders"
    assert update.Accounts[0].DBPrivileges[0].Privilege == "ReadOnly"


def test_present_db_privilege_added(monkeypatch):
    fake = FakeSqlserverClient([_account(Dbs=[])])
    _make_module(monkeypatch, fake)
    _run_args(database_privileges=[_db("orders", "ReadWrite")])
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["account"]["Dbs"] == [{"DBName": "orders", "Privilege": "ReadWrite"}]


def test_present_db_privilege_removed(monkeypatch):
    fake = FakeSqlserverClient([_account(Dbs=[{"DBName": "orders", "Privilege": "ReadWrite"}, {"DBName": "reports", "Privilege": "ReadOnly"}])])
    _make_module(monkeypatch, fake)
    _run_args(database_privileges=[_db("orders", "ReadWrite")])
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["account"]["Dbs"] == [{"DBName": "orders", "Privilege": "ReadWrite"}]
    update = [c for c in fake.calls if c[0] == "ModifyAccountPrivilege"][0][1]
    assert update.Accounts[0].DBPrivileges[0].DBName == "reports"
    assert update.Accounts[0].DBPrivileges[0].Privilege == "Delete"


def test_present_account_type_drift_alone_updates(monkeypatch):
    fake = FakeSqlserverClient([_account()])
    _make_module(monkeypatch, fake)
    _run_args(account_type="L0", database_privileges=[_db("orders", "ReadWrite")])
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["account"]["AccountType"] == "L0"
    update = [c for c in fake.calls if c[0] == "ModifyAccountPrivilege"][0][1]
    assert update.Accounts[0].AccountType == "L0"
    assert update.Accounts[0].DBPrivileges == []  # no db-level change


def test_present_remark_drift_triggers_remark_call(monkeypatch):
    fake = FakeSqlserverClient([_account()])
    _make_module(monkeypatch, fake)
    _run_args(remark="ops account", database_privileges=[_db("orders", "ReadWrite")])
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["account"]["Remark"] == "ops account"
    assert any("ModifyAccountRemark" == c[0] for c in fake.calls)
    assert not any("ModifyAccountPrivilege" == c[0] for c in fake.calls)


def test_present_rotate_password_on_existing(monkeypatch):
    fake = FakeSqlserverClient([_account()])
    _make_module(monkeypatch, fake)
    _run_args(rotate_password=True, password="rotated-pw", database_privileges=[_db("orders", "ReadWrite")])
    result = run(mod.run_module)
    assert result["changed"] is True
    names = [c[0] for c in fake.calls]
    assert names.count("ResetAccountPassword") == 1
    reset = [c for c in fake.calls if c[0] == "ResetAccountPassword"][0][1]
    assert reset.Accounts[0].Password == "rotated-pw"
    # No privilege/remark drift -> only the password op ran.
    assert "ModifyAccountPrivilege" not in names
    assert "ModifyAccountRemark" not in names


def test_check_mode_create_is_dry_run(monkeypatch):
    fake = FakeSqlserverClient()
    _make_module(monkeypatch, fake)
    module_args(_ansible_check_mode=True, **_params(database_privileges=[_db("orders", "ReadWrite")]))
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["account"] is None  # no real account created in check mode
    assert not any("CreateAccount" == c[0] for c in fake.calls)


def test_check_mode_update_is_dry_run(monkeypatch):
    fake = FakeSqlserverClient([_account()])
    _make_module(monkeypatch, fake)
    module_args(_ansible_check_mode=True, **_params(database_privileges=[_db("orders", "ReadOnly")]))
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["account"]["Dbs"] == [{"DBName": "orders", "Privilege": "ReadWrite"}]  # pre-change
    assert not any(name in [c[0] for c in fake.calls] for name in ("CreateAccount", "ModifyAccountPrivilege", "ModifyAccountRemark"))


def test_absent_removes_account(monkeypatch):
    fake = FakeSqlserverClient([_account()])
    _make_module(monkeypatch, fake)
    _run_args(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["account"] is None
    delete = [c for c in fake.calls if c[0] == "DeleteAccount"][0][1]
    assert delete.UserNames == ["app"]
    assert fake.accounts == []


def test_absent_not_found_is_noop(monkeypatch):
    fake = FakeSqlserverClient([_account(Name="other")])
    _make_module(monkeypatch, fake)
    _run_args(state="absent", username="ghost")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["account"] is None
    assert not any("DeleteAccount" == c[0] for c in fake.calls)


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeSqlserverClient([_account()])
    _make_module(monkeypatch, fake)
    module_args(_ansible_check_mode=True, **_params(state="absent"))
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["account"] is not None  # pre-change state reported
    assert not any("DeleteAccount" == c[0] for c in fake.calls)
    assert len(fake.accounts) == 1
