"""Unit tests for the dcdb_backup_config write module (run_module flows).

The module reconciles DCDB automatic backup retention, window, weekdays and
archive transition. The fake DCDB client mutates a config store so the
post-write describe refetch converges.

Scenario matrix:

* argument validation (missing instance, out-of-range retention,
  invalid archive value)
* no-op when the normalized config already matches
* drift applies ``ModifyBackupConfigs`` and re-reads
* check-mode dry run
* the blanket SDK failure path
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import dcdb_backup_config as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

INSTANCE_ID = "tdsqlshard-xxxxxxxx"

CONFIG = {
    "Days": 30,
    "StartBackupTime": "02:00",
    "EndBackupTime": "03:00",
    "WeekDays": ["Friday", "Monday", "Wednesday"],
    "ArchiveDays": 90,
}


def _args(**overrides):
    params = {
        "instance_id": INSTANCE_ID,
        "retention_days": 30,
        "start_time": "02:00",
        "end_time": "03:00",
        "weekdays": ["Monday", "Wednesday", "Friday"],
        "archive_after_days": 90,
    }
    params.update(overrides)
    return module_args(**params)


class FakeDcdbClient(object):
    """In-memory DCDB client with a mutable backup-config store."""

    def __init__(self, config=None):
        self.config = copy.deepcopy(config) if config else None
        self.calls = []

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def DescribeBackupConfigs(self, request):
        self._record("DescribeBackupConfigs", request)
        return FakeResource(self.config or {})

    def ModifyBackupConfigs(self, request):
        self._record("ModifyBackupConfigs", request)
        self.config = {
            "Days": getattr(request, "Days", None),
            "StartBackupTime": getattr(request, "StartBackupTime", None),
            "EndBackupTime": getattr(request, "EndBackupTime", None),
            "WeekDays": list(getattr(request, "WeekDays", None) or []),
            "ArchiveDays": getattr(request, "ArchiveDays", None),
        }
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake, models=None):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (models or FakeModels(), SimpleNamespace(DcdbClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


def test_missing_instance_id_fails(monkeypatch):
    fake = FakeDcdbClient()
    _make_module(monkeypatch, fake)
    module_args()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "missing required arguments" in exc.value.args[0]["msg"]
    assert fake.calls == []


def test_retention_out_of_range_fails(monkeypatch):
    fake = FakeDcdbClient()
    _make_module(monkeypatch, fake)
    module_args(instance_id=INSTANCE_ID, retention_days=0)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "retention_days must be between 1 and 3650" in exc.value.args[0]["msg"]
    assert fake.calls == []


def test_invalid_archive_days_fails(monkeypatch):
    fake = FakeDcdbClient()
    _make_module(monkeypatch, fake)
    module_args(instance_id=INSTANCE_ID, archive_after_days=-2)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "archive_after_days must be -1 or positive" in exc.value.args[0]["msg"]
    assert fake.calls == []


def test_idempotent_when_config_matches(monkeypatch):
    fake = FakeDcdbClient(config=CONFIG)
    _make_module(monkeypatch, fake)
    _args()
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["backup_config"]["retention_days"] == 30
    assert result["backup_config"]["weekdays"] == ["Monday", "Wednesday", "Friday"]
    assert [c for c, unused in fake.calls] == ["DescribeBackupConfigs"]


def test_drift_applies_backup_config(monkeypatch):
    fake = FakeDcdbClient(config=CONFIG)
    _make_module(monkeypatch, fake)
    _args(retention_days=15, weekdays=["Monday", "Wednesday", "Friday", "Sunday"])
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["backup_config"]["retention_days"] == 15
    assert result["backup_config"]["weekdays"] == ["Monday", "Wednesday", "Friday", "Sunday"]
    modify_call = next((c, r) for c, r in fake.calls if c == "ModifyBackupConfigs")
    assert modify_call[1].Days == 15
    assert modify_call[1].WeekDays == ["Monday", "Wednesday", "Friday", "Sunday"]
    assert modify_call[1].ArchiveDays == 90


def test_drift_check_mode_is_dry_run(monkeypatch):
    fake = FakeDcdbClient(config=CONFIG)
    _make_module(monkeypatch, fake)
    _args(_ansible_check_mode=True, retention_days=15)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["backup_config"]["retention_days"] == 30
    assert "ModifyBackupConfigs" not in [c for c, unused in fake.calls]
    assert fake.config["Days"] == 30


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeBackupConfigs(self, request):
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
# legacy helper regression tests (folded from test_dcdb_backup_config.py)
# ---------------------------------------------------------------------------


def test_normalize_orders_weekdays():
    value = mod.normalize(
        {"Days": 30, "StartBackupTime": "02:00", "EndBackupTime": "03:00", "WeekDays": ["Friday", "Monday"], "ArchiveDays": -1}
    )
    assert value["weekdays"] == ["Monday", "Friday"]


def test_desired_deduplicates_weekdays():
    value = mod.desired(
        {"retention_days": 30, "start_time": "02:00", "end_time": "03:00", "weekdays": ["Monday", "Monday", "Friday"], "archive_after_days": 90}
    )
    assert value["weekdays"] == ["Monday", "Friday"]
    assert value["archive_after_days"] == 90
