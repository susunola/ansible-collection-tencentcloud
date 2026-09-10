"""Deep harness tests for the dlc_notebook_statement_info module.

Covers the statement/result request builders, the statement lookup branch,
SQL-result token pagination with inferred task ids, repeated-token and
missing-task_id failures, parameter validation and the sdk_error_payload
failure contract.
"""
from __future__ import absolute_import, division, print_function

__metaclass__ = type

import sys
import types

import pytest

from ansible_collections.susunola.tencentcloud.plugins.modules import dlc_notebook_statement_info


class Object:
    pass


class FakeModels:
    DescribeNotebookSessionStatementRequest = Object
    DescribeNotebookSessionStatementSqlResultRequest = Object


def params(**overrides):
    options = {
        "session_id": "session-1",
        "statement_id": "statement-1",
        "task_id": "task-1",
        "include_sql_result": False,
        "batch_id": "batch-1",
        "max_results": 500,
        "data_field_cut_length": 2048,
    }
    options.update(overrides)
    return options


def test_build_requests_keep_strong_identity():
    request = dlc_notebook_statement_info.statement_request(FakeModels, "session-1", "statement-1", "task-1")
    assert request.SessionId == "session-1"
    assert request.StatementId == "statement-1"
    assert request.TaskId == "task-1"
    request = dlc_notebook_statement_info.result_request(FakeModels, "task-1", params(), "next-1")
    assert request.TaskId == "task-1"
    assert request.MaxResults == 500
    assert request.NextToken == "next-1"
    assert request.BatchId == "batch-1"
    assert request.DataFieldCutLen == 2048


class StatementItem:
    def __init__(self, task_id):
        self.task_id = task_id

    def _serialize(self, allow_none=True):
        return {"TaskId": self.task_id, "State": "ok"}


class Column:
    def __init__(self, name):
        self.name = name

    def _serialize(self, allow_none=True):
        return {"Name": self.name}


class StatementResponse:
    def __init__(self, statement_item, request_id="req-stmt"):
        self.NotebookSessionStatement = statement_item
        self.RequestId = request_id


class ResultResponse:
    def __init__(self, result, token, request_id="req-res"):
        self.TaskId = "task-1"
        self.ResultSet = result
        self.ResultSchema = [Column("id")]
        self.NextToken = token
        self.OutputPath = "cosn://out"
        self.UseTime = 1
        self.AffectRows = 2
        self.DataAmount = 3
        self.UiUrl = "ui"
        self.RequestId = request_id


class FakeClient:
    def __init__(self, statement=None, result_pages=None):
        self.statement = statement
        self._result_pages = list(result_pages or [])
        self.statement_requests = []
        self.result_requests = []

    def DescribeNotebookSessionStatement(self, request):
        self.statement_requests.append(request)
        return self.statement

    def DescribeNotebookSessionStatementSqlResult(self, request):
        self.result_requests.append(request)
        return self._result_pages.pop(0)


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
    monkeypatch.setattr(dlc_notebook_statement_info, "TencentCloudModule", lambda **kwargs: fake)
    with pytest.raises(ModuleFail if expect_fail else ModuleExit):
        dlc_notebook_statement_info.run_module()
    return fake


def test_run_module_returns_statement_without_results(monkeypatch):
    client = FakeClient(statement=StatementResponse(StatementItem("task-1")))
    fake = _run(monkeypatch, client, region="ap-guangzhou", **params())
    payload = fake.exit_payload
    assert payload["changed"] is False
    assert payload["statement"] == {"TaskId": "task-1", "State": "ok"}
    assert payload["result_pages"] == []
    assert payload["request_id"] == "req-stmt"
    request = client.statement_requests[0]
    assert request.SessionId == "session-1" and request.StatementId == "statement-1"


def test_run_module_fetches_result_pages_with_inferred_task_id(monkeypatch):
    p = params(task_id=None, include_sql_result=True)
    client = FakeClient(
        statement=StatementResponse(StatementItem("task-1")),
        result_pages=[ResultResponse("page-1", "n2"), ResultResponse("page-2", None)],
    )
    fake = _run(monkeypatch, client, region="ap-guangzhou", **p)
    payload = fake.exit_payload
    assert [page["ResultSet"] for page in payload["result_pages"]] == ["page-1", "page-2"]
    assert payload["result_pages"][0]["ResultSchema"] == [{"Name": "id"}]
    assert payload["result_pages"][0]["NextToken"] == "n2"
    assert [getattr(request, "NextToken", None) for request in client.result_requests] == [None, "n2"]
    assert [request.TaskId for request in client.result_requests] == ["task-1", "task-1"]


def test_run_module_fails_when_task_id_is_unavailable(monkeypatch):
    p = params(task_id=None, include_sql_result=True)
    client = FakeClient(statement=StatementResponse(None))
    payload = _run(monkeypatch, client, expect_fail=True,
                   region="ap-guangzhou", **p).fail_payload
    assert payload["msg"] == "task_id is required to retrieve SQL results and was not returned by the statement"
    assert payload["statement"] is None


def test_run_module_fails_on_repeated_continuation_token(monkeypatch):
    p = params(include_sql_result=True)
    client = FakeClient(
        statement=StatementResponse(StatementItem("task-1")),
        result_pages=[ResultResponse("page-1", "n1"), ResultResponse("page-2", "n1")],
    )
    payload = _run(monkeypatch, client, expect_fail=True,
                   region="ap-guangzhou", **p).fail_payload
    assert payload["msg"] == "DLC Notebook SQL-result pagination repeated a continuation token"
    assert payload["task_id"] == "task-1"
    assert payload["next_token"] == "n1"


def test_run_module_validates_max_results_and_cut_length(monkeypatch):
    p = params(max_results=0)
    payload = _run(monkeypatch, FakeClient(), expect_fail=True,
                   region="ap-guangzhou", **p).fail_payload
    assert payload["msg"] == "max_results must be between 1 and 1000"
    p = params(data_field_cut_length=0)
    payload = _run(monkeypatch, FakeClient(), expect_fail=True,
                   region="ap-guangzhou", **p).fail_payload
    assert payload["msg"] == "data_field_cut_length must be positive"


def test_run_module_fails_cleanly_on_sdk_error(monkeypatch):
    class FailingClient:
        def DescribeNotebookSessionStatement(self, request):
            raise SDKError("api exploded")

    payload = _run(monkeypatch, FailingClient(), expect_fail=True,
                   region="ap-guangzhou", **params()).fail_payload
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert payload["error"] == "api exploded"
    assert payload["error_code"] == "UnauthorizedOperation"
    assert payload["request_id"] == "req-err"
