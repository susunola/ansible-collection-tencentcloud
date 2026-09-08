"""Unit tests for the dlc_notebook_session write module (run_module flows).

Drives ``run_module()`` end to end against an in-memory fake DLC client whose
write operations mutate the notebook-session store, so the module's post-write
``read_id``/``wait_session`` refetches converge immediately.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import dlc_notebook_session as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

ACTIVE_STATES = {"not_started", "starting", "idle", "busy", "shutting_down"}

SESSION = {
    "SessionId": "sess-000001",
    "Name": "analyst-pyspark",
    "State": "idle",
    "Kind": "spark",
    "DataEngineName": "production-spark",
    "DriverSize": "medium",
    "ExecutorSize": "medium",
    "ExecutorNumbers": 2,
    "ExecutorMaxNumbers": 4,
    "Arguments": [],
}


class NotFound(Exception):
    def get_code(self):
        return "ResourceNotFound.Session"


def _session(**overrides):
    item = copy.deepcopy(SESSION)
    item.update(overrides)
    return item


def _make_module(monkeypatch, fake, models=None):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (models or FakeModels(), SimpleNamespace(DlcClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


class FakeDlcClient(object):
    """In-memory DLC client mutating a notebook-session store."""

    def __init__(self, sessions=None):
        self.sessions = [copy.deepcopy(t) for t in (sessions or [])]
        self.calls = []
        self._next = 0

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def _by_id(self, session_id):
        for item in self.sessions:
            if item.get("SessionId") == session_id:
                return item
        return None

    def DescribeNotebookSession(self, request):
        self._record("DescribeNotebookSession", request)
        item = self._by_id(request.SessionId)
        if item is None:
            raise NotFound("session not found")
        return SimpleNamespace(Session=FakeResource(item), RequestId="req-fake")

    def DescribeNotebookSessions(self, request):
        self._record("DescribeNotebookSessions", request)
        name = request.Filters[0].Values[0]
        data_engine_name = getattr(request, "DataEngineName", None)
        matches = [
            dict(t)
            for t in self.sessions
            if t.get("Name") == name and (data_engine_name is None or t.get("DataEngineName") == data_engine_name)
        ]
        return SimpleNamespace(Sessions=[FakeResource(t) for t in matches], TotalElements=len(matches))

    def CreateNotebookSession(self, request):
        self._record("CreateNotebookSession", request)
        self._next += 1
        item = {
            "SessionId": "sess-new-%03d" % self._next,
            "Name": getattr(request, "Name", None),
            "State": "idle",
            "Kind": getattr(request, "Kind", None),
            "DataEngineName": getattr(request, "DataEngineName", None),
            "Arguments": list(getattr(request, "Arguments", None) or []),
        }
        for attr in (
            "ProgramDependentFiles", "ProgramDependentJars", "ProgramDependentPython",
            "ProgramArchives", "DriverSize", "ExecutorSize", "ExecutorNumbers",
            "ExecutorMaxNumbers", "ProxyUser", "TimeoutInSecond",
        ):
            value = getattr(request, attr, None)
            if value is not None:
                item[attr] = value
        self.sessions.append(item)
        return SimpleNamespace(SessionId=item["SessionId"], RequestId="req-fake")

    def DeleteNotebookSession(self, request):
        self._record("DeleteNotebookSession", request)
        self.sessions = [t for t in self.sessions if t.get("SessionId") != request.SessionId]
        return SimpleNamespace(RequestId="req-fake")


# ---------------------------------------------------------------------------
# absent flows
# ---------------------------------------------------------------------------


def test_absent_missing_session_by_list_is_idempotent(monkeypatch):
    fake = FakeDlcClient(sessions=[])
    _make_module(monkeypatch, fake)
    module_args(state="absent", name="ghost-session")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["session"] is None
    assert result["session_id"] is None
    assert [c for c, unused in fake.calls] == ["DescribeNotebookSessions"]


def test_absent_missing_session_by_id_swallows_not_found(monkeypatch):
    fake = FakeDlcClient(sessions=[])
    _make_module(monkeypatch, fake)
    module_args(state="absent", session_id="sess-ghost")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["session"] is None
    assert [c for c, unused in fake.calls] == ["DescribeNotebookSession"]


def test_absent_requires_allow_delete(monkeypatch):
    fake = FakeDlcClient(sessions=[_session()])
    _make_module(monkeypatch, fake)
    module_args(state="absent", name="analyst-pyspark")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "allow_delete=true" in exc.value.args[0]["msg"]


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeDlcClient(sessions=[_session()])
    _make_module(monkeypatch, fake)
    module_args(_ansible_check_mode=True, state="absent", name="analyst-pyspark", allow_delete=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert len(fake.sessions) == 1
    assert "DeleteNotebookSession" not in [c for c, unused in fake.calls]


def test_absent_deletes_and_waits(monkeypatch):
    fake = FakeDlcClient(sessions=[_session()])
    _make_module(monkeypatch, fake)
    module_args(state="absent", name="analyst-pyspark", allow_delete=True, wait=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["session"] is None
    assert fake.sessions == []
    ops = [c for c, unused in fake.calls]
    assert "DeleteNotebookSession" in ops


# ---------------------------------------------------------------------------
# creation flows
# ---------------------------------------------------------------------------


def test_create_requires_creation_parameters(monkeypatch):
    fake = FakeDlcClient(sessions=[])
    _make_module(monkeypatch, fake)
    module_args(state="present", name="brand-new")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "creation parameters are required" in payload["msg"]
    assert payload["missing"] == ["kind", "data_engine_name"]


def test_create_session_happy_path(monkeypatch):
    fake = FakeDlcClient(sessions=[])
    _make_module(monkeypatch, fake)
    module_args(
        state="present",
        name="analyst-pyspark",
        kind="pyspark",
        data_engine_name="production-spark",
        driver_size="medium",
        executor_size="medium",
        executor_numbers=2,
        executor_max_numbers=4,
        wait=True,
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["session_id"].startswith("sess-new-")
    assert result["session"]["Name"] == "analyst-pyspark"
    assert len(fake.sessions) == 1
    ops = [c for c, unused in fake.calls]
    assert ops[0] == "DescribeNotebookSessions"
    assert "CreateNotebookSession" in ops


def test_create_check_mode_is_dry_run(monkeypatch):
    fake = FakeDlcClient(sessions=[])
    _make_module(monkeypatch, fake)
    module_args(
        _ansible_check_mode=True,
        state="present",
        name="analyst-pyspark",
        kind="pyspark",
        data_engine_name="production-spark",
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["session_id"] is None
    assert result["session"]["Name"] == "analyst-pyspark"
    assert fake.sessions == []
    assert "CreateNotebookSession" not in [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# existing-session flows
# ---------------------------------------------------------------------------


def test_existing_active_session_no_drift_is_idempotent(monkeypatch):
    fake = FakeDlcClient(sessions=[_session()])
    _make_module(monkeypatch, fake)
    module_args(state="present", name="analyst-pyspark", data_engine_name="production-spark")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["session"]["SessionId"] == "sess-000001"
    assert result["session_id"] == "sess-000001"


def test_existing_session_by_id_no_drift(monkeypatch):
    fake = FakeDlcClient(sessions=[_session()])
    _make_module(monkeypatch, fake)
    module_args(state="present", session_id="sess-000001")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["session"]["Name"] == "analyst-pyspark"


def test_drift_requires_allow_replace(monkeypatch):
    fake = FakeDlcClient(sessions=[_session()])
    _make_module(monkeypatch, fake)
    module_args(state="present", session_id="sess-000001", kind="pyspark", name="analyst-pyspark")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "allow_replace=true" in payload["msg"]
    assert "Kind" in payload["immutable_drift"]


def test_allow_replace_recreates_session(monkeypatch):
    fake = FakeDlcClient(sessions=[_session()])
    _make_module(monkeypatch, fake)
    module_args(
        state="present",
        session_id="sess-000001",
        name="analyst-pyspark",
        kind="pyspark",
        data_engine_name="production-spark",
        driver_size="medium",
        allow_replace=True,
        wait=True,
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["session_id"] != "sess-000001"
    assert result["session"]["Kind"] == "pyspark"
    assert len(fake.sessions) == 1
    ops = [c for c, unused in fake.calls]
    assert "DeleteNotebookSession" in ops
    assert "CreateNotebookSession" in ops


def test_present_terminal_session_with_id_fails(monkeypatch):
    fake = FakeDlcClient(sessions=[_session(State="killed")])
    _make_module(monkeypatch, fake)
    module_args(state="present", session_id="sess-000001")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "terminal and cannot be restarted" in exc.value.args[0]["msg"]


def test_present_shutting_down_session_fails(monkeypatch):
    fake = FakeDlcClient(sessions=[_session(State="shutting_down")])
    _make_module(monkeypatch, fake)
    module_args(state="present", session_id="sess-000001")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "shutting down" in exc.value.args[0]["msg"]


def test_multiple_active_matches_fail(monkeypatch):
    fake = FakeDlcClient(sessions=[_session(), _session(SessionId="sess-000002")])
    _make_module(monkeypatch, fake)
    module_args(state="present", name="analyst-pyspark")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "Multiple active DLC Notebook sessions matched" in exc.value.args[0]["msg"]


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeNotebookSessions(self, request):
            raise Boom("connection dropped")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    module_args(state="present", name="analyst-pyspark")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]


def test_describe_non_notfound_error_propagates(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeNotebookSession(self, request):
            raise Boom("describe exploded")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    module_args(state="present", session_id="sess-000001")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "describe exploded" in payload["error"]


def test_name_drift_on_id_lookup_fails_without_replace(monkeypatch):
    fake = FakeDlcClient(sessions=[_session()])
    _make_module(monkeypatch, fake)
    module_args(state="present", session_id="sess-000001", name="renamed-session")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "allow_replace=true" in payload["msg"]
    assert "Name" in payload["immutable_drift"]


def test_replace_requires_a_name(monkeypatch):
    fake = FakeDlcClient(sessions=[_session()])
    _make_module(monkeypatch, fake)
    module_args(state="present", session_id="sess-000001", kind="pyspark", allow_replace=True)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "name is required when replacing" in exc.value.args[0]["msg"]


def test_replace_check_mode_is_dry_run(monkeypatch):
    fake = FakeDlcClient(sessions=[_session()])
    _make_module(monkeypatch, fake)
    module_args(
        _ansible_check_mode=True,
        state="present",
        session_id="sess-000001",
        name="analyst-pyspark",
        kind="pyspark",
        allow_replace=True,
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["session_id"] is None
    assert result["session"]["Kind"] == "pyspark"
    assert len(fake.sessions) == 1
    assert "DeleteNotebookSession" not in [c for c, unused in fake.calls]


def test_arguments_drift_detected(monkeypatch):
    fake = FakeDlcClient(sessions=[_session()])
    _make_module(monkeypatch, fake)
    module_args(
        state="present",
        session_id="sess-000001",
        name="analyst-pyspark",
        arguments=[{"key": "spark.executor.memory", "value": "8g"}],
    )
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "allow_replace=true" in payload["msg"]
    assert "Arguments" in payload["immutable_drift"]


def test_create_with_dependent_files_and_arguments(monkeypatch):
    fake = FakeDlcClient(sessions=[])
    _make_module(monkeypatch, fake)
    module_args(
        state="present",
        name="analyst-pyspark",
        kind="pyspark",
        data_engine_name="production-spark",
        dependent_files=["cosn://b/a.py", "cosn://b/b.py"],
        arguments=[{"key": "spark.executor.memory", "value": "8g"}],
        executor_numbers=2,
        executor_max_numbers=4,
        wait=False,
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["session"]["ProgramDependentFiles"] == ["cosn://b/a.py", "cosn://b/b.py"]
    assert result["session"]["Arguments"] == [{"Key": "spark.executor.memory", "Value": "8g"}]


def test_wait_fails_when_session_enters_failed_state(monkeypatch):
    class FailedClient(object):
        def __init__(self):
            self.calls = []

        def _record(self, name, request=None):
            self.calls.append((name, request))

        def DescribeNotebookSessions(self, request):
            self._record("DescribeNotebookSessions", request)
            return SimpleNamespace(Sessions=[], TotalElements=0)

        def CreateNotebookSession(self, request):
            self._record("CreateNotebookSession", request)
            return SimpleNamespace(SessionId="sess-failing", RequestId="req-fake")

        def DescribeNotebookSession(self, request):
            self._record("DescribeNotebookSession", request)
            return SimpleNamespace(Session=FakeResource(_session(SessionId="sess-failing", State="error")), RequestId="req-fake")

    fake = FailedClient()
    _make_module(monkeypatch, fake)
    module_args(state="present", name="analyst-pyspark", kind="pyspark", data_engine_name="production-spark", wait=True)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "entered a failed state" in exc.value.args[0]["msg"]


def test_session_response_without_session_field_is_absent(monkeypatch):
    class EmptySessionClient(object):
        def __init__(self):
            self.calls = []

        def _record(self, name, request=None):
            self.calls.append((name, request))

        def DescribeNotebookSession(self, request):
            self._record("DescribeNotebookSession", request)
            return SimpleNamespace(Session=None, RequestId="req-fake")

    fake = EmptySessionClient()
    _make_module(monkeypatch, fake)
    module_args(state="absent", session_id="sess-ghost")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["session"] is None


def test_validation_rejects_executor_numbers_above_max(monkeypatch):
    fake = FakeDlcClient(sessions=[])
    _make_module(monkeypatch, fake)
    module_args(state="absent", name="ghost", executor_numbers=8, executor_max_numbers=2)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "executor_numbers must not exceed executor_max_numbers" in exc.value.args[0]["msg"]


def test_validation_rejects_duplicate_argument_keys(monkeypatch):
    fake = FakeDlcClient(sessions=[])
    _make_module(monkeypatch, fake)
    module_args(
        state="absent",
        name="ghost",
        arguments=[{"key": "spark.executor.memory", "value": "4g"}, {"key": "spark.executor.memory", "value": "8g"}],
    )
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "arguments contains duplicate keys" in exc.value.args[0]["msg"]
