from ansible_collections.susunola.tencentcloud.plugins.modules.dlc_model_version_info import build_request, read


class Object:
    pass


class Models:
    ListModelVersionsRequest = Filter = SortField = Object


def params():
    return {
        "model_uid": "model-1",
        "start_time": 10,
        "end_time": 20,
        "filters": {"z": "2", "a": ["1"]},
        "sort_fields": [{"field": "CreateTime", "order": "DESC"}],
        "page_size": 2,
        "max_pages": 5,
    }


def test_request_is_scoped_to_parent_model_and_maps_query_controls():
    request = build_request(Models, params(), 2)
    assert request.ModelUid == "model-1" and request.Page == 2 and request.PageSize == 2
    assert request.StartTime == 10 and request.EndTime == 20
    assert [(x.Name, x.Values) for x in request.Filters] == [("a", ["1"]), ("z", ["2"])]
    assert request.SortFields[0].Field == "CreateTime" and request.SortFields[0].Order == "DESC"


class Item:
    def __init__(self, version):
        self.version = version

    def _serialize(self, allow_none=True):
        return {"Version": self.version}


class Response:
    def __init__(self, values, pages, total, request_id):
        self.Items, self.TotalPages, self.Total, self.RequestId = [Item(x) for x in values], pages, total, request_id


class Client:
    def __init__(self):
        self.responses = [Response(["v1", "v2"], 2, 3, "r1"), Response(["v3"], 2, 3, "r2")]

    def ListModelVersions(self, request):
        return self.responses.pop(0)


class Module:
    def sdk_call(self, fn, request):
        return fn(request)


def test_read_follows_all_parent_scoped_pages():
    values, total, truncated, request_id = read(Module(), Client(), Models, params())
    assert values == [{"Version": "v1"}, {"Version": "v2"}, {"Version": "v3"}]
    assert total == 3 and truncated is False and request_id == "r2"


def test_read_reports_truncation_at_page_budget():
    p = params()
    p["max_pages"] = 1
    values, total, truncated, request_id = read(Module(), Client(), Models, p)
    assert values == [{"Version": "v1"}, {"Version": "v2"}]
    assert total == 3 and truncated is True and request_id == "r1"
