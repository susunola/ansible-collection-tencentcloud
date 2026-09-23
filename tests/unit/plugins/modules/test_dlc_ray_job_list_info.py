"""Deep harness tests for dlc_ray_job_list_info.

Covers build_request (page numbering, time bounds, stable filters,
sort fields, scalar wrapping) and run_module() end to end: page-based
pagination until the reported TotalPages, max_pages truncation,
argument validation, and the sdk_error_payload fail contract.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import sys
import types

import pytest

from ansible_collections.susunola.tencentcloud.plugins.modules import dlc_ray_job_list_info


def params():
    return {
        "start_time": 10,
        "end_time": 20,
        "filters": {"z": "2", "a": ["1"]},
        "sort_fields": [{"field": "CreateTime", "order": "DESC"}],
        "page_size": 2,
        "max_pages": 5,
    }


class FakeRequest:
    pass


class FakeFilter:
    pass


class FakeSortField:
    pass


class FakeModels:
    ListRayJobsRequest = FakeRequest
    Filter = FakeFilter
    SortField = FakeSortField


def test_build_request_maps_page_times_filters_and_sorting():
    request = dlc_ray_job_list_info.build_request(FakeModels, params(), 2)
    assert request.Page == 2
    assert request.PageSize == 2
    assert request.StartTime == 10
    assert request.EndTime == 20
    assert [(item.Name, item.Values) for item in request.Filters] == [
        ("a", ["1"]), ("z", ["2"]),
    ]
    assert request.SortFields[0].Field == "CreateTime"
    assert request.SortFields[0].Order == "DESC"


def test_build_request_omits_unset_optional_fields():
    p = {"page_size": 200, "start_time": None, "end_time": None,
         "filters": {}, "sort_fields": None, "max_pages": 5}
    request = dlc_ray_job_list_info.build_request(FakeModels, p, 1)
    assert request.Page == 1
    assert request.PageSize == 200
    assert not hasattr(request, "StartTime")
    assert not hasattr(request, "EndTime")
    assert not hasattr(request, "Filters")
    assert not hasattr(request, "SortFields")


class FakeItem:
    def __init__(self, marker):
        self.marker = marker

    def _serialize(self, allow_none=True):
        return {"Marker": self.marker}


class FakeResponse:
    def __init__(self, items, total_pages, request_id):
        self.Items = items
        self.TotalPages = total_pages
        self.RequestId = request_id


class FakeClient:
    def __init__(self, pages):
        self._pages = list(pages)
        self.requests = []

    def ListRayJobs(self, request):
        self.requests.append(request)
        return self._pages.pop(0)


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
    service = types.ModuleType("tencentcloud.dlc.v20210125")
    service.models = FakeModels
    service.dlc_client = types.SimpleNamespace(DlcClient=lambda *args: object())
    monkeypatch.setitem(sys.modules, "tencentcloud", types.ModuleType("tencentcloud"))
    monkeypatch.setitem(sys.modules, "tencentcloud.dlc",
                        types.ModuleType("tencentcloud.dlc"))
    monkeypatch.setitem(sys.modules, "tencentcloud.dlc.v20210125", service)


def _run(monkeypatch, client, **params):
    _inject_sdk(monkeypatch, client)
    fake = FakeModule(params)
    fake._client = client
    monkeypatch.setattr(dlc_ray_job_list_info, "TencentCloudModule", lambda **kwargs: fake)
    with pytest.raises(ModuleExit):
        dlc_ray_job_list_info.run_module()
    return fake


def test_run_module_paginates_until_reported_total_pages(monkeypatch):
    client = FakeClient([
        FakeResponse([FakeItem("a"), FakeItem("b")], 2, "req-1"),
        FakeResponse([FakeItem("c")], 2, "req-2"),
    ])
    fake = _run(monkeypatch, client, **params())
    payload = fake.exit_payload
    assert payload["changed"] is False
    assert [item["Marker"] for item in payload["ray_jobs"]] == ["a", "b", "c"]
    assert payload["fetched_count"] == 3
    assert payload["total_pages"] == 2
    assert payload["truncated"] is False
    assert payload["request_id"] == "req-2"
    assert [request.Page for request in client.requests] == [1, 2]


def test_run_module_flags_truncation_when_page_budget_exhausted(monkeypatch):
    p = params()
    p["max_pages"] = 1
    client = FakeClient([FakeResponse([FakeItem("a"), FakeItem("b")], 2, "req-1")])
    fake = _run(monkeypatch, client, **p)
    payload = fake.exit_payload
    assert [item["Marker"] for item in payload["ray_jobs"]] == ["a", "b"]
    assert payload["total_pages"] == 2
    assert payload["truncated"] is True
    assert payload["request_id"] == "req-1"


def test_run_module_validates_page_size_bounds(monkeypatch):
    p = params()
    p["page_size"] = 0
    fake = FakeModule(p)
    monkeypatch.setattr(dlc_ray_job_list_info, "TencentCloudModule", lambda **kwargs: fake)
    with pytest.raises(ModuleFail) as excinfo:
        dlc_ray_job_list_info.run_module()
    assert excinfo.value.payload["msg"] == "page_size must be between 1 and 200"


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
        def ListRayJobs(self, request):
            raise SdkError("FailedOperation", "req-err")

    failing = FailingClient()
    _inject_sdk(monkeypatch, failing)
    fake = FakeModule(params())
    fake._client = failing
    monkeypatch.setattr(dlc_ray_job_list_info, "TencentCloudModule", lambda **kwargs: fake)
    with pytest.raises(ModuleFail) as excinfo:
        dlc_ray_job_list_info.run_module()
    payload = excinfo.value.payload
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert payload["error"] == "api exploded"
    assert payload["error_code"] == "FailedOperation"
    assert payload["request_id"] == "req-err"
