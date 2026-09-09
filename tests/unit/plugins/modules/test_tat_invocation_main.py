"""Unit tests for the tat_invocation action module (run_module flows).

Drives ``run_module()`` end to end against an in-memory fake TAT client
whose invocation write populates the task store so the ``wait_tasks`` loop
converges immediately (every seeded task is already terminal).

Scenario matrix:

* validation guards (started identity, cancelled identity, target count,
  timeout range)
* check-mode dry run (no SDK write)
* cancellation with and without an invocation id
* starting without waiting (no task polling)
* starting and waiting for all tasks to reach a terminal state
* output redaction vs. ``include_output`` and CommandDocument stripping
* failed-task handling with ``fail_on_task_error`` on and off
* the blanket ``sdk_error_payload`` failure path
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import tat_invocation as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

COMMAND_ID = "cmd-8b0a1c2d"
INSTANCE_IDS = ["ins-aaaa", "ins-bbbb"]


def _base(**overrides):
    params = {}
    params.update(overrides)
    return module_args(**params)


def _start_args(**overrides):
    params = {"state": "started", "command_id": COMMAND_ID, "instance_ids": list(INSTANCE_IDS)}
    params.update(overrides)
    return params


def _cancel_args(**overrides):
    params = {"state": "cancelled", "invocation_id": "inv-existing"}
    params.update(overrides)
    return params


class FakeTatClient(object):
    """In-memory TAT client recording invocations and seeding task states."""

    def __init__(self, task_statuses=None):
        self.task_statuses = list(task_statuses or ["SUCCESS", "SUCCESS"])
        self.invocations = {}
        self.calls = []
        self._next = 0

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def InvokeCommand(self, request):
        self._record("InvokeCommand", request)
        self._next += 1
        invocation_id = "inv-new-%03d" % self._next
        instances = sorted(set(getattr(request, "InstanceIds", None) or []))
        tasks = []
        for index, instance in enumerate(instances):
            status = self.task_statuses[index % len(self.task_statuses)]
            tasks.append(
                {
                    "InvocationTaskId": "invt-%03d-%d" % (self._next, index),
                    "InstanceId": instance,
                    "TaskStatus": status,
                    "TaskResult": {
                        "Output": "output-of-%s" % status,
                        "ExitCode": 0 if status == "SUCCESS" else 1,
                    },
                    "CommandDocument": {
                        "CommandId": getattr(request, "CommandId", None),
                        "Content": "echo hi",
                    },
                }
            )
        self.invocations[invocation_id] = tasks
        return SimpleNamespace(InvocationId=invocation_id, RequestId="req-invoke")

    def CancelInvocation(self, request):
        self._record("CancelInvocation", request)
        self.invocations.pop(getattr(request, "InvocationId", None), None)
        return SimpleNamespace(RequestId="req-cancel")

    def DescribeInvocationTasks(self, request):
        self._record("DescribeInvocationTasks", request)
        invocation_id = request.Filters[0].Values[0]
        rows = [dict(t) for t in self.invocations.get(invocation_id, [])]
        offset = getattr(request, "Offset", 0) or 0
        return SimpleNamespace(
            InvocationTaskSet=[FakeResource(t) for t in rows[offset:]],
            TotalCount=len(rows),
            RequestId="req-tasks",
        )


def _make_module(monkeypatch, fake, models=None):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (models or FakeModels(), SimpleNamespace(TatClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)


# ---------------------------------------------------------------------------
# validation guards
# ---------------------------------------------------------------------------


def test_started_requires_command_and_instances(monkeypatch):
    fake = FakeTatClient()
    _make_module(monkeypatch, fake)
    _base(state="started")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "command_id and instance_ids are required when state=started" in exc.value.args[0]["msg"]


def test_cancelled_requires_invocation_id(monkeypatch):
    fake = FakeTatClient()
    _make_module(monkeypatch, fake)
    _base(state="cancelled", command_id=COMMAND_ID, instance_ids=INSTANCE_IDS)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "invocation_id is required when state=cancelled" in exc.value.args[0]["msg"]


def test_more_than_200_instances_fails(monkeypatch):
    fake = FakeTatClient()
    _make_module(monkeypatch, fake)
    too_many = ["ins-%04d" % index for index in range(201)]
    _base(command_id=COMMAND_ID, instance_ids=too_many)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "more than 200" in exc.value.args[0]["msg"]


def test_timeout_out_of_range_fails(monkeypatch):
    fake = FakeTatClient()
    _make_module(monkeypatch, fake)
    _base(**_start_args(timeout=90000))
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "timeout must be between 1 and 86400" in exc.value.args[0]["msg"]


# ---------------------------------------------------------------------------
# check mode / cancelled flows
# ---------------------------------------------------------------------------


def test_check_mode_is_dry_run(monkeypatch):
    fake = FakeTatClient()
    _make_module(monkeypatch, fake)
    _base(_ansible_check_mode=True, **_start_args())
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["invocation_id"] is None
    assert result["tasks"] == []
    assert fake.calls == []


def test_cancel_invocation(monkeypatch):
    fake = FakeTatClient()
    _make_module(monkeypatch, fake)
    _base(**_cancel_args(instance_ids=["ins-aaaa"]))
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["invocation_id"] == "inv-existing"
    assert result["tasks"] == []
    cancels = [req for name, req in fake.calls if name == "CancelInvocation"]
    assert cancels and cancels[0].InvocationId == "inv-existing"
    assert cancels[0].InstanceIds == ["ins-aaaa"]


# ---------------------------------------------------------------------------
# started flows
# ---------------------------------------------------------------------------


def test_start_without_wait(monkeypatch):
    fake = FakeTatClient()
    _make_module(monkeypatch, fake)
    _base(**_start_args(wait=False))
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["invocation_id"].startswith("inv-new-")
    assert result["tasks"] == []
    ops = [c for c, unused in fake.calls]
    assert "InvokeCommand" in ops
    assert "DescribeInvocationTasks" not in ops


def test_start_waits_for_terminal_tasks(monkeypatch):
    fake = FakeTatClient()
    _make_module(monkeypatch, fake)
    _base(**_start_args())
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["invocation_id"].startswith("inv-new-")
    assert len(result["tasks"]) == 2
    assert all(task["TaskStatus"] == "SUCCESS" for task in result["tasks"])
    assert result["status_summary"] == {"SUCCESS": 2}
    assert "DescribeInvocationTasks" in [c for c, unused in fake.calls]


def test_start_redacts_task_output_and_document(monkeypatch):
    fake = FakeTatClient()
    _make_module(monkeypatch, fake)
    _base(**_start_args())
    result = run(mod.run_module)
    for task in result["tasks"]:
        assert "CommandDocument" not in task
        assert task["TaskResult"] == {"Output": "<redacted>"}


def test_start_with_include_output_keeps_output(monkeypatch):
    fake = FakeTatClient()
    _make_module(monkeypatch, fake)
    _base(**_start_args(include_output=True))
    result = run(mod.run_module)
    for task in result["tasks"]:
        assert task["TaskResult"]["Output"].startswith("output-of-")
        assert "CommandDocument" not in task


def test_start_task_failure_fails_when_required(monkeypatch):
    fake = FakeTatClient(task_statuses=["SUCCESS", "FAILED"])
    _make_module(monkeypatch, fake)
    _base(**_start_args())
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "One or more TAT invocation tasks failed" in payload["msg"]
    assert payload["status_summary"] == {"SUCCESS": 1, "FAILED": 1}
    assert len(payload["failed_tasks"]) == 1
    assert payload["failed_tasks"][0]["TaskStatus"] == "FAILED"


def test_start_task_failure_allowed_when_not_required(monkeypatch):
    fake = FakeTatClient(task_statuses=["SUCCESS", "FAILED"])
    _make_module(monkeypatch, fake)
    _base(**_start_args(fail_on_task_error=False))
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["status_summary"] == {"SUCCESS": 1, "FAILED": 1}
    assert len(result["tasks"]) == 2


# ---------------------------------------------------------------------------
# failure paths
# ---------------------------------------------------------------------------


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def InvokeCommand(self, request):
            raise Boom("connection dropped")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    _base(**_start_args())
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]


# ---------------------------------------------------------------------------
# legacy helper regression tests (folded from test_tat_invocation.py)
# ---------------------------------------------------------------------------


class LegacyValue(object):
    pass


class LegacyModels(object):
    InvokeCommandRequest = LegacyValue
    CancelInvocationRequest = LegacyValue
    DescribeInvocationTasksRequest = LegacyValue
    Filter = LegacyValue


def test_invoke_request_is_canonical_and_deduplicates_targets():
    value = mod.invoke_request(
        LegacyModels,
        {
            "command_id": "cmd-1",
            "instance_ids": ["ins-2", "ins-1", "ins-1"],
            "parameters": {"z": 2, "a": 1},
            "username": "deploy",
            "working_directory": None,
            "timeout": 60,
            "output_cos_bucket_url": None,
            "output_cos_key_prefix": None,
        },
    )
    assert value.InstanceIds == ["ins-1", "ins-2"]
    assert value.Parameters == '{"a":"1","z":"2"}'
    assert value.Username == "deploy"


def test_cancel_can_target_selected_instances():
    value = mod.cancel_request(LegacyModels, {"invocation_id": "inv-1", "instance_ids": ["ins-2", "ins-1"]})
    assert value.InvocationId == "inv-1"
    assert value.InstanceIds == ["ins-1", "ins-2"]


def test_task_query_hides_output_by_default():
    value = mod.tasks_request(LegacyModels, "inv-1", 100, False)
    assert value.HideOutput is True
    assert value.Filters[0].Name == "invocation-id"
    assert value.Filters[0].Values == ["inv-1"]
