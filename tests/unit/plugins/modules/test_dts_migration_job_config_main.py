"""Unit tests for the dts_migration_job_config write module (run_module flows).

The module reconciles the configurable fields of an existing DTS migration
job (no create/delete lifecycle). The fake DTS client returns a mutable job
detail and mutates it when ``ModifyMigrationJob`` is called so re-describes
converge.

Scenario matrix:

* an already-matching job is idempotent (immediate and timed flavours,
  including name/tags)
* drift in the migration options or endpoints triggers a modify
* check mode reports the drift without calling modify
* reconfiguring a job in a non-editable status fails
* the timed run mode requires ``expected_run_time``
* the blanket SDK failure path
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import dts_migration_job_config as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

DETAIL = {
    "JobId": "dts-abcd1234",
    "Status": "checkPass",
    "JobName": "migration-job",
    "RunMode": "immediate",
    "ExpectRunTime": "",
    "SrcInfo": {"Region": "ap-guangzhou", "DatabaseType": "mysql", "InstanceId": "cdb-source"},
    "DstInfo": {"Region": "ap-shanghai", "DatabaseType": "mysql", "InstanceId": "cdb-target"},
    "MigrateOption": {"MigrateType": "fullAndIncrement", "Consistency": "afterMigration"},
    "Tags": [{"TagKey": "team", "TagValue": "data"}],
    "AutoRetryTimeRangeMinutes": 0,
}


def _detail(**overrides):
    item = copy.deepcopy(DETAIL)
    item.update(overrides)
    return item


def _args(**overrides):
    params = {
        "job_id": "dts-abcd1234",
        "name": None,
        "run_mode": "immediate",
        "expected_run_time": None,
        "source": {"Region": "ap-guangzhou", "DatabaseType": "mysql", "InstanceId": "cdb-source"},
        "destination": {"Region": "ap-shanghai", "DatabaseType": "mysql", "InstanceId": "cdb-target"},
        "migration_options": {"MigrateType": "fullAndIncrement", "Consistency": "afterMigration"},
        "tags": None,
        "auto_retry_minutes": 0,
    }
    params.update(overrides)
    return module_args(**params)


class FakeDtsClient(object):
    """In-memory DTS client mutating a single migration-job detail."""

    def __init__(self, detail):
        self.detail = copy.deepcopy(detail)
        self.calls = []

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def DescribeMigrationDetail(self, request):
        self._record("DescribeMigrationDetail", request)
        return FakeResource(self.detail)

    def DescribeMigrationJobs(self, request):
        self._record("DescribeMigrationJobs", request)
        return SimpleNamespace(
            JobList=[
                FakeResource(
                    {
                        "Tags": self.detail.get("Tags"),
                        "AutoRetryTimeRangeMinutes": self.detail.get("AutoRetryTimeRangeMinutes"),
                    }
                )
            ]
        )

    def ModifyMigrationJob(self, request):
        self._record("ModifyMigrationJob", request)
        self.detail.update(copy.deepcopy(request.__dict__))
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (FakeModels(), SimpleNamespace(DtsClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


# ---------------------------------------------------------------------------
# idempotent flows
# ---------------------------------------------------------------------------


def test_matching_job_is_idempotent(monkeypatch):
    fake = FakeDtsClient(_detail())
    _make_module(monkeypatch, fake)
    _args()
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["migration_job"]["JobId"] == "dts-abcd1234"
    ops = [c for c, unused in fake.calls]
    assert "ModifyMigrationJob" not in ops


def test_timed_job_with_name_and_tags_is_idempotent(monkeypatch):
    detail = _detail(
        JobName="migration-job",
        RunMode="timed",
        ExpectRunTime="2026-09-10 02:00:00",
    )
    fake = FakeDtsClient(detail)
    _make_module(monkeypatch, fake)
    _args(
        name="migration-job",
        run_mode="timed",
        expected_run_time="2026-09-10 02:00:00",
        tags={"team": "data"},
    )
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["migration_job"]["RunMode"] == "timed"
    ops = [c for c, unused in fake.calls]
    assert "ModifyMigrationJob" not in ops


# ---------------------------------------------------------------------------
# drift flows
# ---------------------------------------------------------------------------


def test_migration_options_drift_triggers_modify(monkeypatch):
    fake = FakeDtsClient(_detail(MigrateOption={"MigrateType": "fullIncrement", "Consistency": "afterMigration"}))
    _make_module(monkeypatch, fake)
    _args()
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["migration_job"]["MigrateOption"] == {"MigrateType": "fullAndIncrement", "Consistency": "afterMigration"}
    ops = [c for c, unused in fake.calls]
    assert "ModifyMigrationJob" in ops


def test_source_drift_triggers_modify(monkeypatch):
    fake = FakeDtsClient(_detail(SrcInfo={"Region": "ap-beijing", "DatabaseType": "mysql", "InstanceId": "cdb-old"}))
    _make_module(monkeypatch, fake)
    _args()
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["migration_job"]["SrcInfo"]["Region"] == "ap-guangzhou"
    modify_call = dict((name, request) for name, request in fake.calls)["ModifyMigrationJob"]
    assert modify_call.SrcInfo["InstanceId"] == "cdb-source"
    assert modify_call.DstInfo["Region"] == "ap-shanghai"


def test_tags_drift_triggers_modify(monkeypatch):
    fake = FakeDtsClient(_detail(Tags=[{"TagKey": "team", "TagValue": "old"}]))
    _make_module(monkeypatch, fake)
    _args(tags={"team": "data"})
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["migration_job"]["Tags"] == [{"TagKey": "team", "TagValue": "data"}]
    ops = [c for c, unused in fake.calls]
    assert "ModifyMigrationJob" in ops


def test_check_mode_reports_drift_without_modify(monkeypatch):
    fake = FakeDtsClient(_detail(MigrateOption={"MigrateType": "fullIncrement", "Consistency": "afterMigration"}))
    _make_module(monkeypatch, fake)
    _args(_ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert "diff" in result
    assert result["migration_job"]["MigrateOption"]["MigrateType"] == "fullIncrement"
    assert "ModifyMigrationJob" not in [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# guards
# ---------------------------------------------------------------------------


def test_non_editable_status_fails(monkeypatch):
    fake = FakeDtsClient(_detail(Status="running", MigrateOption={"MigrateType": "fullIncrement"}))
    _make_module(monkeypatch, fake)
    _args()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "DTS migration configuration cannot be changed in the current state" in payload["msg"]
    assert payload["status"] == "running"
    assert "ModifyMigrationJob" not in [c for c, unused in fake.calls]


def test_timed_mode_requires_expected_run_time(monkeypatch):
    fake = FakeDtsClient(_detail())
    _make_module(monkeypatch, fake)
    # expected_run_time is intentionally absent so required_if fires.
    module_args(
        job_id="dts-abcd1234",
        run_mode="timed",
        source={"Region": "ap-guangzhou", "DatabaseType": "mysql", "InstanceId": "cdb-source"},
        destination={"Region": "ap-shanghai", "DatabaseType": "mysql", "InstanceId": "cdb-target"},
        migration_options={"MigrateType": "fullAndIncrement", "Consistency": "afterMigration"},
        auto_retry_minutes=0,
    )
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "expected_run_time" in exc.value.args[0]["msg"]


# ---------------------------------------------------------------------------
# failure paths
# ---------------------------------------------------------------------------


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeMigrationDetail(self, request):
            raise Boom("connection dropped")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    _args()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]
