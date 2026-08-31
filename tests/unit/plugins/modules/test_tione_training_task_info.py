from ansible_collections.susunola.tencentcloud.plugins.modules.tione_training_task_info import detail_request, list_request, read_list


class Object: pass
class Models: DescribeTrainingTaskRequest = DescribeTrainingTasksRequest = Filter = TagFilter = Object


def params():
    return {"task_id": None, "instance_id": None, "project_id": "p1", "filters": {"Status": ["RUNNING"], "Name": "job"}, "tag_filters": {"team": "ml"}, "order_field": "StartTime", "order": "DESC", "page_size": 2, "max_pages": 5}


def test_detail_request_supports_historical_instance():
    p = params(); p["task_id"], p["instance_id"] = "train-1", "instance-2"
    request = detail_request(Models, p)
    assert request.Id == "train-1" and request.InstanceId == "instance-2" and request.TiProjectId == "p1"


def test_list_request_maps_filters_tags_and_order_stably():
    request = list_request(Models, params(), 2)
    assert request.Offset == 2 and request.Limit == 2
    assert [(x.Name, x.Values) for x in request.Filters] == [("Name", ["job"]), ("Status", ["RUNNING"])]
    assert request.TagFilters[0].TagKey == "team" and request.TagFilters[0].TagValues == ["ml"]
    assert request.OrderField == "StartTime" and request.Order == "DESC"


class Item:
    def __init__(self, value): self.value = value
    def _serialize(self, allow_none=True): return {"Id": self.value}
class Response:
    def __init__(self, values, total, request_id): self.TrainingTaskSet, self.TotalCount, self.RequestId = [Item(x) for x in values], total, request_id
class Client:
    def __init__(self): self.responses = [Response(["t1", "t2"], 3, "r1"), Response(["t3"], 3, "r2")]
    def DescribeTrainingTasks(self, request): return self.responses.pop(0)
class Module:
    def sdk_call(self, fn, request): return fn(request)


def test_read_list_follows_all_offset_pages():
    values, total, truncated, request_id = read_list(Module(), Client(), Models, params())
    assert values == [{"Id": "t1"}, {"Id": "t2"}, {"Id": "t3"}]
    assert total == 3 and truncated is False and request_id == "r2"


def test_read_list_reports_page_budget_truncation():
    p = params(); p["max_pages"] = 1
    values, total, truncated, request_id = read_list(Module(), Client(), Models, p)
    assert values == [{"Id": "t1"}, {"Id": "t2"}] and total == 3 and truncated is True and request_id == "r1"
