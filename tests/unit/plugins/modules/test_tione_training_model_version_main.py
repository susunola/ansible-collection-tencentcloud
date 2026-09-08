"""Unit tests for the tione_training_model_version write module (run_module flows).

Drives ``run_module()`` end to end against an in-memory fake TIONE client
whose write operations mutate the model-version store, so the post-write
detail refetch and waiters converge immediately.

Scenario matrix:

* argument validation (missing model_id / version identity, absent without
  version_id, bounds checks on max_reserved_models / model_clean_period)
* absent on a missing version (idempotent) / allow_delete guard /
  check-mode dry run / real delete
* present on an existing version (unchanged, immutable-conflict failure,
  failed import state)
* creation when missing (version_id present but not found, real create with
  wait, check mode)
* the multiple-match guard
* the blanket ``sdk_error_payload`` failure path
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import tione_training_model_version as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

VERSION = {
    "TrainingModelVersionId": "modelversion-1",
    "TrainingModelId": "model-x",
    "TrainingModelVersion": "v2",
    "TrainingModelStatus": "STATUS_SUCCESS",
    "VersionType": "NORMAL",
    "AlgorithmFramework": "PYTORCH",
    "ModelFormat": "PYTORCH",
    "ReasoningEnvironmentId": "ti-infer-pytorch",
    "TrainingModelSource": "JOB",
}


class NotFoundError(Exception):
    def get_code(self):
        return "ResourceNotFound.TrainingModelVersion"

    def get_request_id(self):
        return "req-404"


def _version(**overrides):
    item = copy.deepcopy(VERSION)
    item.update(overrides)
    return item


def _base(**overrides):
    params = {"model_id": "model-x", "version": "v2"}
    params.update(overrides)
    return module_args(**params)


class FakeTioneClient(object):
    """In-memory TIONE client mutating a model-version store."""

    def __init__(self, versions=None):
        self.versions = [copy.deepcopy(t) for t in (versions or [])]
        self.calls = []
        self._next = 0

    def _find(self, version_id):
        for item in self.versions:
            if item.get("TrainingModelVersionId") == version_id:
                return item
        raise NotFoundError("version %s not found" % version_id)

    def DescribeTrainingModelVersion(self, request):
        self.calls.append("DescribeTrainingModelVersion")
        item = self._find(request.TrainingModelVersionId)
        return SimpleNamespace(TrainingModelVersion=FakeResource(dict(item)), RequestId="req-fake")

    def DescribeTrainingModelVersions(self, request):
        self.calls.append("DescribeTrainingModelVersions")
        matches = [t for t in self.versions if t.get("TrainingModelId") == request.TrainingModelId]
        return SimpleNamespace(TrainingModelVersions=[FakeResource(t) for t in matches], RequestId="req-fake")

    def CreateTrainingModel(self, request):
        self.calls.append("CreateTrainingModel")
        self._next += 1
        item = {"TrainingModelVersionId": "modelversion-new-%03d" % self._next, "TrainingModelStatus": "STATUS_SUCCESS"}
        for attr in (
            "TrainingModelId", "TrainingModelVersion", "AlgorithmFramework", "ModelFormat",
            "ReasoningEnvironmentId", "ReasoningEnvironmentSource", "TrainingJobId",
            "TrainingModelSource", "TrainingJobVersion", "ModelMoveMode",
            "TrainingJobName", "TrainingModelCosPath", "ReasoningEnvironment",
            "TrainingModelIndex", "ReasoningImageInfo", "ModelOutputPath",
            "TrainingPreference", "AutoClean", "MaxReservedModels",
            "ModelCleanPeriod", "IsQAT", "VersionType",
        ):
            value = getattr(request, attr, None)
            if value is not None:
                item[attr] = value
        self.versions.append(item)
        return SimpleNamespace(TrainingModelVersionId=item["TrainingModelVersionId"], RequestId="req-fake")

    def DeleteTrainingModelVersion(self, request):
        self.calls.append("DeleteTrainingModelVersion")
        self.versions = [t for t in self.versions if t.get("TrainingModelVersionId") != getattr(request, "TrainingModelVersionId", None)]
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake, models=None):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (models or FakeModels(), SimpleNamespace(TioneClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


# ---------------------------------------------------------------------------
# argument validation
# ---------------------------------------------------------------------------


def test_present_requires_model_id(monkeypatch):
    fake = FakeTioneClient()
    _make_module(monkeypatch, fake)
    module_args(version="v2")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "model_id is required" in exc.value.args[0]["msg"]


def test_present_requires_version_identity(monkeypatch):
    fake = FakeTioneClient()
    _make_module(monkeypatch, fake)
    module_args(model_id="model-x")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "version or version_id is required" in exc.value.args[0]["msg"]


def test_absent_requires_version_id(monkeypatch):
    fake = FakeTioneClient()
    _make_module(monkeypatch, fake)
    module_args(state="absent", model_id="model-x")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "version_id is required for safe model-version deletion" in exc.value.args[0]["msg"]


def test_max_reserved_models_out_of_range(monkeypatch):
    fake = FakeTioneClient()
    _make_module(monkeypatch, fake)
    _base(max_reserved_models=25)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "max_reserved_models must be between 1 and 24" in exc.value.args[0]["msg"]


def test_model_clean_period_out_of_range(monkeypatch):
    fake = FakeTioneClient()
    _make_module(monkeypatch, fake)
    _base(model_clean_period=2000)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "model_clean_period must be between 1 and 1440" in exc.value.args[0]["msg"]


# ---------------------------------------------------------------------------
# absent flows
# ---------------------------------------------------------------------------


def test_absent_missing_version_is_idempotent(monkeypatch):
    fake = FakeTioneClient()
    _make_module(monkeypatch, fake)
    module_args(state="absent", version_id="modelversion-ghost")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["model_version"] is None
    assert result["version_id"] == "modelversion-ghost"


def test_absent_requires_allow_delete(monkeypatch):
    fake = FakeTioneClient(versions=[_version()])
    _make_module(monkeypatch, fake)
    module_args(state="absent", version_id="modelversion-1")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "allow_delete=true" in exc.value.args[0]["msg"]


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeTioneClient(versions=[_version()])
    _make_module(monkeypatch, fake)
    module_args(_ansible_check_mode=True, state="absent", version_id="modelversion-1", allow_delete=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert len(fake.versions) == 1
    assert "DeleteTrainingModelVersion" not in fake.calls


def test_absent_deletes_version(monkeypatch):
    fake = FakeTioneClient(versions=[_version()])
    _make_module(monkeypatch, fake)
    module_args(state="absent", version_id="modelversion-1", allow_delete=True, wait=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["model_version"] is None
    assert result["model_id"] == "model-x"
    assert fake.versions == []
    ops = list(fake.calls)
    assert "DeleteTrainingModelVersion" in ops


# ---------------------------------------------------------------------------
# present flows
# ---------------------------------------------------------------------------


def test_existing_version_is_idempotent(monkeypatch):
    fake = FakeTioneClient(versions=[_version()])
    _make_module(monkeypatch, fake)
    _base(algorithm_framework="PYTORCH", model_format="PYTORCH", reasoning_environment_id="ti-infer-pytorch")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["model_version"]["TrainingModelVersionId"] == "modelversion-1"
    assert result["version_id"] == "modelversion-1"
    ops = list(fake.calls)
    assert "DescribeTrainingModelVersions" in ops


def test_immutable_conflict_fails(monkeypatch):
    fake = FakeTioneClient(versions=[_version()])
    _make_module(monkeypatch, fake)
    _base(algorithm_framework="TF")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "versions are immutable" in payload["msg"]
    assert "AlgorithmFramework" in payload["immutable_drift"]


def test_failed_import_state_fails(monkeypatch):
    fake = FakeTioneClient(versions=[_version(TrainingModelStatus="STATUS_FAILED")])
    _make_module(monkeypatch, fake)
    _base()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "failed import state" in exc.value.args[0]["msg"]


def test_version_id_not_found_fails(monkeypatch):
    fake = FakeTioneClient()
    _make_module(monkeypatch, fake)
    module_args(state="present", model_id="model-x", version_id="modelversion-ghost")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "does not exist" in exc.value.args[0]["msg"]


def test_create_model_version(monkeypatch):
    fake = FakeTioneClient()
    _make_module(monkeypatch, fake)
    _base(
        model_version_type="NORMAL",
        training_model_source="JOB",
        training_job_id="train-1",
        training_job_version="instance-1",
        algorithm_framework="PYTORCH",
        model_format="PYTORCH",
        reasoning_environment_source="SYSTEM",
        reasoning_environment_id="ti-infer-pytorch",
        wait=True,
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["version_id"].startswith("modelversion-new-")
    assert result["model_version"]["TrainingModelVersion"] == "v2"
    assert len(fake.versions) == 1
    ops = list(fake.calls)
    assert ops[0] == "DescribeTrainingModelVersions"
    assert "CreateTrainingModel" in ops


def test_create_check_mode_is_dry_run(monkeypatch):
    fake = FakeTioneClient()
    _make_module(monkeypatch, fake)
    _base(_ansible_check_mode=True, training_model_source="COS", algorithm_framework="PYTORCH")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["version_id"] is None
    assert result["model_version"]["TrainingModelVersion"] == "v2"
    assert fake.versions == []
    assert "CreateTrainingModel" not in fake.calls


def test_multiple_matches_fail(monkeypatch):
    fake = FakeTioneClient(versions=[_version(), _version(TrainingModelVersionId="modelversion-dup")])
    _make_module(monkeypatch, fake)
    _base()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "Multiple TIONE model versions matched" in exc.value.args[0]["msg"]


# ---------------------------------------------------------------------------
# failure paths
# ---------------------------------------------------------------------------


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeTrainingModelVersions(self, request):
            raise Boom("connection dropped")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    _base()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]
