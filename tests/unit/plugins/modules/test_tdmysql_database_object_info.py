# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
"""Unit tests for the tdmysql_database_object_info read module.

The module has two modes behind one entry point: without ``database`` it
lists databases, and with it, it lists the tables, views, procedures and
functions of that one database. Both modes page with an offset bounded by
``max_pages``, and the tests pin the three outcomes a caller has to
distinguish -- a complete page set, a short or empty page that ends the
walk, and ``truncated=true`` when the page budget ran out while the API
still reported matches. The mode guards are asserted with the module's own
message text and with the fake client left untouched, because a guard that
quietly stopped firing would let a caller believe a regexp had been applied
when the module never even reached the API.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import pytest

from types import SimpleNamespace

from ansible_collections.susunola.tencentcloud.plugins.modules import tdmysql_database_object_info as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

INSTANCE_ID = "tdsql3-abcd1234"

DATABASES = [
    {"DbName": "application", "Status": "online"},
    {"DbName": "reporting", "Status": "online"},
    {"DbName": "archive", "Status": "online"},
    {"DbName": "scratch", "Status": "online"},
    {"DbName": "staging", "Status": "online"},
    {"DbName": "sandbox", "Status": "online"},
]

OBJECT_KEYS = ("Tables", "Views", "Procs", "Funcs")

OBJECTS = {
    "Tables": [{"TableName": "orders"}, {"TableName": "customers"}],
    "Views": [{"ViewName": "open_orders"}],
    "Procs": [],
    "Funcs": [{"FuncName": "order_total"}],
}


def _tables(count):
    return {"Tables": [{"TableName": "table_%d" % index} for index in range(count)]}


class FakeTdmysqlClient(object):
    """Records every call and serves offset-bounded pages from an in-memory store."""

    def __init__(self, databases=None, objects=None, total_count=None):
        self.databases = [dict(item) for item in (databases if databases is not None else DATABASES)]
        source = OBJECTS if objects is None else objects
        self.objects = {key: [dict(item) for item in source.get(key, [])] for key in OBJECT_KEYS}
        self.total_count = total_count
        self.calls = []

    def DescribeDatabases(self, request):
        self.calls.append(("DescribeDatabases", request))
        offset, limit = int(request.Offset), int(request.Limit)
        page = self.databases[offset:offset + limit]
        total = len(self.databases) if self.total_count is None else self.total_count
        return FakeResource({"Databases": [FakeResource(item) for item in page],
                             "TotalCount": total,
                             "RequestId": "req-databases-%d" % offset})

    def DescribeDatabaseObjects(self, request):
        self.calls.append(("DescribeDatabaseObjects", request))
        offset, limit = int(request.Offset), int(request.Limit)
        payload = {key: [FakeResource(item) for item in corpus[offset:offset + limit]]
                   for key, corpus in self.objects.items()}
        payload["RequestId"] = "req-objects-%d" % offset
        return FakeResource(payload)

    def operations(self):
        return [name for name, _request in self.calls]

    def offsets(self, operation):
        return [int(request.Offset) for name, request in self.calls if name == operation]


class _BoomClient(object):
    """Every SDK call raises, so the module's wrapped error path is hit."""

    def __getattr__(self, name):
        def boom(*args, **kwargs):
            raise RuntimeError("service exploded")

        return boom


def _wire(monkeypatch, client):
    """Point the module at the fake client and a no-op SDK check."""
    monkeypatch.setattr(mod.TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load",
                        lambda: (FakeModels(), SimpleNamespace(TdmysqlClient=object())))
    monkeypatch.setattr(mod.TencentCloudModule, "create_client",
                        lambda self, cls, endpoint: client)


# ---------------------------------------------------------------------------
# database-list mode
# ---------------------------------------------------------------------------

def test_database_list_mode_returns_every_database(monkeypatch):
    client = FakeTdmysqlClient()
    _wire(monkeypatch, client)
    module_args(instance_id=INSTANCE_ID)
    result = run(mod.run_module)

    assert result["changed"] is False
    assert [item["DbName"] for item in result["databases"]] == [item["DbName"] for item in DATABASES]
    assert result["total_count"] == len(DATABASES)
    assert result["truncated"] is False
    assert result["request_id"] == "req-databases-0"
    assert "objects" not in result
    assert client.operations() == ["DescribeDatabases"]


def test_database_list_mode_sends_the_first_page_bounds(monkeypatch):
    client = FakeTdmysqlClient()
    _wire(monkeypatch, client)
    module_args(instance_id=INSTANCE_ID)
    run(mod.run_module)
    request = client.calls[0][1]
    assert request.InstanceId == INSTANCE_ID
    assert request.Offset == 0
    assert request.Limit == 100
    assert not hasattr(request, "DatabaseRegexp")


def test_database_list_mode_pages_until_the_total_is_reached(monkeypatch):
    client = FakeTdmysqlClient()
    _wire(monkeypatch, client)
    module_args(instance_id=INSTANCE_ID, page_size=2, max_pages=10)
    result = run(mod.run_module)

    assert client.offsets("DescribeDatabases") == [0, 2, 4]
    assert [item["DbName"] for item in result["databases"]] == [item["DbName"] for item in DATABASES]
    assert result["total_count"] == 6
    assert result["truncated"] is False
    assert result["request_id"] == "req-databases-4"
    assert {request.Limit for _name, request in client.calls} == {2}


def test_database_list_mode_truncates_when_the_page_budget_runs_out(monkeypatch):
    """A budget that stops the walk short of the reported total must say so,
    otherwise the caller cannot tell a complete list from a partial one."""
    client = FakeTdmysqlClient()
    _wire(monkeypatch, client)
    module_args(instance_id=INSTANCE_ID, page_size=2, max_pages=2)
    result = run(mod.run_module)

    assert client.offsets("DescribeDatabases") == [0, 2]
    assert [item["DbName"] for item in result["databases"]] == ["application", "reporting", "archive", "scratch"]
    assert result["total_count"] == 6
    assert result["truncated"] is True
    assert result["request_id"] == "req-databases-2"


def test_database_list_mode_stops_on_an_empty_page(monkeypatch):
    client = FakeTdmysqlClient(databases=DATABASES[:2], total_count=5)
    _wire(monkeypatch, client)
    module_args(instance_id=INSTANCE_ID, page_size=2, max_pages=5)
    result = run(mod.run_module)

    assert client.offsets("DescribeDatabases") == [0, 2]
    assert [item["DbName"] for item in result["databases"]] == ["application", "reporting"]
    assert result["total_count"] == 5
    assert result["truncated"] is False


def test_database_list_mode_with_no_databases(monkeypatch):
    client = FakeTdmysqlClient(databases=[])
    _wire(monkeypatch, client)
    module_args(instance_id=INSTANCE_ID)
    result = run(mod.run_module)

    assert result["changed"] is False
    assert result["databases"] == []
    assert result["total_count"] == 0
    assert result["truncated"] is False
    assert client.operations() == ["DescribeDatabases"]


def test_database_regexp_is_sent_in_database_list_mode(monkeypatch):
    client = FakeTdmysqlClient()
    _wire(monkeypatch, client)
    module_args(instance_id=INSTANCE_ID, database_regexp="app.*")
    run(mod.run_module)
    request = client.calls[0][1]
    assert request.DatabaseRegexp == "app.*"


# ---------------------------------------------------------------------------
# object-list mode
# ---------------------------------------------------------------------------

def test_object_list_mode_returns_the_four_object_types(monkeypatch):
    client = FakeTdmysqlClient()
    _wire(monkeypatch, client)
    module_args(instance_id=INSTANCE_ID, database="application")
    result = run(mod.run_module)

    assert result["changed"] is False
    assert result["objects"] == OBJECTS
    assert result["truncated"] is False
    assert result["request_id"] == "req-objects-0"
    assert "databases" not in result
    assert "total_count" not in result
    assert client.operations() == ["DescribeDatabaseObjects"]


def test_object_list_mode_sends_the_database_and_page_bounds(monkeypatch):
    client = FakeTdmysqlClient()
    _wire(monkeypatch, client)
    module_args(instance_id=INSTANCE_ID, database="application")
    run(mod.run_module)
    request = client.calls[0][1]
    assert request.InstanceId == INSTANCE_ID
    assert request.DbName == "application"
    assert request.Offset == 0
    assert request.Limit == 100
    assert not hasattr(request, "TableRegexp")


def test_object_list_mode_pages_until_a_short_page(monkeypatch):
    """A page shorter than page_size is the last page, so the walk ends
    without a further call even though the budget allows more."""
    client = FakeTdmysqlClient(objects=_tables(5))
    _wire(monkeypatch, client)
    module_args(instance_id=INSTANCE_ID, database="application", page_size=2)
    result = run(mod.run_module)

    assert client.offsets("DescribeDatabaseObjects") == [0, 2, 4]
    assert [item["TableName"] for item in result["objects"]["Tables"]] == [
        "table_0", "table_1", "table_2", "table_3", "table_4",
    ]
    assert result["objects"]["Views"] == []
    assert result["truncated"] is False
    assert result["request_id"] == "req-objects-4"


def test_object_list_mode_truncates_when_the_page_budget_runs_out(monkeypatch):
    client = FakeTdmysqlClient(objects=_tables(6))
    _wire(monkeypatch, client)
    module_args(instance_id=INSTANCE_ID, database="application", page_size=2, max_pages=2)
    result = run(mod.run_module)

    assert client.offsets("DescribeDatabaseObjects") == [0, 2]
    assert [item["TableName"] for item in result["objects"]["Tables"]] == [
        "table_0", "table_1", "table_2", "table_3",
    ]
    assert result["truncated"] is True
    assert result["request_id"] == "req-objects-2"


def test_object_list_mode_tolerates_absent_object_types(monkeypatch):
    """The response only carries the types the database has; the payload
    still exposes all four keys so a task can index them unconditionally."""
    client = FakeTdmysqlClient(objects=_tables(1))
    _wire(monkeypatch, client)
    module_args(instance_id=INSTANCE_ID, database="application")
    result = run(mod.run_module)

    assert set(result["objects"]) == set(OBJECT_KEYS)
    assert result["objects"]["Tables"] == [{"TableName": "table_0"}]
    assert result["objects"]["Views"] == []
    assert result["objects"]["Procs"] == []
    assert result["objects"]["Funcs"] == []


def test_table_regexp_is_sent_in_object_list_mode(monkeypatch):
    client = FakeTdmysqlClient()
    _wire(monkeypatch, client)
    module_args(instance_id=INSTANCE_ID, database="application", table_regexp="ord.*")
    run(mod.run_module)
    request = client.calls[0][1]
    assert request.DbName == "application"
    assert request.TableRegexp == "ord.*"


# ---------------------------------------------------------------------------
# guard rails
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("overrides", [
    {"page_size": 0},
    {"page_size": 101},
    {"max_pages": 0},
    {"max_pages": 1001},
])
def test_pagination_bounds_are_enforced(monkeypatch, overrides):
    client = FakeTdmysqlClient()
    _wire(monkeypatch, client)
    module_args(instance_id=INSTANCE_ID, **overrides)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert exc.value.args[0]["msg"] == "page_size and max_pages are outside supported bounds"
    assert client.calls == []


def test_database_regexp_with_a_database_is_rejected(monkeypatch):
    """``database_regexp`` filters the database list; in object mode the
    single database is already named, so accepting it would silently ignore
    the expression."""
    client = FakeTdmysqlClient()
    _wire(monkeypatch, client)
    module_args(instance_id=INSTANCE_ID, database="application", database_regexp="app.*")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert exc.value.args[0]["msg"] == "database_regexp is only valid in database-list mode"
    assert client.calls == []


def test_table_regexp_without_a_database_is_rejected(monkeypatch):
    client = FakeTdmysqlClient()
    _wire(monkeypatch, client)
    module_args(instance_id=INSTANCE_ID, table_regexp="ord.*")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert exc.value.args[0]["msg"] == "table_regexp requires database"
    assert client.calls == []


def test_instance_id_is_required(monkeypatch):
    client = FakeTdmysqlClient()
    _wire(monkeypatch, client)
    module_args()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "instance_id" in exc.value.args[0]["msg"]
    assert client.calls == []


# ---------------------------------------------------------------------------
# failures
# ---------------------------------------------------------------------------

def test_sdk_error_is_surfaced(monkeypatch):
    _wire(monkeypatch, _BoomClient())
    module_args(instance_id=INSTANCE_ID)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["failed"] is True
    assert "service exploded" in payload["error"]
    assert payload["error_kind"] == "other"
