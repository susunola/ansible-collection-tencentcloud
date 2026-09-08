"""Unit tests for the tione_model_service write module (run_module flows).

Drives ``run_module()`` end to end against an in-memory fake TIONE client
whose write operations mutate the model-service store, so the module's
post-write ``get`` refetch and waiters converge immediately.

Scenario matrix:

* argument validation before any SDK call (missing service_id for delete,
  conflicting service_group_id/service_id)
* absent on a missing service (idempotent no-op), allow_delete guard,
  check-mode dry run and the real delete path
* creation when missing (missing mandatory params, happy path, check mode)
* unknown service_id, no-drift idempotency, immutable create-only drift,
  mutable drift updates
* the blanket ``sdk_error_payload`` failure path
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import tione_model_service as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

CREATE_KEYS = (
    "ServiceGroupName",
    "ServiceDescription",
    "ChargeType",
    "ResourceGroupId",
    "ModelInfo",
    "ImageInfo",
    "Env",
    "Resources",
    "InstanceType",
    "ScaleMode",
    "Replicas",
    "HorizontalPodAutoscaler",
    "LogEnable",
    "LogConfig",
    "AuthorizationEnable",
    "Tags",
    "ScaleStrategy",
    "CronScaleJobs",
    "HybridBillingPrepaidReplicas",
    "CreateSource",
    "ModelHotUpdateEnable",
    "ScheduledAction",
    "VolumeMount",
    "ServiceLimit",
    "ModelTurboEnable",
    "Command",
    "ServiceEIP",
    "ServicePort",
    "DeployType",
    "InstancePerReplicas",
    "TerminationGracePeriodSeconds",
    "PreStopCommand",
    "GrpcEnable",
    "HealthProbe",
    "RollingUpdate",
    "VolumeMounts",
    "SchedulingStrategy",
    "ResourceSupplyAttribute",
    "InferTemplateId",
    "TiProjectId",
)

SERVICE = {
    "ServiceId": "ms-8b0a1c2d",
    "ServiceGroupName": "fraud-detection",
    "ServiceDescription": "fraud scoring",
    "Status": "normal",
    "ChargeType": "POSTPAID_BY_HOUR",
    "ImageInfo": {"ImageType": "TCR", "ImageUrl": "ccr.ccs.tencentyun.com/ml/fraud:v3"},
    "Replicas": 2,
    "ScaleMode": "MANUAL",
    "InstanceType": "TI.S.LARGE.POST",
}


def _service(**overrides):
    item = copy.deepcopy(SERVICE)
    item.update(overrides)
    return item


def _plain(value):
    """Recursively unwrap FakeRequest/model stand-ins into plain data."""
    if value is None or isinstance(value, bool) or isinstance(value, (str, int, float)):
        return value
    if isinstance(value, list):
        return [_plain(item) for item in value]
    if isinstance(value, tuple):
        return [_plain(item) for item in value]
    if isinstance(value, dict):
        return {key: _plain(item) for key, item in value.items()}
    return {key: _plain(item) for key, item in vars(value).items()}


class FakeTioneClient(object):
    """In-memory TIONE client mutating a model-service store."""

    def __init__(self, services=None):
        self.services = [copy.deepcopy(t) for t in (services or [])]
        self.calls = []
        self._next = 0

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def _by_id(self, service_id):
        for item in self.services:
            if item.get("ServiceId") == service_id:
                return item
        return None

    def DescribeModelService(self, request):
        self._record("DescribeModelService", request)
        service = self._by_id(getattr(request, "ServiceId", None))
        return SimpleNamespace(Service=FakeResource(service) if service else None, RequestId="req-fake")

    def CreateModelService(self, request):
        self._record("CreateModelService", request)
        self._next += 1
        item = {"ServiceId": "ms-new-%03d" % self._next, "Status": "normal"}
        for attr in CREATE_KEYS:
            value = getattr(request, attr, None)
            if value is not None:
                item[attr] = _plain(value)
        self.services.append(item)
        return SimpleNamespace(
            Service=SimpleNamespace(ServiceId=item["ServiceId"]),
            RequestId="req-fake",
        )

    def ModifyModelService(self, request):
        self._record("ModifyModelService", request)
        service = self._by_id(getattr(request, "ServiceId", None))
        if service is not None:
            for attr in CREATE_KEYS:
                value = getattr(request, attr, None)
                if value is not None:
                    service[attr] = _plain(value)
        return SimpleNamespace(RequestId="req-fake")

    def DeleteModelService(self, request):
        self._record("DeleteModelService", request)
        service_id = getattr(request, "ServiceId", None)
        self.services = [item for item in self.services if item.get("ServiceId") != service_id]
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake, models=None):
    """Wire the shared monkeypatches; returns the fake client."""
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (models or FakeModels(), SimpleNamespace(TioneClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


def _service_args(**overrides):
    params = {
        "service_id": "ms-8b0a1c2d",
        "service_description": "fraud scoring",
        "charge_type": "POSTPAID_BY_HOUR",
        "image_info": {"ImageType": "TCR", "ImageUrl": "ccr.ccs.tencentyun.com/ml/fraud:v3"},
        "replicas": 2,
        "instance_type": "TI.S.LARGE.POST",
        "scale_mode": "MANUAL",
    }
    params.update(overrides)
    return module_args(**params)


def _creation_args(**overrides):
    params = {
        "service_group_name": "fraud-detection",
        "service_description": "fraud scoring",
        "charge_type": "POSTPAID_BY_HOUR",
        "image_info": {"ImageType": "TCR", "ImageUrl": "ccr.ccs.tencentyun.com/ml/fraud:v3"},
        "replicas": 2,
        "instance_type": "TI.S.LARGE.POST",
        "scale_mode": "MANUAL",
    }
    params.update(overrides)
    return module_args(**params)


# ---------------------------------------------------------------------------
# pre-SDK validation
# ---------------------------------------------------------------------------


def test_absent_requires_service_id(monkeypatch):
    fake = FakeTioneClient(services=[])
    _make_module(monkeypatch, fake)
    module_args(state="absent")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "service_id is required for safe deletion" in exc.value.args[0]["msg"]


def test_service_group_id_and_service_id_conflict(monkeypatch):
    fake = FakeTioneClient(services=[])
    _make_module(monkeypatch, fake)
    module_args(service_id="ms-8b0a1c2d", service_group_id="group-1", charge_type="POSTPAID_BY_HOUR")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "cannot be combined with service_id" in exc.value.args[0]["msg"]


# ---------------------------------------------------------------------------
# absent flows
# ---------------------------------------------------------------------------


def test_absent_missing_service_is_idempotent(monkeypatch):
    fake = FakeTioneClient(services=[])
    _make_module(monkeypatch, fake)
    module_args(state="absent", service_id="ms-ghost")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["service"] is None
    assert result["service_id"] == "ms-ghost"


def test_absent_requires_allow_delete(monkeypatch):
    fake = FakeTioneClient(services=[_service()])
    _make_module(monkeypatch, fake)
    module_args(state="absent", service_id="ms-8b0a1c2d")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "allow_delete=true is required" in exc.value.args[0]["msg"]


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeTioneClient(services=[_service()])
    _make_module(monkeypatch, fake)
    module_args(_ansible_check_mode=True, state="absent", service_id="ms-8b0a1c2d", allow_delete=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert len(fake.services) == 1
    assert "DeleteModelService" not in [c for c, unused in fake.calls]


def test_absent_deletes_service(monkeypatch):
    fake = FakeTioneClient(services=[_service()])
    _make_module(monkeypatch, fake)
    module_args(state="absent", service_id="ms-8b0a1c2d", allow_delete=True, wait=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert fake.services == []
    assert "DeleteModelService" in [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# creation flows
# ---------------------------------------------------------------------------


def test_create_requires_creation_parameters(monkeypatch):
    fake = FakeTioneClient(services=[])
    _make_module(monkeypatch, fake)
    module_args()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "creation parameters are required" in payload["msg"]
    assert payload["missing"] == ["charge_type", "replicas", "image_info or infer_template_id", "service_group_id or service_group_name"]


def test_create_model_service(monkeypatch):
    fake = FakeTioneClient(services=[])
    _make_module(monkeypatch, fake)
    _creation_args(wait=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["service"]["ServiceGroupName"] == "fraud-detection"
    assert result["service"]["Status"] == "normal"
    assert result["service_id"].startswith("ms-new-")
    assert len(fake.services) == 1
    ops = [c for c, unused in fake.calls]
    assert "CreateModelService" in ops
    assert ops[-1] == "DescribeModelService"


def test_create_check_mode_is_dry_run(monkeypatch):
    fake = FakeTioneClient(services=[])
    _make_module(monkeypatch, fake)
    _creation_args(_ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["service_id"] is None
    assert result["service"]["Replicas"] == 2
    assert fake.services == []
    assert "CreateModelService" not in [c for c, unused in fake.calls]


def test_create_with_infer_template(monkeypatch):
    fake = FakeTioneClient(services=[])
    _make_module(monkeypatch, fake)
    _creation_args(infer_template_id="tpl-1", wait=False)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["service"]["InferTemplateId"] == "tpl-1"


# ---------------------------------------------------------------------------
# existing-service flows
# ---------------------------------------------------------------------------


def test_present_unknown_service_id_fails(monkeypatch):
    fake = FakeTioneClient(services=[])
    _make_module(monkeypatch, fake)
    module_args(service_id="ms-ghost")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "requested service_id does not exist" in exc.value.args[0]["msg"]


def test_existing_service_no_drift_is_idempotent(monkeypatch):
    fake = FakeTioneClient(services=[_service()])
    _make_module(monkeypatch, fake)
    _service_args()
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["service"]["ServiceId"] == "ms-8b0a1c2d"
    assert "ModifyModelService" not in [c for c, unused in fake.calls]


def test_create_only_drift_fails(monkeypatch):
    fake = FakeTioneClient(services=[_service()])
    _make_module(monkeypatch, fake)
    _service_args(charge_type="PREPAID")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "create-only configuration drift" in payload["msg"]
    assert "ChargeType" in payload["immutable_drift"]


def test_mutable_drift_updates_service(monkeypatch):
    fake = FakeTioneClient(services=[_service()])
    _make_module(monkeypatch, fake)
    _service_args(replicas=4, wait=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["service"]["Replicas"] == 4
    ops = [c for c, unused in fake.calls]
    assert "ModifyModelService" in ops
    assert fake.services[0]["Replicas"] == 4


def test_mutable_drift_check_mode_is_dry_run(monkeypatch):
    fake = FakeTioneClient(services=[_service()])
    _make_module(monkeypatch, fake)
    _service_args(_ansible_check_mode=True, service_description="updated description")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["service"]["ServiceDescription"] == "updated description"
    assert fake.services[0]["ServiceDescription"] == "fraud scoring"
    assert "ModifyModelService" not in [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# failure paths
# ---------------------------------------------------------------------------


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeModelService(self, request):
            raise Boom("service gone away")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    module_args(service_id="ms-8b0a1c2d")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "service gone away" in payload["error"]
