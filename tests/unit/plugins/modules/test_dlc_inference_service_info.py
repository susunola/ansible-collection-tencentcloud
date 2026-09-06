from ansible_collections.susunola.tencentcloud.plugins.modules.dlc_inference_service_info import build_request, read


class Object:
    pass


class Models:
    ListInferenceServicesRequest = Filter = SortField = Object


def params():
    return {
        "start_time": 10,
        "end_time": 20,
        "filters": {"z": "2", "a": ["1"]},
        "sort_fields": [{"field": "CreateTime", "order": "DESC"}],
        "page_size": 2,
        "max_pages": 5,
    }


def test_request_sorts_filters_and_preserves_sort_priority():
    request = build_request(Models, params(), 2)
    assert request.Page == 2 and request.PageSize == 2 and request.StartTime == 10
    assert [(x.Name, x.Values) for x in request.Filters] == [("a", ["1"]), ("z", ["2"])]
    assert request.SortFields[0].Field == "CreateTime" and request.SortFields[0].Order == "DESC"


class Item:
    def __init__(self, name):
        self.name = name

    def _serialize(self, allow_none=True):
        return {"Name": self.name}


class Response:
    def __init__(self, values, page, pages):
        self.Items, self.Total, self.RequestId, self.TotalPages = [Item(x) for x in values], 3, "r%s" % page, pages


class Client:
    def __init__(self):
        self.responses = [Response(["a", "b"], 1, 2), Response(["c"], 2, 2)]

    def ListInferenceServices(self, request):
        return self.responses.pop(0)


class Module:
    def sdk_call(self, fn, request):
        return fn(request)


def test_read_follows_all_service_pages():
    services, total, truncated, request_id = read(Module(), Client(), Models, params())
    assert services == [{"Name": "a"}, {"Name": "b"}, {"Name": "c"}]
    assert total == 3 and truncated is False and request_id == "r2"
