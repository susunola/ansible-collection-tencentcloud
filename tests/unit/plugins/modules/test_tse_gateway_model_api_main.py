"""Unit tests for the tse_gateway_model_api write module (run_module flows)."""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import tse_gateway_model_api as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

MODEL_API = {
    "Id": "model-api-1",
    "Name": "chat-completions",
    "SceneType": "Chat",
    "RequestProtocol": "OpenAI",
    "ListModelServiceId": ["model-service-x"],
    "BasePath": "/v1",
    "ModelServiceRoute": {
        "SelectedTypes": ["Weighted"],
        "WeightedConfig": [{"ModelServiceId": "model-service-x", "Weight": 100}],
    },
}

CONFIG = {
    "SceneType": "Chat",
    "RequestProtocol": "OpenAI",
    "ListModelServiceId": ["model-service-x"],
    "BasePath": "/v1",
    "ModelServiceRoute": {
        "SelectedTypes": ["Weighted"],
        "WeightedConfig": [{"ModelServiceId": "model-service-x", "Weight": 100}],
    },
}


def _model_api(**overrides):
    item = copy.deepcopy(MODEL_API)
    item.update(overrides)
    return item


def _base(**overrides):
    params = {"gateway_id": "gateway-abc", "name": "chat-completions"}
    params.update(overrides)
    return module_args(**params)


class FakeTseClient(object):
    """In-memory TSE client mutating a Model API store."""

    def __init__(self, items=None):
        self.items = [copy.deepcopy(t) for t in (items or [])]
        self.calls = []
        self._next = 0

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def _find(self, model_api_id=None, name=None):
        for item in self.items:
            if model_api_id is not None and item.get("Id") == model_api_id:
                return item
            if name is not None and item.get("Name") == name:
                return item
        return None

    def DescribeCloudNativeAPIGatewayLLMModelAPIs(self, request):
        self._record("DescribeCloudNativeAPIGatewayLLMModelAPIs", request)
        return SimpleNamespace(Result=SimpleNamespace(DataList=[FakeResource(dict(t)) for t in self.items], TotalCount=len(self.items)))

    def DescribeCloudNativeAPIGatewayLLMModelAPI(self, request):
        self._record("DescribeCloudNativeAPIGatewayLLMModelAPI", request)
        item = self._find(model_api_id=getattr(request, "ModelAPIId", None))
        return SimpleNamespace(Result=FakeResource(dict(item)) if item else None)

    def CreateCloudNativeAPIGatewayLLMModelAPI(self, request):
        self._record("CreateCloudNativeAPIGatewayLLMModelAPI", request)
        self._next += 1
        item = {"Id": "model-api-new-%03d" % self._next}
        for attr in (
            "Name", "SceneType", "RequestProtocol", "RouteList", "BasePath", "Description",
            "ListModelServiceId", "ModelServiceRoute", "MatchHeaders", "EnableCrossServiceFallback",
            "CrossServiceFallbackConfig", "TagFilter", "LogConfig", "MaxDocumentsConfig",
            "SensitiveWordRoute",
        ):
            if hasattr(request, attr):
                item[attr] = getattr(request, attr)
        self.items.append(item)
        return SimpleNamespace(ModelAPIId=item["Id"], RequestId="req-fake")

    def ModifyCloudNativeAPIGatewayLLMModelAPI(self, request):
        self._record("ModifyCloudNativeAPIGatewayLLMModelAPI", request)
        item = self._find(model_api_id=getattr(request, "ModelAPIId", None))
        if item is not None:
            for attr in (
                "Name", "BasePath", "Description", "ListModelServiceId", "ModelServiceRoute",
                "MatchHeaders", "EnableCrossServiceFallback", "CrossServiceFallbackConfig",
                "TagFilter", "LogConfig", "MaxDocumentsConfig", "SensitiveWordRoute",
            ):
                if hasattr(request, attr):
                    item[attr] = getattr(request, attr)
        return SimpleNamespace(RequestId="req-fake")

    def DeleteCloudNativeAPIGatewayLLMModelAPI(self, request):
        self._record("DeleteCloudNativeAPIGatewayLLMModelAPI", request)
        self.items = [t for t in self.items if t.get("Id") != getattr(request, "ModelAPIId", None)]
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake, models=None):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (models or FakeModels(), SimpleNamespace(TseClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


# ---------------------------------------------------------------------------
# absent flows
# ---------------------------------------------------------------------------


def test_absent_missing_is_idempotent(monkeypatch):
    fake = FakeTseClient(items=[])
    _make_module(monkeypatch, fake)
    _base(state="absent", name="ghost")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["model_api"] is None
    assert [c for c, unused in fake.calls] == ["DescribeCloudNativeAPIGatewayLLMModelAPIs"]


def test_absent_by_id_missing_is_idempotent(monkeypatch):
    fake = FakeTseClient(items=[])
    _make_module(monkeypatch, fake)
    module_args(gateway_id="gateway-abc", state="absent", model_api_id="model-api-ghost")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["model_api"] is None


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeTseClient(items=[_model_api()])
    _make_module(monkeypatch, fake)
    _base(_ansible_check_mode=True, state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["model_api"] is None
    assert len(fake.items) == 1
    assert "DeleteCloudNativeAPIGatewayLLMModelAPI" not in [c for c, unused in fake.calls]


def test_absent_deletes(monkeypatch):
    fake = FakeTseClient(items=[_model_api()])
    _make_module(monkeypatch, fake)
    _base(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["model_api"] is None
    assert fake.items == []
    ops = [c for c, unused in fake.calls]
    assert "DeleteCloudNativeAPIGatewayLLMModelAPI" in ops


# ---------------------------------------------------------------------------
# creation flows
# ---------------------------------------------------------------------------


def test_create_requires_name(monkeypatch):
    fake = FakeTseClient(items=[])
    _make_module(monkeypatch, fake)
    module_args(gateway_id="gateway-abc", state="present", model_api_id="model-api-ghost")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "name is required" in exc.value.args[0]["msg"]


def test_create_requires_config_fields(monkeypatch):
    fake = FakeTseClient(items=[])
    _make_module(monkeypatch, fake)
    _base(state="present", name="ghost")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "Required Model API config fields: SceneType, RequestProtocol, ListModelServiceId" in exc.value.args[0]["msg"]


def test_unsupported_config_field_fails(monkeypatch):
    fake = FakeTseClient(items=[])
    _make_module(monkeypatch, fake)
    config = dict(CONFIG)
    config["BogusField"] = 1
    _base(state="present", name="ghost", config=config)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "Unsupported Model API config fields: BogusField" in exc.value.args[0]["msg"]


def test_create_happy_path(monkeypatch):
    fake = FakeTseClient(items=[])
    _make_module(monkeypatch, fake)
    _base(state="present", name="chat-completions", config=CONFIG)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["model_api"]["Name"] == "chat-completions"
    assert result["model_api"]["SceneType"] == "Chat"
    assert len(fake.items) == 1
    ops = [c for c, unused in fake.calls]
    assert ops[0] == "DescribeCloudNativeAPIGatewayLLMModelAPIs"
    assert "CreateCloudNativeAPIGatewayLLMModelAPI" in ops


def test_create_check_mode_is_dry_run(monkeypatch):
    fake = FakeTseClient(items=[])
    _make_module(monkeypatch, fake)
    _base(_ansible_check_mode=True, state="present", name="chat-completions", config=CONFIG)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["model_api"]["Name"] == "chat-completions"
    assert fake.items == []
    assert "CreateCloudNativeAPIGatewayLLMModelAPI" not in [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# existing-model-api flows
# ---------------------------------------------------------------------------


def test_existing_no_drift_is_idempotent(monkeypatch):
    fake = FakeTseClient(items=[_model_api()])
    _make_module(monkeypatch, fake)
    _base(state="present", name="chat-completions", config=CONFIG)
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["model_api"]["Id"] == "model-api-1"
    ops = [c for c, unused in fake.calls]
    assert "ModifyCloudNativeAPIGatewayLLMModelAPI" not in ops


def test_modifiable_drift_updates(monkeypatch):
    fake = FakeTseClient(items=[_model_api()])
    _make_module(monkeypatch, fake)
    config = dict(CONFIG)
    config["BasePath"] = "/v2"
    _base(state="present", name="chat-completions", config=config)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["model_api"]["BasePath"] == "/v2"
    ops = [c for c, unused in fake.calls]
    assert "ModifyCloudNativeAPIGatewayLLMModelAPI" in ops


def test_modifiable_drift_check_mode_is_dry_run(monkeypatch):
    fake = FakeTseClient(items=[_model_api()])
    _make_module(monkeypatch, fake)
    config = dict(CONFIG)
    config["BasePath"] = "/v2"
    _base(_ansible_check_mode=True, state="present", name="chat-completions", config=config)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["model_api"]["BasePath"] == "/v2"
    assert fake.items[0]["BasePath"] == "/v1"
    assert "ModifyCloudNativeAPIGatewayLLMModelAPI" not in [c for c, unused in fake.calls]


def test_immutable_drift_fails(monkeypatch):
    fake = FakeTseClient(items=[_model_api()])
    _make_module(monkeypatch, fake)
    config = dict(CONFIG)
    config["SceneType"] = "Completion"
    _base(state="present", name="chat-completions", config=config)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "Immutable Model API configuration differs" in payload["msg"]
    assert "SceneType" in payload["immutable_drift"]


def test_multiple_matches_fail(monkeypatch):
    fake = FakeTseClient(items=[_model_api(), _model_api(Id="model-api-2")])
    _make_module(monkeypatch, fake)
    _base(state="present", name="chat-completions", config=CONFIG)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "Multiple TSE Model APIs matched" in exc.value.args[0]["msg"]


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeCloudNativeAPIGatewayLLMModelAPIs(self, request):
            raise Boom("connection dropped")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    _base(state="present", name="chat-completions")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]


# ---------------------------------------------------------------------------
# legacy helper regression tests (folded from test_tse_gateway_model_api.py)
# ---------------------------------------------------------------------------


def test_service_ids_normalizes_direct_and_routed_services():
    value = {"ModelServiceId": "s1", "ModelServiceRoute": {"WeightedConfig": [{"ModelServiceId": "s2"}], "ModelNameConfig": [{"ModelServiceId": "s1"}]}}
    assert mod.service_ids(value) == ["s1", "s2"]


def test_modify_payload_preserves_resolved_service_links():
    p = {"gateway_id": "g1", "name": None, "config": {"BasePath": "/v2"}}
    current = {"Id": "api1", "Name": "chat", "BasePath": "/v1", "ModelServiceId": "s1"}
    payload = mod.modify_payload(p, current)
    assert payload["ListModelServiceId"] == ["s1"] and payload["BasePath"] == "/v2"


def test_create_payload_keeps_routing_config():
    p = {"gateway_id": "g1", "name": "chat", "config": {"SceneType": "Chat", "RequestProtocol": "OpenAI", "ListModelServiceId": ["s1"]}}
    assert mod.create_payload(p)["ListModelServiceId"] == ["s1"]
