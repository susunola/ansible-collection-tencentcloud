"""Deep harness tests for tat_invocation_info.

Covers the request builders (exact InvocationIds vs command-id / instance-kind
filters, task output hiding), scrub() redaction and run_module() end to end
through the shared harness: bounded invocation list pagination, exact mode with
per-instance task pagination, the include_output guard and the sdk_error_payload
fail contract.

The module subclasses ``TencentCloudModule``, so the migration patches the base
class's ``create_client`` and the module's own ``_load`` (which is where it
imports its models and client class), and lets ``module_args()`` supply the
credentials the base class validates. The fixture serialises the fields the
module actually returns, so the captured payload is what ``scrub`` leaves
behind -- which is also the documented behaviour of this module.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import types

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import tat_invocation_info
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    module_args,
    run,
)


def list_params(**extra):
    """List-mode arguments; mutually exclusive ones are omitted, not None."""
    params = {
        "command_id": "cmd-1",
        "include_tasks": True,
        "include_output": False,
        "page_size": 20,
        "max_pages": 5,
    }
    params.update(extra)
    return params


def exact_params(**extra):
    params = {
        "invocation_id": "inv-1",
        "include_tasks": True,
        "include_output": False,
        "page_size": 20,
        "max_pages": 5,
    }
    params.update(extra)
    return params


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
    assert request.Offset == 100 and request.Limit == 20
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
            "InvocationId": self.marker,
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


def _patch_sdk(monkeypatch, client):
    """Hand the module its models/client class and the client itself."""
    monkeypatch.setattr(tat_invocation_info, "_load", lambda: (
        FakeModels, types.SimpleNamespace(TatClient=lambda *args: client)))
    monkeypatch.setattr(TencentCloudModule, "create_client",
                        lambda self, client_class, endpoint: client)


def test_run_module_lists_and_scrubs_redacted_invocations(monkeypatch):
    client = FakeClient([
        FakeResponse("InvocationSet", [FakeItem("i1"), FakeItem("i2")], 3, "req-1"),
        FakeResponse("InvocationSet", [FakeItem("i3")], 3, "req-2"),
    ])
    _patch_sdk(monkeypatch, client)
    module_args(**list_params())

    payload = run(tat_invocation_info.run_module)

    assert payload["changed"] is False
    assert [item["InvocationId"] for item in payload["invocations"]] == ["i1", "i2", "i3"]
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
    _patch_sdk(monkeypatch, client)
    module_args(**exact_params())

    payload = run(tat_invocation_info.run_module)

    assert payload["invocation"]["InvocationId"] == "inv-1"
    assert [task["InvocationId"] for task in payload["tasks"]] == ["t1", "t2", "t3"]
    assert payload["request_id"] == "req-t2"
    assert [request.Offset for request in client.task_requests] == [0, 2]


def test_run_module_rejects_include_output_in_list_mode(monkeypatch):
    client = FakeClient([])
    _patch_sdk(monkeypatch, client)
    module_args(**list_params(include_output=True))

    with pytest.raises(AnsibleFailJson) as failure:
        run(tat_invocation_info.run_module)

    assert failure.value.args[0]["msg"] == "include_output requires exact invocation_id mode"


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

    _patch_sdk(monkeypatch, FailingClient())
    module_args(**list_params())

    with pytest.raises(AnsibleFailJson) as failure:
        run(tat_invocation_info.run_module)

    payload = failure.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert payload["error_code"] == "FailedOperation"
    assert payload["request_id"] == "req-err"
