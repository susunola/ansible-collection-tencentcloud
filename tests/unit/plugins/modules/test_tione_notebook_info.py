from ansible_collections.susunola.tencentcloud.plugins.modules.tione_notebook_info import build_request, read


class Object:
    pass


class Models:
    DescribeNotebooksRequest = Filter = TagFilter = Object


def params():
    return {
        "project_id": "p1",
        "filters": {"Status": ["Running"], "Name": "nb"},
        "tag_filters": {"env": "prod"},
        "order_field": "UpdateTime",
        "order": "DESC",
        "page_size": 2,
        "max_pages": 5,
    }


def test_request_maps_filters_tags_and_order_stably():
    request = build_request(Models, params(), 2)
    assert request.Offset == 2 and request.Limit == 2 and request.TiProjectId == "p1"
    assert [(x.Name, x.Values) for x in request.Filters] == [("Name", ["nb"]), ("Status", ["Running"])]
    assert [(x.TagKey, x.TagValues) for x in request.TagFilters] == [("env", ["prod"])]
    assert request.OrderField == "UpdateTime" and request.Order == "DESC"


class Item:
    def __init__(self, value):
        self.value = value

    def _serialize(self, allow_none=True):
        return {"Id": self.value}


class Response:
    def __init__(self, values, total, request_id):
        self.NotebookSet, self.TotalCount, self.RequestId = [Item(x) for x in values], total, request_id


class Client:
    def __init__(self):
        self.responses = [Response(["n1", "n2"], 3, "r1"), Response(["n3"], 3, "r2")]

    def DescribeNotebooks(self, request):
        return self.responses.pop(0)


class Module:
    def sdk_call(self, fn, request):
        return fn(request)


def test_read_follows_all_offset_pages():
    values, total, truncated, request_id = read(Module(), Client(), Models, params())
    assert values == [{"Id": "n1"}, {"Id": "n2"}, {"Id": "n3"}]
    assert total == 3 and truncated is False and request_id == "r2"


def test_read_reports_page_budget_truncation():
    p = params()
    p["max_pages"] = 1
    values, total, truncated, request_id = read(Module(), Client(), Models, p)
    assert values == [{"Id": "n1"}, {"Id": "n2"}] and total == 3 and truncated is True and request_id == "r1"
