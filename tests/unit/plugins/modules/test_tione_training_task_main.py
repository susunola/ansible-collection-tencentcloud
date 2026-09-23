"""Unit tests for the tione_training_task write module (run_module flows).

Complements ``test_tione_training_task.py`` (request-builder level) by
driving ``run_module()`` end to end against an in-memory fake TIONE client
whose write operations mutate the training-task store, so the module's
post-write ``find`` refetch and waiters converge immediately.

Scenario matrix:

* argument validation before any SDK call (missing task_id for delete,
  name/task_id requirement, >10 data_configs)
* absent on a missing task (idempotent no-op), allow_delete guard,
  active-task requires wait, check-mode dry run and the real delete path
* deletion of a running task (stop then delete)
* creation when missing (with/without mandatory creation parameters, check
  mode, waiting, state=stopped create-and-stop)
* unknown task_id for an existing run, no-drift idempotency, immutable
  drift, start/stop transitions, failed terminal state and unsupported
  transitions
* multiple-match and pagination guards in the find loop
* the blanket ``sdk_error_payload`` failure path
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import tione_training_task as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

CREATE_KEYS = (
    "Name",
    "ChargeType",
    "ResourceConfigInfos",
    "FrameworkName",
    "FrameworkVersion",
    "FrameworkEnvironment",
    "ResourceGroupId",
    "Tags",
    "ImageInfo",
    "CodePackagePath",
    "StartCmdInfo",
    "TrainingMode",
    "DataConfigs",
    "VpcId",
    "SubnetId",
    "Output",
    "LogConfig",
    "TuningParameters",
    "LogEnable",
    "Remark",
    "DataSource",
    "CallbackUrl",
    "EncodedStartCmdInfo",
    "CodeRepos",
    "ExposeNetworkConfig",
    "Envs",
    "TrainToolConfig",
    "ResourceSupplyAttribute",
    "Queues",
    "TiProjectId",
)

TASK = {
    "Id": "train-8b0a1c2d",
    "Name": "customer-support-sft",
    "Status": "RUNNING",
    "ChargeType": "POSTPAID_BY_HOUR",
    "ResourceConfigInfos": [{"Role": "WORKER", "InstanceType": "TI.GN10X.2XLARGE40.POST", "InstanceNum": 1}],
    "FrameworkName": "PYTORCH",
    "FrameworkVersion": "2.4",
    "FrameworkEnvironment": "torch2.4-py3.10-cuda12.1-gpu",
}

RESOURCE_CONFIGS = [{"Role": "WORKER", "InstanceType": "TI.GN10X.2XLARGE40.POST", "InstanceNum": 1}]


def _task(**overrides):
    item = copy.deepcopy(TASK)
    item.update(overrides)
    return item


def _plain(value):
    """Recursively unwrap FakeRequest/model stand-ins into plain data."""
    if value is None or isinstance(value, bool) or isinstance(value, (str, int, float)):
        return value
    if isinstance(value, list):
        return [_plain(item) for item in value]
    if isinstance(value, tuple):
        return [_plain(item) for item in value]
    if isinstance(value, dict):
        return {key: _plain(item) for key, item in value.items()}
    return {key: _plain(item) for key, item in vars(value).items()}


class FakeTioneClient(object):
    """In-memory TIONE client mutating a training-task store."""

    def __init__(self, tasks=None, page_size=50):
        self.tasks = [copy.deepcopy(t) for t in (tasks or [])]
        self.page_size = page_size
        self.calls = []
        self._next = 0

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def _by_id(self, task_id):
        for item in self.tasks:
            if item.get("Id") == task_id:
                return item
        return None

    def DescribeTrainingTask(self, request):
        self._record("DescribeTrainingTask", request)
        task = self._by_id(getattr(request, "Id", None))
        return SimpleNamespace(TrainingTaskDetail=FakeResource(task) if task else None, RequestId="req-fake")

    def DescribeTrainingTasks(self, request):
        self._record("DescribeTrainingTasks", request)
        name = request.Filters[0].Values[0]
        offset = getattr(request, "Offset", 0)
        matches = [item for item in self.tasks if item.get("Name") == name]
        page = matches[offset : offset + self.page_size]
        return SimpleNamespace(
            TrainingTaskSet=[FakeResource(item) for item in page],
            TotalCount=len(matches),
            RequestId="req-fake",
        )

    def CreateTrainingTask(self, request):
        self._record("CreateTrainingTask", request)
        self._next += 1
        item = {"Id": "train-new-%03d" % self._next, "Status": "RUNNING"}
        for attr in CREATE_KEYS:
            value = getattr(request, attr, None)
            if value is not None:
                item[attr] = _plain(value)
        self.tasks.append(item)
        return SimpleNamespace(Id=item["Id"], RequestId="req-fake")

    def StartTrainingTask(self, request):
        self._record("StartTrainingTask", request)
        task = self._by_id(getattr(request, "Id", None))
        if task is not None:
            task["Status"] = "RUNNING"
        return SimpleNamespace(RequestId="req-fake")

    def StopTrainingTask(self, request):
        self._record("StopTrainingTask", request)
        task = self._by_id(getattr(request, "Id", None))
        if task is not None:
            task["Status"] = "STOPPED"
        return SimpleNamespace(RequestId="req-fake")

    def DeleteTrainingTask(self, request):
        self._record("DeleteTrainingTask", request)
        task_id = getattr(request, "Id", None)
        self.tasks = [item for item in self.tasks if item.get("Id") != task_id]
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake, models=None):
    """Wire the shared monkeypatches; returns the fake client."""
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (models or FakeModels(), SimpleNamespace(TioneClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


def _creation_params(**overrides):
    params = {
        "state": "started",
        "name": "customer-support-sft",
        "charge_type": "POSTPAID_BY_HOUR",
        "resource_configs": copy.deepcopy(RESOURCE_CONFIGS),
        "framework_name": "PYTORCH",
        "framework_version": "2.4",
        "framework_environment": "torch2.4-py3.10-cuda12.1-gpu",
    }
    params.update(overrides)
    return module_args(**params)


# ---------------------------------------------------------------------------
# pre-SDK validation
# ---------------------------------------------------------------------------


def test_absent_requires_task_id(monkeypatch):
    fake = FakeTioneClient(tasks=[])
    _make_module(monkeypatch, fake)
    module_args(state="absent")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "task_id is required for safe deletion" in exc.value.args[0]["msg"]


def test_present_requires_name_or_task_id(monkeypatch):
    fake = FakeTioneClient(tasks=[])
    _make_module(monkeypatch, fake)
    module_args(state="started")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "name or task_id is required" in exc.value.args[0]["msg"]


def test_data_configs_limit_rejected(monkeypatch):
    fake = FakeTioneClient(tasks=[])
    _make_module(monkeypatch, fake)
    module_args(state="absent", task_id="train-ghost", data_configs=[{"MappingPath": "/d%d" % i} for i in range(11)])
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "at most ten" in exc.value.args[0]["msg"]


# ---------------------------------------------------------------------------
# absent flows
# ---------------------------------------------------------------------------


def test_absent_missing_task_is_idempotent(monkeypatch):
    fake = FakeTioneClient(tasks=[])
    _make_module(monkeypatch, fake)
    module_args(state="absent", task_id="train-ghost")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["training_task"] is None
    assert result["task_id"] == "train-ghost"
    assert [c for c, unused in fake.calls] == ["DescribeTrainingTask"]


def test_absent_requires_allow_delete(monkeypatch):
    fake = FakeTioneClient(tasks=[_task(Status="STOPPED")])
    _make_module(monkeypatch, fake)
    module_args(state="absent", task_id="train-8b0a1c2d")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "allow_delete=true is required" in exc.value.args[0]["msg"]


def test_absent_active_requires_wait(monkeypatch):
    fake = FakeTioneClient(tasks=[_task(Status="RUNNING")])
    _make_module(monkeypatch, fake)
    module_args(state="absent", task_id="train-8b0a1c2d", allow_delete=True, wait=False)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "wait=true is required to stop an active training task" in exc.value.args[0]["msg"]


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeTioneClient(tasks=[_task(Status="STOPPED")])
    _make_module(monkeypatch, fake)
    module_args(_ansible_check_mode=True, state="absent", task_id="train-8b0a1c2d", allow_delete=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert len(fake.tasks) == 1
    assert "DeleteTrainingTask" not in [c for c, unused in fake.calls]


def test_absent_deletes_stopped_task(monkeypatch):
    fake = FakeTioneClient(tasks=[_task(Status="STOPPED")])
    _make_module(monkeypatch, fake)
    module_args(state="absent", task_id="train-8b0a1c2d", allow_delete=True, wait=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["training_task"] is None
    assert fake.tasks == []
    ops = [c for c, unused in fake.calls]
    assert "DeleteTrainingTask" in ops
    assert "StopTrainingTask" not in ops


def test_absent_stops_then_deletes_active_task(monkeypatch):
    fake = FakeTioneClient(tasks=[_task(Status="RUNNING")])
    _make_module(monkeypatch, fake)
    module_args(state="absent", task_id="train-8b0a1c2d", allow_delete=True, wait=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert fake.tasks == []
    ops = [c for c, unused in fake.calls]
    assert "StopTrainingTask" in ops
    assert "DeleteTrainingTask" in ops


# ---------------------------------------------------------------------------
# creation flows
# ---------------------------------------------------------------------------


def test_create_requires_creation_parameters(monkeypatch):
    fake = FakeTioneClient(tasks=[])
    _make_module(monkeypatch, fake)
    module_args(state="started", name="brand-new")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "creation parameters are required" in payload["msg"]
    assert payload["missing"] == ["charge_type", "resource_configs"]


def test_create_training_task(monkeypatch):
    fake = FakeTioneClient(tasks=[])
    _make_module(monkeypatch, fake)
    _creation_params(wait=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["training_task"]["Name"] == "customer-support-sft"
    assert result["training_task"]["Status"] == "RUNNING"
    assert result["training_task"]["ChargeType"] == "POSTPAID_BY_HOUR"
    assert result["task_id"].startswith("train-new-")
    assert len(fake.tasks) == 1
    ops = [c for c, unused in fake.calls]
    assert ops[0] == "DescribeTrainingTasks"
    assert "CreateTrainingTask" in ops


def test_create_check_mode_is_dry_run(monkeypatch):
    fake = FakeTioneClient(tasks=[])
    _make_module(monkeypatch, fake)
    _creation_params(_ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["task_id"] is None
    assert result["training_task"]["Status"] == "RUNNING"
    assert fake.tasks == []
    assert "CreateTrainingTask" not in [c for c, unused in fake.calls]


def test_create_stopped_creates_then_stops(monkeypatch):
    fake = FakeTioneClient(tasks=[])
    _make_module(monkeypatch, fake)
    _creation_params(state="stopped", wait=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["training_task"]["Status"] == "STOPPED"
    ops = [c for c, unused in fake.calls]
    assert "CreateTrainingTask" in ops
    assert "StopTrainingTask" in ops
    assert fake.tasks[0]["Status"] == "STOPPED"


# ---------------------------------------------------------------------------
# existing-task flows
# ---------------------------------------------------------------------------


def test_present_unknown_task_id_fails(monkeypatch):
    fake = FakeTioneClient(tasks=[])
    _make_module(monkeypatch, fake)
    module_args(state="started", task_id="train-ghost")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "task_id does not exist" in exc.value.args[0]["msg"]


def test_existing_task_no_drift_is_idempotent(monkeypatch):
    fake = FakeTioneClient(tasks=[_task()])
    _make_module(monkeypatch, fake)
    _creation_params()
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["training_task"]["Id"] == "train-8b0a1c2d"
    assert result["task_id"] == "train-8b0a1c2d"
    assert "CreateTrainingTask" not in [c for c, unused in fake.calls]


def test_immutable_drift_fails(monkeypatch):
    fake = FakeTioneClient(tasks=[_task()])
    _make_module(monkeypatch, fake)
    module_args(state="started", task_id="train-8b0a1c2d", charge_type="PREPAID", name="customer-support-sft")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "immutable drift" in payload["msg"]
    assert "ChargeType" in payload["immutable_drift"]


def test_start_stopped_task(monkeypatch):
    fake = FakeTioneClient(tasks=[_task(Status="STOPPED")])
    _make_module(monkeypatch, fake)
    _creation_params(state="started", wait=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["training_task"]["Status"] == "RUNNING"
    ops = [c for c, unused in fake.calls]
    assert "StartTrainingTask" in ops


def test_stop_running_task(monkeypatch):
    fake = FakeTioneClient(tasks=[_task(Status="RUNNING")])
    _make_module(monkeypatch, fake)
    _creation_params(state="stopped", wait=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["training_task"]["Status"] == "STOPPED"
    ops = [c for c, unused in fake.calls]
    assert "StopTrainingTask" in ops
    assert "StartTrainingTask" not in ops


def test_failed_terminal_state_fails(monkeypatch):
    fake = FakeTioneClient(tasks=[_task(Status="FAILED")])
    _make_module(monkeypatch, fake)
    module_args(state="started", task_id="train-8b0a1c2d")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "failed terminal state" in exc.value.args[0]["msg"]


def test_unsupported_state_transition_fails(monkeypatch):
    fake = FakeTioneClient(tasks=[_task(Status="PAUSED")])
    _make_module(monkeypatch, fake)
    module_args(state="stopped", task_id="train-8b0a1c2d")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "unsupported state transition" in payload["msg"]
    assert payload["status"] == "PAUSED"


# ---------------------------------------------------------------------------
# find guards / failure paths
# ---------------------------------------------------------------------------


def test_multiple_matches_fail_across_pages(monkeypatch):
    fake = FakeTioneClient(tasks=[_task(), _task(Id="train-dup")], page_size=1)
    _make_module(monkeypatch, fake)
    _creation_params()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "Multiple TIONE training tasks matched" in exc.value.args[0]["msg"]
    assert [c for c, unused in fake.calls].count("DescribeTrainingTasks") == 2


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeTrainingTasks(self, request):
            raise Boom("connection dropped")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    _creation_params()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]
