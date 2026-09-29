"""Deep harness tests for the dlc_notebook_statement_info module.

Covers the statement/result request builders, the statement lookup branch,
SQL-result token pagination with inferred task ids, repeated-token and
missing-task_id failures, parameter validation and the sdk_error_payload
failure contract.

The module subclasses ``TencentCloudModule``, so the migration patches the
base class's ``create_client`` and the module's own ``_load`` (which is where
it imports its models and client class), and lets ``module_args()`` supply the
credentials the base class validates. The fake statement serialises ``TaskId``
and ``State`` from ``NotebookSessionStatementInfo``, and the fake result page
carries the real ``DescribeNotebookSessionStatementSqlResultResponse`` fields.
``params()`` drops ``None`` overrides (``task_id=None``) so an absent option is
omitted from the module args rather than passed as an explicit ``None``.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import types

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import dlc_notebook_statement_info
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    module_args,
    run,
)


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
    return {key: value for key, value in options.items() if value is not None}


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


class SDKError(Exception):
    def get_code(self):
        return "UnauthorizedOperation"

    def get_request_id(self):
        return "req-err"


def _patch_sdk(monkeypatch, client):
    """Hand the module its models/client class and the client itself."""
    monkeypatch.setattr(dlc_notebook_statement_info, "_load", lambda: (
        FakeModels, types.SimpleNamespace(DlcClient=lambda *args: client)))
    monkeypatch.setattr(TencentCloudModule, "create_client",
                        lambda self, client_class, endpoint: client)


def test_run_module_returns_statement_without_results(monkeypatch):
    client = FakeClient(statement=StatementResponse(StatementItem("task-1")))
    _patch_sdk(monkeypatch, client)
    module_args(region="ap-guangzhou", **params())

    payload = run(dlc_notebook_statement_info.run_module)

    assert payload["changed"] is False
    assert payload["statement"] == {"TaskId": "task-1", "State": "ok"}
    assert payload["result_pages"] == []
    assert payload["request_id"] == "req-stmt"
    request = client.statement_requests[0]
    assert request.SessionId == "session-1" and request.StatementId == "statement-1"


def test_run_module_fetches_result_pages_with_inferred_task_id(monkeypatch):
    client = FakeClient(
        statement=StatementResponse(StatementItem("task-1")),
        result_pages=[ResultResponse("page-1", "n2"), ResultResponse("page-2", None)],
    )
    _patch_sdk(monkeypatch, client)
    module_args(region="ap-guangzhou", **params(task_id=None, include_sql_result=True))

    payload = run(dlc_notebook_statement_info.run_module)

    assert [page["ResultSet"] for page in payload["result_pages"]] == ["page-1", "page-2"]
    assert payload["result_pages"][0]["ResultSchema"] == [{"Name": "id"}]
    assert payload["result_pages"][0]["NextToken"] == "n2"
    assert [getattr(request, "NextToken", None) for request in client.result_requests] == [None, "n2"]
    assert [request.TaskId for request in client.result_requests] == ["task-1", "task-1"]


def test_run_module_fails_when_task_id_is_unavailable(monkeypatch):
    client = FakeClient(statement=StatementResponse(None))
    _patch_sdk(monkeypatch, client)
    module_args(region="ap-guangzhou", **params(task_id=None, include_sql_result=True))

    with pytest.raises(AnsibleFailJson) as failure:
        run(dlc_notebook_statement_info.run_module)

    payload = failure.value.args[0]
    assert payload["msg"] == "task_id is required to retrieve SQL results and was not returned by the statement"
    assert payload["statement"] is None


def test_run_module_fails_on_repeated_continuation_token(monkeypatch):
    client = FakeClient(
        statement=StatementResponse(StatementItem("task-1")),
        result_pages=[ResultResponse("page-1", "n1"), ResultResponse("page-2", "n1")],
    )
    _patch_sdk(monkeypatch, client)
    module_args(region="ap-guangzhou", **params(include_sql_result=True))

    with pytest.raises(AnsibleFailJson) as failure:
        run(dlc_notebook_statement_info.run_module)

    payload = failure.value.args[0]
    assert payload["msg"] == "DLC Notebook SQL-result pagination repeated a continuation token"
    assert payload["task_id"] == "task-1"
    assert payload["next_token"] == "n1"


def test_run_module_validates_max_results_and_cut_length(monkeypatch):
    module_args(region="ap-guangzhou", **params(max_results=0))

    with pytest.raises(AnsibleFailJson) as failure:
        run(dlc_notebook_statement_info.run_module)

    assert failure.value.args[0]["msg"] == "max_results must be between 1 and 1000"

    module_args(region="ap-guangzhou", **params(data_field_cut_length=0))

    with pytest.raises(AnsibleFailJson) as failure:
        run(dlc_notebook_statement_info.run_module)

    assert failure.value.args[0]["msg"] == "data_field_cut_length must be positive"


def test_run_module_fails_cleanly_on_sdk_error(monkeypatch):
    class FailingClient:
        def DescribeNotebookSessionStatement(self, request):
            raise SDKError("api exploded")

    _patch_sdk(monkeypatch, FailingClient())
    module_args(region="ap-guangzhou", **params())

    with pytest.raises(AnsibleFailJson) as failure:
        run(dlc_notebook_statement_info.run_module)

    payload = failure.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert payload["error"] == "api exploded"
    assert payload["error_code"] == "UnauthorizedOperation"
    assert payload["request_id"] == "req-err"
