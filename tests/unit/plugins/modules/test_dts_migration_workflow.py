"""Tests for DTS migration workflow module helpers."""

from ansible_collections.susunola.tencentcloud.plugins.modules.dts_migration_action import DONE, VALID_FROM, execute
from ansible_collections.susunola.tencentcloud.plugins.modules.dts_migration_check import start
from ansible_collections.susunola.tencentcloud.plugins.modules.dts_migration_job_config import comparable, desired


class Request(object):
    def __init__(self):
        self.JobId = None


class Models(object):
    CreateMigrateCheckJobRequest = Request
    StartMigrateJobRequest = Request
    PauseMigrateJobRequest = Request
    ResumeMigrateJobRequest = Request
    StopMigrateJobRequest = Request
    CompleteMigrateJobRequest = Request


class Client(object):
    def __init__(self):
        self.calls = []

    def CreateMigrateCheckJob(self, request):
        self.calls.append(("check", request))
        return object()

    def StartMigrateJob(self, request):
        self.calls.append(("start", request))
        return object()

    def PauseMigrateJob(self, request):
        self.calls.append(("pause", request))
        return object()

    def ResumeMigrateJob(self, request):
        self.calls.append(("resume", request))
        return object()

    def StopMigrateJob(self, request):
        self.calls.append(("stop", request))
        return object()

    def CompleteMigrateJob(self, request):
        self.calls.append(("complete", request))
        return object()


class Module(object):
    def sdk_call(self, method, request):
        return method(request)


def test_desired_configuration_maps_and_sorts_tags():
    value = desired(
        {
            "job_id": "dts-1",
            "run_mode": "immediate",
            "source": {"Region": "a"},
            "destination": {"Region": "b"},
            "migration_options": {"MigrateType": "full"},
            "auto_retry_minutes": 0,
            "name": None,
            "expected_run_time": None,
            "tags": {"z": "2", "a": "1"},
        }
    )
    assert value["JobId"] == "dts-1"
    assert value["Tags"] == [{"TagKey": "a", "TagValue": "1"}, {"TagKey": "z", "TagValue": "2"}]


def test_comparable_ignores_read_only_detail_fields():
    wanted = {"JobId": "dts-1", "RunMode": "immediate"}
    assert comparable({"JobId": "dts-1", "RunMode": "immediate", "Status": "created"}, wanted) == wanted


def test_check_start_uses_new_api_name():
    client = Client()
    start(Module(), client, Models, "dts-1")
    assert client.calls[0][0] == "check"
    assert client.calls[0][1].JobId == "dts-1"


def test_actions_build_sdk_requests():
    for action in DONE:
        client = Client()
        execute(Module(), client, Models, {"job_id": "dts-1", "action": action, "resume_option": "normal", "complete_mode": "waitForSync"})
        assert client.calls[0][0] == action
        assert client.calls[0][1].JobId == "dts-1"


def test_action_done_states_cover_safe_idempotency():
    assert "running" in DONE["start"]
    assert "manualPaused" in DONE["pause"]
    assert "success" in DONE["complete"]
    assert VALID_FROM["start"] == {"checkPass", "readyRun"}
    assert VALID_FROM["complete"] == {"readyComplete"}
