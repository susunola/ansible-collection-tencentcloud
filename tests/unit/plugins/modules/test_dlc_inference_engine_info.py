"""Deep harness tests for the dlc_inference_engine_info module.

Covers build_request (time bounds, stable filter ordering, ordered sort
fields, page-number pagination) plus run_module page pagination, page-budget
truncation, empty results, parameter validation and sdk_error_payload fails.
"""
from __future__ import absolute_import, division, print_function

__metaclass__ = type

import sys
import types

import pytest

from ansible_collections.susunola.tencentcloud.plugins.modules import dlc_inference_engine_info


class Object:
    pass


class FakeModels:
    Filter = Object
    SortField = Object
    ListInferenceEnginesRequest = Object


def params(**overrides):
    options = {
        "start_time": 10,
        "end_time": 20,
        "filters": {"model_type": ["LLM"], "enabled": "true"},
        "sort_fields": [{"field": "Name", "order": "ASC"}],
        "page_size": 2,
        "max_pages": 5,
    }
    options.update(overrides)
    return options


def test_build_request_maps_runtime_discovery_controls_stably():
    request = dlc_inference_engine_info.build_request(FakeModels, params(), 2)
    assert request.Page == 2
    assert request.PageSize == 2
    assert request.StartTime == 10
    assert request.EndTime == 20
    assert [(item.Name, item.Values) for item in request.Filters] == [
        ("enabled", ["true"]), ("model_type", ["LLM"]),
    ]
    assert [(item.Field, item.Order) for item in request.SortFields] == [("Name", "ASC")]


def test_build_request_omits_absent_bounds_filters_and_sort():
    p = {"start_time": None, "end_time": None, "filters": {}, "sort_fields": None, "page_size": 2, "max_pages": 5}
    request = dlc_inference_engine_info.build_request(FakeModels, p, 1)
    assert request.Page == 1
    for attribute in ("StartTime", "EndTime", "Filters", "SortFields"):
        assert not hasattr(request, attribute)


class FakeItem:
    def __init__(self, engine_id):
        self.engine_id = engine_id

    def _serialize(self, allow_none=True):
        return {"EngineId": self.engine_id}


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

    def ListInferenceEngines(self, request):
        self.requests.append(request)
        return self._pages.pop(0)


class ModuleExit(BaseException):
    pass


class ModuleFail(BaseException):
    def __init__(self, payload):
        self.payload = payload
        super(ModuleFail, self).__init__("module failed: %r" % (payload,))


class SDKError(Exception):
    def get_code(self):
        return "UnauthorizedOperation"

    def get_request_id(self):
        return "req-err"


class FakeModule:
    def __init__(self, params, client):
        self.params = params
        self.client = client
        self.exit_payload = None
        self.fail_payload = None

    def exit_json(self, **kwargs):
        self.exit_payload = kwargs
        raise ModuleExit()

    def fail_json(self, **kwargs):
        self.fail_payload = kwargs
        raise ModuleFail(kwargs)

    def require_sdk(self):
        pass

    def create_client(self, client_class, endpoint):
        return self.client

    def sdk_call(self, operation, request=None, retry=True):
        if request is None:
            return operation()
        return operation(request)


def _inject_sdk(monkeypatch):
    service = types.ModuleType("tencentcloud.dlc.v20210125")
    service.models = FakeModels
    service.dlc_client = types.SimpleNamespace(DlcClient=object)
    monkeypatch.setitem(sys.modules, "tencentcloud", types.ModuleType("tencentcloud"))
    monkeypatch.setitem(sys.modules, "tencentcloud.dlc",
                        types.ModuleType("tencentcloud.dlc"))
    monkeypatch.setitem(sys.modules, "tencentcloud.dlc.v20210125", service)


def _run(monkeypatch, client, expect_fail=False, **p):
    _inject_sdk(monkeypatch)
    fake = FakeModule(p, client)
    monkeypatch.setattr(dlc_inference_engine_info, "TencentCloudModule", lambda **kwargs: fake)
    with pytest.raises(ModuleFail if expect_fail else ModuleExit):
        dlc_inference_engine_info.run_module()
    return fake


def test_run_module_follows_all_engine_pages(monkeypatch):
    client = FakeClient([
        FakeResponse([FakeItem("e1"), FakeItem("e2")], 2, 3, "r1"),
        FakeResponse([FakeItem("e3")], 2, 3, "r2"),
    ])
    fake = _run(monkeypatch, client, region="ap-guangzhou", **params())
    payload = fake.exit_payload
    assert payload["changed"] is False
    assert [item["EngineId"] for item in payload["engines"]] == ["e1", "e2", "e3"]
    assert payload["total_count"] == 3
    assert payload["truncated"] is False
    assert payload["request_id"] == "r2"
    assert [request.Page for request in client.requests] == [1, 2]
    assert [request.PageSize for request in client.requests] == [2, 2]


def test_run_module_reports_truncation_at_max_pages(monkeypatch):
    p = params(max_pages=1)
    client = FakeClient([FakeResponse([FakeItem("e1"), FakeItem("e2")], 2, 3, "r1")])
    fake = _run(monkeypatch, client, region="ap-guangzhou", **p)
    payload = fake.exit_payload
    assert [item["EngineId"] for item in payload["engines"]] == ["e1", "e2"]
    assert payload["total_count"] == 3
    assert payload["truncated"] is True
    assert payload["request_id"] == "r1"


def test_run_module_returns_empty_when_no_engines(monkeypatch):
    client = FakeClient([FakeResponse([], 0, 0, "r-empty")])
    fake = _run(monkeypatch, client, region="ap-guangzhou", **params())
    payload = fake.exit_payload
    assert payload["engines"] == []
    assert payload["total_count"] == 0
    assert payload["truncated"] is False


def test_run_module_validates_page_size_and_time_bounds(monkeypatch):
    payload = _run(monkeypatch, FakeClient([]), expect_fail=True,
                   region="ap-guangzhou", **params(page_size=0)).fail_payload
    assert payload["msg"] == "page_size must be between 1 and 200"
    payload = _run(monkeypatch, FakeClient([]), expect_fail=True,
                   region="ap-guangzhou", **params(start_time=30, end_time=10)).fail_payload
    assert payload["msg"] == "start_time must not exceed end_time"


def test_run_module_fails_cleanly_on_sdk_error(monkeypatch):
    class FailingClient:
        def ListInferenceEngines(self, request):
            raise SDKError("api exploded")

    payload = _run(monkeypatch, FailingClient(), expect_fail=True,
                   region="ap-guangzhou", **params()).fail_payload
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert payload["error"] == "api exploded"
    assert payload["error_code"] == "UnauthorizedOperation"
    assert payload["request_id"] == "req-err"
