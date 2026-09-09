"""Unit tests for the tdmysql_maintenance_window write module (run_module flows).

The module reconciles the weekly maintenance window (days + HH:MM-HH:MM
range) of a TDSQL MySQL instance. There is no delete lifecycle; a mismatch
always drives ``ModifyMaintenanceWindow``. The fake TDSQL client stores the
effective window and mutates it on modify so re-describes converge.

Scenario matrix:

* a matching window is idempotent
* a start-time / duration / weekday drift triggers a modify and normalises
  the returned window (HH:MM, HH:MM:SS and overnight inputs)
* check mode reports the change without writing
* invalid ``start_time`` and non-unique ``week_days`` fail validation before
  any SDK call
* the blanket SDK failure path
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import tdmysql_maintenance_window as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    module_args,
    run,
)

INSTANCE_ID = "tdsql3-abcdef12"
WINDOW = "02:00-04:00"
WEEKDAYS = ["Tuesday", "Saturday"]


def _args(**overrides):
    params = {
        "instance_id": INSTANCE_ID,
        "start_time": "02:00",
        "duration_hours": 2,
        "week_days": WEEKDAYS,
    }
    params.update(overrides)
    return module_args(**params)


class FakeTdmysqlClient(object):
    """In-memory TDSQL client storing one maintenance window."""

    def __init__(self, window, weekdays):
        self.window = window
        self.weekdays = list(weekdays)
        self.calls = []

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def DescribeMaintenanceWindow(self, request):
        self._record("DescribeMaintenanceWindow", request)
        return SimpleNamespace(MaintenanceWindow=self.window, WeekDays=list(self.weekdays))

    def ModifyMaintenanceWindow(self, request):
        self._record("ModifyMaintenanceWindow", request)
        # The API reports the range as StartTime..start+duration, matching the
        # window string ``DescribeMaintenanceWindow`` echoes back.
        hour = int(request.StartTime[:2])
        minute = int(request.StartTime[3:5])
        end_minutes = (hour * 60 + minute + request.Duration * 60) % 1440
        self.window = "%s-%02d:%02d" % (request.StartTime[:-3], end_minutes // 60, end_minutes % 60)
        self.weekdays = list(request.WeekDays or [])
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (FakeModels(), SimpleNamespace(TdmysqlClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


# ---------------------------------------------------------------------------
# idempotent flows
# ---------------------------------------------------------------------------


def test_matching_window_is_idempotent(monkeypatch):
    fake = FakeTdmysqlClient(WINDOW, WEEKDAYS)
    _make_module(monkeypatch, fake)
    _args()
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["maintenance_window"]["MaintenanceWindow"] == WINDOW
    assert result["maintenance_window"]["WeekDays"] == WEEKDAYS
    assert [c for c, unused in fake.calls] == ["DescribeMaintenanceWindow"]


# ---------------------------------------------------------------------------
# drift flows
# ---------------------------------------------------------------------------


def test_start_time_drift_triggers_modify(monkeypatch):
    fake = FakeTdmysqlClient("03:00-05:00", WEEKDAYS)
    _make_module(monkeypatch, fake)
    _args(start_time="02:00")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["maintenance_window"]["MaintenanceWindow"] == "02:00-04:00"
    ops = [c for c, unused in fake.calls]
    assert "ModifyMaintenanceWindow" in ops


def test_weekday_drift_triggers_modify(monkeypatch):
    fake = FakeTdmysqlClient(WINDOW, ["Monday"])
    _make_module(monkeypatch, fake)
    _args()
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["maintenance_window"]["WeekDays"] == ["Tuesday", "Saturday"]
    ops = [c for c, unused in fake.calls]
    assert "ModifyMaintenanceWindow" in ops


def test_seconds_start_time_normalises_and_updates(monkeypatch):
    # HH:MM:SS input is normalised to HH:MM and an overnight window wraps
    # past midnight; the fake reports the range the API would echo back.
    fake = FakeTdmysqlClient("00:00-01:00", WEEKDAYS)
    _make_module(monkeypatch, fake)
    _args(start_time="23:30:00", duration_hours=1)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["maintenance_window"]["MaintenanceWindow"] == "23:30-00:30"


def test_check_mode_reports_change_without_writing(monkeypatch):
    fake = FakeTdmysqlClient("03:00-05:00", WEEKDAYS)
    _make_module(monkeypatch, fake)
    _args(_ansible_check_mode=True, start_time="02:00")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert "diff" in result
    # Check mode returns the target shape directly.
    assert result["maintenance_window"]["MaintenanceWindow"] == "02:00-04:00"
    assert "ModifyMaintenanceWindow" not in [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# validation guards
# ---------------------------------------------------------------------------


def test_invalid_start_time_fails_validation(monkeypatch):
    fake = FakeTdmysqlClient(WINDOW, WEEKDAYS)
    _make_module(monkeypatch, fake)
    _args(start_time="25:00")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "start_time must use HH:MM or HH:MM:SS" in exc.value.args[0]["msg"]
    assert fake.calls == []


def test_duplicate_week_days_fail_validation(monkeypatch):
    fake = FakeTdmysqlClient(WINDOW, WEEKDAYS)
    _make_module(monkeypatch, fake)
    _args(week_days=["Tuesday", "Tuesday"])
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "week_days must be non-empty and unique" in exc.value.args[0]["msg"]
    assert fake.calls == []


def test_empty_week_days_fail_validation(monkeypatch):
    fake = FakeTdmysqlClient(WINDOW, WEEKDAYS)
    _make_module(monkeypatch, fake)
    _args(week_days=[])
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "week_days must be non-empty and unique" in exc.value.args[0]["msg"]
    assert fake.calls == []


# ---------------------------------------------------------------------------
# failure paths
# ---------------------------------------------------------------------------


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeMaintenanceWindow(self, request):
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
# legacy helper regression tests (folded from test_tdmysql_maintenance_ssl.py)
# ---------------------------------------------------------------------------


def test_normalize_start_and_expected_range_helpers():
    assert mod.normalize_start("02:30:00") == "02:30"
    assert mod.expected_range("23:30", 2) == "23:30-01:30"


def test_modify_request_sorts_weekdays_chronologically():
    class _Request(object):
        pass

    class _Models(object):
        ModifyMaintenanceWindowRequest = _Request

    params = {
        "instance_id": "db1",
        "start_time": "02:00",
        "duration_hours": 2,
        "week_days": ["Saturday", "Tuesday"],
    }
    request = mod.modify_request(_Models, params)
    assert request.StartTime == "02:00:00"
    assert request.Duration == 2
    assert request.WeekDays == ["Tuesday", "Saturday"]
