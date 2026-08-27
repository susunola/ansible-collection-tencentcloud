"""Unit tests for the tat connection plugin.

These exercise the TAT orchestration (command cache, invoke, poll, file
transfer) against fake SDK models/clients; they deliberately do not require
the Tencent Cloud SDK, which is not installed in the ansible-test unit
environment.
"""

from __future__ import absolute_import, division, print_function
__metaclass__ = type

import pytest

from ansible.errors import AnsibleConnectionFailure

from ansible_collections.susunola.tencentcloud.plugins.connection import tat as tat_mod
from ansible_collections.susunola.tencentcloud.plugins.connection.tat import (
    Connection,
    _OptionAdapter,
)


class FakePlayContext(object):
    shell = None
    executable = "/bin/sh"
    timeout = 60
    become = False
    become_user = None
    connection = "susunola.tencentcloud.tat"


class FakeRequest(object):
    pass


class FakeModels(object):
    CreateCommandRequest = FakeRequest
    InvokeCommandRequest = FakeRequest
    DescribeInvocationTasksRequest = FakeRequest


class FakeCreateCommandResponse(object):
    def __init__(self, command_id):
        self.CommandId = command_id


class FakeInvokeResponse(object):
    def __init__(self, task_ids):
        self.InvocationTaskIdSet = task_ids


class FakeTaskResult(object):
    def __init__(self, exit_code=0, output="", error=None):
        self.ExitCode = exit_code
        self.Output = output
        self.ErrorMsg = error


class FakeTask(object):
    def __init__(self, state, result=None):
        self.TaskStatus = state
        self.TaskResult = result


class FakeDescribeResponse(object):
    def __init__(self, tasks):
        self.InvocationTaskSet = tasks


class FakeClient(object):
    def __init__(self):
        self.created = []
        self.invoked = []
        self.described = []
        self.requests = []

    def CreateCommand(self, request):
        self.created.append(request)
        return FakeCreateCommandResponse("cmd-%d" % len(self.created))

    def InvokeCommand(self, request):
        self.invoked.append(request)
        return FakeInvokeResponse(["task-%d" % len(self.invoked)])

    def DescribeInvocationTasks(self, request):
        self.described.append(request)
        if not self.requests:
            return FakeDescribeResponse([])
        return FakeDescribeResponse([self.requests.pop(0)])


def make_connection(options=None):
    conn = Connection(FakePlayContext(), None)

    def get_option(name):
        return (options or {}).get(name)

    conn.get_option = get_option
    conn._models = FakeModels
    conn._client = FakeClient()
    conn._instance_id = "ins-1"
    conn._connected = True
    return conn


# ---------------------------------------------------------------------------
# option adapter
# ---------------------------------------------------------------------------


class FakeOptionConnection(object):
    def get_option(self, name):
        if name == "region":
            return "ap-guangzhou"
        raise KeyError(name)


def test_option_adapter_exposes_params_and_fail_json():
    adapter = _OptionAdapter(FakeOptionConnection(), region=None)
    assert adapter.params["region"] == "ap-guangzhou"
    assert adapter.params["secret_id"] is None
    with pytest.raises(AnsibleConnectionFailure, match="boom"):
        adapter.fail_json(msg="boom")


# ---------------------------------------------------------------------------
# command lifecycle
# ---------------------------------------------------------------------------


def test_ensure_command_creates_and_caches():
    conn = make_connection()
    first = conn._ensure_command("echo hi", None)
    second = conn._ensure_command("echo hi", None)
    assert first == second
    assert len(conn._client.created) == 1
    request = conn._client.created[0]
    assert request.CommandName.startswith("ansible-tat-")
    assert request.Content == "echo hi"
    assert request.Type == "SHELL"
    assert request.WorkingDirectory == "/root"
    assert request.Timeout == 60
    assert not hasattr(request, "Username")


def test_ensure_command_sets_username_for_non_root():
    conn = make_connection()
    conn._ensure_command("whoami", "app")
    assert conn._client.created[0].Username == "app"
    # root user does not set Username (TAT agent user)
    conn._ensure_command("whoami", "root")
    assert not hasattr(conn._client.created[1], "Username")


def test_ensure_command_rejects_oversized_payload():
    conn = make_connection({"max_command_chars": 10})
    with pytest.raises(AnsibleConnectionFailure, match="max_command_chars"):
        conn._ensure_command("x" * 20, None)


def test_ensure_command_lru_evicts_oldest():
    conn = make_connection()
    for index in range(10):
        conn._ensure_command("payload-%d" % index, None)
    assert len(conn._command_cache) == 8
    # the oldest entries are gone and are re-created on demand
    conn._ensure_command("payload-0", None)
    assert len(conn._client.created) == 11


def test_invoke_returns_first_task_id():
    conn = make_connection()
    task_id = conn._invoke("cmd-1", None)
    assert task_id == "task-1"
    request = conn._client.invoked[0]
    assert request.CommandId == "cmd-1"
    assert request.InstanceIds == ["ins-1"]


def test_invoke_fails_without_task_ids():
    conn = make_connection()
    conn._client.InvokeCommand = lambda request: FakeInvokeResponse([])
    with pytest.raises(AnsibleConnectionFailure, match="no task IDs"):
        conn._invoke("cmd-1", None)


def test_poll_task_success():
    conn = make_connection()
    conn._client.requests = [FakeTask("SUCCESS", FakeTaskResult(0, "all good"))]
    rc, output = conn._poll_task("task-1")
    assert rc == 0
    assert output == "all good"


def test_poll_task_failure_appends_error():
    conn = make_connection()
    conn._client.requests = [
        FakeTask("FAILED", FakeTaskResult(2, "boom", "permission denied"))
    ]
    rc, output = conn._poll_task("task-1")
    assert rc == 2
    assert "permission denied" in output


def test_poll_task_timeout_raises():
    conn = make_connection({"poll_interval": 0, "poll_timeout": 1})
    conn._client.requests = []
    # FakeClient returns an empty task set forever -> raise
    with pytest.raises(AnsibleConnectionFailure, match="no task"):
        conn._poll_task("task-1")


def test_poll_task_exhausts_deadline():
    conn = make_connection({"poll_interval": 0, "poll_timeout": 1})

    class StuckClient(FakeClient):
        def DescribeInvocationTasks(self, request):
            return FakeDescribeResponse([FakeTask("RUNNING")])

    conn._client = StuckClient()
    with pytest.raises(AnsibleConnectionFailure, match="still in state RUNNING"):
        conn._poll_task("task-1")


# ---------------------------------------------------------------------------
# exec_command
# ---------------------------------------------------------------------------


def test_exec_command_runs_and_returns_output():
    conn = make_connection()
    conn._client.requests = [FakeTask("SUCCESS", FakeTaskResult(0, "hello"))]
    rc, stdout, stderr = conn.exec_command("echo hello")
    assert (rc, stdout, stderr) == (0, "hello", "")


def test_exec_command_wraps_in_data_as_base64_stdin():
    conn = make_connection()
    conn._client.requests = [FakeTask("SUCCESS", FakeTaskResult(0, ""))]
    conn.exec_command("cat", in_data=b"secret payload")
    command = conn._client.created[0].Content
    assert command.startswith("printf ")
    assert "base64 -d > /tmp/ansible_stdin_" in command
    assert command.endswith("\ncat")


def test_exec_command_passes_become_user():
    conn = make_connection()
    conn._play_context.become = True
    conn._play_context.become_user = "deploy"
    conn._client.requests = [FakeTask("SUCCESS", FakeTaskResult(0, ""))]
    conn.exec_command("whoami")
    assert conn._client.created[0].Username == "deploy"
    assert conn._client.invoked[0].Username == "deploy"


# ---------------------------------------------------------------------------
# file transfer
# ---------------------------------------------------------------------------


def test_put_file_streams_chunks_then_decodes(tmp_path):
    conn = make_connection({"max_command_chars": 100})
    commands = []

    def fake_exec(cmd, in_data=None, sudoable=True):
        commands.append(cmd)
        return (0, "", "")

    # exec_command succeeds for every transfer chunk and decode; record the
    # commands so we can assert on the chunked transfer shape.
    conn.exec_command = fake_exec

    local = tmp_path / "payload.bin"
    local.write_bytes(b"x" * 4000)
    conn.put_file(str(local), "/etc/app/payload.bin")

    # chunked write (1 truncating + N appends for a 4000-byte file at ~5360
    # base64 chars/chunk) then a decode + atomic rename
    assert any("> '/etc/app/payload.bin.tc-b64'" in command for command in commands)
    assert any(">> '/etc/app/payload.bin.tc-b64'" in command for command in commands)
    decode = [c for c in commands if "base64 -d <" in c]
    assert len(decode) == 1
    assert "mv '/etc/app/payload.bin.tmp' '/etc/app/payload.bin'" in decode[0]


def test_put_file_fails_on_chunk_error(tmp_path):
    conn = make_connection()
    conn.exec_command = lambda cmd, in_data=None, sudoable=True: (1, "", "disk full")
    local = tmp_path / "payload.bin"
    local.write_bytes(b"y" * 100)
    with pytest.raises(AnsibleConnectionFailure, match="Failed to transfer"):
        conn.put_file(str(local), "/etc/payload.bin")


def test_fetch_file_decodes_and_writes(tmp_path):
    conn = make_connection()
    out_dir = tmp_path / "nested" / "dir"
    out_path = out_dir / "result.txt"
    import base64 as _b64

    conn.exec_command = lambda cmd, in_data=None, sudoable=True: (
        0, _b64.b64encode(b"remote data").decode("ascii"), ""
    )
    conn.fetch_file("/etc/result.txt", str(out_path))
    assert out_path.read_bytes() == b"remote data"


def test_fetch_file_raises_on_bad_base64(tmp_path):
    conn = make_connection()
    conn.exec_command = lambda cmd, in_data=None, sudoable=True: (0, "not base64!!", "")
    with pytest.raises(AnsibleConnectionFailure, match="did not return valid base64"):
        conn.fetch_file("/etc/result.txt", str(tmp_path / "out.txt"))


# ---------------------------------------------------------------------------
# connect / build client
# ---------------------------------------------------------------------------


def test_connect_requires_instance_id():
    conn = Connection(FakePlayContext(), None)
    conn.get_option = lambda name: None
    conn._connected = False
    with pytest.raises(AnsibleConnectionFailure, match="instance_id is required"):
        conn._connect()


def test_build_client_requires_credentials(monkeypatch):
    conn = Connection(FakePlayContext(), None)
    conn.get_option = lambda name: None
    monkeypatch.setattr(tat_mod, "load_profile", lambda profile=None: {})
    monkeypatch.delenv("TENCENTCLOUD_SECRET_ID", raising=False)
    monkeypatch.delenv("TENCENTCLOUD_SECRET_KEY", raising=False)
    monkeypatch.delenv("TENCENTCLOUD_TOKEN", raising=False)
    with pytest.raises(AnsibleConnectionFailure, match="secret_id"):
        conn._build_client()


def test_build_client_requires_region(monkeypatch):
    conn = Connection(FakePlayContext(), None)
    conn.get_option = lambda name: None
    monkeypatch.setenv("TENCENTCLOUD_SECRET_ID", "akid")
    monkeypatch.setenv("TENCENTCLOUD_SECRET_KEY", "secret")
    monkeypatch.setenv("TENCENTCLOUD_REGION", "")
    monkeypatch.setattr(tat_mod, "load_profile", lambda profile=None: {})
    with pytest.raises(AnsibleConnectionFailure, match="region"):
        conn._build_client()
