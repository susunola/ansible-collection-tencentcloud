from ansible_collections.susunola.tencentcloud.plugins.modules.dlc_inference_model_info import build_request, read


class Object:
    pass


class Models:
    ListInferenceModelsRequest = Filter = SortField = Object


def params():
    return {
        "start_time": 10,
        "end_time": 20,
        "parameter_size_min": 7.0,
        "parameter_size_max": 70.0,
        "filters": {"name": "llm"},
        "sort_fields": [{"field": "CreateTime", "order": "DESC"}],
        "page_size": 2,
        "max_pages": 5,
    }


def test_request_maps_model_specific_bounds():
    request = build_request(Models, params(), 2)
    assert request.Page == 2 and request.ParameterSizeMin == 7.0 and request.ParameterSizeMax == 70.0
    assert request.Filters[0].Name == "name" and request.SortFields[0].Order == "DESC"


class Item:
    def __init__(self, name):
        self.name = name

    def _serialize(self, allow_none=True):
        return {"Name": self.name}


class Response:
    def __init__(self, values, pages, request_id):
        self.Items, self.TotalPages, self.Total, self.RequestId = [Item(x) for x in values], pages, 3, request_id


class Client:
    def __init__(self):
        self.responses = [Response(["a", "b"], 2, "r1"), Response(["c"], 2, "r2")]

    def ListInferenceModels(self, request):
        return self.responses.pop(0)


class Module:
    def sdk_call(self, fn, request):
        return fn(request)


def test_read_follows_all_model_pages():
    values, total, truncated, request_id = read(Module(), Client(), Models, params())
    assert values == [{"Name": "a"}, {"Name": "b"}, {"Name": "c"}]
    assert total == 3 and truncated is False and request_id == "r2"
