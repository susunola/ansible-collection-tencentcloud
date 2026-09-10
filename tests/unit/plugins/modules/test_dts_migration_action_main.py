"""Unit tests for the dts_migration_action action module (run_module flows).

One-shot state machine over an existing DTS migration job: start / pause /
resume / stop / complete, with state-aware idempotency. There is no
create/delete lifecycle. The fake DTS client tracks a mutable job status and
applies the requested action so re-describes converge.

Scenario matrix:

* an already-terminal state per action is idempotent
* each action transitions a valid starting state and re-describes
* stop/complete require ``confirm_impact=true``
* an action requested from an invalid state fails
* check mode reports the change without executing the action
* the blanket SDK failure path
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import dts_migration_action as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

# Next status per action, applied by the fake client after execution.
TRANSITIONS = {
    "start": "running",
    "pause": "manualPaused",
    "resume": "running",
    "stop": "success",
    "complete": "success",
}

DONE_STATES = {
    "start": {"running", "readyComplete", "success"},
    "pause": {"pausing", "manualPaused"},
    "resume": {"running", "readyComplete", "success"},
    "stop": {"stopping", "success"},
    "complete": {"completing", "success"},
}

VALID_FROM = {
    "start": {"checkPass", "readyRun"},
    "pause": {"running", "readyComplete"},
    "resume": {"manualPaused", "resumableErr", "failed"},
    "complete": {"readyComplete"},
}


def _args(**overrides):
    params = {
        "job_id": "dts-abcd1234",
        "action": "start",
        "resume_option": "normal",
        "complete_mode": "waitForSync",
        "confirm_impact": False,
    }
    params.update(overrides)
    return module_args(**params)


class FakeDtsClient(object):
    """In-memory DTS client with a mutable single-job status."""

    def __init__(self, status):
        self.status = status
        self.calls = []

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def DescribeMigrationDetail(self, request):
        self._record("DescribeMigrationDetail", request)
        return FakeResource({"JobId": "dts-abcd1234", "Status": self.status})

    def _apply(self, request, action):
        self.status = TRANSITIONS[action]
        return SimpleNamespace(RequestId="req-fake")

    def StartMigrateJob(self, request):
        self._record("StartMigrateJob", request)
        return self._apply(request, "start")

    def PauseMigrateJob(self, request):
        self._record("PauseMigrateJob", request)
        return self._apply(request, "pause")

    def ResumeMigrateJob(self, request):
        self._record("ResumeMigrateJob", request)
        return self._apply(request, "resume")

    def StopMigrateJob(self, request):
        self._record("StopMigrateJob", request)
        return self._apply(request, "stop")

    def CompleteMigrateJob(self, request):
        self._record("CompleteMigrateJob", request)
        return self._apply(request, "complete")


def _make_module(monkeypatch, fake):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (FakeModels(), SimpleNamespace(DtsClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


# ---------------------------------------------------------------------------
# idempotent flows
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("action,status", [("start", "running"), ("pause", "manualPaused"), ("stop", "success"), ("complete", "success")])
def test_action_already_done_is_idempotent(monkeypatch, action, status):
    fake = FakeDtsClient(status)
    _make_module(monkeypatch, fake)
    _args(action=action)
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["migration_job"]["Status"] == status
    # describe ran but no execution method was reached.
    assert len(fake.calls) == 1
    assert fake.calls[0][0] == "DescribeMigrationDetail"


# ---------------------------------------------------------------------------
# happy-path transitions
# ---------------------------------------------------------------------------


def test_start_transitions_job(monkeypatch):
    fake = FakeDtsClient("checkPass")
    _make_module(monkeypatch, fake)
    _args(action="start")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["migration_job"]["Status"] == "running"
    ops = [c for c, unused in fake.calls]
    assert ops[0] == "DescribeMigrationDetail"
    assert ops[1] == "StartMigrateJob"
    assert ops[2] == "DescribeMigrationDetail"


def test_pause_transitions_job(monkeypatch):
    fake = FakeDtsClient("running")
    _make_module(monkeypatch, fake)
    _args(action="pause")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["migration_job"]["Status"] == "manualPaused"
    ops = [c for c, unused in fake.calls]
    assert "PauseMigrateJob" in ops


def test_resume_sets_resume_option(monkeypatch):
    fake = FakeDtsClient("manualPaused")
    _make_module(monkeypatch, fake)
    _args(action="resume", resume_option="clearData")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["migration_job"]["Status"] == "running"
    resume_call = dict((name, request) for name, request in fake.calls)["ResumeMigrateJob"]
    assert resume_call.ResumeOption == "clearData"


def test_complete_transitions_job(monkeypatch):
    fake = FakeDtsClient("readyComplete")
    _make_module(monkeypatch, fake)
    _args(action="complete", confirm_impact=True, complete_mode="immediately")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["migration_job"]["Status"] == "success"
    complete_call = dict((name, request) for name, request in fake.calls)["CompleteMigrateJob"]
    assert complete_call.CompleteMode == "immediately"


def test_stop_requires_confirm_impact(monkeypatch):
    fake = FakeDtsClient("running")
    _make_module(monkeypatch, fake)
    _args(action="stop")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert exc.value.args[0]["msg"] == "confirm_impact=true is required for DTS stop"
    assert "StopMigrateJob" not in [c for c, unused in fake.calls]


def test_complete_requires_confirm_impact(monkeypatch):
    fake = FakeDtsClient("readyComplete")
    _make_module(monkeypatch, fake)
    _args(action="complete")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert exc.value.args[0]["msg"] == "confirm_impact=true is required for DTS complete"


# ---------------------------------------------------------------------------
# invalid-state guards
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("action,status", [("start", "manualPaused"), ("pause", "checkPass"), ("resume", "checkPass"), ("complete", "running")])
def test_action_from_invalid_state_fails(monkeypatch, action, status):
    fake = FakeDtsClient(status)
    _make_module(monkeypatch, fake)
    _args(action=action, confirm_impact=True)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "DTS %s is not valid in state %s" % (action, status) in payload["msg"]
    assert payload["valid_states"] == sorted(VALID_FROM[action])
    assert "migration_job" in payload


# ---------------------------------------------------------------------------
# check-mode flow
# ---------------------------------------------------------------------------


def test_check_mode_reports_change_without_executing(monkeypatch):
    fake = FakeDtsClient("checkPass")
    _make_module(monkeypatch, fake)
    _args(_ansible_check_mode=True, action="start")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["migration_job"]["Status"] == "checkPass"
    ops = [c for c, unused in fake.calls]
    assert ops == ["DescribeMigrationDetail"]


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
    _args(action="start")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]
