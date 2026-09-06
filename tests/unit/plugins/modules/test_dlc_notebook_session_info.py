from ansible_collections.susunola.tencentcloud.plugins.modules.dlc_notebook_session_info import build_request, read


class Object:
    pass


class Models:
    DescribeNotebookSessionsRequest = Filter = Object


def params():
    return {
        "data_engine_name": "spark-prod",
        "states": ["idle", "busy"],
        "keyword": "analyst",
        "engine_generation": "supersql",
        "sort_fields": ["create_time"],
        "ascending": True,
        "page_size": 2,
    }


def test_build_request_maps_filters_sort_and_pagination():
    request = build_request(Models, params(), 4)
    assert request.Offset == 4 and request.Limit == 2 and request.Asc is True
    assert request.DataEngineName == "spark-prod" and request.State == ["idle", "busy"]
    assert [(x.Name, x.Values) for x in request.Filters] == [("engine-generation", ["supersql"]), ("notebook-keyword", ["analyst"])]


class Item:
    def __init__(self, name):
        self.name = name

    def _serialize(self, allow_none=True):
        return {"Name": self.name}


class Response:
    def __init__(self, values, total, request_id):
        self.Sessions, self.TotalElements, self.RequestId = values, total, request_id


class Module:
    def sdk_call(self, fn, request):
        return fn(request)


class Client:
    def __init__(self):
        self.pages = [Response([Item("a"), Item("b")], 3, "r1"), Response([Item("c")], 3, "r2")]
        self.offsets = []

    def DescribeNotebookSessions(self, request):
        self.offsets.append(request.Offset)
        return self.pages.pop(0)


def test_read_fetches_all_pages_and_returns_final_request_id():
    client = Client()
    sessions, total, request_id = read(Module(), client, Models, params())
    assert sessions == [{"Name": "a"}, {"Name": "b"}, {"Name": "c"}]
    assert total == 3 and request_id == "r2" and client.offsets == [0, 2]
