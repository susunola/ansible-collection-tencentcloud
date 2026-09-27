"""Deep harness tests for tione_notebook_info.

Covers build_request (offset pagination, workspace scoping, stable
filters, tag filters, ordering) and run_module() end to end through the
shared harness: offset-based pagination until TotalCount, max_pages
truncation, argument validation, and the sdk_error_payload fail contract.

The module subclasses ``TencentCloudModule``, so the migration patches the
base class's ``create_client`` and the module's own ``_load`` (which is where
it imports its models and client class), and lets ``module_args()`` supply the
credentials the base class validates. The fixture serialises ``Id``, the
identity field the sibling ``tione_notebook`` module reads off a
``NotebookSetItem``, rather than a generic ``Marker``, so the payload is what
``add_return_samples.py`` captures as the module's documented sample.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import types

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import tione_notebook_info
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    module_args,
    run,
)


def params():
    return {
        "project_id": "p1",
        "filters": {"Status": ["Running"], "Name": "nb"},
        "tag_filters": {"env": "prod"},
        "order_field": "UpdateTime",
        "order": "DESC",
        "page_size": 2,
        "max_pages": 5,
    }


class FakeRequest:
    pass


class FakeFilter:
    pass


class FakeTagFilter:
    pass


class FakeModels:
    DescribeNotebooksRequest = FakeRequest
    Filter = FakeFilter
    TagFilter = FakeTagFilter


def test_build_request_maps_filters_tags_and_order_stably():
    request = tione_notebook_info.build_request(FakeModels, params(), 2)
    assert request.Offset == 2 and request.Limit == 2 and request.TiProjectId == "p1"
    assert [(x.Name, x.Values) for x in request.Filters] == [("Name", ["nb"]), ("Status", ["Running"])]
    assert [(x.TagKey, x.TagValues) for x in request.TagFilters] == [("env", ["prod"])]
    assert request.OrderField == "UpdateTime" and request.Order == "DESC"


class FakeItem:
    def __init__(self, marker):
        self.marker = marker

    def _serialize(self, allow_none=True):
        return {"Id": self.marker}


class FakeResponse:
    def __init__(self, items, total_count, request_id):
        self.NotebookSet = items
        self.TotalCount = total_count
        self.RequestId = request_id


class FakeClient:
    def __init__(self, pages):
        self._pages = list(pages)
        self.requests = []

    def DescribeNotebooks(self, request):
        self.requests.append(request)
        return self._pages.pop(0)


def _patch_sdk(monkeypatch, client):
    """Hand the module its models/client class and the client itself."""
    monkeypatch.setattr(tione_notebook_info, "_load", lambda: (
        FakeModels, types.SimpleNamespace(TioneClient=lambda *args: client)))
    monkeypatch.setattr(TencentCloudModule, "create_client",
                        lambda self, client_class, endpoint: client)


def test_run_module_paginates_until_total_count(monkeypatch):
    client = FakeClient([
        FakeResponse([FakeItem("n1"), FakeItem("n2")], 3, "req-1"),
        FakeResponse([FakeItem("n3")], 3, "req-2"),
    ])
    _patch_sdk(monkeypatch, client)
    module_args(**params())

    payload = run(tione_notebook_info.run_module)

    assert payload["changed"] is False
    assert [item["Id"] for item in payload["notebooks"]] == ["n1", "n2", "n3"]
    assert payload["total_count"] == 3
    assert payload["truncated"] is False
    assert payload["request_id"] == "req-2"
    assert [request.Offset for request in client.requests] == [0, 2]


def test_run_module_flags_truncation_when_page_budget_exhausted(monkeypatch):
    p = params()
    p["max_pages"] = 1
    client = FakeClient([FakeResponse([FakeItem("n1"), FakeItem("n2")], 3, "req-1")])
    _patch_sdk(monkeypatch, client)
    module_args(**p)

    payload = run(tione_notebook_info.run_module)

    assert [item["Id"] for item in payload["notebooks"]] == ["n1", "n2"]
    assert payload["total_count"] == 3
    assert payload["truncated"] is True
    assert payload["request_id"] == "req-1"


def test_run_module_validates_page_size_bounds(monkeypatch):
    p = params()
    p["page_size"] = 201
    _patch_sdk(monkeypatch, FakeClient([]))
    module_args(**p)

    with pytest.raises(AnsibleFailJson) as failure:
        run(tione_notebook_info.run_module)

    assert failure.value.args[0]["msg"] == "page_size must be between 1 and 200"


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
        def DescribeNotebooks(self, request):
            raise SdkError("FailedOperation", "req-err")

    _patch_sdk(monkeypatch, FailingClient())
    module_args(**params())

    with pytest.raises(AnsibleFailJson) as failure:
        run(tione_notebook_info.run_module)

    payload = failure.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert payload["error"] == "api exploded"
    assert payload["error_code"] == "FailedOperation"
    assert payload["request_id"] == "req-err"
