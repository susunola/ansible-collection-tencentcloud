"""Unit tests for the redis_backup_config write module (run_module flows).

Reconciles backup weekdays, the daily backup time period, backup type and
retention for a Redis instance. There is no ``state`` parameter and no
lookup-by-name loop: ``DescribeAutoBackupConfig`` returns the current values
directly and, on drift, ``ModifyAutoBackupConfig`` converges the instance.
The drifted run reports the desired target (no re-describe).

Scenario matrix:

* matching configuration is idempotent
* weekday/period/type/retention drift triggers a modify
* drift in check mode is a dry run reporting the target
* SDK failure maps to the standard error envelope
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import redis_backup_config as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    module_args,
    run,
)

CONFIG = {
    "WeekDays": ["Monday", "Wednesday", "Friday"],
    "TimePeriod": "03:00-04:00",
    "AutoBackupType": 0,
    "BackupStorageDays": 30,
}


def _config(**overrides):
    item = copy.deepcopy(CONFIG)
    item.update(overrides)
    return item


def _params(**overrides):
    params = {
        "instance_id": "crs-abc123",
        "week_days": ["Monday", "Wednesday", "Friday"],
        "time_period": "03:00-04:00",
        "backup_type": 0,
        "storage_days": 30,
    }
    params.update(overrides)
    return params


def _run_args(**overrides):
    return module_args(**_params(**overrides))


def _target(p):
    return {
        "WeekDays": sorted(p["week_days"]),
        "TimePeriod": p["time_period"],
        "AutoBackupType": p["backup_type"],
        "BackupStorageDays": p["storage_days"],
    }


class FakeRedisClient(object):
    """In-memory Redis client holding one per-instance auto-backup config."""

    def __init__(self, config=None):
        self.config = _config(**(config or {}))
        self.calls = []

    def DescribeAutoBackupConfig(self, request):
        self.calls.append(("DescribeAutoBackupConfig", request))
        return SimpleNamespace(**self.config)

    def ModifyAutoBackupConfig(self, request):
        self.calls.append(("ModifyAutoBackupConfig", request))
        self.config["WeekDays"] = sorted(request.WeekDays or [])
        self.config["TimePeriod"] = request.TimePeriod
        self.config["AutoBackupType"] = request.AutoBackupType
        self.config["BackupStorageDays"] = request.BackupStorageDays
        return SimpleNamespace(RequestId="req-fake")


class _BoomClient(object):
    """Every SDK call raises so the wrapped SDK failure path is reached."""

    def __getattr__(self, name):
        def boom(*args, **kwargs):
            raise RuntimeError("service exploded")

        return boom


def _make_module(monkeypatch, fake):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (FakeModels(), SimpleNamespace(RedisClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


# ---------------------------------------------------------------------------
# matching configuration
# ---------------------------------------------------------------------------


def test_matching_config_is_idempotent(monkeypatch):
    fake = FakeRedisClient()
    _make_module(monkeypatch, fake)
    _run_args()
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["backup_config"] == _target(_params())
    assert [name for name, unused in fake.calls] == ["DescribeAutoBackupConfig"]


def test_unsorted_stored_weekdays_still_idempotent(monkeypatch):
    fake = FakeRedisClient({"WeekDays": ["Friday", "Monday", "Wednesday"]})
    _make_module(monkeypatch, fake)
    _run_args(week_days=["Wednesday", "Friday", "Monday"])
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["backup_config"]["WeekDays"] == ["Friday", "Monday", "Wednesday"]


# ---------------------------------------------------------------------------
# drift handling
# ---------------------------------------------------------------------------


def test_time_period_drift_modifies(monkeypatch):
    fake = FakeRedisClient({"TimePeriod": "02:00-03:00"})
    _make_module(monkeypatch, fake)
    _run_args()
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["backup_config"]["TimePeriod"] == "03:00-04:00"  # target reported
    ops = [name for name, unused in fake.calls]
    assert ops == ["DescribeAutoBackupConfig", "ModifyAutoBackupConfig"]
    modify = [request for name, request in fake.calls if name == "ModifyAutoBackupConfig"][0]
    assert modify.InstanceId == "crs-abc123"
    assert modify.TimePeriod == "03:00-04:00"
    assert modify.WeekDays == ["Friday", "Monday", "Wednesday"]
    assert fake.config["TimePeriod"] == "03:00-04:00"


def test_weekday_retention_type_drift_modifies(monkeypatch):
    fake = FakeRedisClient({"WeekDays": ["Monday", "Tuesday", "Wednesday"], "BackupStorageDays": 7, "AutoBackupType": 2})
    _make_module(monkeypatch, fake)
    _run_args(week_days=["Monday", "Wednesday", "Friday"], storage_days=60, backup_type=1)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["backup_config"]["WeekDays"] == ["Friday", "Monday", "Wednesday"]
    assert result["backup_config"]["AutoBackupType"] == 1
    assert result["backup_config"]["BackupStorageDays"] == 60


def test_drift_in_check_mode_is_dry_run(monkeypatch):
    fake = FakeRedisClient({"TimePeriod": "02:00-03:00"})
    _make_module(monkeypatch, fake)
    _run_args(_ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["backup_config"]["TimePeriod"] == "03:00-04:00"  # target shown in check mode
    assert result["diff"]["after"]["TimePeriod"] == "03:00-04:00"
    assert "ModifyAutoBackupConfig" not in [name for name, unused in fake.calls]


# ---------------------------------------------------------------------------
# failure paths
# ---------------------------------------------------------------------------


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    _make_module(monkeypatch, _BoomClient())
    _run_args()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert payload["error"] == "service exploded"


def test_main_entrypoint_runs_module(monkeypatch):
    fake = FakeRedisClient()
    _make_module(monkeypatch, fake)
    _run_args()
    result = run(mod.main)
    assert result["changed"] is False
    assert result["backup_config"]["WeekDays"] == ["Friday", "Monday", "Wednesday"]
