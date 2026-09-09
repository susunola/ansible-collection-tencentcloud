"""Deep harness tests for tione_model_service_info.

Covers the exact service/group request builders, the list-mode request
builder (offset pagination, workspace scoping, stable filters, tag
filters, ordering) and run_module() end to end: exact service and
group lookups, bounded service-group list pagination with global
totals, argument validation, and the sdk_error_payload fail contract.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import sys
import types

import pytest

from ansible_collections.susunola.tencentcloud.plugins.modules import tione_model_service_info


def params():
    return {
        "service_id": None,
        "service_group_id": None,
        "project_id": "p1",
        "filters": {"Status": "Normal", "ModelVersionId": ["mv1"]},
        "tag_filters": {"env": "prod"},
        "order_field": "UpdateTime",
        "order": "DESC",
        "page_size": 2,
        "max_pages": 5,
    }


class FakeRequest:
    pass


class FakeFilter:
    pass


class FakeTagFilter:
    pass


class FakeModels:
    DescribeModelServiceRequest = FakeRequest
    DescribeModelServiceGroupRequest = FakeRequest
    DescribeModelServiceGroupsRequest = FakeRequest
    Filter = FakeFilter
    TagFilter = FakeTagFilter


def test_exact_requests_use_distinct_strong_identities():
    service = tione_model_service_info.service_request(FakeModels, dict(params(), service_id="ms-1"))
    group = tione_model_service_info.group_request(FakeModels, dict(params(), service_group_id="msg-1"))
    assert service.ServiceId == "ms-1"
    assert service.TiProjectId == "p1"
    assert group.ServiceGroupId == "msg-1"
    assert group.TiProjectId == "p1"


def test_exact_requests_skip_missing_workspace():
    p = dict(params(), project_id=None, service_id="ms-1", service_group_id="msg-1")
    assert not hasattr(tione_model_service_info.service_request(FakeModels, p), "TiProjectId")
    assert not hasattr(tione_model_service_info.group_request(FakeModels, p), "TiProjectId")


def test_list_request_maps_filters_tags_and_order_stably():
    request = tione_model_service_info.list_request(FakeModels, params(), 2)
    assert request.Offset == 2 and request.Limit == 2 and request.TiProjectId == "p1"
    assert [(x.Name, x.Values) for x in request.Filters] == [("ModelVersionId", ["mv1"]), ("Status", ["Normal"])]
    assert request.TagFilters[0].TagKey == "env"
    assert request.OrderField == "UpdateTime" and request.Order == "DESC"


class FakeItem:
    def __init__(self, marker):
        self.marker = marker

    def _serialize(self, allow_none=True):
        return {"Marker": self.marker}


class FakeResponse:
    def __init__(self, items, total_count, global_total, request_id):
        self.ServiceGroups = items
        self.TotalCount = total_count
        self.GlobalTotalCount = global_total
        self.RequestId = request_id


class FakeClient:
    def __init__(self, pages=None):
        self._pages = list(pages or [])
        self.service_requests = []
        self.group_requests = []
        self.list_requests = []
        self.service_response = None
        self.group_response = None

    def DescribeModelService(self, request):
        self.service_requests.append(request)
        return self.service_response

    def DescribeModelServiceGroup(self, request):
        self.group_requests.append(request)
        return self.group_response

    def DescribeModelServiceGroups(self, request):
        self.list_requests.append(request)
        return self._pages.pop(0)


class ModuleExit(BaseException):
    pass


class ModuleFail(BaseException):
    def __init__(self, payload):
        self.payload = payload
        super(ModuleFail, self).__init__("module failed: %r" % (payload,))


class FakeModule:
    def __init__(self, params):
        self.params = params
        self.exit_payload = None
        self.fail_payload = None

    def require_sdk(self):
        pass

    def create_client(self, client_class, endpoint):
        return self._client

    def sdk_call(self, operation, request=None):
        if request is not None:
            return operation(request)
        return operation()

    def exit_json(self, **kwargs):
        self.exit_payload = kwargs
        raise ModuleExit()

    def fail_json(self, **kwargs):
        self.fail_payload = kwargs
        raise ModuleFail(kwargs)


def _inject_sdk(monkeypatch, client):
    service = types.ModuleType("tencentcloud.tione.v20211111")
    service.models = FakeModels
    service.tione_client = types.SimpleNamespace(TioneClient=lambda *args: object())
    monkeypatch.setitem(sys.modules, "tencentcloud", types.ModuleType("tencentcloud"))
    monkeypatch.setitem(sys.modules, "tencentcloud.tione",
                        types.ModuleType("tencentcloud.tione"))
    monkeypatch.setitem(sys.modules, "tencentcloud.tione.v20211111", service)


def _run(monkeypatch, client, **params):
    _inject_sdk(monkeypatch, client)
    fake = FakeModule(params)
    fake._client = client
    monkeypatch.setattr(tione_model_service_info, "TencentCloudModule", lambda **kwargs: fake)
    with pytest.raises(ModuleExit):
        tione_model_service_info.run_module()
    return fake


def test_run_module_paginates_service_groups_until_total_count(monkeypatch):
    client = FakeClient([
        FakeResponse([FakeItem("g1"), FakeItem("g2")], 3, 8, "req-1"),
        FakeResponse([FakeItem("g3")], 3, 8, "req-2"),
    ])
    fake = _run(monkeypatch, client, **params())
    payload = fake.exit_payload
    assert payload["changed"] is False
    assert [item["Marker"] for item in payload["service_groups"]] == ["g1", "g2", "g3"]
    assert payload["total_count"] == 3
    assert payload["global_total_count"] == 8
    assert payload["truncated"] is False
    assert payload["request_id"] == "req-2"
    assert [request.Offset for request in client.list_requests] == [0, 2]


def test_run_module_describes_exact_service(monkeypatch):
    client = FakeClient()
    client.service_response = types.SimpleNamespace(Service=FakeItem("ms-1"), RequestId="req-svc")
    p = params()
    p["service_id"] = "ms-1"
    fake = _run(monkeypatch, client, **p)
    payload = fake.exit_payload
    assert payload["service"] == {"Marker": "ms-1"}
    assert payload["request_id"] == "req-svc"
    assert len(client.service_requests) == 1


def test_run_module_describes_exact_service_group(monkeypatch):
    client = FakeClient()
    client.group_response = types.SimpleNamespace(ServiceGroup=FakeItem("msg-1"), RequestId="req-grp")
    p = params()
    p["service_group_id"] = "msg-1"
    fake = _run(monkeypatch, client, **p)
    payload = fake.exit_payload
    assert payload["service_group"] == {"Marker": "msg-1"}
    assert payload["request_id"] == "req-grp"
    assert len(client.group_requests) == 1


def test_run_module_validates_page_size_bounds(monkeypatch):
    p = params()
    p["page_size"] = 101
    fake = FakeModule(p)
    monkeypatch.setattr(tione_model_service_info, "TencentCloudModule", lambda **kwargs: fake)
    with pytest.raises(ModuleFail) as excinfo:
        tione_model_service_info.run_module()
    assert excinfo.value.payload["msg"] == "page_size must be between 1 and 100"


class SdkError(Exception):
    def __init__(self, code, request_id):
        self._code = code
        self._request_id = request_id
        super(SdkError, self).__init__("api exploded")

    def get_code(self):
        return self._code

    def get_request_id(self):
        return self._request_id


def test_run_module_fails_cleanly_on_sdk_error(monkeypatch):
    class FailingClient:
        def DescribeModelServiceGroups(self, request):
            raise SdkError("FailedOperation", "req-err")

    failing = FailingClient()
    _inject_sdk(monkeypatch, failing)
    fake = FakeModule(params())
    fake._client = failing
    monkeypatch.setattr(tione_model_service_info, "TencentCloudModule", lambda **kwargs: fake)
    with pytest.raises(ModuleFail) as excinfo:
        tione_model_service_info.run_module()
    payload = excinfo.value.payload
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert payload["error_code"] == "FailedOperation"
    assert payload["request_id"] == "req-err"
