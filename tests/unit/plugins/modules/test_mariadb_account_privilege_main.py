"""Unit tests for the mariadb_account_privilege write module (run_module flows).

The module reconciles the complete privilege set for one scoped account
(global, database, table, view, procedure, function or column). ``present``
grants exactly the requested names and ``absent`` grants an empty set, so a
single ``GrantAccountPrivileges`` call is the only write operation. The
scoping rules (what may be non-``*`` at each level) are validated up front.

Scenario matrix:

* matching privileges are idempotent (including absent on empty scope)
* privilege drift grants the exact desired set
* drift in check mode is a dry run
* absent clears the scope's privileges
* invalid scope combinations fail validation
* SDK failure maps to the standard error envelope
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import mariadb_account_privilege as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    module_args,
    run,
)


def _scope_args(**overrides):
    """module args for a table scope on db ``orders``."""
    params = {
        "instance_id": "tdsql-abc123",
        "username": "app",
        "host": "%",
        "database": "orders",
        "object_type": "table",
        "object_name": "events",
        "column": "*",
        "privileges": ["SELECT", "INSERT"],
    }
    params.update(overrides)
    return module_args(**params)


def _global_args(**overrides):
    params = {
        "instance_id": "tdsql-abc123",
        "username": "app",
        "database": "*",
        "object_type": "*",
        "object_name": "*",
        "column": "*",
        "privileges": ["SELECT", "INSERT", "UPDATE"],
    }
    params.update(overrides)
    return module_args(**params)


class FakeMariadbClient(object):
    """In-memory MariaDB client holding one account's privilege list."""

    def __init__(self, privileges=None):
        self.privileges = sorted(set(privileges or []))
        self.calls = []

    def DescribeAccountPrivileges(self, request):
        self.calls.append(("DescribeAccountPrivileges", request))
        return SimpleNamespace(Privileges=list(self.privileges))

    def GrantAccountPrivileges(self, request):
        self.calls.append(("GrantAccountPrivileges", request))
        self.privileges = sorted(set(getattr(request, "Privileges", None) or []))
        return SimpleNamespace(RequestId="req-fake")


class _BoomClient(object):
    """Every SDK call raises so the wrapped SDK failure path is reached."""

    def __getattr__(self, name):
        def boom(*args, **kwargs):
            raise RuntimeError("service exploded")

        return boom


def _make_module(monkeypatch, fake):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (FakeModels(), SimpleNamespace(MariadbClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


# ---------------------------------------------------------------------------
# matching privileges
# ---------------------------------------------------------------------------


def test_matching_privileges_are_idempotent(monkeypatch):
    fake = FakeMariadbClient(privileges=["INSERT", "SELECT"])
    _make_module(monkeypatch, fake)
    _scope_args()
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["privileges"] == ["INSERT", "SELECT"]
    assert [name for name, unused in fake.calls] == ["DescribeAccountPrivileges"]


def test_empty_absent_scope_is_idempotent(monkeypatch):
    fake = FakeMariadbClient(privileges=[])
    _make_module(monkeypatch, fake)
    _scope_args(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["privileges"] == []
    assert "GrantAccountPrivileges" not in [name for name, unused in fake.calls]


# ---------------------------------------------------------------------------
# privilege changes
# ---------------------------------------------------------------------------


def test_privilege_drift_grants_exact_set(monkeypatch):
    fake = FakeMariadbClient(privileges=["SELECT"])
    _make_module(monkeypatch, fake)
    _scope_args(privileges=["SELECT", "INSERT", "UPDATE"])
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["privileges"] == ["INSERT", "SELECT", "UPDATE"]
    ops = [name for name, unused in fake.calls]
    assert ops == ["DescribeAccountPrivileges", "GrantAccountPrivileges", "DescribeAccountPrivileges"]
    grant = [request for name, request in fake.calls if name == "GrantAccountPrivileges"][0]
    assert grant.Privileges == ["INSERT", "SELECT", "UPDATE"]
    assert grant.InstanceId == "tdsql-abc123"
    assert grant.UserName == "app"
    assert grant.DbName == "orders"
    assert grant.Type == "table"
    assert grant.Object == "events"


def test_drift_in_check_mode_is_dry_run(monkeypatch):
    fake = FakeMariadbClient(privileges=["SELECT"])
    _make_module(monkeypatch, fake)
    _scope_args(_ansible_check_mode=True, privileges=["SELECT", "INSERT"])
    result = run(mod.run_module)
    assert result["changed"] is True
    assert "GrantAccountPrivileges" not in [name for name, unused in fake.calls]
    assert result["diff"]["after"] == ["INSERT", "SELECT"]


def test_absent_clears_scope_privileges(monkeypatch):
    fake = FakeMariadbClient(privileges=["SELECT", "INSERT", "UPDATE"])
    _make_module(monkeypatch, fake)
    _scope_args(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["privileges"] == []
    assert fake.privileges == []
    grant = [request for name, request in fake.calls if name == "GrantAccountPrivileges"][0]
    assert grant.Privileges == []


def test_global_scope_grant(monkeypatch):
    fake = FakeMariadbClient(privileges=["SELECT"])
    _make_module(monkeypatch, fake)
    _global_args()
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["privileges"] == ["INSERT", "SELECT", "UPDATE"]
    grant = [request for name, request in fake.calls if name == "GrantAccountPrivileges"][0]
    assert grant.DbName == "*"
    assert grant.Type == "*"
    assert grant.Object == "*"


# ---------------------------------------------------------------------------
# validation and failure paths
# ---------------------------------------------------------------------------


def test_global_scope_with_non_star_object_fails(monkeypatch):
    _make_module(monkeypatch, FakeMariadbClient())
    _global_args(object_type="table")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "global scope" in exc.value.args[0]["msg"]


def test_database_scope_with_object_name_fails(monkeypatch):
    _make_module(monkeypatch, FakeMariadbClient())
    _scope_args(object_type="*", object_name="events")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "database scope" in exc.value.args[0]["msg"]


def test_column_on_non_table_scope_fails(monkeypatch):
    _make_module(monkeypatch, FakeMariadbClient())
    _scope_args(object_type="view", column="price")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "column can only be set for table scopes" in exc.value.args[0]["msg"]


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    _make_module(monkeypatch, _BoomClient())
    _scope_args()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert payload["error"] == "service exploded"


def test_main_entrypoint_runs_module(monkeypatch):
    fake = FakeMariadbClient(privileges=["INSERT", "SELECT"])
    _make_module(monkeypatch, fake)
    _scope_args()
    result = run(mod.main)
    assert result["changed"] is False
    assert result["privileges"] == ["INSERT", "SELECT"]
