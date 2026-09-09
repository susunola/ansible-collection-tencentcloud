"""Unit tests for the sqlserver_backup_config write module (run_module flows).

Reconciles the regular data/log backup schedule, execution hour, mode and
retention of a SQL Server instance. Backup configuration is a per-instance
singleton; the module resolves the instance through ``DescribeDBInstances``
and fails when the requested ``instance_id`` is not returned. Weekly backups
carry a weekday cycle, daily backups do not.

Scenario matrix:

* matching daily configuration is idempotent
* matching weekly configuration is idempotent (string backup times parsed)
* retention/hour drift triggers a modify
* drift in check mode is a dry run
* an unknown instance id fails the lookup
* parameter validation failures are reported
* SDK failure maps to the standard error envelope
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import sqlserver_backup_config as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

INSTANCE = {
    "InstanceId": "mssql-abc123",
    "Region": "ap-guangzhou",
    "Name": "orders-db",
    "BackupCycleType": "daily",
    "BackupTime": 3,
    "BackupCycle": [],
    "BackupModel": "master_pkg",
    "BackupSaveDays": 7,
}


def _instance(**overrides):
    item = copy.deepcopy(INSTANCE)
    item.update(overrides)
    return item


def _daily_args(**overrides):
    params = {
        "instance_id": "mssql-abc123",
        "backup_type": "daily",
        "backup_hour": 3,
        "backup_cycle": [],
        "backup_model": "master_pkg",
        "retention_days": 7,
    }
    params.update(overrides)
    return module_args(**params)


def _weekly_args(**overrides):
    params = {
        "instance_id": "mssql-abc123",
        "backup_type": "weekly",
        "backup_hour": 3,
        "backup_cycle": [1, 3, 5],
        "backup_model": "master_pkg",
        "retention_days": 30,
    }
    params.update(overrides)
    return module_args(**params)


class FakeSqlserverClient(object):
    """In-memory SQL Server client listing instances the module searches."""

    def __init__(self, instances=None):
        self.instances = [copy.deepcopy(i) for i in (instances or [_instance()])]
        self.calls = []

    def DescribeDBInstances(self, request):
        self.calls.append(("DescribeDBInstances", request))
        return SimpleNamespace(DBInstances=[FakeResource(i) for i in self.instances])

    def ModifyBackupStrategy(self, request):
        self.calls.append(("ModifyBackupStrategy", request))
        for item in self.instances:
            if item.get("InstanceId") == request.InstanceId:
                item["BackupCycleType"] = request.BackupType
                item["BackupTime"] = request.BackupTime
                item["BackupCycle"] = sorted(request.BackupCycle or [])
                item["BackupModel"] = request.BackupModel
                item["BackupSaveDays"] = request.BackupSaveDays
        return SimpleNamespace(RequestId="req-fake")


class _BoomClient(object):
    """Every SDK call raises so the wrapped SDK failure path is reached."""

    def __getattr__(self, name):
        def boom(*args, **kwargs):
            raise RuntimeError("service exploded")

        return boom


def _make_module(monkeypatch, fake):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (FakeModels(), SimpleNamespace(SqlserverClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


# ---------------------------------------------------------------------------
# matching configuration
# ---------------------------------------------------------------------------


def test_matching_daily_config_is_idempotent(monkeypatch):
    fake = FakeSqlserverClient(instances=[_instance()])
    _make_module(monkeypatch, fake)
    _daily_args()
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["backup_config"]["InstanceId"] == "mssql-abc123"
    assert result["backup_config"]["BackupModel"] == "master_pkg"
    assert [name for name, unused in fake.calls] == ["DescribeDBInstances"]


def test_matching_weekly_config_is_idempotent(monkeypatch):
    # BackupTime arrives as "03:00"; the module parses the leading hour.
    fake = FakeSqlserverClient(
        instances=[_instance(BackupCycleType="weekly", BackupTime="03:00", BackupCycle=[1, 3, 5], BackupSaveDays=30)]
    )
    _make_module(monkeypatch, fake)
    _weekly_args(backup_cycle=[5, 3, 1])  # unsorted request still matches
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["backup_config"]["BackupCycleType"] == "weekly"
    assert result["backup_config"]["BackupCycle"] == [1, 3, 5]


def test_other_instances_in_response_are_skipped(monkeypatch):
    fake = FakeSqlserverClient(instances=[_instance(InstanceId="mssql-other"), _instance()])
    _make_module(monkeypatch, fake)
    _daily_args()
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["backup_config"]["InstanceId"] == "mssql-abc123"


# ---------------------------------------------------------------------------
# drift handling
# ---------------------------------------------------------------------------


def test_daily_drift_modifies(monkeypatch):
    fake = FakeSqlserverClient(instances=[_instance(BackupSaveDays=30, BackupModel="slave_no_pkg")])
    _make_module(monkeypatch, fake)
    _daily_args()
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["backup_config"]["BackupSaveDays"] == 7
    ops = [name for name, unused in fake.calls]
    assert ops == ["DescribeDBInstances", "ModifyBackupStrategy", "DescribeDBInstances"]
    modify = [request for name, request in fake.calls if name == "ModifyBackupStrategy"][0]
    assert modify.InstanceId == "mssql-abc123"
    assert modify.BackupDay == 1
    assert modify.BackupCycle is None
    assert modify.BackupModel == "master_pkg"


def test_weekly_drift_modifies(monkeypatch):
    fake = FakeSqlserverClient(instances=[_instance(BackupCycleType="weekly", BackupCycle=[1, 2, 3], BackupSaveDays=7)])
    _make_module(monkeypatch, fake)
    _weekly_args()
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["backup_config"]["BackupCycle"] == [1, 3, 5]
    modify = [request for name, request in fake.calls if name == "ModifyBackupStrategy"][0]
    assert modify.BackupDay is None
    assert modify.BackupCycle == [1, 3, 5]


def test_drift_in_check_mode_is_dry_run(monkeypatch):
    fake = FakeSqlserverClient(instances=[_instance(BackupSaveDays=30)])
    _make_module(monkeypatch, fake)
    _daily_args(_ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["backup_config"]["BackupSaveDays"] == 30  # drifted current shown
    assert result["diff"]["after"]["BackupSaveDays"] == 7
    assert "ModifyBackupStrategy" not in [name for name, unused in fake.calls]


# ---------------------------------------------------------------------------
# lookup and validation failures
# ---------------------------------------------------------------------------


def test_unknown_instance_fails_lookup(monkeypatch):
    fake = FakeSqlserverClient(instances=[_instance(InstanceId="mssql-other")])
    _make_module(monkeypatch, fake)
    _daily_args(instance_id="mssql-ghost")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "SQL Server instance was not found"
    assert payload["instance_id"] == "mssql-ghost"


def test_invalid_backup_hour_fails_validation(monkeypatch):
    _make_module(monkeypatch, FakeSqlserverClient())
    _daily_args(backup_hour=24)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "backup_hour" in exc.value.args[0]["msg"]


def test_invalid_weekly_cycle_fails_validation(monkeypatch):
    _make_module(monkeypatch, FakeSqlserverClient())
    _weekly_args(backup_cycle=[1])
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "backup_cycle" in exc.value.args[0]["msg"]


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    _make_module(monkeypatch, _BoomClient())
    _daily_args()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert payload["error"] == "service exploded"


def test_main_entrypoint_runs_module(monkeypatch):
    fake = FakeSqlserverClient(instances=[_instance()])
    _make_module(monkeypatch, fake)
    _daily_args()
    result = run(mod.main)
    assert result["changed"] is False
    assert result["backup_config"]["InstanceId"] == "mssql-abc123"
