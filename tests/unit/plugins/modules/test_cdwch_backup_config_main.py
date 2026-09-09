"""Unit tests for the cdwch_backup_config write module (run_module flows).

The module reconciles the ClickHouse backup service switch plus the
metadata/table-data schedules. The fake CDW ClickHouse client mutates an
in-memory backup state so the post-write ``describe`` refetch converges.

Scenario matrix:

* argument validation (missing required arguments)
* no-op when the switch and every managed schedule already match
* enabling a disabled instance (switch, schedule creation, dry-run check mode)
* disabling a running backup
* drift on the metadata schedule drives ``CreateBackUpSchedule``
* enabling without a COS bucket name fails
* the blanket SDK failure path
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import cdwch_backup_config as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

INSTANCE_ID = "cdwch-xxxxxxxx"


def _args(**overrides):
    params = {"instance_id": INSTANCE_ID, "enabled": True, "cos_bucket_name": "analytics-backup-1250000000"}
    params.update(overrides)
    return module_args(**params)


class FakeCdwchClient(object):
    """In-memory CDW ClickHouse client with a mutable backup configuration."""

    def __init__(self, opened=False, meta=None, data=None, tables=None):
        self.state = {
            "opened": opened,
            "meta": copy.deepcopy(meta) if meta else None,
            "data": copy.deepcopy(data) if data else None,
            "tables": [copy.deepcopy(t) for t in (tables or [])],
        }
        self.calls = []

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def DescribeBackUpSchedule(self, request):
        self._record("DescribeBackUpSchedule", request)
        state = self.state
        return SimpleNamespace(
            BackUpOpened=state["opened"],
            MetaStrategy=FakeResource(state["meta"]) if state["meta"] else None,
            DataStrategy=FakeResource(state["data"]) if state["data"] else None,
            BackUpContents=[FakeResource(t) for t in state["tables"]],
            ErrorMsg=None,
        )

    def OpenBackUp(self, request):
        self._record("OpenBackUp", request)
        self.state["opened"] = getattr(request, "OperationType", None) == "OPEN"
        return SimpleNamespace(ErrorMsg=None, RequestId="req-fake")

    def CreateBackUpSchedule(self, request):
        self._record("CreateBackUpSchedule", request)
        kind = getattr(request, "ScheduleType", None)
        item = {
            "RetainDays": getattr(request, "RetainDays", None),
            "WeekDays": getattr(request, "WeekDays", None),
            "ExecuteHour": getattr(request, "ExecuteHour", None),
        }
        if kind == "meta":
            self.state["meta"] = item
        else:
            self.state["data"] = item
            self.state["tables"] = [{"Database": t.Database, "Table": t.Table} for t in (getattr(request, "BackUpTables", None) or [])]
        return SimpleNamespace(ErrorMsg=None, RequestId="req-fake")


def _make_module(monkeypatch, fake, models=None):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (models or FakeModels(), SimpleNamespace(CdwchClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


def _full_meta():
    return {"RetainDays": 30, "WeekDays": "1,3,5", "ExecuteHour": 2}


def _full_data():
    return {"RetainDays": 14, "WeekDays": "0,6", "ExecuteHour": 3}


def test_missing_required_args_fails(monkeypatch):
    fake = FakeCdwchClient()
    _make_module(monkeypatch, fake)
    module_args()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "missing required arguments" in exc.value.args[0]["msg"]
    assert fake.calls == []


def test_idempotent_when_switch_and_schedules_match(monkeypatch):
    fake = FakeCdwchClient(opened=True, meta=_full_meta(), data=_full_data(), tables=[{"Database": "analytics", "Table": "events"}])
    _make_module(monkeypatch, fake)
    _args(
        meta_strategy={"retain_days": 30, "week_days": "1,3,5", "execute_hour": 2},
        data_strategy={"retain_days": 14, "week_days": "0,6", "execute_hour": 3},
        backup_tables=[{"Database": "analytics", "Table": "events"}],
    )
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["backup_config"]["enabled"] is True
    assert [c for c, unused in fake.calls] == ["DescribeBackUpSchedule"]


def test_enable_disabled_instance_opens_backup(monkeypatch):
    fake = FakeCdwchClient(opened=False)
    _make_module(monkeypatch, fake)
    _args(enabled=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["backup_config"]["enabled"] is True
    open_call = next((c, r) for c, r in fake.calls if c == "OpenBackUp")
    assert getattr(open_call[1], "OperationType") == "OPEN"


def test_enable_creates_initial_data_schedule(monkeypatch):
    fake = FakeCdwchClient(opened=True, tables=[])
    _make_module(monkeypatch, fake)
    _args(enabled=True, data_strategy={"retain_days": 14, "week_days": "0,6", "execute_hour": 3},
          backup_tables=[{"Database": "analytics", "Table": "events"}])
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["backup_config"]["data_strategy"]["RetainDays"] == 14
    ops = [c for c, unused in fake.calls]
    assert "CreateBackUpSchedule" in ops
    create_call = next((c, r) for c, r in fake.calls if c == "CreateBackUpSchedule")
    request = create_call[1]
    assert getattr(request, "ScheduleType") == "data"
    assert getattr(request, "OperationType") == "create"
    assert getattr(request, "BackUpTables")[0].Database == "analytics"


def test_disable_backup_closes_switch(monkeypatch):
    fake = FakeCdwchClient(opened=True, meta=_full_meta())
    _make_module(monkeypatch, fake)
    _args(enabled=False)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["backup_config"]["enabled"] is False
    close_call = next((c, r) for c, r in fake.calls if c == "OpenBackUp")
    assert getattr(close_call[1], "OperationType") == "CLOSE"


def test_meta_strategy_drift_updates_schedule(monkeypatch):
    fake = FakeCdwchClient(opened=True, meta=_full_meta())
    _make_module(monkeypatch, fake)
    _args(enabled=True, meta_strategy={"retain_days": 30, "week_days": "1,3,5", "execute_hour": 4})
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["backup_config"]["meta_strategy"]["ExecuteHour"] == 4
    update = next((c, r) for c, r in fake.calls if c == "CreateBackUpSchedule")
    assert getattr(update[1], "ScheduleType") == "meta"
    assert getattr(update[1], "OperationType") == "update"
    assert getattr(update[1], "ExecuteHour") == 4


def test_enable_check_mode_is_dry_run(monkeypatch):
    fake = FakeCdwchClient(opened=False)
    _make_module(monkeypatch, fake)
    _args(_ansible_check_mode=True, enabled=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["backup_config"] == {"enabled": True}
    assert "OpenBackUp" not in [c for c, unused in fake.calls]
    assert fake.state["opened"] is False


def test_enable_without_cos_bucket_fails(monkeypatch):
    fake = FakeCdwchClient(opened=False)
    _make_module(monkeypatch, fake)
    _args(enabled=True, cos_bucket_name=None)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "cos_bucket_name is required" in exc.value.args[0]["msg"]


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeBackUpSchedule(self, request):
            raise Boom("connection dropped")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    _args(enabled=True)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]


# ---------------------------------------------------------------------------
# legacy helper regression tests (folded from test_cdwch_backup_config.py)
# ---------------------------------------------------------------------------


def test_normalize_strategy_uses_api_fields():
    assert mod.normalize_strategy({"retain_days": 30, "week_days": "1,3", "execute_hour": 2}) == {"RetainDays": 30, "WeekDays": "1,3", "ExecuteHour": 2}


def test_normalize_strategy_skips_absent_fields():
    assert mod.normalize_strategy({"retain_days": 30}) == {"RetainDays": 30}


def test_normalize_tables_is_stable():
    assert mod.normalize_tables([{"Database": "b", "Table": "t"}, {"Database": "a", "Table": "z"}]) == [
        {"Database": "a", "Table": "z"}, {"Database": "b", "Table": "t"},
    ]


def test_normalize_tables_drops_server_computed_fields():
    assert mod.normalize_tables([{"Database": "a", "Table": "t", "TotalBytes": 42, "BackupStatus": 1}]) == [{"Database": "a", "Table": "t"}]
