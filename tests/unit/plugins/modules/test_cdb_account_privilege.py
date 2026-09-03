"""Unit tests for the cdb_account_privilege write module (helpers + run_module).

Reconciles the complete global / database / table / column privilege set of a
single CDB account. The module compares the current normalized set against the
desired set and, when they differ, calls ModifyAccountPrivileges with the exact
target set. ``state=absent`` revokes every managed privilege (writes the empty
target) without deleting the account.

The fake CDB client stores an API-shaped privilege state and mutates it on
ModifyAccountPrivileges so the post-write refetch converges.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import cdb_account_privilege as mod
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
    "ColumnPrivileges": [],
}


def _state(**overrides):
    """API-shaped current privilege state (raw, unsorted is fine)."""
    state = copy.deepcopy(EMPTY_STATE)
    state.update(copy.deepcopy(overrides))
    return state


def _params(**overrides):
    """Module parameters pre-filled from the argument spec defaults."""
    params = {
        "state": "present",
        "instance_id": "cdb-abc",
        "username": "app",
        "host": "%",
        "global_privileges": [],
        "database_privileges": [],
        "table_privileges": [],
        "column_privileges": [],
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


class FakeCdbClient(object):
    """In-memory CdbClient stand-in storing one account's privilege state.

    DescribeAccountPrivileges returns a :class:`FakeResource` so the module's
    ``response._serialize(allow_none=True)`` read path works; the write
    operation rebuilds the state from the request's wanted privilege lists so
    the post-write refetch converges.
    """

    def __init__(self, state=None):
        self.state = copy.deepcopy(state if state is not None else EMPTY_STATE)
        self.calls = []

    def _record(self, name, request):
        self.calls.append((name, request))
        return request

    def DescribeAccountPrivileges(self, request):
        self._record("DescribeAccountPrivileges", request)
        return FakeResource(copy.deepcopy(self.state))

    def ModifyAccountPrivileges(self, request):
        self._record("ModifyAccountPrivileges", request)
        self.state = {
            "GlobalPrivileges": sorted(request.GlobalPrivileges or []),
            "DatabasePrivileges": [
                {"Database": d.Database, "Privileges": sorted(d.Privileges)} for d in (request.DatabasePrivileges or [])
            ],
            "TablePrivileges": [
                {"Database": t.Database, "Table": t.Table, "Privileges": sorted(t.Privileges)}
                for t in (request.TablePrivileges or [])
            ],
            "ColumnPrivileges": [
                {"Database": c.Database, "Table": c.Table, "Column": c.Column, "Privileges": sorted(c.Privileges)}
                for c in (request.ColumnPrivileges or [])
            ],
        }
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
    column_privileges=[{"database": "orders", "table": "line_items", "column": "id", "privileges": ["select"]}],
)

FULL_STATE = _state(
    GlobalPrivileges=["INSERT", "SELECT"],
    DatabasePrivileges=[{"Database": "orders", "Privileges": ["insert", "select"]}],
    TablePrivileges=[{"Database": "orders", "Table": "line_items", "Privileges": ["select"]}],
    ColumnPrivileges=[{"Database": "orders", "Table": "line_items", "Column": "id", "Privileges": ["select"]}],
)


# ---------------------------------------------------------------------------
# request-builder / helper tests
# ---------------------------------------------------------------------------


def test_describe_request_fields():
    request = mod.describe_request(FakeModels(), _params())
    assert request.InstanceId == "cdb-abc"
    assert request.User == "app"
    assert request.Host == "%"


def test_objects_sorts_privileges_and_maps_identity():
    values = [{"database": "db2", "privileges": ["b", "a"]}, {"database": "db1", "privileges": ["c"]}]
    items = mod._objects(FakeModels(), "DatabasePrivilege", values, (("database", "Database"), ("privileges", "Privileges")))
    assert [item.Database for item in items] == ["db2", "db1"]
    assert items[0].Privileges == ["a", "b"]
    assert items[1].Privileges == ["c"]


def test_modify_request_builds_full_target():
    models = FakeModels()
    wanted = mod.desired(dict(_params(), **FULL_PARAMS))
    request = mod.modify_request(models, _params(), wanted)
    assert request.InstanceId == "cdb-abc"
    assert len(request.Accounts) == 1
    assert request.Accounts[0].User == "app"
    assert request.Accounts[0].Host == "%"
    assert request.GlobalPrivileges == ["INSERT", "SELECT"]
    db = request.DatabasePrivileges[0]
    assert db.Database == "orders"
    assert db.Privileges == ["insert", "select"]
    table = request.TablePrivileges[0]
    assert table.Database == "orders"
    assert table.Table == "line_items"
    column = request.ColumnPrivileges[0]
    assert column.Database == "orders"
    assert column.Table == "line_items"
    assert column.Column == "id"
    assert column.Privileges == ["select"]


def test_normalize_items_plain_dicts_sorted_by_identity():
    values = [
        {"Database": "db2", "Privileges": ["b", "a"]},
        {"Database": "db1", "Privileges": ["c"]},
    ]
    result = mod._normalize_items(values, ("Database",))
    assert result == [
        {"database": "db1", "privileges": ["c"]},
        {"database": "db2", "privileges": ["a", "b"]},
    ]


def test_normalize_items_serializable_objects():
    values = [
        FakeResource({"Database": "db1", "Privileges": ["b", "a"]}),
        FakeResource({"Database": "db0", "Table": "t1", "Privileges": []}),
    ]
    result = mod._normalize_items(values, ("Database", "Table"))
    assert result == [
        {"database": "db0", "table": "t1", "privileges": []},
        {"database": "db1", "table": None, "privileges": ["a", "b"]},
    ]


def test_normalize_items_none_returns_empty():
    assert mod._normalize_items(None, ("Database",)) == []


def test_normalize_empty_state():
    assert mod.normalize({}) == {
        "GlobalPrivileges": [],
        "DatabasePrivileges": [],
        "TablePrivileges": [],
        "ColumnPrivileges": [],
    }


def test_normalize_full_state_sorts_everything():
    result = mod.normalize(
        {
            "GlobalPrivileges": ["INSERT", "SELECT"],
            "DatabasePrivileges": [{"Database": "orders", "Privileges": ["insert", "select"]}],
            "TablePrivileges": [{"Database": "b", "Table": "t2", "Privileges": []}, {"Database": "a", "Table": "t1", "Privileges": ["x"]}],
            "ColumnPrivileges": [
                {"Database": "a", "Table": "t1", "Column": "c2", "Privileges": []},
                {"Database": "a", "Table": "t1", "Column": "c1", "Privileges": ["x"]},
            ],
        }
    )
    assert result["GlobalPrivileges"] == ["INSERT", "SELECT"]
    assert result["DatabasePrivileges"] == [{"database": "orders", "privileges": ["insert", "select"]}]
    assert result["TablePrivileges"] == [
        {"database": "a", "table": "t1", "privileges": ["x"]},
        {"database": "b", "table": "t2", "privileges": []},
    ]
    assert result["ColumnPrivileges"] == [
        {"database": "a", "table": "t1", "column": "c1", "privileges": ["x"]},
        {"database": "a", "table": "t1", "column": "c2", "privileges": []},
    ]


def test_desired_builds_normalized_target():
    result = mod.desired(dict(_params(), **FULL_PARAMS))
    assert result == mod.normalize(
        {
            "GlobalPrivileges": ["SELECT", "INSERT"],
            "DatabasePrivileges": [{"Database": "orders", "Privileges": ["select", "insert"]}],
            "TablePrivileges": [{"Database": "orders", "Table": "line_items", "Privileges": ["select"]}],
            "ColumnPrivileges": [{"Database": "orders", "Table": "line_items", "Column": "id", "Privileges": ["select"]}],
        }
    )


def test_fetch_describes_and_normalizes(monkeypatch):
    fake = FakeCdbClient(FULL_STATE)
    _make_module(monkeypatch, fake)
    module = FakeModule()
    result = mod.fetch(module, fake, FakeModels(), _params())
    assert result["GlobalPrivileges"] == ["INSERT", "SELECT"]
    assert result["DatabasePrivileges"] == [{"database": "orders", "privileges": ["insert", "select"]}]
    assert module.sdk_calls[0][0].__name__ == "DescribeAccountPrivileges"


# ---------------------------------------------------------------------------
# run_module main-path tests
# ---------------------------------------------------------------------------


def test_present_noop_when_current_matches(monkeypatch):
    fake = FakeCdbClient(FULL_STATE)
    _make_module(monkeypatch, fake)
    _run_args(**FULL_PARAMS)
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["privileges"]["GlobalPrivileges"] == ["INSERT", "SELECT"]
    assert not any(c[0] == "ModifyAccountPrivileges" for c in fake.calls)


def test_present_change_writes_and_refetches(monkeypatch):
    fake = FakeCdbClient()
    _make_module(monkeypatch, fake)
    _run_args(**FULL_PARAMS)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["privileges"]["GlobalPrivileges"] == ["INSERT", "SELECT"]
    assert result["privileges"]["DatabasePrivileges"] == [{"database": "orders", "privileges": ["insert", "select"]}]
    write = [c for c in fake.calls if c[0] == "ModifyAccountPrivileges"]
    assert len(write) == 1
    assert write[0][1].GlobalPrivileges == ["INSERT", "SELECT"]
    describes = [c for c in fake.calls if c[0] == "DescribeAccountPrivileges"]
    assert len(describes) == 2  # fetch + refetch


def test_present_drift_revokes_removed_privilege(monkeypatch):
    seeded = _state(
        GlobalPrivileges=["SELECT", "INSERT", "UPDATE"],
        DatabasePrivileges=[{"Database": "orders", "Privileges": ["select", "insert", "update"]}],
    )
    fake = FakeCdbClient(seeded)
    _make_module(monkeypatch, fake)
    _run_args(global_privileges=["SELECT"], database_privileges=[{"database": "orders", "privileges": ["select"]}])
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["privileges"]["GlobalPrivileges"] == ["SELECT"]
    assert result["privileges"]["DatabasePrivileges"] == [{"database": "orders", "privileges": ["select"]}]


def test_absent_revokes_all_privileges(monkeypatch):
    fake = FakeCdbClient(FULL_STATE)
    _make_module(monkeypatch, fake)
    _run_args(state="absent", **FULL_PARAMS)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["privileges"] == {
        "GlobalPrivileges": [],
        "DatabasePrivileges": [],
        "TablePrivileges": [],
        "ColumnPrivileges": [],
    }
    write = [c for c in fake.calls if c[0] == "ModifyAccountPrivileges"]
    assert len(write) == 1
    request = write[0][1]
    assert request.GlobalPrivileges == []
    assert request.DatabasePrivileges == []
    assert request.TablePrivileges == []
    assert request.ColumnPrivileges == []


def test_absent_noop_when_already_empty(monkeypatch):
    fake = FakeCdbClient()
    _make_module(monkeypatch, fake)
    _run_args(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert not any(c[0] == "ModifyAccountPrivileges" for c in fake.calls)


def test_check_mode_change_reports_diff_without_write(monkeypatch):
    fake = FakeCdbClient()
    _make_module(monkeypatch, fake)
    _run_args(_ansible_check_mode=True, **FULL_PARAMS)
    result = run(mod.run_module)
    assert result["changed"] is True
    # empty containers are stripped from diff payloads by comparison._normalize
    assert result["diff"]["before"] == {}
    assert result["diff"]["after"]["GlobalPrivileges"] == ["INSERT", "SELECT"]
    assert result["diff"]["after"]["DatabasePrivileges"] == [
        {"database": "orders", "privileges": ["insert", "select"]}
    ]
    # check mode keeps the pre-change state and never writes
    assert result["privileges"]["GlobalPrivileges"] == []
    assert not any(c[0] == "ModifyAccountPrivileges" for c in fake.calls)


def test_check_mode_noop_still_reports_changed_false(monkeypatch):
    fake = FakeCdbClient(FULL_STATE)
    _make_module(monkeypatch, fake)
    _run_args(_ansible_check_mode=True, **FULL_PARAMS)
    result = run(mod.run_module)
    assert result["changed"] is False


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
    _run_args(**FULL_PARAMS)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert payload["error"] == "service exploded"
