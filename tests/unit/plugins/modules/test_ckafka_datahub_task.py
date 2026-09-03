"""Unit tests for the ckafka_datahub_task write module (roadmap #57 lever 1).

Hand-finished after scripts/generate_module_test_skeleton.py: covers the
_deserialize model builder, scrub/project normalization, every request
builder, the detail/find helpers (including ResourceNotFound mapping) and all
present/absent/check-mode/pause-resume/immutable reconcile paths.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import ckafka_datahub_task as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeResource,
    module_args,
    run,
)

SRC = {"Type": "MYSQL", "MySQLParam": {"Resource": "resource-8b0a1c2d", "Database": "orders", "Table": "*"}}
TGT = {"Type": "TOPIC", "TopicParam": {"Resource": "1250000000-orders"}}

WRITE_OPS = (
    "CreateDatahubTask",
    "ModifyDatahubTask",
    "PauseDatahubTask",
    "ResumeDatahubTask",
    "DeleteDatahubTask",
)


class _NotFoundError(Exception):
    """Stand-in for the SDK's ResourceNotFound exception."""

    def get_code(self):
        return "ResourceNotFound"


class _DeserializeModel(object):
    """SDK model stand-in supporting _deserialize/_serialize round-trips."""

    def _deserialize(self, value):
        self._data = copy.deepcopy(value)
        return self

    def _serialize(self, allow_none=True):
        return copy.deepcopy(getattr(self, "_data", {}))


class FakeCkafkaModels(object):
    """Any model name resolves to a fresh _DeserializeModel subclass."""

    def __getattr__(self, name):
        return type(name, (_DeserializeModel,), {})


def _task(**overrides):
    """API-shaped task dict matching the module defaults."""
    task = {
        "TaskId": "task-8b0a1c2d",
        "TaskName": "mysql-orders-to-datahub",
        "TaskType": "SOURCE",
        "SourceResource": copy.deepcopy(SRC),
        "TargetResource": copy.deepcopy(TGT),
        "TransformParam": {},
        "TransformsParam": {},
        "SchemaId": None,
        "Description": "",
        "TaskMax": 1,
        "SyncThrottleLimit": 20,
        "AutoExpandFlag": True,
        "Status": 1,
    }
    task.update(overrides)
    return task


def _params(**overrides):
    """Module parameters pre-filled from the argument spec (base params included)."""
    params = {
        "state": "present",
        "task_id": None,
        "name": "mysql-orders-to-datahub",
        "task_type": "SOURCE",
        "source_resource": copy.deepcopy(SRC),
        "target_resource": copy.deepcopy(TGT),
        "transform": None,
        "transforms": None,
        "schema_id": None,
        "description": "",
        "desired_status": "running",
        "tasks_max": 1,
        "sync_throttle_limit": 20,
        "auto_expand": True,
        "retries": 5,
        "waiter_delay": 5,
        "waiter_timeout": 120,
    }
    params.update(overrides)
    return params


def _run_args(**extra):
    """module_args() pre-filled with every module parameter."""
    args = dict(_params())
    args.update(extra)
    return module_args(**args)


class FakeModule(object):
    """Minimal stand-in for helpers that need sdk_call / fail_json."""

    def __init__(self, params=None):
        self.params = params or _params()
        self.sdk_calls = []

    def sdk_call(self, operation, request):
        self.sdk_calls.append((operation, request))
        return operation(request)

    def fail_json(self, **kwargs):
        raise AnsibleFailJson(kwargs)


class FakeCkafkaClient(object):
    """In-memory CkafkaClient stand-in.

    Stores API-shaped task dicts. DescribeDatahubTask on an unknown id raises
    the ResourceNotFound stand-in so the module's idempotent detail() path is
    exercised; write ops mutate the store so refetches converge.
    """

    def __init__(self, items=None):
        self.items = [dict(item) for item in (items or [])]
        self.calls = []
        self._next_id = 1

    def _record(self, name, request):
        self.calls.append((name, request))
        return request

    def _find(self, task_id):
        for item in self.items:
            if item["TaskId"] == task_id:
                return item
        return None

    def CreateDatahubTask(self, request):
        self._record("CreateDatahubTask", request)
        task_id = "task-fake-%d" % self._next_id
        self._next_id += 1
        self.items.append(
            {
                "TaskId": task_id,
                "TaskName": request.TaskName,
                "TaskType": request.TaskType,
                "SourceResource": request.SourceResource._serialize(allow_none=True),
                "TargetResource": request.TargetResource._serialize(allow_none=True),
                "TransformParam": getattr(request, "TransformParam", None)._serialize(allow_none=True) if getattr(request, "TransformParam", None) else {},
                "TransformsParam": getattr(request, "TransformsParam", None)._serialize(allow_none=True) if getattr(request, "TransformsParam", None) else {},
                "SchemaId": getattr(request, "SchemaId", None),
                "Description": request.Description,
                "TaskMax": 1,
                "SyncThrottleLimit": 20,
                "AutoExpandFlag": True,
                "Status": 1,
            }
        )
        return SimpleNamespace(Result=SimpleNamespace(TaskId=task_id), RequestId="req-fake")

    def DeleteDatahubTask(self, request):
        self._record("DeleteDatahubTask", request)
        self.items = [item for item in self.items if item["TaskId"] != request.TaskId]
        return SimpleNamespace(RequestId="req-fake")

    def DescribeDatahubTask(self, request):
        self._record("DescribeDatahubTask", request)
        item = self._find(request.TaskId)
        if item is None:
            raise _NotFoundError("task does not exist")
        return SimpleNamespace(Result=FakeResource(dict(item)), RequestId="req-fake")

    def DescribeDatahubTasks(self, request):
        self._record("DescribeDatahubTasks", request)
        return SimpleNamespace(
            Result=SimpleNamespace(
                TaskList=[FakeResource(dict(item)) for item in self.items],
                TotalCount=len(self.items),
            ),
            RequestId="req-fake",
        )

    def ModifyDatahubTask(self, request):
        self._record("ModifyDatahubTask", request)
        item = self._find(request.TaskId)
        if item:
            item["TaskName"] = request.TaskName
            item["Description"] = request.Description
            item["TaskMax"] = request.TasksMax
            item["SyncThrottleLimit"] = request.SyncThrottleLimit
            item["AutoExpandFlag"] = request.AutoExpandFlag
        return SimpleNamespace(RequestId="req-fake")

    def PauseDatahubTask(self, request):
        self._record("PauseDatahubTask", request)
        item = self._find(request.TaskId)
        if item:
            item["Status"] = 5
        return SimpleNamespace(RequestId="req-fake")

    def ResumeDatahubTask(self, request):
        self._record("ResumeDatahubTask", request)
        item = self._find(request.TaskId)
        if item:
            item["Status"] = 1
        return SimpleNamespace(RequestId="req-fake")

    def written(self):
        return [name for name, request in self.calls if name in WRITE_OPS]


def _patch_env(monkeypatch, fake):
    """Wire the module's SDK boundary to the in-memory client."""
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(
        mod,
        "_load",
        lambda: (FakeCkafkaModels(), SimpleNamespace(CkafkaClient=object)),
    )
    monkeypatch.setattr(
        TencentCloudModule,
        "create_client",
        lambda self, client_class, endpoint: fake,
    )
    return fake


# ---------------------------------------------------------------------------
# Pure helpers: _model, scrub, project
# ---------------------------------------------------------------------------


def test_model_round_trip():
    obj = mod._model(FakeCkafkaModels(), "DatahubResource", SRC)
    assert obj._serialize(allow_none=True) == SRC


def test_model_returns_fresh_instance():
    first = mod._model(FakeCkafkaModels(), "DatahubResource", {"Type": "TOPIC"})
    second = mod._model(FakeCkafkaModels(), "DatahubResource", {"Type": "MYSQL"})
    assert first._serialize() != second._serialize()


def test_scrub_drops_sensitive_keys_nested():
    value = {
        "User": "reader",
        "Password": "hunter2",
        "MySQLParam": {"Table": "*", "PrivateKey": "key", "Keep": 1},
        "Items": [{"Token": "t", "Safe": True}],
    }
    scrubbed = mod.scrub(value)
    assert scrubbed == {
        "User": "reader",
        "MySQLParam": {"Table": "*", "Keep": 1},
        "Items": [{"Safe": True}],
    }


def test_scrub_passthrough_scalars():
    assert mod.scrub("plain") == "plain"
    assert mod.scrub(42) == 42
    assert mod.scrub(None) is None


def test_project_follows_shape():
    value = {"Type": "MYSQL", "MySQLParam": {"Database": "orders", "Extra": 1}, "ExtraTop": 99}
    shape = {"Type": object(), "MySQLParam": {"Database": object()}}
    assert mod.project(value, shape) == {"Type": "MYSQL", "MySQLParam": {"Database": "orders"}}


def test_project_list_and_scalar_shapes():
    assert mod.project(["a", "b"], [object()]) == ["a", "b"]
    assert mod.project(None, [object()]) == []
    assert mod.project("x", object()) == "x"


# ---------------------------------------------------------------------------
# Request-builder helpers
# ---------------------------------------------------------------------------


def test_describe_request():
    request = mod.describe_request(FakeCkafkaModels(), "task-8b0a1c2d")
    assert request.TaskId == "task-8b0a1c2d"


def test_list_request():
    request = mod.list_request(FakeCkafkaModels(), _params(name="orders", task_type="SINK"), offset=200)
    assert request.Limit == 100
    assert request.Offset == 200
    assert request.SearchWord == "orders"
    assert request.TaskType == "SINK"


def test_create_request_with_transform_and_schema():
    transform = {"Type": "REPLACE"}
    p = _params(transform=transform, schema_id="schema-1", description="order pipeline")
    request = mod.create_request(FakeCkafkaModels(), p)
    assert request.TaskName == "mysql-orders-to-datahub"
    assert request.TaskType == "SOURCE"
    assert request.SourceResource._serialize() == SRC
    assert request.TargetResource._serialize() == TGT
    assert request.TransformParam._serialize() == transform
    assert request.SchemaId == "schema-1"
    assert request.Description == "order pipeline"


def test_create_request_without_transform_skips_params():
    request = mod.create_request(FakeCkafkaModels(), _params(transforms=None, schema_id=None))
    assert not hasattr(request, "TransformParam")
    assert not hasattr(request, "TransformsParam")
    assert request.SchemaId is None


def test_update_request():
    p = _params(name="renamed", description="new desc", tasks_max=4, sync_throttle_limit=50, auto_expand=False)
    request = mod.update_request(FakeCkafkaModels(), p, "task-8b0a1c2d")
    assert request.TaskId == "task-8b0a1c2d"
    assert request.TaskName == "renamed"
    assert request.Description == "new desc"
    assert request.TasksMax == 4
    assert request.SyncThrottleLimit == 50
    assert request.AutoExpandFlag is False


def test_delete_pause_resume_requests():
    deleted = mod.delete_request(FakeCkafkaModels(), "task-8b0a1c2d")
    assert deleted.TaskId == "task-8b0a1c2d"
    paused = mod.pause_request(FakeCkafkaModels(), "task-8b0a1c2d")
    assert paused.TaskId == "task-8b0a1c2d"
    resumed = mod.resume_request(FakeCkafkaModels(), "task-8b0a1c2d")
    assert resumed.TaskId == "task-8b0a1c2d"


# ---------------------------------------------------------------------------
# comparable / desired
# ---------------------------------------------------------------------------


def test_comparable_status_running_and_paused():
    p = _params()
    running = mod.comparable(_task(Status=2), p)
    assert running["DesiredStatus"] == "running"
    paused = mod.comparable(_task(Status=6), p)
    assert paused["DesiredStatus"] == "paused"


def test_comparable_defaults_when_api_fields_missing():
    value = _task()
    value.pop("TaskMax")
    value.pop("SyncThrottleLimit")
    value.pop("AutoExpandFlag")
    value["Description"] = None
    comparable = mod.comparable(value, _params())
    assert comparable["TasksMax"] == 1
    assert comparable["SyncThrottleLimit"] == 20
    assert comparable["AutoExpandFlag"] is False
    assert comparable["Description"] == ""


def test_comparable_projects_scrubbed_resource_shape():
    p = _params()
    comparable = mod.comparable(_task(SourceResource=dict(SRC, Password="hunter2")), p)
    assert comparable["SourceResource"] == SRC


def test_desired_returns_full_shape():
    p = _params(
        name="renamed",
        task_type="SINK",
        schema_id="schema-9",
        description="new",
        desired_status="paused",
        tasks_max=3,
        sync_throttle_limit=30,
        auto_expand=False,
        transform={"Type": "REPLACE"},
    )
    assert mod.desired(p) == {
        "TaskName": "renamed",
        "TaskType": "SINK",
        "SourceResource": SRC,
        "TargetResource": TGT,
        "TransformParam": {"Type": "REPLACE"},
        "TransformsParam": {},
        "SchemaId": "schema-9",
        "Description": "new",
        "TasksMax": 3,
        "SyncThrottleLimit": 30,
        "AutoExpandFlag": False,
        "DesiredStatus": "paused",
    }


# ---------------------------------------------------------------------------
# detail() / find()
# ---------------------------------------------------------------------------


def test_detail_returns_scrubbed_task():
    fake = FakeCkafkaClient(items=[_task(SourceResource=dict(SRC, Password="hunter2"))])
    module = FakeModule()
    value = mod.detail(module, fake, FakeCkafkaModels(), "task-8b0a1c2d")
    assert value["TaskName"] == "mysql-orders-to-datahub"
    assert "Password" not in value["SourceResource"]


def test_detail_none_when_not_found():
    fake = FakeCkafkaClient()
    module = FakeModule()
    assert mod.detail(module, fake, FakeCkafkaModels(), "task-missing") is None


def test_find_by_task_id():
    fake = FakeCkafkaClient(items=[_task()])
    module = FakeModule()
    found = mod.find(module, fake, FakeCkafkaModels(), _params(task_id="task-8b0a1c2d"))
    assert found["TaskId"] == "task-8b0a1c2d"
    assert [name for name, request in fake.calls] == ["DescribeDatahubTask"]


def test_find_by_name_and_type():
    fake = FakeCkafkaClient(items=[_task()])
    module = FakeModule()
    found = mod.find(module, fake, FakeCkafkaModels(), _params())
    assert found["TaskId"] == "task-8b0a1c2d"
    assert [name for name, request in fake.calls] == ["DescribeDatahubTasks", "DescribeDatahubTask"]


def test_find_ignores_other_name_or_type():
    fake = FakeCkafkaClient(items=[_task()])
    module = FakeModule()
    assert mod.find(module, fake, FakeCkafkaModels(), _params(name="other-task")) is None
    assert mod.find(module, fake, FakeCkafkaModels(), _params(task_type="SINK")) is None


def test_find_none_when_empty_store():
    fake = FakeCkafkaClient()
    module = FakeModule()
    assert mod.find(module, fake, FakeCkafkaModels(), _params()) is None


def test_find_fails_on_multiple_matches():
    fake = FakeCkafkaClient(items=[_task(), _task(TaskId="task-2")])
    module = FakeModule()
    with pytest.raises(AnsibleFailJson) as exc:
        mod.find(module, fake, FakeCkafkaModels(), _params())
    assert "multiple CKafka Datahub tasks matched" in exc.value.args[0]["msg"]


# ---------------------------------------------------------------------------
# run_module main paths
# ---------------------------------------------------------------------------


def test_required_arguments_enforced(monkeypatch):
    _patch_env(monkeypatch, FakeCkafkaClient())
    module_args()
    with pytest.raises(AnsibleFailJson):
        run(mod.run_module)


def test_sdk_error_is_reported(monkeypatch):
    _patch_env(monkeypatch, _BoomClient())
    _run_args(task_id="task-8b0a1c2d")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["failed"] is True
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert payload["error"] == "service exploded"


def test_absent_noop_when_not_found(monkeypatch):
    fake = _patch_env(monkeypatch, FakeCkafkaClient())
    _run_args(state="absent", task_id="task-missing")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["datahub_task"] is None
    assert fake.written() == []


def test_absent_removes_existing(monkeypatch):
    fake = _patch_env(monkeypatch, FakeCkafkaClient(items=[_task()]))
    _run_args(state="absent", task_id="task-8b0a1c2d")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["datahub_task"] is None
    assert fake.written() == ["DeleteDatahubTask"]
    assert fake.items == []


def test_absent_check_mode_does_not_delete(monkeypatch):
    fake = _patch_env(monkeypatch, FakeCkafkaClient(items=[_task()]))
    _run_args(_ansible_check_mode=True, state="absent", task_id="task-8b0a1c2d")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["datahub_task"]["TaskId"] == "task-8b0a1c2d"
    assert fake.written() == []
    assert len(fake.items) == 1


def test_present_up_to_date_noop(monkeypatch):
    fake = _patch_env(monkeypatch, FakeCkafkaClient(items=[_task()]))
    _run_args(task_id="task-8b0a1c2d")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert fake.written() == []


def test_present_creates_running_task(monkeypatch):
    fake = _patch_env(monkeypatch, FakeCkafkaClient())
    _run_args(
        name="mysql-orders-to-datahub",
        task_type="SOURCE",
        description="order pipeline",
        desired_status="running",
        tasks_max=2,
        sync_throttle_limit=30,
        auto_expand=False,
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert fake.written() == ["CreateDatahubTask", "ModifyDatahubTask"]
    task = result["datahub_task"]
    assert task["TaskId"].startswith("task-fake-")
    assert task["TaskName"] == "mysql-orders-to-datahub"
    assert task["Description"] == "order pipeline"
    assert task["TaskMax"] == 2
    assert task["AutoExpandFlag"] is False
    assert len(fake.items) == 1
    assert fake.items[0]["Status"] == 1


def test_present_creates_then_pauses_when_desired_paused(monkeypatch):
    fake = _patch_env(monkeypatch, FakeCkafkaClient())
    _run_args(desired_status="paused")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert fake.written() == ["CreateDatahubTask", "ModifyDatahubTask", "PauseDatahubTask"]
    assert result["datahub_task"]["Status"] == 5


def test_present_renames_existing(monkeypatch):
    fake = _patch_env(monkeypatch, FakeCkafkaClient(items=[_task()]))
    _run_args(task_id="task-8b0a1c2d", name="renamed-task")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert fake.written() == ["ModifyDatahubTask"]
    assert result["datahub_task"]["TaskName"] == "renamed-task"
    assert fake.items[0]["TaskName"] == "renamed-task"


def test_present_pauses_running_task(monkeypatch):
    fake = _patch_env(monkeypatch, FakeCkafkaClient(items=[_task()]))
    _run_args(task_id="task-8b0a1c2d", desired_status="paused")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert fake.written() == ["ModifyDatahubTask", "PauseDatahubTask"]
    assert result["datahub_task"]["Status"] == 5


def test_present_resumes_paused_task(monkeypatch):
    fake = _patch_env(monkeypatch, FakeCkafkaClient(items=[_task(Status=5)]))
    _run_args(task_id="task-8b0a1c2d", desired_status="running")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert fake.written() == ["ModifyDatahubTask", "ResumeDatahubTask"]
    assert result["datahub_task"]["Status"] == 1


def test_immutable_source_resource_change_fails(monkeypatch):
    fake = _patch_env(monkeypatch, FakeCkafkaClient(items=[_task()]))
    changed_source = copy.deepcopy(SRC)
    changed_source["MySQLParam"]["Database"] = "analytics"
    _run_args(task_id="task-8b0a1c2d", source_resource=changed_source)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "Immutable fields cannot be changed" in exc.value.args[0]["msg"]
    assert fake.written() == []


def test_task_id_not_found_fails_before_create(monkeypatch):
    fake = _patch_env(monkeypatch, FakeCkafkaClient())
    _run_args(task_id="task-missing")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "task_id was not found" in exc.value.args[0]["msg"]
    assert fake.written() == []


def test_present_check_mode_create_does_not_write(monkeypatch):
    fake = _patch_env(monkeypatch, FakeCkafkaClient())
    _run_args(_ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["datahub_task"] is None
    assert fake.written() == []
    assert fake.items == []


def test_present_check_mode_update_does_not_write(monkeypatch):
    fake = _patch_env(monkeypatch, FakeCkafkaClient(items=[_task()]))
    _run_args(_ansible_check_mode=True, task_id="task-8b0a1c2d", name="renamed-task")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["datahub_task"]["TaskName"] == "mysql-orders-to-datahub"
    assert fake.written() == []


class _BoomClient(object):
    """Every SDK call raises, so the module's wrapped error path is hit."""

    def __getattr__(self, name):
        def boom(*args, **kwargs):
            raise RuntimeError("service exploded")

        return boom
