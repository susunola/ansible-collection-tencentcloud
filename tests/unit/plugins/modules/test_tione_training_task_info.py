"""Deep harness tests for tione_training_task_info.

Covers the exact task detail request (task_id plus optional historical
instance_id and TiProjectId), the list request builder (offset
pagination, project scoping, stable filters, tag filters, ordering), the
read_list pagination loop including max_pages budget truncation, and
run_module() end to end through the shared harness: exact detail lookup,
bounded list pagination, argument validation and the sdk_error_payload fail
contract.

The module subclasses ``TencentCloudModule``, so the migration patches the
base class's ``create_client`` and the module's own ``_load`` (which is where
it imports its models and client class), and lets ``module_args()`` supply the
credentials the base class validates. Its fixture already serialised ``Id``,
the identity field the sibling ``tione_training_task`` module reads off a
``TrainingTaskSetItem``, so no field is renamed here.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import types

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import tione_training_task_info
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    module_args,
    run,
)


class FakeFilter:
    pass


class FakeTagFilter:
    pass


class FakeRequest:
    pass


class FakeModels:
    DescribeTrainingTaskRequest = FakeRequest
    DescribeTrainingTasksRequest = FakeRequest
    Filter = FakeFilter
    TagFilter = FakeTagFilter


def params():
    return {
        "task_id": None,
        "instance_id": None,
        "project_id": "p1",
        "filters": {"Status": ["RUNNING"], "Name": "job"},
        "tag_filters": {"team": "ml"},
        "order_field": "StartTime",
        "order": "DESC",
        "page_size": 2,
        "max_pages": 5,
    }


def module_params(**overrides):
    """Module arguments with the unsupplied keys omitted, not passed as None.

    ``params()`` carries ``task_id``/``instance_id`` as ``None`` for the
    request-builder tests, but Ansible counts an explicitly passed ``None`` as
    specified, so ``task_id=None`` next to the defaulted ``filters`` trips the
    module's ``("task_id", "filters")`` mutual exclusion. Detail mode is
    mutually exclusive with both filter options as well, so they are dropped
    whenever ``task_id`` is supplied.
    """
    values = {key: value for key, value in params().items() if value is not None}
    values.update(overrides)
    if values.get("task_id"):
        values.pop("filters", None)
        values.pop("tag_filters", None)
    return values


def test_detail_request_supports_historical_instance():
    p = params()
    p["task_id"], p["instance_id"] = "train-1", "instance-2"
    request = tione_training_task_info.detail_request(FakeModels, p)
    assert request.Id == "train-1"
    assert request.InstanceId == "instance-2"
    assert request.TiProjectId == "p1"


def test_detail_request_skips_missing_workspace_and_instance():
    p = params()
    p["task_id"] = "train-1"
    p["project_id"] = None
    request = tione_training_task_info.detail_request(FakeModels, p)
    assert request.Id == "train-1"
    assert not hasattr(request, "TiProjectId")
    assert not hasattr(request, "InstanceId")


def test_list_request_maps_filters_tags_and_order_stably():
    request = tione_training_task_info.list_request(FakeModels, params(), 2)
    assert request.Offset == 2 and request.Limit == 2
    assert request.TiProjectId == "p1"
    assert [(item.Name, item.Values) for item in request.Filters] == [
        ("Name", ["job"]), ("Status", ["RUNNING"])]
    assert request.TagFilters[0].TagKey == "team"
    assert request.TagFilters[0].TagValues == ["ml"]
    assert request.OrderField == "StartTime" and request.Order == "DESC"


class FakeItem:
    def __init__(self, marker):
        self.marker = marker

    def _serialize(self, allow_none=True):
        return {"Id": self.marker}


class FakeListResponse:
    def __init__(self, items, total_count, request_id):
        self.TrainingTaskSet = items
        self.TotalCount = total_count
        self.RequestId = request_id


class FakeDetailResponse:
    def __init__(self, detail, request_id):
        self.TrainingTaskDetail = detail
        self.RequestId = request_id


class FakeClient:
    def __init__(self, pages=None):
        self._pages = list(pages or [])
        self.list_requests = []
        self.detail_request = None
        self.detail_response = None

    def DescribeTrainingTasks(self, request):
        self.list_requests.append(request)
        return self._pages.pop(0)

    def DescribeTrainingTask(self, request):
        self.detail_request = request
        return self.detail_response


def _patch_sdk(monkeypatch, client):
    """Hand the module its models/client class and the client itself."""
    monkeypatch.setattr(tione_training_task_info, "_load", lambda: (
        FakeModels, types.SimpleNamespace(TioneClient=lambda *args: client)))
    monkeypatch.setattr(TencentCloudModule, "create_client",
                        lambda self, client_class, endpoint: client)


def test_run_module_describes_exact_task(monkeypatch):
    client = FakeClient()
    client.detail_response = FakeDetailResponse(FakeItem("train-1"), "req-detail")
    _patch_sdk(monkeypatch, client)
    module_args(**module_params(task_id="train-1"))

    payload = run(tione_training_task_info.run_module)

    assert payload["changed"] is False
    assert payload["training_task"] == {"Id": "train-1"}
    assert payload["request_id"] == "req-detail"
    assert client.detail_request.Id == "train-1"
    assert client.list_requests == []


def test_run_module_paginates_tasks_until_total_count(monkeypatch):
    client = FakeClient([
        FakeListResponse([FakeItem("t1"), FakeItem("t2")], 3, "req-1"),
        FakeListResponse([FakeItem("t3")], 3, "req-2"),
    ])
    _patch_sdk(monkeypatch, client)
    module_args(**module_params())

    payload = run(tione_training_task_info.run_module)

    assert payload["changed"] is False
    assert [item["Id"] for item in payload["training_tasks"]] == ["t1", "t2", "t3"]
    assert payload["total_count"] == 3
    assert payload["truncated"] is False
    assert payload["request_id"] == "req-2"
    assert [request.Offset for request in client.list_requests] == [0, 2]


def test_run_module_reports_truncation_when_max_pages_exhausted(monkeypatch):
    client = FakeClient([
        FakeListResponse([FakeItem("t1"), FakeItem("t2")], 3, "req-1"),
        FakeListResponse([FakeItem("t3")], 3, "req-2"),
    ])
    _patch_sdk(monkeypatch, client)
    module_args(**module_params(max_pages=1))

    payload = run(tione_training_task_info.run_module)

    assert [item["Id"] for item in payload["training_tasks"]] == ["t1", "t2"]
    assert payload["total_count"] == 3
    assert payload["truncated"] is True
    assert payload["request_id"] == "req-1"
    assert len(client.list_requests) == 1


def test_run_module_empty_page_reports_zero(monkeypatch):
    client = FakeClient([FakeListResponse([], 0, "req-empty")])
    _patch_sdk(monkeypatch, client)
    module_args(**module_params())

    payload = run(tione_training_task_info.run_module)

    assert payload["training_tasks"] == []
    assert payload["total_count"] == 0
    assert payload["truncated"] is False


@pytest.mark.parametrize("overrides,message", [
    ({"page_size": 0}, "page_size must be between 1 and 50"),
    ({"page_size": 51}, "page_size must be between 1 and 50"),
    ({"max_pages": 0}, "max_pages must be between 1 and 1000"),
    ({"max_pages": 1001}, "max_pages must be between 1 and 1000"),
])
def test_run_module_validates_pagination_bounds(monkeypatch, overrides, message):
    _patch_sdk(monkeypatch, FakeClient([]))
    module_args(**module_params(**overrides))

    with pytest.raises(AnsibleFailJson) as failure:
        run(tione_training_task_info.run_module)

    assert failure.value.args[0]["msg"] == message


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
        def DescribeTrainingTasks(self, request):
            raise SdkError("FailedOperation", "req-err")

    _patch_sdk(monkeypatch, FailingClient())
    module_args(**module_params())

    with pytest.raises(AnsibleFailJson) as failure:
        run(tione_training_task_info.run_module)

    payload = failure.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert payload["error"] == "api exploded"
    assert payload["error_code"] == "FailedOperation"
    assert payload["request_id"] == "req-err"
