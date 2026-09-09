"""Unit tests for the dbbrain_sql_filter write module (run_module flows).

The module reconciles one RUNNING SQL concurrency filter, re-creating it
when its concurrency changes and deleting it for ``state=absent``. The fake
DBbrain client mutates a filter store so the delete-then-create flow and the
module's convergence waiter converge immediately.

Scenario matrix:

* argument validation (missing required arguments)
* no-op when the RUNNING filter already matches
* creation flows (real and check-mode dry run)
* concurrency drift re-creates the filter (delete then create)
* deletion flows (present, absent no-op, check-mode dry run)
* the blanket SDK failure path
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import dbbrain_sql_filter as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

P = {
    "instance_id": "cdb-xxxxxxxx",
    "sql_type": "SELECT",
    "filter_key": "select,user",
    "max_concurrency": 2,
    "duration": -1,
    "session_token": "secret",
    "product": "mysql",
}


def _filter(**overrides):
    item = {"Id": 1, "SqlType": "SELECT", "OriginKeys": "select,user", "Status": "RUNNING", "MaxConcurrency": 2}
    item.update(overrides)
    return item


def _args(**overrides):
    params = dict(P)
    params.update(overrides)
    return module_args(**params)


class FakeDbbrainClient(object):
    """In-memory DBbrain client mutating a SQL-filter store."""

    def __init__(self, filters=None):
        self.filters = [copy.deepcopy(f) for f in (filters or [])]
        self._next_id = max([f.get("Id", 0) for f in self.filters] or [0]) + 1
        self.calls = []

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def DescribeSqlFilters(self, request):
        self._record("DescribeSqlFilters", request)
        return SimpleNamespace(Items=[FakeResource(f) for f in self.filters], TotalCount=len(self.filters))

    def CreateSqlFilter(self, request):
        self._record("CreateSqlFilter", request)
        item = {
            "Id": self._next_id,
            "SqlType": getattr(request, "SqlType", None),
            "OriginKeys": getattr(request, "FilterKey", None),
            "MaxConcurrency": getattr(request, "MaxConcurrency", None),
            "Status": "RUNNING",
        }
        self._next_id += 1
        self.filters.append(item)
        return SimpleNamespace(RequestId="req-fake")

    def DeleteSqlFilters(self, request):
        self._record("DeleteSqlFilters", request)
        ids = list(getattr(request, "FilterIds", None) or [])
        self.filters = [f for f in self.filters if f.get("Id") not in ids]
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake, models=None):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load_dbbrain", lambda: (models or FakeModels(), SimpleNamespace(DbbrainClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


def test_missing_required_args_fails(monkeypatch):
    fake = FakeDbbrainClient()
    _make_module(monkeypatch, fake)
    module_args()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "missing required arguments" in exc.value.args[0]["msg"]
    assert fake.calls == []


def test_idempotent_when_running_filter_matches(monkeypatch):
    fake = FakeDbbrainClient(filters=[_filter()])
    _make_module(monkeypatch, fake)
    _args()
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["sql_filter"]["MaxConcurrency"] == 2
    assert [c for c, unused in fake.calls] == ["DescribeSqlFilters"]


def test_create_sql_filter(monkeypatch):
    fake = FakeDbbrainClient()
    _make_module(monkeypatch, fake)
    _args()
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["sql_filter"]["MaxConcurrency"] == 2
    assert len(fake.filters) == 1
    create_call = next((c, r) for c, r in fake.calls if c == "CreateSqlFilter")
    assert getattr(create_call[1], "FilterKey") == "select,user"
    assert getattr(create_call[1], "SqlType") == "SELECT"
    assert getattr(create_call[1], "Product") == "mysql"


def test_create_check_mode_is_dry_run(monkeypatch):
    fake = FakeDbbrainClient()
    _make_module(monkeypatch, fake)
    _args(_ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert fake.filters == []
    assert "CreateSqlFilter" not in [c for c, unused in fake.calls]


def test_concurrency_drift_recreates_filter(monkeypatch):
    fake = FakeDbbrainClient(filters=[_filter(MaxConcurrency=2)])
    _make_module(monkeypatch, fake)
    _args(max_concurrency=5)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["sql_filter"]["MaxConcurrency"] == 5
    ops = [c for c, unused in fake.calls]
    assert "DeleteSqlFilters" in ops
    assert "CreateSqlFilter" in ops
    assert fake.filters[0]["Id"] == 2
    delete_call = next((c, r) for c, r in fake.calls if c == "DeleteSqlFilters")
    assert getattr(delete_call[1], "FilterIds") == [1]


def test_drift_check_mode_does_not_write(monkeypatch):
    fake = FakeDbbrainClient(filters=[_filter(MaxConcurrency=2)])
    _make_module(monkeypatch, fake)
    _args(_ansible_check_mode=True, max_concurrency=5)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert len(fake.filters) == 1
    assert "DeleteSqlFilters" not in [c for c, unused in fake.calls]
    assert "CreateSqlFilter" not in [c for c, unused in fake.calls]


def test_delete_sql_filter(monkeypatch):
    fake = FakeDbbrainClient(filters=[_filter()])
    _make_module(monkeypatch, fake)
    _args(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["sql_filter"] is None
    assert fake.filters == []
    delete_call = next((c, r) for c, r in fake.calls if c == "DeleteSqlFilters")
    assert getattr(delete_call[1], "FilterIds") == [1]


def test_delete_missing_filter_is_idempotent(monkeypatch):
    fake = FakeDbbrainClient()
    _make_module(monkeypatch, fake)
    _args(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["sql_filter"] is None
    assert "DeleteSqlFilters" not in [c for c, unused in fake.calls]


def test_delete_check_mode_is_dry_run(monkeypatch):
    fake = FakeDbbrainClient(filters=[_filter()])
    _make_module(monkeypatch, fake)
    _args(_ansible_check_mode=True, state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert len(fake.filters) == 1
    assert "DeleteSqlFilters" not in [c for c, unused in fake.calls]


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeSqlFilters(self, request):
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
# legacy helper regression tests (folded from test_dbbrain_sql_filter.py)
# ---------------------------------------------------------------------------


def test_request_builders_map_filter_fields():
    models = FakeModels()
    assert mod.build_create_request(models, P).FilterKey == "select,user"
    assert mod.build_describe_request(models, P).Statuses == ["RUNNING"]
    assert mod.build_delete_request(models, P, [1]).FilterIds == [1]


def test_desired_includes_max_concurrency():
    assert mod._desired(P)["MaxConcurrency"] == 2


def test_find_returns_running_filter_match():
    item = FakeResource({"SqlType": "SELECT", "OriginKeys": "select,user", "Status": "RUNNING", "Id": 1})
    assert mod._find([item], P) == {"SqlType": "SELECT", "OriginKeys": "select,user", "Status": "RUNNING", "Id": 1}
