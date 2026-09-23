"""Unit tests for the dlc_inference_service write module (run_module flows).

Drives ``run_module()`` end to end against an in-memory fake DLC client whose
write operations mutate the inference-service store, so the module's
post-write ``find``/waiter refetches converge immediately.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import dlc_inference_service as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

SERVICE = {
    "ServiceId": "isvc-8b0a1c2d",
    "Name": "bge-openai",
    "Status": "Running",
    "ModelUid": "model-bge-managed",
    "ModelVersion": "v2",
    "Engine": "vllm",
    "Replicas": 2,
    "ResourcePartitionId": "rp-00000001",
    "Image": "ccr.ccs.tencentyun.com/inference/vllm:stable",
    "ModelIdentifier": "bge-production",
    "Queue": "inference",
    "ResourceTags": [{"TagKey": "team", "TagValue": "ml"}],
}

CREATE_MINIMAL = {
    "model_uid": "model-bge-managed",
    "engine": "vllm",
    "replicas": 2,
    "resource_partition_id": "rp-00000001",
    "image": "ccr.ccs.tencentyun.com/inference/vllm:stable",
    "model_identifier": "bge-production",
    "queue": "inference",
}


def _service(**overrides):
    item = copy.deepcopy(SERVICE)
    item.update(overrides)
    return item


def _base(**overrides):
    params = {"name": "bge-openai"}
    params.update(overrides)
    return module_args(**params)


class FakeDlcClient(object):
    """In-memory DLC client mutating a small inference-service store."""

    def __init__(self, services=None):
        self.services = [copy.deepcopy(t) for t in (services or [])]
        self.calls = []
        self._next = 0

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def _find(self, name):
        for item in self.services:
            if item.get("Name") == name:
                return item
        return None

    def ListInferenceServices(self, request):
        self._record("ListInferenceServices", request)
        matches = [dict(t) for t in self.services]
        return SimpleNamespace(Items=[FakeResource(t) for t in matches], TotalPages=1)

    def GetInferenceService(self, request):
        self._record("GetInferenceService", request)
        service_id = request.ServiceId
        matches = [dict(t) for t in self.services if t.get("ServiceId") == service_id]
        return FakeResource(matches[0]) if matches else FakeResource({})

    def CreateInferenceService(self, request):
        self._record("CreateInferenceService", request)
        self._next += 1
        item = {
            "ServiceId": "isvc-new-%03d" % self._next,
            "Name": request.Name,
            "Status": "Running",
        }
        for attr in (
            "ModelUid", "ModelVersion", "Engine", "Replicas", "ResourcePartitionId", "Image",
            "ModelIdentifier", "Queue", "DeploymentName", "HeadHighAvailabilityEnabled",
            "AdvancedParams", "ImagePullPolicy", "AutoscalingEnabled", "MinReplicas",
            "MaxReplicas", "AutoscalerOptions", "ApiKeyIds", "AdvancedOptions", "IsCustom",
            "RuntimeEnv",
        ):
            value = getattr(request, attr, None)
            if value is not None:
                item[attr] = value
        tags = getattr(request, "ResourceTags", None)
        if tags:
            item["ResourceTags"] = [
                {"TagKey": getattr(t, "TagKey", None), "TagValue": getattr(t, "TagValue", None)} for t in tags
            ]
        self.services.append(item)
        return SimpleNamespace(ServiceId=item["ServiceId"], RequestId="req-fake")

    def StopInferenceService(self, request):
        self._record("StopInferenceService", request)
        for item in self.services:
            if item.get("ServiceId") == request.ServiceId:
                item["Status"] = "Stopped"
        return SimpleNamespace(RequestId="req-fake")

    def RestartInferenceService(self, request):
        self._record("RestartInferenceService", request)
        for item in self.services:
            if item.get("ServiceId") == request.ServiceId:
                item["Status"] = "Running"
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake, models=None):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (models or FakeModels(), SimpleNamespace(DlcClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


# ---------------------------------------------------------------------------
# validation guards (run before any SDK call)
# ---------------------------------------------------------------------------


def test_min_replicas_exceeds_max_fails(monkeypatch):
    fake = FakeDlcClient(services=[])
    _make_module(monkeypatch, fake)
    _base(state="running", min_replicas=8, max_replicas=2)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "min_replicas must not exceed max_replicas" in exc.value.args[0]["msg"]


def test_invalid_json_creation_field_fails(monkeypatch):
    fake = FakeDlcClient(services=[])
    _make_module(monkeypatch, fake)
    _base(state="running", advanced_params="not-json")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "advanced_params must be valid JSON" in exc.value.args[0]["msg"]


# ---------------------------------------------------------------------------
# creation flows
# ---------------------------------------------------------------------------


def test_create_requires_creation_parameters(monkeypatch):
    fake = FakeDlcClient(services=[])
    _make_module(monkeypatch, fake)
    _base(state="running", name="ghost")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "creation parameters are required" in payload["msg"]
    assert payload["missing"] == ["model_uid", "engine", "replicas", "resource_partition_id", "image", "model_identifier", "queue"]


def test_create_into_stopped_requires_wait(monkeypatch):
    fake = FakeDlcClient(services=[])
    _make_module(monkeypatch, fake)
    _base(state="stopped", name="ghost", **CREATE_MINIMAL, wait=False)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "wait=true is required" in exc.value.args[0]["msg"]


def test_create_happy_path(monkeypatch):
    fake = FakeDlcClient(services=[])
    _make_module(monkeypatch, fake)
    _base(state="running", **CREATE_MINIMAL, wait=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["inference_service"]["Name"] == "bge-openai"
    assert result["inference_service"]["Status"] == "Running"
    assert result["inference_service"]["ModelUid"] == "model-bge-managed"
    assert result["service_id"].startswith("isvc-new-")
    assert len(fake.services) == 1
    ops = [c for c, unused in fake.calls]
    assert ops[0] == "ListInferenceServices"
    assert "CreateInferenceService" in ops


def test_create_stopped_directly(monkeypatch):
    fake = FakeDlcClient(services=[])
    _make_module(monkeypatch, fake)
    _base(state="stopped", **CREATE_MINIMAL, wait=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["inference_service"]["Status"] == "Stopped"
    assert result["service_id"].startswith("isvc-new-")
    ops = [c for c, unused in fake.calls]
    assert "StopInferenceService" in ops
    assert "RestartInferenceService" not in ops


def test_create_check_mode_is_dry_run(monkeypatch):
    fake = FakeDlcClient(services=[])
    _make_module(monkeypatch, fake)
    _base(_ansible_check_mode=True, state="running", **CREATE_MINIMAL)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["inference_service"]["Name"] == "bge-openai"
    assert result["inference_service"]["Status"] == "Running"
    assert result["service_id"] is None
    assert fake.services == []
    assert "CreateInferenceService" not in [c for c, unused in fake.calls]


def test_create_with_resource_tags(monkeypatch):
    fake = FakeDlcClient(services=[])
    _make_module(monkeypatch, fake)
    _base(
        state="running",
        resource_tags=[{"key": "env", "value": "prod"}, {"key": "team", "value": "ml"}],
        **CREATE_MINIMAL,
        wait=True,
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    tags = result["inference_service"]["ResourceTags"]
    assert {"TagKey": "env", "TagValue": "prod"} in tags
    assert {"TagKey": "team", "TagValue": "ml"} in tags


# ---------------------------------------------------------------------------
# existing-service flows
# ---------------------------------------------------------------------------


def test_existing_service_no_drift_is_idempotent(monkeypatch):
    fake = FakeDlcClient(services=[_service()])
    _make_module(monkeypatch, fake)
    _base(state="running")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["inference_service"]["ServiceId"] == "isvc-8b0a1c2d"
    assert result["service_id"] == "isvc-8b0a1c2d"
    ops = [c for c, unused in fake.calls]
    assert ops == ["ListInferenceServices", "GetInferenceService"]


def test_stop_running_service(monkeypatch):
    fake = FakeDlcClient(services=[_service()])
    _make_module(monkeypatch, fake)
    _base(state="stopped", wait=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["inference_service"]["Status"] == "Stopped"
    ops = [c for c, unused in fake.calls]
    assert "StopInferenceService" in ops


def test_restart_stopped_service(monkeypatch):
    fake = FakeDlcClient(services=[_service(Status="Stopped")])
    _make_module(monkeypatch, fake)
    _base(state="running", wait=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["inference_service"]["Status"] == "Running"
    ops = [c for c, unused in fake.calls]
    assert "RestartInferenceService" in ops


def test_stop_check_mode_is_dry_run(monkeypatch):
    fake = FakeDlcClient(services=[_service()])
    _make_module(monkeypatch, fake)
    _base(_ansible_check_mode=True, state="stopped")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["inference_service"]["Status"] == "Stopped"
    assert fake.services[0]["Status"] == "Running"
    assert "StopInferenceService" not in [c for c, unused in fake.calls]


def test_immutable_creation_field_drift_fails(monkeypatch):
    fake = FakeDlcClient(services=[_service()])
    _make_module(monkeypatch, fake)
    _base(state="running", model_uid="different-model")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "creation fields are immutable" in payload["msg"]
    assert "ModelUid" in payload["immutable_drift"]


# ---------------------------------------------------------------------------
# status-transition / failure guards
# ---------------------------------------------------------------------------


def test_failed_state_fails(monkeypatch):
    fake = FakeDlcClient(services=[_service(Status="Failed")])
    _make_module(monkeypatch, fake)
    _base(state="running")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "failed state" in exc.value.args[0]["msg"]


def test_transitioning_without_wait_fails(monkeypatch):
    fake = FakeDlcClient(services=[_service(Status="Deploying")])
    _make_module(monkeypatch, fake)
    _base(state="running", wait=False)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "still transitioning" in exc.value.args[0]["msg"]


def test_stopping_without_wait_fails(monkeypatch):
    fake = FakeDlcClient(services=[_service(Status="Stopping")])
    _make_module(monkeypatch, fake)
    _base(state="running", wait=False)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "still stopping" in exc.value.args[0]["msg"]


def test_unsupported_status_fails(monkeypatch):
    fake = FakeDlcClient(services=[_service(Status="Draining")])
    _make_module(monkeypatch, fake)
    _base(state="running")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "unsupported operational state" in payload["msg"]
    assert payload["status"] == "Draining"


def test_multiple_matches_fail(monkeypatch):
    fake = FakeDlcClient(services=[_service(), _service(ServiceId="isvc-dup")])
    _make_module(monkeypatch, fake)
    _base(state="running")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "Multiple DLC inference services matched" in exc.value.args[0]["msg"]


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def ListInferenceServices(self, request):
            raise Boom("connection dropped")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    _base(state="running", name="bge-openai")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]


# ---------------------------------------------------------------------------
# legacy helper regression tests (folded from test_dlc_inference_service.py)
# ---------------------------------------------------------------------------


class LegacyModel(object):
    def from_json_string(self, value):
        import json

        for key, item in json.loads(value).items():
            setattr(self, key, item)


class LegacyModels(object):
    CreateInferenceServiceRequest = LegacyModel
    GetInferenceServiceRequest = LegacyModel
    ListInferenceServicesRequest = LegacyModel
    StopInferenceServiceRequest = LegacyModel
    RestartInferenceServiceRequest = LegacyModel
    Tag = LegacyModel


def legacy_params():
    return {
        "name": "bge",
        "model_uid": "model-1",
        "model_version": "v2",
        "engine": "vllm",
        "replicas": 2,
        "resource_partition_id": "rp-1",
        "image": "image",
        "model_identifier": "bge-prod",
        "queue": "inference",
        "deployment_name": None,
        "head_high_availability_enabled": True,
        "advanced_params": '{"b":2,"a":1}',
        "image_pull_policy": "IfNotPresent",
        "autoscaling_enabled": True,
        "min_replicas": 1,
        "max_replicas": 4,
        "autoscaler_options": None,
        "api_key_ids": ["key-1"],
        "advanced_options": None,
        "is_custom": False,
        "runtime_env": None,
        "resource_tags": [{"key": "env", "value": "prod"}],
    }


def test_create_payload_normalizes_json_and_tags():
    p = legacy_params()
    request = mod.create_request(LegacyModels, p)
    assert request.ModelUid == "model-1" and request.ModelVersion == "v2"
    assert request.AdvancedParams == '{"a":1,"b":2}' and request.ResourceTags[0].TagKey == "env"


def test_identity_state_and_conflict_requests():
    p = legacy_params()
    current = {
        "ModelUid": "model-1",
        "ModelVersion": "v1",
        "ModelIdentifier": "bge-prod",
        "IsCustom": False,
        "ResourceTags": [{"TagKey": "env", "TagValue": "prod"}],
    }
    assert mod.readable_conflict(p, current) == {"ModelVersion": ("v1", "v2")}
    assert mod.list_request(LegacyModels, 2).Page == 2 and mod.get_request(LegacyModels, "svc-1").ServiceId == "svc-1"
    assert mod.state_request(LegacyModels.StopInferenceServiceRequest, "svc-1").ServiceId == "svc-1"
