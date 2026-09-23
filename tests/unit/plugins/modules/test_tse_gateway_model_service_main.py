"""Unit tests for the tse_gateway_model_service write module (run_module flows).

Drives ``run_module()`` end to end against an in-memory fake TSE client whose
write operations mutate the model-service store, so the post-write list/detail
refetch converges immediately.

Scenario matrix:

* argument validation (missing name and model_service_id)
* absent on a missing service (idempotent) / check-mode dry run / real delete
* creation when missing (name/config validation, unsupported config field,
  check mode, real create)
* no-op when nothing drifts
* drift updates (immutable-config failure and a mutable config change)
* the multiple-match guard
* the blanket ``sdk_error_payload`` failure path
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import tse_gateway_model_service as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

SERVICE = {
    "Id": "ms-8b0a1c2d",
    "Name": "openai-primary",
    "ServiceType": "LLMService",
    "ModelProvider": "OpenAI",
    "ModelProtocol": "OpenAI/v1",
    "ModelSelector": "Specify",
    "SecretKeyIds": ["secret-key-1"],
    "DefaultModel": "gpt-4.1",
    "Description": "primary",
    "ConnectTimeout": 10000,
    "ReadTimeout": 60000,
}


def _service(**overrides):
    item = copy.deepcopy(SERVICE)
    item.update(overrides)
    return item


def _base(**overrides):
    params = {"gateway_id": "gateway-1", "name": "openai-primary"}
    params.update(overrides)
    return module_args(**params)


class FakeTseClient(object):
    """In-memory TSE client mutating a model-service store."""

    def __init__(self, services=None):
        self.services = [copy.deepcopy(t) for t in (services or [])]
        self.calls = []
        self._next = 0

    def _find(self, service_id):
        for item in self.services:
            if item.get("Id") == service_id:
                return item
        return None

    def _copy(self, request):
        return {k: v for k, v in dict(getattr(request, "__dict__", {})).items() if not k.startswith("_")}

    def DescribeCloudNativeAPIGatewayLLMModelServices(self, request):
        self.calls.append("DescribeCloudNativeAPIGatewayLLMModelServices")
        result = SimpleNamespace(DataList=[FakeResource(t) for t in self.services], TotalCount=len(self.services))
        return SimpleNamespace(Result=result, RequestId="req-fake")

    def DescribeCloudNativeAPIGatewayLLMModelService(self, request):
        self.calls.append("DescribeCloudNativeAPIGatewayLLMModelService")
        item = self._find(getattr(request, "ModelServiceId", None))
        result = FakeResource(dict(item)) if item is not None else None
        return SimpleNamespace(Result=result, RequestId="req-fake")

    def CreateCloudNativeAPIGatewayLLMModelService(self, request):
        self.calls.append("CreateCloudNativeAPIGatewayLLMModelService")
        self._next += 1
        item = self._copy(request)
        item["Id"] = "ms-new-%03d" % self._next
        self.services.append(item)
        return SimpleNamespace(ModelServiceId=item["Id"], RequestId="req-fake")

    def ModifyCloudNativeAPIGatewayLLMModelService(self, request):
        self.calls.append("ModifyCloudNativeAPIGatewayLLMModelService")
        data = self._copy(request)
        item = self._find(data.get("ModelServiceId"))
        if item is not None:
            for key in ("Name", "DefaultModel", "Description", "ModelSelector", "EnableModelFallback",
                        "UpstreamURL", "ConnectTimeout", "ReadTimeout", "WriteTimeout", "Retries",
                        "QuotaLimit", "Tags", "SourceId", "Namespace", "ServiceName", "Protocol",
                        "ExtParams", "KeyRotationEnabled", "KeyRotationPeriodDays"):
                if key in data and key != "ModelServiceId":
                    item[key] = data[key]
        return SimpleNamespace(RequestId="req-fake")

    def DeleteCloudNativeAPIGatewayLLMModelService(self, request):
        self.calls.append("DeleteCloudNativeAPIGatewayLLMModelService")
        self.services = [t for t in self.services if t.get("Id") != getattr(request, "ModelServiceId", None)]
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake, models=None):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (models or FakeModels(), SimpleNamespace(TseClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


# ---------------------------------------------------------------------------
# argument validation
# ---------------------------------------------------------------------------


def test_name_or_model_service_id_required(monkeypatch):
    fake = FakeTseClient()
    _make_module(monkeypatch, fake)
    module_args(gateway_id="gateway-1")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "one of the following is required" in exc.value.args[0]["msg"]


# ---------------------------------------------------------------------------
# absent flows
# ---------------------------------------------------------------------------


def test_absent_missing_service_is_idempotent(monkeypatch):
    fake = FakeTseClient()
    _make_module(monkeypatch, fake)
    _base(state="absent", name="ghost")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["model_service"] is None


def test_absent_deletes_service(monkeypatch):
    fake = FakeTseClient(services=[_service()])
    _make_module(monkeypatch, fake)
    _base(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert fake.services == []
    ops = list(fake.calls)
    assert "DeleteCloudNativeAPIGatewayLLMModelService" in ops


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeTseClient(services=[_service()])
    _make_module(monkeypatch, fake)
    _base(_ansible_check_mode=True, state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert len(fake.services) == 1
    assert "DeleteCloudNativeAPIGatewayLLMModelService" not in fake.calls


# ---------------------------------------------------------------------------
# creation flows
# ---------------------------------------------------------------------------


def test_create_requires_name(monkeypatch):
    fake = FakeTseClient()
    _make_module(monkeypatch, fake)
    module_args(gateway_id="gateway-1", model_service_id="ms-ghost", config={"ServiceType": "LLMService"})
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "name is required for a new TSE model service" in exc.value.args[0]["msg"]


def test_create_requires_config_fields(monkeypatch):
    fake = FakeTseClient()
    _make_module(monkeypatch, fake)
    _base(name="openai-primary", config={"ServiceType": "LLMService"})
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "Required model service config fields" in exc.value.args[0]["msg"]


def test_create_unknown_config_field_fails(monkeypatch):
    fake = FakeTseClient()
    _make_module(monkeypatch, fake)
    _base(
        name="openai-primary",
        config={
            "ServiceType": "LLMService",
            "ModelProvider": "OpenAI",
            "ModelProtocol": "OpenAI/v1",
            "ModelSelector": "Specify",
            "BogusField": 1,
        },
    )
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "Unsupported model service config fields" in exc.value.args[0]["msg"]


def test_create_model_service(monkeypatch):
    fake = FakeTseClient()
    _make_module(monkeypatch, fake)
    _base(
        config={
            "ServiceType": "LLMService",
            "ModelProvider": "OpenAI",
            "ModelProtocol": "OpenAI/v1",
            "ModelSelector": "Specify",
            "SecretKeyIds": ["secret-key-1"],
            "DefaultModel": "gpt-4.1",
            "ConnectTimeout": 10000,
            "ReadTimeout": 60000,
        }
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["model_service"]["Id"].startswith("ms-new-")
    assert result["model_service"]["Name"] == "openai-primary"
    assert result["model_service"]["DefaultModel"] == "gpt-4.1"
    assert len(fake.services) == 1
    ops = list(fake.calls)
    assert "CreateCloudNativeAPIGatewayLLMModelService" in ops


def test_create_check_mode_is_dry_run(monkeypatch):
    fake = FakeTseClient()
    _make_module(monkeypatch, fake)
    _base(
        _ansible_check_mode=True,
        config={
            "ServiceType": "LLMService",
            "ModelProvider": "OpenAI",
            "ModelProtocol": "OpenAI/v1",
            "ModelSelector": "Specify",
            "DefaultModel": "gpt-4.1",
        },
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["model_service"]["Name"] == "openai-primary"
    assert result["model_service"]["DefaultModel"] == "gpt-4.1"
    assert fake.services == []
    assert "CreateCloudNativeAPIGatewayLLMModelService" not in fake.calls


# ---------------------------------------------------------------------------
# existing-service flows
# ---------------------------------------------------------------------------


def test_existing_service_no_drift_is_idempotent(monkeypatch):
    fake = FakeTseClient(services=[_service()])
    _make_module(monkeypatch, fake)
    _base(config={"DefaultModel": "gpt-4.1"})
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["model_service"]["Id"] == "ms-8b0a1c2d"
    ops = list(fake.calls)
    assert "ModifyCloudNativeAPIGatewayLLMModelService" not in ops


def test_immutable_drift_fails(monkeypatch):
    fake = FakeTseClient(services=[_service()])
    _make_module(monkeypatch, fake)
    _base(config={"ModelProvider": "Anthropic"})
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "Immutable model service configuration differs" in payload["msg"]
    assert "ModelProvider" in payload["immutable_drift"]


def test_update_model_service(monkeypatch):
    fake = FakeTseClient(services=[_service()])
    _make_module(monkeypatch, fake)
    _base(config={"DefaultModel": "gpt-4o", "Description": "updated"})
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["model_service"]["DefaultModel"] == "gpt-4o"
    assert result["model_service"]["Description"] == "updated"
    ops = list(fake.calls)
    assert "ModifyCloudNativeAPIGatewayLLMModelService" in ops


def test_update_check_mode_is_dry_run(monkeypatch):
    fake = FakeTseClient(services=[_service()])
    _make_module(monkeypatch, fake)
    _base(_ansible_check_mode=True, config={"DefaultModel": "gpt-4o"})
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["model_service"]["DefaultModel"] == "gpt-4o"
    assert "ModifyCloudNativeAPIGatewayLLMModelService" not in fake.calls


def test_multiple_matches_fail(monkeypatch):
    fake = FakeTseClient(services=[_service(), _service(Id="ms-dup")])
    _make_module(monkeypatch, fake)
    _base()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "Multiple TSE model services matched" in exc.value.args[0]["msg"]


# ---------------------------------------------------------------------------
# failure paths
# ---------------------------------------------------------------------------


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeCloudNativeAPIGatewayLLMModelServices(self, request):
            raise Boom("connection dropped")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    _base()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]


# ---------------------------------------------------------------------------
# legacy helper regression tests (folded from test_tse_gateway_model_service.py)
# ---------------------------------------------------------------------------


def test_create_payload_maps_full_service_identity():
    p = {
        "gateway_id": "g1",
        "name": "openai",
        "config": {
            "ServiceType": "LLMService",
            "ModelProvider": "OpenAI",
            "ModelProtocol": "OpenAI/v1",
            "ModelSelector": "Specify",
            "DefaultModel": "gpt",
        },
    }
    assert mod.create_payload(p)["ModelProvider"] == "OpenAI"


def test_modify_payload_preserves_unspecified_values():
    p = {"gateway_id": "g1", "name": None, "config": {"ReadTimeout": 30000}}
    current = {"Id": "ms1", "Name": "openai", "ReadTimeout": 60000, "Retries": 2}
    payload = mod.modify_payload(p, current)
    assert payload["ReadTimeout"] == 30000 and payload["Retries"] == 2
