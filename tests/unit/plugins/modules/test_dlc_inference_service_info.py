"""Deep harness tests for the dlc_inference_service_info module.

Covers build_request (time bounds, stable filter ordering, ordered sort
fields, page-number pagination) plus run_module page pagination, page-budget
truncation, empty results, parameter validation and the sdk_error_payload
failure contract.

The module subclasses ``TencentCloudModule``, so the migration patches the base
class's ``create_client`` and the module's own ``_load`` (which is where it
imports its models and client class), and lets ``module_args()`` supply the
credentials the base class validates. The fake item serialises ``Name``, a real
``InferenceServiceInfo`` field the API returns, so the payload
``add_return_samples.py`` captures is the shape a caller really sees.
"""
from __future__ import absolute_import, division, print_function

__metaclass__ = type

import types

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import dlc_inference_service_info
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    module_args,
    run,
)


class Object:
    pass


class FakeModels:
    Filter = Object
    SortField = Object
    ListInferenceServicesRequest = Object


def params(**overrides):
    options = {
        "start_time": 10,
        "end_time": 20,
        "filters": {"z": "2", "a": ["1"]},
        "sort_fields": [{"field": "CreateTime", "order": "DESC"}],
        "page_size": 2,
        "max_pages": 5,
    }
    options.update(overrides)
    return options


def test_build_request_sorts_filters_and_preserves_sort_priority():
    request = dlc_inference_service_info.build_request(FakeModels, params(), 2)
    assert request.Page == 2
    assert request.PageSize == 2
    assert request.StartTime == 10
    assert request.EndTime == 20
    assert [(item.Name, item.Values) for item in request.Filters] == [("a", ["1"]), ("z", ["2"])]
    assert [(item.Field, item.Order) for item in request.SortFields] == [("CreateTime", "DESC")]


def test_build_request_omits_absent_bounds_filters_and_sort():
    p = {"start_time": None, "end_time": None, "filters": {}, "sort_fields": None, "page_size": 2, "max_pages": 5}
    request = dlc_inference_service_info.build_request(FakeModels, p, 1)
    assert request.Page == 1
    for attribute in ("StartTime", "EndTime", "Filters", "SortFields"):
        assert not hasattr(request, attribute)


class FakeItem:
    def __init__(self, name):
        self.name = name

    def _serialize(self, allow_none=True):
        return {"Name": self.name}


class FakeResponse:
    def __init__(self, items, total_pages, total, request_id):
        self.Items = items
        self.TotalPages = total_pages
        self.Total = total
        self.RequestId = request_id


class FakeClient:
    def __init__(self, pages):
        self._pages = list(pages)
        self.requests = []

    def ListInferenceServices(self, request):
        self.requests.append(request)
        return self._pages.pop(0)


class SDKError(Exception):
    def get_code(self):
        return "UnauthorizedOperation"

    def get_request_id(self):
        return "req-err"


def _patch_sdk(monkeypatch, client):
    """Hand the module its models/client class and the client itself."""
    monkeypatch.setattr(dlc_inference_service_info, "_load", lambda: (
        FakeModels, types.SimpleNamespace(DlcClient=lambda *args: client)))
    monkeypatch.setattr(TencentCloudModule, "create_client",
                        lambda self, client_class, endpoint: client)


def test_run_module_follows_all_service_pages(monkeypatch):
    client = FakeClient([
        FakeResponse([FakeItem("a"), FakeItem("b")], 2, 3, "r1"),
        FakeResponse([FakeItem("c")], 2, 3, "r2"),
    ])
    _patch_sdk(monkeypatch, client)
    module_args(region="ap-guangzhou", **params())

    payload = run(dlc_inference_service_info.run_module)

    assert payload["changed"] is False
    assert [item["Name"] for item in payload["services"]] == ["a", "b", "c"]
    assert payload["total_count"] == 3
    assert payload["truncated"] is False
    assert payload["request_id"] == "r2"
    assert [request.Page for request in client.requests] == [1, 2]
    assert [request.PageSize for request in client.requests] == [2, 2]


def test_run_module_reports_truncation_at_max_pages(monkeypatch):
    client = FakeClient([FakeResponse([FakeItem("a"), FakeItem("b")], 2, 3, "r1")])
    _patch_sdk(monkeypatch, client)
    module_args(region="ap-guangzhou", **params(max_pages=1))

    payload = run(dlc_inference_service_info.run_module)

    assert [item["Name"] for item in payload["services"]] == ["a", "b"]
    assert payload["total_count"] == 3
    assert payload["truncated"] is True
    assert payload["request_id"] == "r1"


def test_run_module_returns_empty_when_no_services(monkeypatch):
    client = FakeClient([FakeResponse([], 0, 0, "r-empty")])
    _patch_sdk(monkeypatch, client)
    module_args(region="ap-guangzhou", **params())

    payload = run(dlc_inference_service_info.run_module)

    assert payload["services"] == []
    assert payload["total_count"] == 0
    assert payload["truncated"] is False


def test_run_module_validates_page_size_and_time_bounds(monkeypatch):
    _patch_sdk(monkeypatch, FakeClient([]))

    module_args(region="ap-guangzhou", **params(page_size=300))
    with pytest.raises(AnsibleFailJson) as failure:
        run(dlc_inference_service_info.run_module)
    assert failure.value.args[0]["msg"] == "page_size must be between 1 and 200"

    module_args(region="ap-guangzhou", **params(start_time=30, end_time=10))
    with pytest.raises(AnsibleFailJson) as failure:
        run(dlc_inference_service_info.run_module)
    assert failure.value.args[0]["msg"] == "start_time must not exceed end_time"


def test_run_module_fails_cleanly_on_sdk_error(monkeypatch):
    class FailingClient:
        def ListInferenceServices(self, request):
            raise SDKError("api exploded")

    _patch_sdk(monkeypatch, FailingClient())
    module_args(region="ap-guangzhou", **params())

    with pytest.raises(AnsibleFailJson) as failure:
        run(dlc_inference_service_info.run_module)

    payload = failure.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert payload["error"] == "api exploded"
    assert payload["error_code"] == "UnauthorizedOperation"
    assert payload["request_id"] == "req-err"
