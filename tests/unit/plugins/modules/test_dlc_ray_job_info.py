"""Deep harness tests for the dlc_ray_job_info module.

Covers the request helpers (job identity, page/context diagnostics), the
GetRayJob detail branch and each optional diagnostic stream (history, events,
pods, yaml) through run_module, plus truncation, repeated-context and
parameter-validation failures and the sdk_error_payload failure contract.
"""
from __future__ import absolute_import, division, print_function

__metaclass__ = type

import sys
import types

import pytest

from ansible_collections.susunola.tencentcloud.plugins.modules import dlc_ray_job_info


class Object:
    pass


class FakeModels:
    GetRayJobRequest = Object
    GetRayJobHistoryRequest = Object
    GetRayJobPodsRequest = Object
    GetRayJobEventRequest = Object
    GetRayJobYamlRequest = Object


def params():
    return {
        "ray_job_id": "job-1",
        "include_history": False,
        "include_events": False,
        "include_pods": False,
        "include_yaml": False,
        "start_time": 10,
        "end_time": 20,
        "event_type": "Warning",
        "page_size": 2,
        "max_pages": 5,
    }


def test_request_helpers_keep_job_identity_and_diagnostic_bounds():
    assert dlc_ray_job_info.id_request(Object, "job-1").Id == "job-1"
    history = dlc_ray_job_info.history_request(FakeModels, params(), 2)
    assert history.Id == "job-1"
    assert history.Page == 2
    assert history.PageSize == 2
    pods = dlc_ray_job_info.pods_request(FakeModels, params(), 3)
    assert pods.Page == 3
    assert pods.StartTime == 10
    assert pods.EndTime == 20
    event = dlc_ray_job_info.event_request(FakeModels, params(), "ctx")
    assert event.Context == "ctx"
    assert event.EventType == "Warning"
    assert event.StartTime == 10


class FakeItem:
    def __init__(self, value):
        self.value = value

    def _serialize(self, allow_none=True):
        return {"Value": self.value}


class DetailResponse:
    def __init__(self, data):
        self._data = dict(data)

    def _serialize(self, allow_none=True):
        return dict(self._data)


class PageResponse:
    def __init__(self, values, total_pages):
        self.Items = [FakeItem(value) for value in values]
        self.TotalPages = total_pages


class EventResponse:
    def __init__(self, values, context, list_over):
        self.Events = [FakeItem(value) for value in values]
        self.Context = context
        self.ListOver = list_over


class YamlResponse:
    def __init__(self, yaml):
        self.Yaml = yaml


class FakeClient:
    def __init__(self, detail=None, history=None, events=None, pods=None, yaml_response=None):
        self.detail = detail
        self._history = list(history or [])
        self._events = list(events or [])
        self._pods = list(pods or [])
        self.yaml_response = yaml_response
        self.detail_requests = []
        self.history_pages = []
        self.pod_pages = []
        self.event_contexts = []
        self.yaml_requests = []

    def GetRayJob(self, request):
        self.detail_requests.append(request)
        return self.detail

    def GetRayJobHistory(self, request):
        self.history_pages.append(request.Page)
        return self._history.pop(0)

    def GetRayJobEvent(self, request):
        self.event_contexts.append(getattr(request, "Context", None))
        return self._events.pop(0)

    def GetRayJobPods(self, request):
        self.pod_pages.append(request.Page)
        return self._pods.pop(0)

    def GetRayJobYaml(self, request):
        self.yaml_requests.append(request)
        return self.yaml_response


class ModuleExit(BaseException):
    pass


class ModuleFail(BaseException):
    def __init__(self, payload):
        self.payload = payload
        super(ModuleFail, self).__init__("module failed: %r" % (payload,))


class SDKError(Exception):
    def get_code(self):
        return "UnauthorizedOperation"

    def get_request_id(self):
        return "req-err"


class FakeModule:
    def __init__(self, params, client):
        self.params = params
        self.client = client
        self.exit_payload = None
        self.fail_payload = None

    def exit_json(self, **kwargs):
        self.exit_payload = kwargs
        raise ModuleExit()

    def fail_json(self, **kwargs):
        self.fail_payload = kwargs
        raise ModuleFail(kwargs)

    def require_sdk(self):
        pass

    def create_client(self, client_class, endpoint):
        return self.client

    def sdk_call(self, operation, request=None, retry=True):
        if request is None:
            return operation()
        return operation(request)


def _inject_sdk(monkeypatch):
    service = types.ModuleType("tencentcloud.dlc.v20210125")
    service.models = FakeModels
    service.dlc_client = types.SimpleNamespace(DlcClient=object)
    monkeypatch.setitem(sys.modules, "tencentcloud", types.ModuleType("tencentcloud"))
    monkeypatch.setitem(sys.modules, "tencentcloud.dlc",
                        types.ModuleType("tencentcloud.dlc"))
    monkeypatch.setitem(sys.modules, "tencentcloud.dlc.v20210125", service)


def _run(monkeypatch, client, expect_fail=False, **p):
    _inject_sdk(monkeypatch)
    fake = FakeModule(p, client)
    monkeypatch.setattr(dlc_ray_job_info, "TencentCloudModule", lambda **kwargs: fake)
    with pytest.raises(ModuleFail if expect_fail else ModuleExit):
        dlc_ray_job_info.run_module()
    return fake


def test_run_module_collects_all_diagnostics(monkeypatch):
    p = dict(params(), include_history=True, include_events=True, include_pods=True, include_yaml=True)
    client = FakeClient(
        detail=DetailResponse({"RayJobId": "job-1", "Status": "running", "RequestId": "rr"}),
        history=[PageResponse(["h1", "h2"], 2), PageResponse(["h3"], 2)],
        events=[EventResponse(["ev1"], "c2", False), EventResponse(["ev2"], None, True)],
        pods=[PageResponse(["p1", "p2"], 1)],
        yaml_response=YamlResponse("kind: RayJob"),
    )
    fake = _run(monkeypatch, client, region="ap-guangzhou", **p)
    payload = fake.exit_payload
    assert payload["changed"] is False
    assert payload["ray_job"] == {"RayJobId": "job-1", "Status": "running"}
    assert payload["request_id"] == "rr"
    assert [item["Value"] for item in payload["history"]] == ["h1", "h2", "h3"]
    assert [item["Value"] for item in payload["events"]] == ["ev1", "ev2"]
    assert [item["Value"] for item in payload["pods"]] == ["p1", "p2"]
    assert payload["yaml"] == "kind: RayJob"
    assert payload["truncated"] == {"history": False, "events": False, "pods": False}
    assert client.history_pages == [1, 2]
    assert client.pod_pages == [1]
    assert client.event_contexts == [None, "c2"]
    assert len(client.detail_requests) == 1
    assert len(client.yaml_requests) == 1


def test_run_module_fetches_history_only(monkeypatch):
    p = dict(params(), include_history=True)
    client = FakeClient(
        detail=DetailResponse({"RayJobId": "job-1", "RequestId": "rr"}),
        history=[PageResponse(["h1", "h2"], 1)],
    )
    fake = _run(monkeypatch, client, region="ap-guangzhou", **p)
    payload = fake.exit_payload
    assert [item["Value"] for item in payload["history"]] == ["h1", "h2"]
    assert payload["events"] == []
    assert payload["pods"] == []
    assert payload["yaml"] is None
    assert payload["truncated"] == {"history": False, "events": False, "pods": False}
    assert client.pod_pages == []
    assert client.yaml_requests == []


def test_run_module_reports_truncated_history_at_max_pages(monkeypatch):
    p = dict(params(), include_history=True, max_pages=1)
    client = FakeClient(
        detail=DetailResponse({"RayJobId": "job-1", "RequestId": "rr"}),
        history=[PageResponse(["h1", "h2"], 2)],
    )
    fake = _run(monkeypatch, client, region="ap-guangzhou", **p)
    payload = fake.exit_payload
    assert [item["Value"] for item in payload["history"]] == ["h1", "h2"]
    assert payload["truncated"] == {"history": True, "events": False, "pods": False}


def test_run_module_fails_on_repeated_event_context(monkeypatch):
    p = dict(params(), include_events=True)
    client = FakeClient(
        detail=DetailResponse({"RayJobId": "job-1", "RequestId": "rr"}),
        events=[EventResponse(["ev1"], "ctx", False), EventResponse(["ev2"], "ctx", False)],
    )
    payload = _run(monkeypatch, client, expect_fail=True,
                   region="ap-guangzhou", **p).fail_payload
    assert payload["msg"] == "DLC Ray job event pagination repeated a context token"
    assert payload["ray_job_id"] == "job-1"
    assert payload["context"] == "ctx"


def test_run_module_validates_page_size_and_event_type(monkeypatch):
    payload = _run(monkeypatch, FakeClient(), expect_fail=True,
                   region="ap-guangzhou", **dict(params(), page_size=300)).fail_payload
    assert payload["msg"] == "page_size must be between 1 and 200"
    payload = _run(monkeypatch, FakeClient(), expect_fail=True,
                   region="ap-guangzhou", **dict(params(), event_type="Warn123")).fail_payload
    assert payload["msg"] == "event_type must contain ASCII letters only"
    payload = _run(monkeypatch, FakeClient(), expect_fail=True,
                   region="ap-guangzhou", **dict(params(), start_time=30, end_time=10)).fail_payload
    assert payload["msg"] == "start_time must not exceed end_time"


def test_run_module_fails_cleanly_on_sdk_error(monkeypatch):
    class FailingClient:
        def GetRayJob(self, request):
            raise SDKError("api exploded")

    payload = _run(monkeypatch, FailingClient(), expect_fail=True,
                   region="ap-guangzhou", **params()).fail_payload
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert payload["error"] == "api exploded"
    assert payload["error_code"] == "UnauthorizedOperation"
    assert payload["request_id"] == "req-err"
