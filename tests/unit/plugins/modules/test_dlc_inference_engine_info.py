from ansible_collections.susunola.tencentcloud.plugins.modules.dlc_inference_engine_info import build_request, read


class Object:
    pass


class Models:
    ListInferenceEnginesRequest = Filter = SortField = Object


def params():
    return {
        "start_time": 10,
        "end_time": 20,
        "filters": {"model_type": ["LLM"], "enabled": "true"},
        "sort_fields": [{"field": "Name", "order": "ASC"}],
        "page_size": 2,
        "max_pages": 5,
    }


def test_request_maps_runtime_discovery_controls_stably():
    request = build_request(Models, params(), 2)
    assert request.Page == 2 and request.PageSize == 2 and request.StartTime == 10 and request.EndTime == 20
    assert [(x.Name, x.Values) for x in request.Filters] == [("enabled", ["true"]), ("model_type", ["LLM"])]
    assert request.SortFields[0].Field == "Name" and request.SortFields[0].Order == "ASC"


class Item:
    def __init__(self, engine_id):
        self.engine_id = engine_id

    def _serialize(self, allow_none=True):
        return {"EngineId": self.engine_id}


class Response:
    def __init__(self, values, pages, total, request_id):
        self.Items, self.TotalPages, self.Total, self.RequestId = [Item(x) for x in values], pages, total, request_id


class Client:
    def __init__(self):
        self.responses = [Response(["e1", "e2"], 2, 3, "r1"), Response(["e3"], 2, 3, "r2")]

    def ListInferenceEngines(self, request):
        return self.responses.pop(0)


class Module:
    def sdk_call(self, fn, request):
        return fn(request)


def test_read_follows_all_engine_pages():
    values, total, truncated, request_id = read(Module(), Client(), Models, params())
    assert values == [{"EngineId": "e1"}, {"EngineId": "e2"}, {"EngineId": "e3"}]
    assert total == 3 and truncated is False and request_id == "r2"


def test_read_reports_page_budget_truncation():
    p = params()
    p["max_pages"] = 1
    values, total, truncated, request_id = read(Module(), Client(), Models, p)
    assert values == [{"EngineId": "e1"}, {"EngineId": "e2"}]
    assert total == 3 and truncated is True and request_id == "r1"
