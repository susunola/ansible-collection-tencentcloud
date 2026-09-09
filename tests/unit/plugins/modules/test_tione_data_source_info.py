"""Deep harness tests for tione_data_source_info.

Covers build_request (offset pagination, workspace scoping, stable
filters, tag filters, ordering) and run_module() end to end:
offset-based pagination until TotalCount, max_pages truncation,
argument validation, and the sdk_error_payload fail contract.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import sys
import types

import pytest

from ansible_collections.susunola.tencentcloud.plugins.modules import tione_data_source_info


def params():
    return {
        "project_id": "p1",
        "filters": {"z": "2", "a": ["1"]},
        "tag_filters": {"team": ["ml"], "env": "prod"},
        "order_field": "CreateTime",
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
    DescribeDataSourcesRequest = FakeRequest
    Filter = FakeFilter
    TagFilter = FakeTagFilter


def test_build_request_maps_workspace_filters_tags_and_order_stably():
    request = tione_data_source_info.build_request(FakeModels, params(), 2)
    assert request.Offset == 2 and request.Limit == 2 and request.TiProjectId == "p1"
    assert [(x.Name, x.Values) for x in request.Filters] == [("a", ["1"]), ("z", ["2"])]
    assert [(x.TagKey, x.TagValues) for x in request.TagFilters] == [("env", ["prod"]), ("team", ["ml"])]
    assert request.OrderField == "CreateTime" and request.Order == "DESC"


class FakeItem:
    def __init__(self, marker):
        self.marker = marker

    def _serialize(self, allow_none=True):
        return {"Marker": self.marker}


class FakeResponse:
    def __init__(self, items, total_count, request_id):
        self.DataSourceInfos = items
        self.TotalCount = total_count
        self.RequestId = request_id


class FakeClient:
    def __init__(self, pages):
        self._pages = list(pages)
        self.requests = []

    def DescribeDataSources(self, request):
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
    service = types.ModuleType("tencentcloud.tione.v20211111")
    service.models = FakeModels
    service.tione_client = types.SimpleNamespace(TioneClient=lambda *args: object())
    monkeypatch.setitem(sys.modules, "tencentcloud", types.ModuleType("tencentcloud"))
    monkeypatch.setitem(sys.modules, "tencentcloud.tione",
                        types.ModuleType("tencentcloud.tione"))
    monkeypatch.setitem(sys.modules, "tencentcloud.tione.v20211111", service)


def _run(monkeypatch, client, **params):
    _inject_sdk(monkeypatch, client)
    fake = FakeModule(params)
    fake._client = client
    monkeypatch.setattr(tione_data_source_info, "TencentCloudModule", lambda **kwargs: fake)
    with pytest.raises(ModuleExit):
        tione_data_source_info.run_module()
    return fake


def test_run_module_paginates_until_total_count(monkeypatch):
    client = FakeClient([
        FakeResponse([FakeItem("d1"), FakeItem("d2")], 3, "req-1"),
        FakeResponse([FakeItem("d3")], 3, "req-2"),
    ])
    fake = _run(monkeypatch, client, **params())
    payload = fake.exit_payload
    assert payload["changed"] is False
    assert [item["Marker"] for item in payload["data_sources"]] == ["d1", "d2", "d3"]
    assert payload["total_count"] == 3
    assert payload["truncated"] is False
    assert payload["request_id"] == "req-2"
    assert [request.Offset for request in client.requests] == [0, 2]


def test_run_module_flags_truncation_when_page_budget_exhausted(monkeypatch):
    p = params()
    p["max_pages"] = 1
    client = FakeClient([FakeResponse([FakeItem("d1"), FakeItem("d2")], 3, "req-1")])
    fake = _run(monkeypatch, client, **p)
    payload = fake.exit_payload
    assert [item["Marker"] for item in payload["data_sources"]] == ["d1", "d2"]
    assert payload["total_count"] == 3
    assert payload["truncated"] is True
    assert payload["request_id"] == "req-1"


def test_run_module_validates_page_size_bounds(monkeypatch):
    p = params()
    p["page_size"] = 0
    fake = FakeModule(p)
    monkeypatch.setattr(tione_data_source_info, "TencentCloudModule", lambda **kwargs: fake)
    with pytest.raises(ModuleFail) as excinfo:
        tione_data_source_info.run_module()
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
        def DescribeDataSources(self, request):
            raise SdkError("FailedOperation", "req-err")

    failing = FailingClient()
    _inject_sdk(monkeypatch, failing)
    fake = FakeModule(params())
    fake._client = failing
    monkeypatch.setattr(tione_data_source_info, "TencentCloudModule", lambda **kwargs: fake)
    with pytest.raises(ModuleFail) as excinfo:
        tione_data_source_info.run_module()
    payload = excinfo.value.payload
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert payload["error"] == "api exploded"
    assert payload["error_code"] == "FailedOperation"
    assert payload["request_id"] == "req-err"
