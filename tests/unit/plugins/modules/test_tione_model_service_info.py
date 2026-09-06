from ansible_collections.susunola.tencentcloud.plugins.modules.tione_model_service_info import service_request, group_request, list_request, read_list


class Object:
    pass


class Models:
    DescribeModelServiceRequest = DescribeModelServiceGroupRequest = DescribeModelServiceGroupsRequest = Filter = TagFilter = Object


def params():
    return {
        "service_id": "s1",
        "service_group_id": "g1",
        "project_id": "p1",
        "filters": {"Status": "Normal", "ModelVersionId": ["mv1"]},
        "tag_filters": {"env": "prod"},
        "order_field": "UpdateTime",
        "order": "DESC",
        "page_size": 2,
        "max_pages": 5,
    }


def test_exact_requests_use_distinct_strong_identities():
    assert service_request(Models, params()).ServiceId == "s1"
    assert group_request(Models, params()).ServiceGroupId == "g1"


def test_list_request_maps_filters_tags_and_order_stably():
    request = list_request(Models, params(), 2)
    assert request.Offset == 2 and request.Limit == 2 and request.TiProjectId == "p1"
    assert [(x.Name, x.Values) for x in request.Filters] == [("ModelVersionId", ["mv1"]), ("Status", ["Normal"])]
    assert request.TagFilters[0].TagKey == "env" and request.OrderField == "UpdateTime"


class Item:
    def __init__(self, value):
        self.value = value

    def _serialize(self, allow_none=True):
        return {"ServiceGroupId": self.value}


class Response:
    def __init__(self, values, total, global_total, request_id):
        self.ServiceGroups, self.TotalCount, self.GlobalTotalCount, self.RequestId = [Item(x) for x in values], total, global_total, request_id


class Client:
    def __init__(self):
        self.responses = [Response(["g1", "g2"], 3, 8, "r1"), Response(["g3"], 3, 8, "r2")]

    def DescribeModelServiceGroups(self, request):
        return self.responses.pop(0)


class Module:
    def sdk_call(self, fn, request):
        return fn(request)


def test_read_list_follows_all_pages_and_preserves_global_total():
    values, total, global_total, truncated, request_id = read_list(Module(), Client(), Models, params())
    assert values == [{"ServiceGroupId": "g1"}, {"ServiceGroupId": "g2"}, {"ServiceGroupId": "g3"}]
    assert total == 3 and global_total == 8 and truncated is False and request_id == "r2"


def test_read_list_reports_page_budget_truncation():
    p = params()
    p["max_pages"] = 1
    values, total, global_total, truncated, request_id = read_list(Module(), Client(), Models, p)
    assert len(values) == 2 and total == 3 and global_total == 8 and truncated is True and request_id == "r1"
