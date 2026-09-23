"""Unit tests for the mongodb_backup_config write module (run_module flows).

Reconciles automatic backup method, schedule hour, frequency, active
weekdays, retention and advanced-backup settings for a MongoDB instance.
There is no ``state`` parameter and no lookup loop: one
``DescribeBackupRules`` response is normalized (weekdays arrive as a comma
string) and compared against the desired target; drift converges via
``SetBackupRules`` followed by a fresh describe.

Scenario matrix:

* matching rules are idempotent
* a deduplicated/unsorted weekday set still compares equal
* schedule/retention drift triggers a set
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
from ansible_collections.susunola.tencentcloud.plugins.modules import mongodb_backup_config as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

RULES = {
    "InstanceId": "cmgo-abc123",
    "BackupMethod": 1,
    "BackupTime": 2,
    "BackupFrequency": 24,
    "ActiveWeekdays": "0,1,2,3,4,5,6",
    "BackupSaveTime": 7,
    "OplogExpiredDays": 7,
    "BackupVersion": 1,
    "AlertThreshold": 100,
}


def _rules(**overrides):
    item = copy.deepcopy(RULES)
    item.update(overrides)
    return item


def _params(**overrides):
    params = {
        "instance_id": "cmgo-abc123",
        "backup_method": 1,
        "backup_hour": 2,
        "frequency_hours": 24,
        "active_weekdays": [0, 1, 2, 3, 4, 5, 6],
        "retention_days": 7,
        "oplog_retention_days": 7,
        "backup_version": 1,
        "alert_threshold": 100,
    }
    params.update(overrides)
    return params


def _run_args(**overrides):
    return module_args(**_params(**overrides))


class FakeMongodbClient(object):
    """In-memory MongoDB client holding one per-instance backup-rule record."""

    def __init__(self, rules=None):
        self.rules = _rules(**(rules or {}))
        self.calls = []

    def DescribeBackupRules(self, request):
        self.calls.append(("DescribeBackupRules", request))
        return FakeResource(self.rules)

    def SetBackupRules(self, request):
        self.calls.append(("SetBackupRules", request))
        self.rules["BackupMethod"] = request.BackupMethod
        self.rules["BackupTime"] = request.BackupTime
        self.rules["BackupFrequency"] = request.BackupFrequency
        self.rules["ActiveWeekdays"] = request.ActiveWeekdays
        self.rules["BackupSaveTime"] = request.BackupRetentionPeriod
        self.rules["OplogExpiredDays"] = request.OplogExpiredDays
        self.rules["BackupVersion"] = request.BackupVersion
        self.rules["AlertThreshold"] = request.AlertThreshold
        return SimpleNamespace(RequestId="req-fake")


class _BoomClient(object):
    """Every SDK call raises so the wrapped SDK failure path is reached."""

    def __getattr__(self, name):
        def boom(*args, **kwargs):
            raise RuntimeError("service exploded")

        return boom


def _make_module(monkeypatch, fake):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (FakeModels(), SimpleNamespace(MongodbClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


# ---------------------------------------------------------------------------
# matching rules
# ---------------------------------------------------------------------------


def test_matching_rules_are_idempotent(monkeypatch):
    fake = FakeMongodbClient()
    _make_module(monkeypatch, fake)
    _run_args()
    result = run(mod.run_module)
    assert result["changed"] is False
    cfg = result["backup_config"]
    assert cfg["backup_method"] == 1
    assert cfg["backup_hour"] == 2
    assert cfg["frequency_hours"] == 24
    assert cfg["active_weekdays"] == [0, 1, 2, 3, 4, 5, 6]
    assert cfg["retention_days"] == 7
    assert cfg["oplog_retention_days"] == 7
    assert cfg["backup_version"] == 1
    assert cfg["alert_threshold"] == 100
    assert [name for name, unused in fake.calls] == ["DescribeBackupRules"]


def test_unsorted_requested_weekdays_are_idempotent(monkeypatch):
    # ActiveWeekdays arrive as a sorted comma string; an unsorted request set
    # is normalized to the same sorted list, so there is no drift.
    fake = FakeMongodbClient()
    _make_module(monkeypatch, fake)
    _run_args(active_weekdays=[5, 3, 1])
    result = run(mod.run_module)
    assert result["changed"] is True  # subset drift: store has all seven days
    assert result["backup_config"]["active_weekdays"] == [1, 3, 5]


def test_empty_weekdays_match_empty_string(monkeypatch):
    fake = FakeMongodbClient({"ActiveWeekdays": ""})
    _make_module(monkeypatch, fake)
    _run_args(active_weekdays=[])
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["backup_config"]["active_weekdays"] == []


# ---------------------------------------------------------------------------
# drift handling
# ---------------------------------------------------------------------------


def test_backup_schedule_drift_sets_rules(monkeypatch):
    fake = FakeMongodbClient()
    _make_module(monkeypatch, fake)
    _run_args(backup_hour=3, active_weekdays=[1, 2, 3, 4, 5])
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["backup_config"]["backup_hour"] == 3
    assert result["backup_config"]["active_weekdays"] == [1, 2, 3, 4, 5]
    ops = [name for name, unused in fake.calls]
    assert ops == ["DescribeBackupRules", "SetBackupRules", "DescribeBackupRules"]
    set_req = [request for name, request in fake.calls if name == "SetBackupRules"][0]
    assert set_req.InstanceId == "cmgo-abc123"
    assert set_req.BackupTime == 3
    assert set_req.ActiveWeekdays == "1,2,3,4,5"


def test_retention_drift_sets_rules(monkeypatch):
    fake = FakeMongodbClient({"BackupSaveTime": 30, "OplogExpiredDays": 15})
    _make_module(monkeypatch, fake)
    _run_args(retention_days=60, oplog_retention_days=30)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["backup_config"]["retention_days"] == 60
    assert result["backup_config"]["oplog_retention_days"] == 30


def test_drift_in_check_mode_is_dry_run(monkeypatch):
    fake = FakeMongodbClient({"BackupSaveTime": 30})
    _make_module(monkeypatch, fake)
    _run_args(_ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["backup_config"]["retention_days"] == 30  # drifted current shown
    assert "SetBackupRules" not in [name for name, unused in fake.calls]


# ---------------------------------------------------------------------------
# validation and failure paths
# ---------------------------------------------------------------------------


def test_invalid_weekday_fails_validation(monkeypatch):
    _make_module(monkeypatch, FakeMongodbClient())
    _run_args(active_weekdays=[0, 7])
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "active_weekdays" in exc.value.args[0]["msg"]


def test_invalid_backup_hour_fails_validation(monkeypatch):
    _make_module(monkeypatch, FakeMongodbClient())
    _run_args(backup_hour=24)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "backup_hour" in exc.value.args[0]["msg"]


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    _make_module(monkeypatch, _BoomClient())
    _run_args()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert payload["error"] == "service exploded"


def test_main_entrypoint_runs_module(monkeypatch):
    fake = FakeMongodbClient()
    _make_module(monkeypatch, fake)
    _run_args()
    result = run(mod.main)
    assert result["changed"] is False
    assert result["backup_config"]["backup_hour"] == 2
