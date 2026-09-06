from ansible_collections.susunola.tencentcloud.plugins.modules.dlc_ray_job_list_info import build_request, read


class Object:
    pass


class Models:
    ListRayJobsRequest = Filter = SortField = Object


def params():
    return {
        "start_time": 10,
        "end_time": 20,
        "filters": {"z": "2", "a": ["1"]},
        "sort_fields": [{"field": "CreateTime", "order": "DESC"}],
        "page_size": 2,
        "max_pages": 5,
    }


def test_request_maps_stable_filters_and_sorting():
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
    def __init__(self, values, pages, request_id):
        self.Items, self.TotalPages, self.RequestId = [Item(x) for x in values], pages, request_id


class Client:
    def __init__(self):
        self.responses = [Response(["a", "b"], 2, "r1"), Response(["c"], 2, "r2")]

    def ListRayJobs(self, request):
        return self.responses.pop(0)


class Module:
    def sdk_call(self, fn, request):
        return fn(request)


def test_read_follows_reported_total_pages():
    jobs, pages, truncated, request_id = read(Module(), Client(), Models, params())
    assert jobs == [{"Name": "a"}, {"Name": "b"}, {"Name": "c"}]
    assert pages == 2 and truncated is False and request_id == "r2"
