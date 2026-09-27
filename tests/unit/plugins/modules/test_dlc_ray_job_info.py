"""Deep harness tests for the dlc_ray_job_info module.

Covers the request helpers (job identity, page/context diagnostics), the
GetRayJob detail branch and each optional diagnostic stream (history, events,
pods, yaml) through run_module, plus truncation, repeated-context and
parameter-validation failures and the sdk_error_payload failure contract.

The module subclasses ``TencentCloudModule``, so the migration patches the base
class's ``create_client`` and the module's own ``_load`` (which is where it
imports its models and client class), and lets ``module_args()`` supply the
credentials the base class validates. The fixtures serialise real fields the
API returns: the detail carries ``Id`` (there is no ``RayJobId`` in
``GetRayJobResponse``), and each stream names a field of its own item model --
``JobStatusHistory.Id`` for history, ``RayJobEventItem.Message`` for events and
``JobPodEntity.PodName`` for pods -- instead of the generic ``Value``, so the
payload ``add_return_samples.py`` captures is the shape a caller really sees.
"""
from __future__ import absolute_import, division, print_function

__metaclass__ = type

import types

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import dlc_ray_job_info
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    module_args,
    run,
)


class Object:
    pass


class FakeModels:
    GetRayJobRequest = Object
    GetRayJobHistoryRequest = Object
    GetRayJobPodsRequest = Object
    GetRayJobEventRequest = Object
    GetRayJobYamlRequest = Object


def params(**overrides):
    options = {
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
    options.update(overrides)
    return options


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
    """Serialisable item whose ``field`` names a real field of its item model."""

    def __init__(self, value, field):
        self.value = value
        self.field = field

    def _serialize(self, allow_none=True):
        return {self.field: self.value}


class DetailResponse:
    def __init__(self, data):
        self._data = dict(data)

    def _serialize(self, allow_none=True):
        return dict(self._data)


class PageResponse:
    def __init__(self, values, total_pages, field):
        self.Items = [FakeItem(value, field) for value in values]
        self.TotalPages = total_pages


class EventResponse:
    def __init__(self, values, context, list_over, field):
        self.Events = [FakeItem(value, field) for value in values]
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


class SDKError(Exception):
    def get_code(self):
        return "UnauthorizedOperation"

    def get_request_id(self):
        return "req-err"


def _patch_sdk(monkeypatch, client):
    """Hand the module its models/client class and the client itself."""
    monkeypatch.setattr(dlc_ray_job_info, "_load", lambda: (
        FakeModels, types.SimpleNamespace(DlcClient=lambda *args: client)))
    monkeypatch.setattr(TencentCloudModule, "create_client",
                        lambda self, client_class, endpoint: client)


def test_run_module_collects_all_diagnostics(monkeypatch):
    p = params(include_history=True, include_events=True, include_pods=True, include_yaml=True)
    client = FakeClient(
        detail=DetailResponse({"Id": "job-1", "Status": "running", "RequestId": "rr"}),
        history=[PageResponse(["h1", "h2"], 2, "Id"), PageResponse(["h3"], 2, "Id")],
        events=[EventResponse(["ev1"], "c2", False, "Message"),
                EventResponse(["ev2"], None, True, "Message")],
        pods=[PageResponse(["p1", "p2"], 1, "PodName")],
        yaml_response=YamlResponse("kind: RayJob"),
    )
    _patch_sdk(monkeypatch, client)
    module_args(region="ap-guangzhou", **p)

    payload = run(dlc_ray_job_info.run_module)

    assert payload["changed"] is False
    assert payload["ray_job"] == {"Id": "job-1", "Status": "running"}
    assert payload["request_id"] == "rr"
    assert [item["Id"] for item in payload["history"]] == ["h1", "h2", "h3"]
    assert [item["Message"] for item in payload["events"]] == ["ev1", "ev2"]
    assert [item["PodName"] for item in payload["pods"]] == ["p1", "p2"]
    assert payload["yaml"] == "kind: RayJob"
    assert payload["truncated"] == {"history": False, "events": False, "pods": False}
    assert client.history_pages == [1, 2]
    assert client.pod_pages == [1]
    assert client.event_contexts == [None, "c2"]
    assert len(client.detail_requests) == 1
    assert len(client.yaml_requests) == 1


def test_run_module_fetches_history_only(monkeypatch):
    p = params(include_history=True)
    client = FakeClient(
        detail=DetailResponse({"Id": "job-1", "RequestId": "rr"}),
        history=[PageResponse(["h1", "h2"], 1, "Id")],
    )
    _patch_sdk(monkeypatch, client)
    module_args(region="ap-guangzhou", **p)

    payload = run(dlc_ray_job_info.run_module)

    assert [item["Id"] for item in payload["history"]] == ["h1", "h2"]
    assert payload["events"] == []
    assert payload["pods"] == []
    assert payload["yaml"] is None
    assert payload["truncated"] == {"history": False, "events": False, "pods": False}
    assert client.pod_pages == []
    assert client.yaml_requests == []


def test_run_module_reports_truncated_history_at_max_pages(monkeypatch):
    p = params(include_history=True, max_pages=1)
    client = FakeClient(
        detail=DetailResponse({"Id": "job-1", "RequestId": "rr"}),
        history=[PageResponse(["h1", "h2"], 2, "Id")],
    )
    _patch_sdk(monkeypatch, client)
    module_args(region="ap-guangzhou", **p)

    payload = run(dlc_ray_job_info.run_module)

    assert [item["Id"] for item in payload["history"]] == ["h1", "h2"]
    assert payload["truncated"] == {"history": True, "events": False, "pods": False}


def test_run_module_fails_on_repeated_event_context(monkeypatch):
    p = params(include_events=True)
    client = FakeClient(
        detail=DetailResponse({"Id": "job-1", "RequestId": "rr"}),
        events=[EventResponse(["ev1"], "ctx", False, "Message"),
                EventResponse(["ev2"], "ctx", False, "Message")],
    )
    _patch_sdk(monkeypatch, client)
    module_args(region="ap-guangzhou", **p)

    with pytest.raises(AnsibleFailJson) as failure:
        run(dlc_ray_job_info.run_module)

    payload = failure.value.args[0]
    assert payload["msg"] == "DLC Ray job event pagination repeated a context token"
    assert payload["ray_job_id"] == "job-1"
    assert payload["context"] == "ctx"


def test_run_module_validates_page_size_and_event_type(monkeypatch):
    _patch_sdk(monkeypatch, FakeClient())

    module_args(region="ap-guangzhou", **params(page_size=300))
    with pytest.raises(AnsibleFailJson) as failure:
        run(dlc_ray_job_info.run_module)
    assert failure.value.args[0]["msg"] == "page_size must be between 1 and 200"

    module_args(region="ap-guangzhou", **params(event_type="Warn123"))
    with pytest.raises(AnsibleFailJson) as failure:
        run(dlc_ray_job_info.run_module)
    assert failure.value.args[0]["msg"] == "event_type must contain ASCII letters only"

    module_args(region="ap-guangzhou", **params(start_time=30, end_time=10))
    with pytest.raises(AnsibleFailJson) as failure:
        run(dlc_ray_job_info.run_module)
    assert failure.value.args[0]["msg"] == "start_time must not exceed end_time"


def test_run_module_fails_cleanly_on_sdk_error(monkeypatch):
    class FailingClient:
        def GetRayJob(self, request):
            raise SDKError("api exploded")

    _patch_sdk(monkeypatch, FailingClient())
    module_args(region="ap-guangzhou", **params())

    with pytest.raises(AnsibleFailJson) as failure:
        run(dlc_ray_job_info.run_module)

    payload = failure.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert payload["error"] == "api exploded"
    assert payload["error_code"] == "UnauthorizedOperation"
    assert payload["request_id"] == "req-err"
