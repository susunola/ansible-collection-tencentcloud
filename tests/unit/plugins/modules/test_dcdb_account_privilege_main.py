"""Unit tests for the dcdb_account_privilege write module (run_module flows).

The module reconciles the complete privilege set for one database/table/
column scope and grants the empty set for ``state=absent``. The fake DCDB
client mutates a privilege store so the post-write describe refetch
converges.

Scenario matrix:

* argument validation (missing instance/username, scope-shape guards)
* no-op when the current privilege set already matches
* granting a wider set (drift) and clearing via ``state=absent``
* check-mode dry run
* the blanket SDK failure path
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import dcdb_account_privilege as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    module_args,
    run,
)

INSTANCE_ID = "tdsqlshard-xxxxxxxx"


def _args(**overrides):
    params = {
        "instance_id": INSTANCE_ID,
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


class FakeDcdbClient(object):
    """In-memory DCDB client with a mutable scoped privilege store."""

    def __init__(self, privileges=None):
        self.privileges = sorted(set(privileges or []))
        self.calls = []

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def DescribeAccountPrivileges(self, request):
        self._record("DescribeAccountPrivileges", request)
        return SimpleNamespace(Privileges=list(self.privileges))

    def GrantAccountPrivileges(self, request):
        self._record("GrantAccountPrivileges", request)
        self.privileges = sorted(set(getattr(request, "Privileges", None) or []))
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


def test_global_scope_requires_star_objects(monkeypatch):
    fake = FakeDcdbClient()
    _make_module(monkeypatch, fake)
    _args(database="*", object_type="table")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "global scope requires" in exc.value.args[0]["msg"]
    assert fake.calls == []


def test_database_scope_requires_star_object_and_column(monkeypatch):
    fake = FakeDcdbClient()
    _make_module(monkeypatch, fake)
    _args(database="orders", object_type="*", object_name="events")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "database scope requires" in exc.value.args[0]["msg"]
    assert fake.calls == []


def test_idempotent_when_privileges_match(monkeypatch):
    fake = FakeDcdbClient(privileges=["SELECT", "INSERT"])
    _make_module(monkeypatch, fake)
    _args()
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["privileges"] == ["INSERT", "SELECT"]
    assert [c for c, unused in fake.calls] == ["DescribeAccountPrivileges"]


def test_grant_expanded_privileges(monkeypatch):
    fake = FakeDcdbClient(privileges=["SELECT"])
    _make_module(monkeypatch, fake)
    _args(privileges=["SELECT", "INSERT", "UPDATE", "UPDATE"])
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["privileges"] == ["INSERT", "SELECT", "UPDATE"]
    grant_call = next((c, r) for c, r in fake.calls if c == "GrantAccountPrivileges")
    assert grant_call[1].InstanceId == INSTANCE_ID
    assert grant_call[1].DbName == "orders"
    assert grant_call[1].Type == "table"
    assert grant_call[1].Object == "events"
    assert grant_call[1].Privileges == ["INSERT", "SELECT", "UPDATE"]


def test_absent_revokes_all_privileges(monkeypatch):
    fake = FakeDcdbClient(privileges=["SELECT", "INSERT"])
    _make_module(monkeypatch, fake)
    _args(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["privileges"] == []
    assert fake.privileges == []
    grant_call = next((c, r) for c, r in fake.calls if c == "GrantAccountPrivileges")
    assert grant_call[1].Privileges == []


def test_grant_check_mode_is_dry_run(monkeypatch):
    fake = FakeDcdbClient(privileges=["SELECT"])
    _make_module(monkeypatch, fake)
    _args(_ansible_check_mode=True, privileges=["SELECT", "INSERT"])
    result = run(mod.run_module)
    assert result["changed"] is True
    assert "GrantAccountPrivileges" not in [c for c, unused in fake.calls]
    assert fake.privileges == ["SELECT"]


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeAccountPrivileges(self, request):
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
# legacy helper regression tests (folded from test_dcdb_account_privilege.py)
# ---------------------------------------------------------------------------


def test_privilege_request_maps_scope_and_deduplicates_privileges():
    params = {
        "instance_id": "dcdb-1",
        "username": "app",
        "host": "%",
        "database": "orders",
        "object_type": "table",
        "object_name": "events",
        "column": "*",
    }
    value = mod.request(FakeModels(), "GrantAccountPrivilegesRequest", params, ["UPDATE", "SELECT", "SELECT"])
    assert value.InstanceId == "dcdb-1"
    assert (value.DbName, value.Type, value.Object, value.ColName) == ("orders", "table", "events", "*")
    assert value.Privileges == ["SELECT", "UPDATE"]
