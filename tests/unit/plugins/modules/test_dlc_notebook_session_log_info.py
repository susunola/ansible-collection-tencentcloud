"""Deep harness tests for the dlc_notebook_session_log_info module.

Covers build_request (exact session identity, offset pagination) plus
run_module log-line pagination that stops on a short page, page-cap
truncation, empty results, page_size/max_pages validation and the
sdk_error_payload failure contract.
"""
from __future__ import absolute_import, division, print_function

__metaclass__ = type

import sys
import types

import pytest

from ansible_collections.susunola.tencentcloud.plugins.modules import dlc_notebook_session_log_info


class Object:
    pass


class FakeModels:
    DescribeNotebookSessionLogRequest = Object


def test_build_request_uses_exact_session_and_offset():
    request = dlc_notebook_session_log_info.build_request(FakeModels, "session-1", 200, 200)
    assert request.SessionId == "session-1"
    assert request.Offset == 200
    assert request.Limit == 200


class FakeResponse:
    def __init__(self, logs, request_id):
        self.Logs = logs
        self.RequestId = request_id


class FakeClient:
    def __init__(self, pages):
        self._pages = list(pages)
        self.requests = []

    def DescribeNotebookSessionLog(self, request):
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
    monkeypatch.setattr(dlc_notebook_session_log_info, "TencentCloudModule", lambda **kwargs: fake)
    with pytest.raises(ModuleFail if expect_fail else ModuleExit):
        dlc_notebook_session_log_info.run_module()
    return fake


def test_run_module_stops_on_short_page(monkeypatch):
    p = {"session_id": "session-1", "page_size": 2, "max_pages": 5}
    client = FakeClient([FakeResponse(["a", "b"], "r1"), FakeResponse(["c"], "r2")])
    fake = _run(monkeypatch, client, region="ap-guangzhou", **p)
    payload = fake.exit_payload
    assert payload["changed"] is False
    assert payload["logs"] == ["a", "b", "c"]
    assert payload["truncated"] is False
    assert payload["request_id"] == "r2"
    assert [request.Offset for request in client.requests] == [0, 2]
    assert [request.SessionId for request in client.requests] == ["session-1", "session-1"]


def test_run_module_reports_page_cap_on_full_pages(monkeypatch):
    p = {"session_id": "session-1", "page_size": 1, "max_pages": 1}
    client = FakeClient([FakeResponse(["a"], "r1")])
    fake = _run(monkeypatch, client, region="ap-guangzhou", **p)
    payload = fake.exit_payload
    assert payload["logs"] == ["a"]
    assert payload["truncated"] is True
    assert payload["request_id"] == "r1"
    assert [request.Offset for request in client.requests] == [0]


def test_run_module_returns_empty_when_no_logs(monkeypatch):
    p = {"session_id": "session-1", "page_size": 2, "max_pages": 5}
    client = FakeClient([FakeResponse([], "r-empty")])
    fake = _run(monkeypatch, client, region="ap-guangzhou", **p)
    payload = fake.exit_payload
    assert payload["logs"] == []
    assert payload["truncated"] is False
    assert payload["request_id"] == "r-empty"
    assert [request.Offset for request in client.requests] == [0]


def test_run_module_validates_page_size_and_max_pages(monkeypatch):
    payload = _run(monkeypatch, FakeClient([]), expect_fail=True, region="ap-guangzhou",
                   session_id="session-1", page_size=0, max_pages=5).fail_payload
    assert payload["msg"] == "page_size must be between 1 and 1000"
    payload = _run(monkeypatch, FakeClient([]), expect_fail=True, region="ap-guangzhou",
                   session_id="session-1", page_size=2, max_pages=1001).fail_payload
    assert payload["msg"] == "max_pages must be between 1 and 1000"


def test_run_module_fails_cleanly_on_sdk_error(monkeypatch):
    class FailingClient:
        def DescribeNotebookSessionLog(self, request):
            raise SDKError("api exploded")

    p = {"session_id": "session-1", "page_size": 2, "max_pages": 5}
    payload = _run(monkeypatch, FailingClient(), expect_fail=True,
                   region="ap-guangzhou", **p).fail_payload
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert payload["error"] == "api exploded"
    assert payload["error_code"] == "UnauthorizedOperation"
    assert payload["request_id"] == "req-err"
