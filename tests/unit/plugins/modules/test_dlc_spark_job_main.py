"""Unit tests for the dlc_spark_job write module (run_module flows).

Drives ``run_module()`` end to end against an in-memory fake DLC client whose
write operations mutate the Spark job-definition store, so the post-write
describe refetch and waiters converge immediately.

Scenario matrix:

* argument validation (executor_nums vs executor_max_nums)
* absent on a missing definition (idempotent) / allow_delete guard /
  active-task guard / check-mode dry run / real delete
* creation when missing (missing creation parameters, check mode, real
  create)
* no-op when nothing drifts
* drift updates on mutable definition fields
* the blanket ``sdk_error_payload`` failure path
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import dlc_spark_job as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

WRITE_TO_READ = {
    "AppType": "JobType",
    "DataEngine": "DataEngine",
    "AppFile": "JobFile",
    "RoleArn": "RoleArn",
    "AppDriverSize": "JobDriverSize",
    "AppExecutorSize": "JobExecutorSize",
    "AppExecutorNums": "JobExecutorNums",
    "AppExecutorMaxNumbers": "JobExecutorMaxNumbers",
    "MainClass": "MainClass",
    "AppConf": "JobConf",
    "CmdArgs": "CmdArgs",
    "MaxRetries": "JobMaxAttempts",
    "DataSource": "DataSource",
    "AppJars": "JobJars",
    "AppFiles": "JobFiles",
    "AppPythonFiles": "JobPythonFiles",
    "AppArchives": "JobArchives",
    "SparkImage": "SparkImage",
    "SparkImageVersion": "SparkImageVersion",
    "SessionId": "SessionId",
    "IsSessionStarted": "IsSessionStarted",
    "IsInherit": "IsInherit",
}

JOB = {
    "JobId": "job-8b0a1c2d",
    "JobName": "daily-customer-etl",
    "TaskNum": 0,
    "JobType": 1,
    "DataEngine": "production-spark",
    "JobFile": "cosn://analytics/jobs/customer-etl.jar",
    "RoleArn": 100000000001,
    "JobDriverSize": "medium",
    "JobExecutorSize": "large",
    "JobExecutorNums": 2,
    "IsLocal": "cos",
}


def _job(**overrides):
    item = copy.deepcopy(JOB)
    item.update(overrides)
    return item


def _base(**overrides):
    params = {"name": "daily-customer-etl"}
    params.update(overrides)
    return module_args(**params)


def _request_data(request):
    return {k: v for k, v in dict(getattr(request, "__dict__", {})).items() if not k.startswith("_")}


class FakeDlcClient(object):
    """In-memory DLC client mutating a Spark job-definition store."""

    def __init__(self, jobs=None):
        self.jobs = [copy.deepcopy(t) for t in (jobs or [])]
        self.calls = []
        self._next = 0

    def _find_by_job_id(self, job_id):
        for item in self.jobs:
            if item.get("JobId") == job_id:
                return item
        return None

    def _apply_write(self, request, item):
        for write_key, read_key in WRITE_TO_READ.items():
            value = getattr(request, write_key, None)
            if value is not None:
                item[read_key] = value

    def DescribeSparkAppJob(self, request):
        self.calls.append("DescribeSparkAppJob")
        job_id = getattr(request, "JobId", None)
        job_name = getattr(request, "JobName", None)
        item = None
        if job_id is not None:
            item = self._find_by_job_id(job_id)
        elif job_name is not None:
            for candidate in self.jobs:
                if candidate.get("JobName") == job_name:
                    item = candidate
                    break
        if item is None:
            return SimpleNamespace(IsExists=False, Job=None, RequestId="req-fake")
        return SimpleNamespace(IsExists=True, Job=FakeResource(dict(item)), RequestId="req-fake")

    def CreateSparkApp(self, request):
        self.calls.append("CreateSparkApp")
        self._next += 1
        data = _request_data(request)
        item = {"JobId": "job-new-%03d" % self._next, "JobName": data.get("AppName"), "TaskNum": 0}
        for key, value in data.items():
            if key == "AppName":
                continue
            read_key = WRITE_TO_READ.get(key, key)
            item[read_key] = value
        self.jobs.append(item)
        return SimpleNamespace(SparkAppId=item["JobId"], RequestId="req-fake")

    def ModifySparkApp(self, request):
        self.calls.append("ModifySparkApp")
        data = _request_data(request)
        item = self._find_by_job_id(data.get("SparkAppId"))
        if item is not None:
            for key, value in data.items():
                if key in ("SparkAppId", "AppName"):
                    continue
                read_key = WRITE_TO_READ.get(key, key)
                item[read_key] = value
        return SimpleNamespace(RequestId="req-fake")

    def DeleteSparkApp(self, request):
        self.calls.append("DeleteSparkApp")
        self.jobs = [t for t in self.jobs if t.get("JobName") != getattr(request, "AppName", None)]
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake, models=None):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (models or FakeModels(), SimpleNamespace(DlcClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


# ---------------------------------------------------------------------------
# argument validation
# ---------------------------------------------------------------------------


def test_executor_nums_above_max_fails(monkeypatch):
    fake = FakeDlcClient()
    _make_module(monkeypatch, fake)
    _base(executor_nums=5, executor_max_nums=2)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "executor_nums must not exceed executor_max_nums" in exc.value.args[0]["msg"]


# ---------------------------------------------------------------------------
# absent flows
# ---------------------------------------------------------------------------


def test_absent_missing_job_is_idempotent(monkeypatch):
    fake = FakeDlcClient()
    _make_module(monkeypatch, fake)
    _base(state="absent", name="ghost")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["spark_job"] is None
    assert result["spark_job_id"] is None
    assert list(fake.calls) == ["DescribeSparkAppJob"]


def test_absent_requires_allow_delete(monkeypatch):
    fake = FakeDlcClient(jobs=[_job()])
    _make_module(monkeypatch, fake)
    _base(state="absent")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "allow_delete=true" in exc.value.args[0]["msg"]


def test_absent_active_tasks_requires_allow_delete_running(monkeypatch):
    fake = FakeDlcClient(jobs=[_job(TaskNum=3)])
    _make_module(monkeypatch, fake)
    _base(state="absent", allow_delete=True)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "allow_delete_running=true" in exc.value.args[0]["msg"]


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeDlcClient(jobs=[_job()])
    _make_module(monkeypatch, fake)
    _base(_ansible_check_mode=True, state="absent", allow_delete=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert len(fake.jobs) == 1
    assert "DeleteSparkApp" not in fake.calls


def test_absent_deletes_job(monkeypatch):
    fake = FakeDlcClient(jobs=[_job()])
    _make_module(monkeypatch, fake)
    _base(state="absent", allow_delete=True, wait=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert fake.jobs == []
    ops = list(fake.calls)
    assert "DeleteSparkApp" in ops


# ---------------------------------------------------------------------------
# creation flows
# ---------------------------------------------------------------------------


def test_create_requires_creation_parameters(monkeypatch):
    fake = FakeDlcClient()
    _make_module(monkeypatch, fake)
    _base()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "creation parameters are required" in payload["msg"]
    assert "package_source" in payload["missing"]


def test_create_spark_job(monkeypatch):
    fake = FakeDlcClient()
    _make_module(monkeypatch, fake)
    _base(
        app_type=1,
        data_engine="production-spark",
        app_file="cosn://analytics/jobs/customer-etl.jar",
        role_arn=100000000001,
        driver_size="medium",
        executor_size="large",
        executor_nums=2,
        package_source="cos",
        wait=True,
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["spark_job_id"].startswith("job-new-")
    assert result["spark_job"]["JobName"] == "daily-customer-etl"
    assert result["spark_job"]["DataEngine"] == "production-spark"
    assert len(fake.jobs) == 1
    ops = list(fake.calls)
    assert ops[0] == "DescribeSparkAppJob"
    assert "CreateSparkApp" in ops


def test_create_check_mode_is_dry_run(monkeypatch):
    fake = FakeDlcClient()
    _make_module(monkeypatch, fake)
    _base(
        _ansible_check_mode=True,
        app_type=1,
        data_engine="production-spark",
        app_file="cosn://analytics/jobs/customer-etl.jar",
        role_arn=100000000001,
        driver_size="medium",
        executor_size="large",
        executor_nums=2,
        package_source="cos",
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["spark_job_id"] is None
    assert result["spark_job"]["DataEngine"] == "production-spark"
    assert fake.jobs == []
    assert "CreateSparkApp" not in fake.calls


# ---------------------------------------------------------------------------
# existing-job flows
# ---------------------------------------------------------------------------


def test_existing_job_no_drift_is_idempotent(monkeypatch):
    fake = FakeDlcClient(jobs=[_job()])
    _make_module(monkeypatch, fake)
    _base(data_engine="production-spark", package_source="cos")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["spark_job"]["JobId"] == "job-8b0a1c2d"
    ops = list(fake.calls)
    assert "ModifySparkApp" not in ops


def test_update_drift_changes_mutable_fields(monkeypatch):
    fake = FakeDlcClient(jobs=[_job()])
    _make_module(monkeypatch, fake)
    _base(data_engine="analytics-spark", package_source="cos", wait=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["spark_job"]["DataEngine"] == "analytics-spark"
    ops = list(fake.calls)
    assert "ModifySparkApp" in ops


def test_update_check_mode_is_dry_run(monkeypatch):
    fake = FakeDlcClient(jobs=[_job()])
    _make_module(monkeypatch, fake)
    _base(_ansible_check_mode=True, data_engine="analytics-spark", package_source="cos")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["spark_job"]["DataEngine"] == "analytics-spark"
    assert "ModifySparkApp" not in fake.calls


# ---------------------------------------------------------------------------
# failure paths
# ---------------------------------------------------------------------------


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeSparkAppJob(self, request):
            raise Boom("connection dropped")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    _base()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]
