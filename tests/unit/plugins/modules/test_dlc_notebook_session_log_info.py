from ansible_collections.susunola.tencentcloud.plugins.modules.dlc_notebook_session_log_info import build_request, read


class Object:
    pass


class Models:
    DescribeNotebookSessionLogRequest = Object


def test_log_request_uses_exact_session_and_offset():
    request = build_request(Models, "session-1", 200, 200)
    assert request.SessionId == "session-1" and request.Offset == 200 and request.Limit == 200


class Response:
    def __init__(self, logs, request_id):
        self.Logs, self.RequestId = logs, request_id


class Client:
    def __init__(self, responses):
        self.responses, self.offsets = responses, []

    def DescribeNotebookSessionLog(self, request):
        self.offsets.append(request.Offset)
        return self.responses.pop(0)


class Module:
    def sdk_call(self, fn, request):
        return fn(request)


def test_log_read_stops_on_short_page():
    client = Client([Response(["a", "b"], "r1"), Response(["c"], "r2")])
    logs, truncated, request_id = read(Module(), client, Models, {"session_id": "s", "page_size": 2, "max_pages": 5})
    assert logs == ["a", "b", "c"] and truncated is False and request_id == "r2" and client.offsets == [0, 2]


def test_log_read_reports_page_cap():
    client = Client([Response(["a"], "r1"), Response(["b"], "r2")])
    logs, truncated, _ = read(Module(), client, Models, {"session_id": "s", "page_size": 1, "max_pages": 2})
    assert logs == ["a", "b"] and truncated is True
