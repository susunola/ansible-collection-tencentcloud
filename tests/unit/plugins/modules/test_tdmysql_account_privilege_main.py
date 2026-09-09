"""Unit tests for the tdmysql_account_privilege write module (run_module flows).

The module reconciles the full privilege set of one account at global,
database or table scope; an empty privilege list revokes everything at that
scope. There is no delete lifecycle; any mismatch drives
``ModifyUserPrivileges``. The fake TDSQL client stores the effective
privilege list and mutates it on modify so re-describes converge.

Scenario matrix:

* an identical privilege set is idempotent at global / database scope
* grant drift at database and table scope triggers a modify
* an empty desired list revokes all privileges at the scope
* check mode reports the change without writing
* missing database/table arguments and duplicate privileges fail validation
* the blanket SDK failure path
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import tdmysql_account_privilege as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    module_args,
    run,
)

INSTANCE_ID = "tdsql3-abcdef12"


def _args(**overrides):
    params = {
        "instance_id": INSTANCE_ID,
        "username": "reporting",
        "host": "%",
        "scope": "global",
        "database": None,
        "table": None,
        "privileges": ["SELECT"],
    }
    params.update(overrides)
    return module_args(**params)


class FakeTdmysqlClient(object):
    """In-memory TDSQL client storing one account's privilege list."""

    def __init__(self, privileges):
        self.privileges = list(privileges)
        self.calls = []

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def DescribeUserPrivileges(self, request):
        self._record("DescribeUserPrivileges", request)
        return SimpleNamespace(Privileges=list(self.privileges))

    def ModifyUserPrivileges(self, request):
        self._record("ModifyUserPrivileges", request)
        global_privs = getattr(request, "GlobalPrivileges", None)
        if global_privs is not None:
            self.privileges = list(global_privs)
        else:
            items = getattr(request, "DatabasePrivileges", None)
            if not items:
                items = getattr(request, "TablePrivileges", None)
            self.privileges = list(items[0].Privileges) if items else []
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (FakeModels(), SimpleNamespace(TdmysqlClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


# ---------------------------------------------------------------------------
# idempotent flows
# ---------------------------------------------------------------------------


def test_global_scope_matching_set_is_idempotent(monkeypatch):
    fake = FakeTdmysqlClient(["SELECT", "INSERT"])
    _make_module(monkeypatch, fake)
    _args(privileges=["INSERT", "SELECT"])
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["privilege"]["Privileges"] == ["INSERT", "SELECT"]
    assert result["privilege"]["Scope"] == "global"
    assert result["privilege"]["Host"] == "%"
    assert "Database" not in result["privilege"]
    assert [c for c, unused in fake.calls] == ["DescribeUserPrivileges"]


def test_database_scope_matching_set_is_idempotent(monkeypatch):
    fake = FakeTdmysqlClient(["SELECT"])
    _make_module(monkeypatch, fake)
    _args(scope="database", database="analytics", privileges=["SELECT"])
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["privilege"]["Database"] == "analytics"
    assert "ModifyUserPrivileges" not in [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# drift flows
# ---------------------------------------------------------------------------


def test_database_scope_grant_drift_triggers_modify(monkeypatch):
    fake = FakeTdmysqlClient(["SELECT"])
    _make_module(monkeypatch, fake)
    _args(scope="database", database="analytics", privileges=["SELECT", "UPDATE"])
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["privilege"]["Privileges"] == ["SELECT", "UPDATE"]
    assert result["privilege"]["Database"] == "analytics"
    ops = [c for c, unused in fake.calls]
    assert ops[0] == "DescribeUserPrivileges"
    assert "ModifyUserPrivileges" in ops
    assert ops[-1] == "DescribeUserPrivileges"
    modify_call = dict((name, request) for name, request in fake.calls)["ModifyUserPrivileges"]
    assert len(modify_call.Users) == 1
    assert modify_call.Users[0].UserName == "reporting"
    assert modify_call.Users[0].Host == "%"
    assert modify_call.DatabasePrivileges[0].Database == "analytics"
    assert list(modify_call.DatabasePrivileges[0].Privileges) == ["SELECT", "UPDATE"]


def test_table_scope_grants_privileges(monkeypatch):
    fake = FakeTdmysqlClient([])
    _make_module(monkeypatch, fake)
    _args(scope="table", database="analytics", table="orders", privileges=["SELECT", "INSERT"])
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["privilege"]["Privileges"] == ["INSERT", "SELECT"]
    assert result["privilege"]["Table"] == "orders"
    assert "ModifyUserPrivileges" in [c for c, unused in fake.calls]


def test_empty_desired_set_revokes_all(monkeypatch):
    fake = FakeTdmysqlClient(["SELECT", "UPDATE"])
    _make_module(monkeypatch, fake)
    _args(scope="database", database="analytics", privileges=[])
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["privilege"]["Privileges"] == []
    assert fake.privileges == []


def test_check_mode_reports_change_without_writing(monkeypatch):
    fake = FakeTdmysqlClient(["SELECT"])
    _make_module(monkeypatch, fake)
    _args(_ansible_check_mode=True, scope="database", database="analytics", privileges=["SELECT", "UPDATE"])
    result = run(mod.run_module)
    assert result["changed"] is True
    assert "diff" in result
    assert result["privilege"]["Privileges"] == ["SELECT", "UPDATE"]
    assert "ModifyUserPrivileges" not in [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# validation guards
# ---------------------------------------------------------------------------


def test_database_scope_requires_database(monkeypatch):
    fake = FakeTdmysqlClient([])
    _make_module(monkeypatch, fake)
    _args(scope="database")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "database is required for database and table scope" in exc.value.args[0]["msg"]
    assert fake.calls == []


def test_table_scope_requires_table(monkeypatch):
    fake = FakeTdmysqlClient([])
    _make_module(monkeypatch, fake)
    _args(scope="table", database="analytics")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "table is required for table scope" in exc.value.args[0]["msg"]
    assert fake.calls == []


def test_duplicate_privileges_fail_validation(monkeypatch):
    fake = FakeTdmysqlClient([])
    _make_module(monkeypatch, fake)
    _args(privileges=["SELECT", "SELECT"])
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "privileges must not contain duplicates" in exc.value.args[0]["msg"]
    assert fake.calls == []


# ---------------------------------------------------------------------------
# failure paths
# ---------------------------------------------------------------------------


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeUserPrivileges(self, request):
            raise Boom("connection dropped")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    _args()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]
