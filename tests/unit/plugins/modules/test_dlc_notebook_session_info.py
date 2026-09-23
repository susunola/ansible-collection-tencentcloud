"""Deep harness tests for the dlc_notebook_session_info module.

Covers build_request (offset pagination, exact engine/state filters, ordered
notebook-keyword and engine-generation filter pairs, sort fields) plus
run_module offset pagination over DescribeNotebookSessions, empty results,
page_size validation and the sdk_error_payload failure contract.
"""
from __future__ import absolute_import, division, print_function

__metaclass__ = type

import sys
import types

import pytest

from ansible_collections.susunola.tencentcloud.plugins.modules import dlc_notebook_session_info


class Object:
    pass


class FakeModels:
    Filter = Object
    DescribeNotebookSessionsRequest = Object


def params(**overrides):
    options = {
        "data_engine_name": "spark-prod",
        "states": ["idle", "busy"],
        "keyword": "analyst",
        "engine_generation": "supersql",
        "sort_fields": ["create_time"],
        "ascending": True,
        "page_size": 2,
    }
    options.update(overrides)
    return options


def test_build_request_maps_filters_sort_and_pagination():
    request = dlc_notebook_session_info.build_request(FakeModels, params(), 4)
    assert request.Offset == 4
    assert request.Limit == 2
    assert request.Asc is True
    assert request.DataEngineName == "spark-prod"
    assert request.State == ["idle", "busy"]
    assert request.SortFields == ["create_time"]
    assert [(item.Name, item.Values) for item in request.Filters] == [
        ("engine-generation", ["supersql"]), ("notebook-keyword", ["analyst"]),
    ]


def test_build_request_defaults_offset_and_omits_absent_filters():
    p = {"data_engine_name": None, "states": None, "keyword": None, "engine_generation": None,
         "sort_fields": None, "ascending": False, "page_size": 2}
    request = dlc_notebook_session_info.build_request(FakeModels, p)
    assert request.Offset == 0
    assert request.Limit == 2
    assert request.Asc is False
    for attribute in ("DataEngineName", "State", "SortFields", "Filters"):
        assert not hasattr(request, attribute)


class FakeItem:
    def __init__(self, name):
        self.name = name

    def _serialize(self, allow_none=True):
        return {"Name": self.name}


class FakeResponse:
    def __init__(self, sessions, total_elements, request_id):
        self.Sessions = sessions
        self.TotalElements = total_elements
        self.RequestId = request_id


class FakeClient:
    def __init__(self, pages):
        self._pages = list(pages)
        self.requests = []

    def DescribeNotebookSessions(self, request):
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
    monkeypatch.setattr(dlc_notebook_session_info, "TencentCloudModule", lambda **kwargs: fake)
    with pytest.raises(ModuleFail if expect_fail else ModuleExit):
        dlc_notebook_session_info.run_module()
    return fake


def test_run_module_fetches_all_session_pages(monkeypatch):
    client = FakeClient([
        FakeResponse([FakeItem("a"), FakeItem("b")], 3, "r1"),
        FakeResponse([FakeItem("c")], 3, "r2"),
    ])
    fake = _run(monkeypatch, client, region="ap-guangzhou", **params())
    payload = fake.exit_payload
    assert payload["changed"] is False
    assert [item["Name"] for item in payload["sessions"]] == ["a", "b", "c"]
    assert payload["total_count"] == 3
    assert payload["request_id"] == "r2"
    assert [request.Offset for request in client.requests] == [0, 2]
    assert [request.Limit for request in client.requests] == [2, 2]


def test_run_module_returns_empty_when_no_sessions(monkeypatch):
    p = {"data_engine_name": None, "states": None, "keyword": None, "engine_generation": None,
         "sort_fields": None, "ascending": False, "page_size": 2}
    client = FakeClient([FakeResponse([], 0, "r-empty")])
    fake = _run(monkeypatch, client, region="ap-guangzhou", **p)
    payload = fake.exit_payload
    assert payload["sessions"] == []
    assert payload["total_count"] == 0
    assert payload["request_id"] == "r-empty"
    assert len(client.requests) == 1


def test_run_module_validates_page_size_range(monkeypatch):
    payload = _run(monkeypatch, FakeClient([]), expect_fail=True,
                   region="ap-guangzhou", **params(page_size=200)).fail_payload
    assert payload["msg"] == "page_size must be between 1 and 100"


def test_run_module_fails_cleanly_on_sdk_error(monkeypatch):
    class FailingClient:
        def DescribeNotebookSessions(self, request):
            raise SDKError("api exploded")

    payload = _run(monkeypatch, FailingClient(), expect_fail=True,
                   region="ap-guangzhou", **params()).fail_payload
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert payload["error"] == "api exploded"
    assert payload["error_code"] == "UnauthorizedOperation"
    assert payload["request_id"] == "req-err"
