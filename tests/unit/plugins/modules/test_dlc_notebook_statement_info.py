from ansible_collections.susunola.tencentcloud.plugins.modules.dlc_notebook_statement_info import read_results, result_request, statement_request


class Object:
    pass


class Models:
    DescribeNotebookSessionStatementRequest = DescribeNotebookSessionStatementSqlResultRequest = Object


def params():
    return {"max_results": 500, "batch_id": "batch-1", "data_field_cut_length": 2048}


def test_statement_and_result_requests_keep_strong_identity():
    request = statement_request(Models, "session-1", "statement-1", "task-1")
    assert request.SessionId == "session-1" and request.StatementId == "statement-1" and request.TaskId == "task-1"
    request = result_request(Models, "task-1", params(), "next-1")
    assert request.TaskId == "task-1" and request.MaxResults == 500 and request.NextToken == "next-1"
    assert request.BatchId == "batch-1" and request.DataFieldCutLen == 2048


class Column:
    def __init__(self, name):
        self.name = name

    def _serialize(self, allow_none=True):
        return {"Name": self.name}


class Response:
    def __init__(self, token, result):
        self.TaskId, self.ResultSet, self.ResultSchema, self.NextToken = "task-1", result, [Column("id")], token
        self.OutputPath, self.UseTime, self.AffectRows, self.DataAmount, self.UiUrl, self.RequestId = "cosn://result", 1, 2, 3, "ui", "req"


class Client:
    def __init__(self):
        self.responses = [Response("n2", "page-1"), Response(None, "page-2")]
        self.tokens = []

    def DescribeNotebookSessionStatementSqlResult(self, request):
        self.tokens.append(getattr(request, "NextToken", None))
        return self.responses.pop(0)


class Module:
    def sdk_call(self, fn, request):
        return fn(request)

    def fail_json(self, **kwargs):
        raise AssertionError(kwargs)


def test_sql_results_preserve_pages_and_follow_tokens():
    client = Client()
    pages = read_results(Module(), client, Models, "task-1", params())
    assert [x["ResultSet"] for x in pages] == ["page-1", "page-2"]
    assert pages[0]["ResultSchema"] == [{"Name": "id"}] and client.tokens == [None, "n2"]
