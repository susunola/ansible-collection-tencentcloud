from ansible_collections.susunola.tencentcloud.plugins.modules.tione_data_source_info import build_request, read


class Object: pass
class Models: DescribeDataSourcesRequest = Filter = TagFilter = Object


def params():
    return {"project_id": "p1", "filters": {"z": "2", "a": ["1"]}, "tag_filters": {"team": ["ml"], "env": "prod"}, "order_field": "CreateTime", "order": "DESC", "page_size": 2, "max_pages": 5}


def test_request_maps_workspace_filters_tags_and_order_stably():
    request = build_request(Models, params(), 2)
    assert request.Offset == 2 and request.Limit == 2 and request.TiProjectId == "p1"
    assert [(x.Name, x.Values) for x in request.Filters] == [("a", ["1"]), ("z", ["2"])]
    assert [(x.TagKey, x.TagValues) for x in request.TagFilters] == [("env", ["prod"]), ("team", ["ml"])]
    assert request.OrderField == "CreateTime" and request.Order == "DESC"


class Item:
    def __init__(self, value): self.value = value
    def _serialize(self, allow_none=True): return {"Id": self.value}
class Response:
    def __init__(self, values, total, request_id): self.DataSourceInfos, self.TotalCount, self.RequestId = [Item(x) for x in values], total, request_id
class Client:
    def __init__(self): self.responses = [Response(["d1", "d2"], 3, "r1"), Response(["d3"], 3, "r2")]
    def DescribeDataSources(self, request): return self.responses.pop(0)
class Module:
    def sdk_call(self, fn, request): return fn(request)


def test_read_follows_offset_pages():
    values, total, truncated, request_id = read(Module(), Client(), Models, params())
    assert values == [{"Id": "d1"}, {"Id": "d2"}, {"Id": "d3"}]
    assert total == 3 and truncated is False and request_id == "r2"


def test_read_reports_page_budget_truncation():
    p = params(); p["max_pages"] = 1
    values, total, truncated, request_id = read(Module(), Client(), Models, p)
    assert values == [{"Id": "d1"}, {"Id": "d2"}] and total == 3 and truncated is True and request_id == "r1"
