"""Unit tests for the mariadb_backup_config write module (run_module flows).

Reconciles MariaDB automatic backup retention, execution window, weekdays and
archive transition. There is no ``state`` parameter and no lookup loop: a
single per-instance ``DescribeBackupConfigs`` response is normalized and
compared against the desired target; on drift a ``ModifyBackupConfigs`` call
converges it and a fresh describe reports the effective state.

Scenario matrix:

* matching configuration is idempotent (regardless of stored weekday order)
* retention/window/weekday drift triggers a modify
* drift in check mode is a dry run
* parameter validation failures are reported
* SDK failure maps to the standard error envelope
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import mariadb_backup_config as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

CONFIG = {
    "InstanceId": "tdsql-abc123",
    "Days": 7,
    "StartBackupTime": "22:00",
    "EndBackupTime": "23:59",
    "WeekDays": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"],
    "ArchiveDays": -1,
}


def _config(**overrides):
    item = copy.deepcopy(CONFIG)
    item.update(overrides)
    return item


def _params(**overrides):
    params = {
        "instance_id": "tdsql-abc123",
        "retention_days": 7,
        "start_time": "22:00",
        "end_time": "23:59",
        "weekdays": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"],
        "archive_after_days": -1,
    }
    params.update(overrides)
    return params


def _run_args(**overrides):
    return module_args(**_params(**overrides))


class FakeMariadbClient(object):
    """In-memory MariaDB client holding one per-instance backup configuration."""

    def __init__(self, config=None):
        self.config = _config(**(config or {}))
        self.calls = []

    def DescribeBackupConfigs(self, request):
        self.calls.append(("DescribeBackupConfigs", request))
        return FakeResource(self.config)

    def ModifyBackupConfigs(self, request):
        self.calls.append(("ModifyBackupConfigs", request))
        self.config["Days"] = request.Days
        self.config["StartBackupTime"] = request.StartBackupTime
        self.config["EndBackupTime"] = request.EndBackupTime
        self.config["WeekDays"] = list(request.WeekDays or [])
        self.config["ArchiveDays"] = request.ArchiveDays
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
# matching configuration
# ---------------------------------------------------------------------------


def test_matching_config_is_idempotent(monkeypatch):
    fake = FakeMariadbClient()
    _make_module(monkeypatch, fake)
    _run_args()
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["backup_config"]["retention_days"] == 7
    assert result["backup_config"]["start_time"] == "22:00"
    assert result["backup_config"]["end_time"] == "23:59"
    assert result["backup_config"]["archive_after_days"] == -1
    assert [name for name, unused in fake.calls] == ["DescribeBackupConfigs"]


def test_unsorted_stored_weekdays_still_idempotent(monkeypatch):
    # Normalization orders weekdays by the canonical WEEKDAYS list, so a
    # service that returns them unsorted does not look like drift.
    fake = FakeMariadbClient({"WeekDays": ["Sunday", "Monday", "Wednesday"]})
    _make_module(monkeypatch, fake)
    _run_args(weekdays=["Wednesday", "Monday", "Sunday"])
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["backup_config"]["weekdays"] == ["Monday", "Wednesday", "Sunday"]


# ---------------------------------------------------------------------------
# drift handling
# ---------------------------------------------------------------------------


def test_retention_drift_modifies(monkeypatch):
    fake = FakeMariadbClient({"Days": 30})
    _make_module(monkeypatch, fake)
    _run_args()
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["backup_config"]["retention_days"] == 7
    ops = [name for name, unused in fake.calls]
    assert ops == ["DescribeBackupConfigs", "ModifyBackupConfigs", "DescribeBackupConfigs"]
    modify = [request for name, request in fake.calls if name == "ModifyBackupConfigs"][0]
    assert modify.InstanceId == "tdsql-abc123"
    assert modify.Days == 7
    assert modify.ArchiveDays == -1


def test_window_and_archive_drift_modifies(monkeypatch):
    fake = FakeMariadbClient({"StartBackupTime": "02:00", "EndBackupTime": "03:00", "ArchiveDays": 90})
    _make_module(monkeypatch, fake)
    _run_args(start_time="23:00", end_time="23:30", archive_after_days=180)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["backup_config"]["start_time"] == "23:00"
    assert result["backup_config"]["end_time"] == "23:30"
    assert result["backup_config"]["archive_after_days"] == 180


def test_weekday_drift_modifies(monkeypatch):
    fake = FakeMariadbClient()
    _make_module(monkeypatch, fake)
    _run_args(weekdays=["Monday", "Wednesday", "Friday"])
    result = run(mod.run_module)
    assert result["changed"] is True
    modify = [request for name, request in fake.calls if name == "ModifyBackupConfigs"][0]
    assert modify.WeekDays == ["Monday", "Wednesday", "Friday"]
    assert result["backup_config"]["weekdays"] == ["Monday", "Wednesday", "Friday"]


def test_drift_in_check_mode_is_dry_run(monkeypatch):
    fake = FakeMariadbClient({"Days": 30})
    _make_module(monkeypatch, fake)
    _run_args(_ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["backup_config"]["retention_days"] == 30  # drifted current shown
    assert result["diff"]["after"]["retention_days"] == 7
    assert "ModifyBackupConfigs" not in [name for name, unused in fake.calls]


# ---------------------------------------------------------------------------
# validation and failure paths
# ---------------------------------------------------------------------------


def test_invalid_retention_days_fails_validation(monkeypatch):
    _make_module(monkeypatch, FakeMariadbClient())
    _run_args(retention_days=0)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "retention_days" in exc.value.args[0]["msg"]


def test_invalid_archive_days_fails_validation(monkeypatch):
    _make_module(monkeypatch, FakeMariadbClient())
    _run_args(archive_after_days=0)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "archive_after_days" in exc.value.args[0]["msg"]


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    _make_module(monkeypatch, _BoomClient())
    _run_args()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert payload["error"] == "service exploded"


def test_main_entrypoint_runs_module(monkeypatch):
    fake = FakeMariadbClient()
    _make_module(monkeypatch, fake)
    _run_args()
    result = run(mod.main)
    assert result["changed"] is False
    assert result["backup_config"]["retention_days"] == 7
