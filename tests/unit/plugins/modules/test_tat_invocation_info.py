"""Deep harness tests for tat_invocation_info.

Covers the request builders (exact InvocationIds vs command-id /
instance-kind filters, task output hiding), scrub() redaction and
run_module() end to end: bounded invocation list pagination, exact
mode with per-instance task pagination, and the sdk_error_payload
fail contract.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import sys
import types

import pytest

from ansible_collections.susunola.tencentcloud.plugins.modules import tat_invocation_info


def list_params():
    return {
        "invocation_id": None,
        "command_id": "cmd-1",
        "instance_kind": None,
        "include_tasks": True,
        "include_output": False,
        "page_size": 2,
        "max_pages": 5,
    }


def exact_params():
    return {
        "invocation_id": "inv-1",
        "command_id": None,
        "instance_kind": None,
        "include_tasks": True,
        "include_output": False,
        "page_size": 2,
        "max_pages": 5,
    }


class FakeRequest:
    pass


class FakeFilter:
    pass


class FakeModels:
    DescribeInvocationsRequest = FakeRequest
    DescribeInvocationTasksRequest = FakeRequest
    Filter = FakeFilter


def test_invocation_request_selects_ids_or_filters():
    exact = tat_invocation_info.invocation_request(FakeModels, exact_params(), 0)
    assert exact.InvocationIds == ["inv-1"]
    assert not hasattr(exact, "Filters")
    listing = tat_invocation_info.invocation_request(FakeModels, list_params(), 10)
    assert [(item.Name, item.Values) for item in listing.Filters] == [("command-id", ["cmd-1"])]
    assert not hasattr(listing, "InvocationIds")


def test_task_request_hides_output_and_filters_on_invocation():
    request = tat_invocation_info.task_request(FakeModels, exact_params(), 100)
    assert request.Offset == 100 and request.Limit == 2
    assert request.HideOutput is True
    assert [(item.Name, item.Values) for item in request.Filters] == [("invocation-id", ["inv-1"])]


def test_scrub_removes_command_and_parameter_material():
    value = tat_invocation_info.scrub({
        "Parameters": '{"password":"x"}',
        "DefaultParameters": "x",
        "CommandContent": "base64",
        "CommandDocument": {"Content": "x"},
        "TaskResult": {"Output": "secret", "ExitCode": 0},
    })
    assert value["Parameters"] == "<redacted>"
    assert value["DefaultParameters"] == "<redacted>"
    assert value["CommandContent"] == "<redacted>"
    assert value["TaskResult"] == {"Output": "<redacted>"}
    assert "CommandDocument" not in value


class FakeItem:
    def __init__(self, marker):
        self.marker = marker

    def _serialize(self, allow_none=True):
        return {
            "Marker": self.marker,
            "Parameters": '{"password":"x"}',
            "TaskResult": {"Output": "secret", "ExitCode": 0},
        }


class FakeResponse:
    def __init__(self, item_attr, items, total_count, request_id):
        setattr(self, item_attr, items)
        self.TotalCount = total_count
        self.RequestId = request_id


class FakeClient:
    def __init__(self, invocation_pages, task_pages=None):
        self._invocations = list(invocation_pages)
        self._tasks = list(task_pages or [])
        self.invocation_requests = []
        self.task_requests = []

    def DescribeInvocations(self, request):
        self.invocation_requests.append(request)
        return self._invocations.pop(0)

    def DescribeInvocationTasks(self, request):
        self.task_requests.append(request)
        return self._tasks.pop(0)


class ModuleExit(BaseException):
    pass


class ModuleFail(BaseException):
    def __init__(self, payload):
        self.payload = payload
        super(ModuleFail, self).__init__("module failed: %r" % (payload,))


class FakeModule:
    def __init__(self, params):
        self.params = params
        self.exit_payload = None
        self.fail_payload = None

    def require_sdk(self):
        pass

    def create_client(self, client_class, endpoint):
        return self._client

    def sdk_call(self, operation, request=None):
        if request is not None:
            return operation(request)
        return operation()

    def exit_json(self, **kwargs):
        self.exit_payload = kwargs
        raise ModuleExit()

    def fail_json(self, **kwargs):
        self.fail_payload = kwargs
        raise ModuleFail(kwargs)


def _inject_sdk(monkeypatch, client):
    service = types.ModuleType("tencentcloud.tat.v20201028")
    service.models = FakeModels
    service.tat_client = types.SimpleNamespace(TatClient=lambda *args: object())
    monkeypatch.setitem(sys.modules, "tencentcloud", types.ModuleType("tencentcloud"))
    monkeypatch.setitem(sys.modules, "tencentcloud.tat",
                        types.ModuleType("tencentcloud.tat"))
    monkeypatch.setitem(sys.modules, "tencentcloud.tat.v20201028", service)


def _run(monkeypatch, client, **params):
    _inject_sdk(monkeypatch, client)
    fake = FakeModule(params)
    fake._client = client
    monkeypatch.setattr(tat_invocation_info, "TencentCloudModule", lambda **kwargs: fake)
    with pytest.raises(ModuleExit):
        tat_invocation_info.run_module()
    return fake


def test_run_module_lists_and_scrubs_redacted_invocations(monkeypatch):
    client = FakeClient([
        FakeResponse("InvocationSet", [FakeItem("i1"), FakeItem("i2")], 3, "req-1"),
        FakeResponse("InvocationSet", [FakeItem("i3")], 3, "req-2"),
    ])
    fake = _run(monkeypatch, client, **list_params())
    payload = fake.exit_payload
    assert payload["changed"] is False
    assert [item["Marker"] for item in payload["invocations"]] == ["i1", "i2", "i3"]
    assert all(item["Parameters"] == "<redacted>" for item in payload["invocations"])
    assert all(item["TaskResult"] == {"Output": "<redacted>"} for item in payload["invocations"])
    assert payload["total_count"] == 3
    assert payload["truncated"] is False
    assert payload["request_id"] == "req-2"
    assert [request.Offset for request in client.invocation_requests] == [0, 2]


def test_run_module_exact_mode_paginates_tasks(monkeypatch):
    client = FakeClient(
        [FakeResponse("InvocationSet", [FakeItem("inv-1")], 1, "req-inv")],
        [
            FakeResponse("InvocationTaskSet", [FakeItem("t1"), FakeItem("t2")], 3, "req-t1"),
            FakeResponse("InvocationTaskSet", [FakeItem("t3")], 3, "req-t2"),
        ],
    )
    fake = _run(monkeypatch, client, **exact_params())
    payload = fake.exit_payload
    assert payload["invocation"]["Marker"] == "inv-1"
    assert [task["Marker"] for task in payload["tasks"]] == ["t1", "t2", "t3"]
    assert payload["request_id"] == "req-t2"
    assert [request.Offset for request in client.task_requests] == [0, 2]


def test_run_module_rejects_include_output_in_list_mode(monkeypatch):
    p = list_params()
    p["include_output"] = True
    fake = FakeModule(p)
    monkeypatch.setattr(tat_invocation_info, "TencentCloudModule", lambda **kwargs: fake)
    with pytest.raises(ModuleFail) as excinfo:
        tat_invocation_info.run_module()
    assert excinfo.value.payload["msg"] == "include_output requires exact invocation_id mode"


class SdkError(Exception):
    def __init__(self, code, request_id):
        self._code = code
        self._request_id = request_id
        super(SdkError, self).__init__("api exploded")

    def get_code(self):
        return self._code

    def get_request_id(self):
        return self._request_id


def test_run_module_fails_cleanly_on_sdk_error(monkeypatch):
    class FailingClient:
        def DescribeInvocations(self, request):
            raise SdkError("FailedOperation", "req-err")

    failing = FailingClient()
    _inject_sdk(monkeypatch, failing)
    fake = FakeModule(list_params())
    fake._client = failing
    monkeypatch.setattr(tat_invocation_info, "TencentCloudModule", lambda **kwargs: fake)
    with pytest.raises(ModuleFail) as excinfo:
        tat_invocation_info.run_module()
    payload = excinfo.value.payload
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert payload["error_code"] == "FailedOperation"
    assert payload["request_id"] == "req-err"
