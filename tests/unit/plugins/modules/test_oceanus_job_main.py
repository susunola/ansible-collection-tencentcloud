"""Unit tests for the oceanus_job write module (run_module flows).

Drives ``run_module()`` end to end against an in-memory fake Oceanus client
whose write operations mutate the job store (and a folder tree used for
``folder_id`` resolution), so post-write refetches and waiters converge on
the first poll.

Scenario matrix:

* absent on a missing job (idempotent)
* absent on stopped/running jobs (stop-then-delete, check mode)
* creation guards (name/job_type, dedicated cluster id)
* create happy path with/without a desired runtime state and check mode
* idempotency on a matching job
* immutable engine/cluster placement drift failure
* remark/folder updates through ModifyJob
* desired runtime transitions (stop, run)
* the multiple-match guard and the SDK failure path
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import oceanus_job as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

JOB = {
    "JobId": "job-8b0a1c2d",
    "Name": "orders-stream",
    "JobType": 1,
    "ClusterType": 1,
    "ClusterId": None,
    "CuMem": 4,
    "WorkSpaceId": "space-1",
    "Status": 5,
    "Remark": None,
    "Description": None,
    "ContinueAlarm": None,
}


def _job(**overrides):
    item = copy.deepcopy(JOB)
    item.update(overrides)
    return item


def _base(**overrides):
    params = {"workspace_id": "space-1"}
    params.update(overrides)
    return module_args(**params)


class FakeOceanusClient(object):
    """In-memory Oceanus job store with a small folder tree."""

    def __init__(self, jobs=None):
        self.jobs = [copy.deepcopy(t) for t in (jobs or [])]
        self.folders = {"root": []}
        for item in self.jobs:
            self.folders.setdefault(item.get("FolderId") or "root", []).append(item["JobId"])
        self.calls = []
        self._next = 0

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def _job(self, job_id):
        for item in self.jobs:
            if item.get("JobId") == job_id:
                return item
        return None

    def DescribeJobs(self, request):
        self._record("DescribeJobs", request)
        return SimpleNamespace(
            JobSet=[FakeResource(t) for t in self.jobs],
            TotalCount=len(self.jobs),
            RequestId="req-fake",
        )

    def DescribeTreeJobs(self, request):
        self._record("DescribeTreeJobs", request)
        children = []
        for folder_id, job_ids in self.folders.items():
            if folder_id == "root":
                continue
            children.append({"Id": folder_id, "JobSet": [{"JobId": j} for j in job_ids], "Children": []})
        root = {"Id": "root", "JobSet": [{"JobId": j} for j in self.folders.get("root", [])], "Children": children}
        return FakeResource(root)

    def CreateJob(self, request):
        self._record("CreateJob", request)
        self._next += 1
        folder = getattr(request, "FolderId", None) or "root"
        item = {
            "JobId": "job-new-%03d" % self._next,
            "Name": getattr(request, "Name", None),
            "JobType": getattr(request, "JobType", None),
            "ClusterType": getattr(request, "ClusterType", 1),
            "ClusterId": getattr(request, "ClusterId", None),
            "CuMem": getattr(request, "CuMem", 4),
            "WorkSpaceId": getattr(request, "WorkSpaceId", None),
            "FolderId": folder,
            "Status": 5,
        }
        for attr in ("Remark", "Description", "FlinkVersion", "JdkVersion"):
            value = getattr(request, attr, None)
            if value is not None:
                item[attr] = value
        self.jobs.append(item)
        self.folders.setdefault(folder, []).append(item["JobId"])
        return SimpleNamespace(JobId=item["JobId"], RequestId="req-fake")

    def ModifyJob(self, request):
        self._record("ModifyJob", request)
        item = self._job(getattr(request, "JobId", None))
        if item is None:
            return SimpleNamespace(RequestId="req-fake")
        if getattr(request, "Name", None) is not None:
            item["Name"] = request.Name
        if getattr(request, "Remark", None) is not None:
            item["Remark"] = request.Remark
        if getattr(request, "Description", None) is not None:
            item["Description"] = request.Description
        if getattr(request, "ContinueAlarm", None) is not None:
            item["ContinueAlarm"] = request.ContinueAlarm
        target = getattr(request, "TargetFolderId", None)
        if target is not None:
            for jobs in self.folders.values():
                if item["JobId"] in jobs:
                    jobs.remove(item["JobId"])
            self.folders.setdefault(target, []).append(item["JobId"])
            item["FolderId"] = target
        return SimpleNamespace(RequestId="req-fake")

    def RunJobs(self, request):
        self._record("RunJobs", request)
        for description in getattr(request, "RunJobDescriptions", None) or []:
            item = self._job(getattr(description, "JobId", None))
            if item is not None:
                item["Status"] = 4
        return SimpleNamespace(RequestId="req-fake")

    def StopJobs(self, request):
        self._record("StopJobs", request)
        for description in getattr(request, "StopJobDescriptions", None) or []:
            item = self._job(getattr(description, "JobId", None))
            if item is not None:
                item["Status"] = 6 if getattr(description, "StopType", 1) == 2 else 5
        return SimpleNamespace(RequestId="req-fake")

    def DeleteJobs(self, request):
        self._record("DeleteJobs", request)
        ids = list(getattr(request, "JobIds", None) or [])
        self.jobs = [t for t in self.jobs if t.get("JobId") not in ids]
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake, models=None):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (models or FakeModels(), SimpleNamespace(OceanusClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


# ---------------------------------------------------------------------------
# absent flows
# ---------------------------------------------------------------------------


def test_absent_missing_job_is_idempotent(monkeypatch):
    fake = FakeOceanusClient(jobs=[])
    _make_module(monkeypatch, fake)
    _base(state="absent", name="ghost")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["job"] is None
    assert [c for c, unused in fake.calls] == ["DescribeJobs"]


def test_absent_stopped_job_deletes(monkeypatch):
    fake = FakeOceanusClient(jobs=[_job()])
    _make_module(monkeypatch, fake)
    _base(state="absent", job_id="job-8b0a1c2d")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert fake.jobs == []
    ops = [c for c, unused in fake.calls]
    assert "StopJobs" not in ops
    assert "DeleteJobs" in ops


def test_absent_running_job_stops_then_deletes(monkeypatch):
    fake = FakeOceanusClient(jobs=[_job(Status=4)])
    _make_module(monkeypatch, fake)
    _base(state="absent", job_id="job-8b0a1c2d")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert fake.jobs == []
    ops = [c for c, unused in fake.calls]
    assert "StopJobs" in ops
    assert "DeleteJobs" in ops


def test_absent_paused_job_stops_then_deletes(monkeypatch):
    fake = FakeOceanusClient(jobs=[_job(Status=6)])
    _make_module(monkeypatch, fake)
    _base(state="absent", job_id="job-8b0a1c2d")
    result = run(mod.run_module)
    assert result["changed"] is True
    ops = [c for c, unused in fake.calls]
    assert "StopJobs" in ops


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeOceanusClient(jobs=[_job(Status=4)])
    _make_module(monkeypatch, fake)
    _base(_ansible_check_mode=True, state="absent", job_id="job-8b0a1c2d")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert len(fake.jobs) == 1
    assert "DeleteJobs" not in [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# creation flows
# ---------------------------------------------------------------------------


def test_create_requires_name_and_job_type(monkeypatch):
    fake = FakeOceanusClient(jobs=[])
    _make_module(monkeypatch, fake)
    _base(state="present", name="orders-stream")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "name and job_type are required" in exc.value.args[0]["msg"]


def test_create_dedicated_requires_cluster_id(monkeypatch):
    fake = FakeOceanusClient(jobs=[])
    _make_module(monkeypatch, fake)
    _base(state="present", name="orders-stream", job_type=1, cluster_type=2)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "cluster_id is required for a dedicated Oceanus job" in exc.value.args[0]["msg"]


def test_create_job(monkeypatch):
    fake = FakeOceanusClient(jobs=[])
    _make_module(monkeypatch, fake)
    _base(
        state="present",
        name="orders-stream",
        job_type=1,
        cluster_type=1,
        flink_version="Flink-1.17",
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["job"]["Name"] == "orders-stream"
    assert result["job"]["Status"] == 5
    assert result["job"]["CuMem"] == 4
    assert len(fake.jobs) == 1
    ops = [c for c, unused in fake.calls]
    assert ops[0] == "DescribeJobs"
    assert "CreateJob" in ops


def test_create_job_desired_running(monkeypatch):
    fake = FakeOceanusClient(jobs=[])
    _make_module(monkeypatch, fake)
    _base(
        state="present",
        name="orders-stream",
        job_type=1,
        cluster_type=1,
        desired_status="running",
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["job"]["Status"] == 4
    ops = [c for c, unused in fake.calls]
    assert "RunJobs" in ops


def test_create_job_in_folder(monkeypatch):
    fake = FakeOceanusClient(jobs=[])
    _make_module(monkeypatch, fake)
    _base(
        state="present",
        name="orders-stream",
        job_type=1,
        cluster_type=1,
        folder_id="folder-1",
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["job"]["FolderId"] == "folder-1"
    assert "DescribeTreeJobs" in [c for c, unused in fake.calls]


def test_create_check_mode_is_dry_run(monkeypatch):
    fake = FakeOceanusClient(jobs=[])
    _make_module(monkeypatch, fake)
    _base(
        _ansible_check_mode=True,
        state="present",
        name="orders-stream",
        job_type=1,
        cluster_type=1,
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["job"]["Name"] == "orders-stream"
    assert result["job"]["Status"] == 5
    assert fake.jobs == []
    assert "CreateJob" not in [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# existing-job flows
# ---------------------------------------------------------------------------


def test_existing_job_no_drift_is_idempotent(monkeypatch):
    fake = FakeOceanusClient(jobs=[_job()])
    _make_module(monkeypatch, fake)
    _base(state="present", name="orders-stream", job_type=1, cluster_type=1)
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["job"]["JobId"] == "job-8b0a1c2d"


def test_immutable_placement_drift_fails(monkeypatch):
    fake = FakeOceanusClient(jobs=[_job()])
    _make_module(monkeypatch, fake)
    _base(state="present", job_id="job-8b0a1c2d", job_type=2)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "immutable" in payload["msg"]
    assert "JobType" in payload["immutable_drift"]


def test_update_remark(monkeypatch):
    fake = FakeOceanusClient(jobs=[_job()])
    _make_module(monkeypatch, fake)
    _base(state="present", job_id="job-8b0a1c2d", remark="billing pipeline")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["job"]["Remark"] == "billing pipeline"
    ops = [c for c, unused in fake.calls]
    assert "ModifyJob" in ops


def test_update_move_folder(monkeypatch):
    fake = FakeOceanusClient(jobs=[_job()])
    _make_module(monkeypatch, fake)
    _base(state="present", job_id="job-8b0a1c2d", folder_id="folder-9")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["job"]["FolderId"] == "folder-9"
    ops = [c for c, unused in fake.calls]
    assert "ModifyJob" in ops
    assert "DescribeTreeJobs" in ops


def test_stop_running_job(monkeypatch):
    fake = FakeOceanusClient(jobs=[_job(Status=4)])
    _make_module(monkeypatch, fake)
    _base(state="present", job_id="job-8b0a1c2d", desired_status="stopped")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["job"]["Status"] == 5
    ops = [c for c, unused in fake.calls]
    assert "StopJobs" in ops


def test_pause_and_resume_job(monkeypatch):
    fake = FakeOceanusClient(jobs=[_job(Status=4)])
    _make_module(monkeypatch, fake)
    _base(state="present", job_id="job-8b0a1c2d", desired_status="paused")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["job"]["Status"] == 6
    _base(state="present", job_id="job-8b0a1c2d", desired_status="running")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["job"]["Status"] == 4


def test_status_unchanged_is_idempotent(monkeypatch):
    fake = FakeOceanusClient(jobs=[_job(Status=5)])
    _make_module(monkeypatch, fake)
    _base(state="present", job_id="job-8b0a1c2d", desired_status="stopped")
    result = run(mod.run_module)
    assert result["changed"] is False


def test_multiple_matches_fail(monkeypatch):
    fake = FakeOceanusClient(jobs=[_job(), _job(JobId="job-dup")])
    _make_module(monkeypatch, fake)
    _base(state="present", name="orders-stream")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "specify job_id" in exc.value.args[0]["msg"]


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class ExplodingClient(object):
        def DescribeJobs(self, request):
            raise RuntimeError("connection dropped")

    _make_module(monkeypatch, ExplodingClient())
    _base(state="present", name="orders-stream")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]


# ---------------------------------------------------------------------------
# legacy helper regression tests (folded from test_oceanus_job.py)
# ---------------------------------------------------------------------------


def test_folder_for_job_finds_nested_placement():
    tree = {"Id": "root", "JobSet": [], "Children": [{"Id": "folder-a", "JobSet": [{"JobId": "job-1"}], "Children": []}]}
    assert mod._folder_for_job(tree, "job-1") == "folder-a"


def test_folder_for_job_returns_none_for_missing_job():
    assert mod._folder_for_job({"Id": "root", "JobSet": [], "Children": []}, "missing") is None


def test_describe_request_carries_pagination_offset():
    class Request:
        pass

    class Filter:
        pass

    Models = type("Models", (), {"DescribeJobsRequest": Request, "Filter": Filter})
    request = mod.describe_request(Models, {"workspace_id": "space-1", "name": "job"}, 200)
    assert (request.Offset, request.Limit, request.WorkSpaceId) == (200, 100, "space-1")
