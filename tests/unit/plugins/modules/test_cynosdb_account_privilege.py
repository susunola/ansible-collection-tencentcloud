"""Unit tests for the cynosdb_account_privilege write module (helpers + run_module).

Reconciles the complete global / database / table privilege set of one CynosDB
account. Unlike cdb_account_privilege there is no ``state`` parameter: every
run converges the account toward the exact desired set. The describe response
attributes (``GlobalPrivileges`` / ``DatabasePrivileges`` / ``TablePrivileges``)
are read directly off the SDK response — no ``_serialize`` of the whole
response — so the fake returns plain attribute-accessible objects.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import cynosdb_account_privilege as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

EMPTY_STATE = {
    "GlobalPrivileges": [],
    "DatabasePrivileges": [],
    "TablePrivileges": [],
}


def _state(**overrides):
    """API-shaped current privilege state (raw, unsorted is fine)."""
    state = copy.deepcopy(EMPTY_STATE)
    state.update(copy.deepcopy(overrides))
    return state


def _params(**overrides):
    """Module parameters pre-filled from the argument spec defaults."""
    params = {
        "cluster_id": "cynosdbmysql-abc",
        "account_name": "app",
        "host": "%",
        "global_privileges": [],
        "database_privileges": [],
        "table_privileges": [],
    }
    params.update(overrides)
    return params


def _run_args(**extra):
    """module_args() pre-filled with every module parameter."""
    return module_args(**dict(_params(), **extra))


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


class FakeCynosdbClient(object):
    """In-memory CynosdbClient stand-in storing one account's privilege state."""

    def __init__(self, state=None):
        self.state = copy.deepcopy(state if state is not None else EMPTY_STATE)
        self.calls = []

    def _record(self, name, request):
        self.calls.append((name, request))
        return request

    def DescribeAccountAllGrantPrivileges(self, request):
        self._record("DescribeAccountAllGrantPrivileges", request)
        return SimpleNamespace(
            GlobalPrivileges=list(self.state["GlobalPrivileges"]),
            DatabasePrivileges=copy.deepcopy(self.state["DatabasePrivileges"]),
            TablePrivileges=copy.deepcopy(self.state["TablePrivileges"]),
            RequestId="req-fake",
        )

    def ModifyAccountPrivileges(self, request):
        self._record("ModifyAccountPrivileges", request)
        self.state = {
            "GlobalPrivileges": sorted(set(request.GlobalPrivileges or [])),
            "DatabasePrivileges": [
                {"Db": d.Db, "Privileges": sorted(set(d.Privileges))} for d in (request.DatabasePrivileges or [])
            ],
            "TablePrivileges": [
                {"Db": t.Db, "TableName": t.TableName, "Privileges": sorted(set(t.Privileges))}
                for t in (request.TablePrivileges or [])
            ],
        }
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake):
    """Wire the shared monkeypatches and return the fake client."""
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(
        mod,
        "_load",
        lambda: (FakeModels(), SimpleNamespace(CynosdbClient=object)),
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


FULL_PARAMS = dict(
    global_privileges=["SELECT", "INSERT"],
    database_privileges=[{"database": "orders", "privileges": ["select", "insert"]}],
    table_privileges=[{"database": "orders", "table": "line_items", "privileges": ["select"]}],
)

FULL_STATE = _state(
    GlobalPrivileges=["INSERT", "SELECT"],
    DatabasePrivileges=[{"Db": "orders", "Privileges": ["insert", "select"]}],
    TablePrivileges=[{"Db": "orders", "TableName": "line_items", "Privileges": ["select"]}],
)


# ---------------------------------------------------------------------------
# request-builder / helper tests
# ---------------------------------------------------------------------------


def test_account_object_fields():
    account = mod._account(FakeModels(), _params())
    assert account.AccountName == "app"
    assert account.Host == "%"


def test_describe_request_fields():
    request = mod.describe_request(FakeModels(), _params())
    assert request.ClusterId == "cynosdbmysql-abc"
    assert request.Account.AccountName == "app"
    assert request.Account.Host == "%"


def test_databases_maps_db_and_sorts_privileges():
    items = mod._databases(FakeModels(), [{"database": "db1", "privileges": ["b", "a"]}])
    assert len(items) == 1
    assert items[0].Db == "db1"
    assert items[0].Privileges == ["a", "b"]


def test_tables_maps_db_table_and_sorts_privileges():
    items = mod._tables(FakeModels(), [{"database": "db1", "table": "t1", "privileges": ["c", "b"]}])
    assert len(items) == 1
    assert items[0].Db == "db1"
    assert items[0].TableName == "t1"
    assert items[0].Privileges == ["b", "c"]


def test_update_request_builds_full_target():
    models = FakeModels()
    request = mod.update_request(models, _params(**FULL_PARAMS))
    assert request.ClusterId == "cynosdbmysql-abc"
    assert request.Account.AccountName == "app"
    assert request.Account.Host == "%"
    assert request.GlobalPrivileges == ["INSERT", "SELECT"]
    assert request.DatabasePrivileges[0].Db == "orders"
    assert request.DatabasePrivileges[0].Privileges == ["insert", "select"]
    assert request.TablePrivileges[0].Db == "orders"
    assert request.TablePrivileges[0].TableName == "line_items"
    assert request.TablePrivileges[0].Privileges == ["select"]


def test_dbs_normalizes_plain_dicts_sorted_by_db():
    values = [{"Db": "b", "Privileges": ["x"]}, {"Db": "a", "Privileges": ["b", "a"]}]
    assert mod._dbs(values) == [
        {"database": "a", "privileges": ["a", "b"]},
        {"database": "b", "privileges": ["x"]},
    ]


def test_dbs_normalizes_serializable_objects():
    values = [FakeResource({"Db": "db1", "Privileges": ["c", "b"]})]
    assert mod._dbs(values) == [{"database": "db1", "privileges": ["b", "c"]}]


def test_dbs_none_returns_empty():
    assert mod._dbs(None) == []


def test_tabs_normalizes_and_sorts_by_db_then_table():
    values = [
        {"Db": "b", "TableName": "t1", "Privileges": ["x"]},
        {"Db": "a", "TableName": "t2", "Privileges": []},
        {"Db": "a", "TableName": "t1", "Privileges": ["y"]},
    ]
    assert mod._tabs(values) == [
        {"database": "a", "table": "t1", "privileges": ["y"]},
        {"database": "a", "table": "t2", "privileges": []},
        {"database": "b", "table": "t1", "privileges": ["x"]},
    ]


def test_tabs_serializable_objects():
    values = [FakeResource({"Db": "db1", "TableName": "t1", "Privileges": ["b", "a"]})]
    assert mod._tabs(values) == [{"database": "db1", "table": "t1", "privileges": ["a", "b"]}]


def test_normalize_sorts_all_levels():
    result = mod.normalize(["INSERT", "SELECT"], [{"Db": "a", "Privileges": ["b", "a"]}], [])
    assert result == {
        "GlobalPrivileges": ["INSERT", "SELECT"],
        "DatabasePrivileges": [{"database": "a", "privileges": ["a", "b"]}],
        "TablePrivileges": [],
    }


def test_desired_builds_normalized_target():
    result = mod.desired(_params(**FULL_PARAMS))
    assert result == mod.normalize(
        ["SELECT", "INSERT"],
        [{"Db": "orders", "Privileges": ["select", "insert"]}],
        [{"Db": "orders", "TableName": "line_items", "Privileges": ["select"]}],
    )


# ---------------------------------------------------------------------------
# run_module main-path tests
# ---------------------------------------------------------------------------


def test_present_noop_when_current_matches(monkeypatch):
    fake = FakeCynosdbClient(FULL_STATE)
    _make_module(monkeypatch, fake)
    _run_args(**FULL_PARAMS)
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["account_privileges"]["GlobalPrivileges"] == ["INSERT", "SELECT"]
    assert not any(c[0] == "ModifyAccountPrivileges" for c in fake.calls)


def test_present_change_writes_and_refetches(monkeypatch):
    fake = FakeCynosdbClient()
    _make_module(monkeypatch, fake)
    _run_args(**FULL_PARAMS)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["account_privileges"]["GlobalPrivileges"] == ["INSERT", "SELECT"]
    assert result["account_privileges"]["DatabasePrivileges"] == [
        {"database": "orders", "privileges": ["insert", "select"]}
    ]
    assert result["account_privileges"]["TablePrivileges"] == [
        {"database": "orders", "table": "line_items", "privileges": ["select"]}
    ]
    write = [c for c in fake.calls if c[0] == "ModifyAccountPrivileges"]
    assert len(write) == 1
    describes = [c for c in fake.calls if c[0] == "DescribeAccountAllGrantPrivileges"]
    assert len(describes) == 2  # fetch + refetch


def test_drift_grants_additional_database(monkeypatch):
    seeded = _state(
        DatabasePrivileges=[{"Db": "orders", "Privileges": ["select"]}],
    )
    fake = FakeCynosdbClient(seeded)
    _make_module(monkeypatch, fake)
    _run_args(database_privileges=[{"database": "orders", "privileges": ["select", "update"]}])
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["account_privileges"]["DatabasePrivileges"] == [
        {"database": "orders", "privileges": ["select", "update"]}
    ]


def test_check_mode_change_reports_diff_without_write(monkeypatch):
    fake = FakeCynosdbClient()
    _make_module(monkeypatch, fake)
    _run_args(_ansible_check_mode=True, **FULL_PARAMS)
    result = run(mod.run_module)
    assert result["changed"] is True
    # empty containers are stripped from diff payloads by comparison._normalize
    assert result["diff"]["before"] == {}
    assert result["diff"]["after"]["GlobalPrivileges"] == ["INSERT", "SELECT"]
    assert result["account_privileges"]["GlobalPrivileges"] == []  # pre-change state
    assert not any(c[0] == "ModifyAccountPrivileges" for c in fake.calls)


def test_sdk_error_is_reported(monkeypatch):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(
        mod,
        "_load",
        lambda: (FakeModels(), SimpleNamespace(CynosdbClient=object)),
    )
    monkeypatch.setattr(
        TencentCloudModule,
        "create_client",
        lambda self, client_class, endpoint: _BoomClient(),
    )
    _run_args(**FULL_PARAMS)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert payload["error"] == "service exploded"
