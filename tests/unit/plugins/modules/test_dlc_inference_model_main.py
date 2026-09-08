"""Unit tests for the dlc_inference_model write module (run_module flows).

Drives ``run_module()`` end to end against an in-memory fake DLC client
whose write operations mutate the inference-model store, so the module's
post-write ``find`` refetch and waiters converge immediately.

Scenario matrix:

* pre-SDK validation (name length)
* creation when missing (missing creation params, happy path, check mode)
* no-drift idempotency, immutable creation-field drift
* mutable metadata updates (description / parameter_size / tags /
  resource_tags) with check-mode dry run
* model_uid/name mismatch and multiple-match guards
* the blanket ``sdk_error_payload`` failure path
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import dlc_inference_model as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

MODEL = {
    "Name": "embedding-bge",
    "ModelUid": "model-bge-managed",
    "ModelId": "42",
    "ModelType": "Embedding",
    "Provider": "BAAI",
    "Description": "bge embeddings",
    "ParameterSize": "1.5B",
    "Tags": ["embedding", "nlp"],
    "Tasks": ["Embedding"],
    "StorageType": "COS",
    "StorageUri": "cos://model-bucket/bge/v1/",
    "HasCustomStorage": False,
    "ResourceTags": [{"TagKey": "environment", "TagValue": "production"}],
}

RESOURCE_TAGS = [{"key": "environment", "value": "production"}]


def _model(**overrides):
    item = copy.deepcopy(MODEL)
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


class FakeDlcInferenceClient(object):
    """In-memory DLC client mutating an inference-model store."""

    def __init__(self, models=None):
        self.models = [copy.deepcopy(t) for t in (models or [])]
        self.calls = []
        self._next = 0

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def _matching(self, p):
        if p.get("model_uid"):
            return [item for item in self.models if item.get("ModelUid") == p["model_uid"]]
        return [item for item in self.models if item.get("Name") == p["name"]]

    def ListInferenceModels(self, request):
        self._record("ListInferenceModels", request)
        # The module reads Name/ModelUid off each item after listing all pages.
        items = [FakeResource(item) for item in self.models]
        return SimpleNamespace(Items=items, TotalPages=1, RequestId="req-fake")

    def CreateInferenceModel(self, request):
        self._record("CreateInferenceModel", request)
        self._next += 1
        item = {"ModelUid": "model-created-%03d" % self._next, "ModelId": str(self._next)}
        for key, value in vars(request).items():
            item[key] = _plain(value)
        self.models.append(item)
        return SimpleNamespace(ModelUid=item["ModelUid"], ModelId=item["ModelId"], RequestId="req-fake")

    def UpdateInferenceModel(self, request):
        self._record("UpdateInferenceModel", request)
        for model in self.models:
            if model.get("ModelUid") == getattr(request, "ModelUid", None):
                for key, value in vars(request).items():
                    if key != "ModelUid":
                        model[key] = _plain(value)
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake, models=None):
    """Wire the shared monkeypatches; returns the fake client."""
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (models or FakeModels(), SimpleNamespace(DlcClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


def _model_args(**overrides):
    params = {
        "name": "embedding-bge",
        "description": "bge embeddings",
        "parameter_size": "1.5B",
        "tags": ["embedding", "nlp"],
        "resource_tags": copy.deepcopy(RESOURCE_TAGS),
    }
    params.update(overrides)
    return module_args(**params)


def _creation_args(**overrides):
    params = {
        "name": "embedding-bge",
        "model_uid": "model-bge-managed",
        "model_type": "Embedding",
        "initial_version": "v1",
        "provider": "BAAI",
        "description": "bge embeddings",
        "parameter_size": "1.5B",
        "tags": ["embedding", "nlp"],
        "tasks": ["Embedding"],
        "storage_type": "COS",
        "storage_uri": "cos://model-bucket/bge/v1/",
        "resource_tags": copy.deepcopy(RESOURCE_TAGS),
    }
    params.update(overrides)
    return module_args(**params)


# ---------------------------------------------------------------------------
# validation / creation flows
# ---------------------------------------------------------------------------


def test_name_too_long_fails(monkeypatch):
    fake = FakeDlcInferenceClient(models=[])
    _make_module(monkeypatch, fake)
    module_args(name="x" * 300)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "256 characters" in exc.value.args[0]["msg"]


def test_create_requires_creation_parameters(monkeypatch):
    fake = FakeDlcInferenceClient(models=[])
    _make_module(monkeypatch, fake)
    module_args(name="embedding-bge")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "creation parameters are required" in payload["msg"]
    assert payload["missing"] == ["model_type", "initial_version"]


def test_create_inference_model(monkeypatch):
    fake = FakeDlcInferenceClient(models=[])
    _make_module(monkeypatch, fake)
    _creation_args(wait=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["model"]["ModelType"] == "Embedding"
    assert result["model"]["StorageType"] == "COS"
    assert result["model"]["Name"] == "embedding-bge"
    assert result["model_uid"] == "model-bge-managed"
    assert result["model_id"] == "1"
    assert len(fake.models) == 1
    ops = [c for c, unused in fake.calls]
    assert "CreateInferenceModel" in ops
    assert ops[-1] == "ListInferenceModels"


def test_create_check_mode_is_dry_run(monkeypatch):
    fake = FakeDlcInferenceClient(models=[])
    _make_module(monkeypatch, fake)
    _creation_args(_ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["model_uid"] == "model-bge-managed"
    assert result["model_id"] is None
    assert fake.models == []
    assert "CreateInferenceModel" not in [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# existing-model flows
# ---------------------------------------------------------------------------


def test_existing_model_no_drift_is_idempotent(monkeypatch):
    fake = FakeDlcInferenceClient(models=[_model()])
    _make_module(monkeypatch, fake)
    _model_args()
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["model_uid"] == "model-bge-managed"
    assert result["model_id"] == "42"
    assert "UpdateInferenceModel" not in [c for c, unused in fake.calls]


def test_immutable_drift_fails(monkeypatch):
    fake = FakeDlcInferenceClient(models=[_model()])
    _make_module(monkeypatch, fake)
    _model_args(model_type="Reranker")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "are immutable" in payload["msg"]
    assert "ModelType" in payload["immutable_drift"]


def test_mutable_drift_updates_model(monkeypatch):
    fake = FakeDlcInferenceClient(models=[_model()])
    _make_module(monkeypatch, fake)
    _model_args(description="updated bge description", wait=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["model"]["Description"] == "updated bge description"
    assert "UpdateInferenceModel" in [c for c, unused in fake.calls]


def test_mutable_drift_check_mode_is_dry_run(monkeypatch):
    fake = FakeDlcInferenceClient(models=[_model()])
    _make_module(monkeypatch, fake)
    _model_args(_ansible_check_mode=True, parameter_size="7B")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["model"]["ParameterSize"] == "7B"
    assert fake.models[0]["ParameterSize"] == "1.5B"
    assert "UpdateInferenceModel" not in [c for c, unused in fake.calls]


def test_model_uid_name_mismatch_fails(monkeypatch):
    fake = FakeDlcInferenceClient(models=[_model()])
    _make_module(monkeypatch, fake)
    module_args(name="other-name", model_uid="model-bge-managed")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "exists with a different name" in payload["msg"]
    assert payload["requested_name"] == "other-name"


def test_multiple_matches_fail(monkeypatch):
    fake = FakeDlcInferenceClient(models=[_model(), _model(ModelUid="model-dup")])
    _make_module(monkeypatch, fake)
    module_args(name="embedding-bge")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "Multiple DLC inference models matched" in exc.value.args[0]["msg"]


# ---------------------------------------------------------------------------
# failure paths
# ---------------------------------------------------------------------------


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def ListInferenceModels(self, request):
            raise Boom("catalog unavailable")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    _creation_args()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "catalog unavailable" in payload["error"]
