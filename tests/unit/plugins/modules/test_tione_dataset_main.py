"""Unit tests for the tione_dataset write module (run_module flows).

Drives ``run_module()`` end to end against an in-memory fake TIONE client
whose write operations mutate the dataset store, so the post-write list
refetch and waiters converge immediately.

Scenario matrix:

* argument validation (name for presence, dataset_id for deletion,
  cfs_config only for the LLM scene)
* absent on a missing dataset (idempotent) / allow_delete guard /
  check-mode dry run / real delete
* present on an existing dataset (unchanged and immutable-drift failure)
* creation when missing (dataset_type requirement, real create, check mode)
* the multiple-match guard
* the blanket ``sdk_error_payload`` failure path
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import tione_dataset as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

DATASET = {
    "DatasetId": "ds-8b0a1c2d",
    "DatasetName": "customer-support-sft",
    "DatasetType": "TYPE_DATASET_LLM",
    "DatasetScene": "LLM",
    "StorageDataPath": {"Bucket": "ml-datasets-1250000000", "Region": "ap-guangzhou", "Paths": ["/support/sft/"]},
}


def _dataset(**overrides):
    item = copy.deepcopy(DATASET)
    item.update(overrides)
    return item


def _base(**overrides):
    params = {"name": "customer-support-sft"}
    params.update(overrides)
    return module_args(**params)


class FakeTioneClient(object):
    """In-memory TIONE client mutating a dataset store."""

    def __init__(self, datasets=None):
        self.datasets = [copy.deepcopy(t) for t in (datasets or [])]
        self.calls = []
        self._next = 0

    def _copy_request(self, request):
        return {k: v for k, v in dict(getattr(request, "__dict__", {}) or {}).items() if not k.startswith("_")}

    def DescribeDatasets(self, request):
        self.calls.append("DescribeDatasets")
        return SimpleNamespace(DatasetGroups=[FakeResource(t) for t in self.datasets], TotalCount=len(self.datasets), RequestId="req-fake")

    def CreateDataset(self, request):
        self.calls.append("CreateDataset")
        self._next += 1
        data = self._copy_request(request)
        item = dict(data)
        item["DatasetId"] = "ds-new-%03d" % self._next
        self.datasets.append(item)
        return SimpleNamespace(DatasetId=item["DatasetId"], RequestId="req-fake")

    def DeleteDataset(self, request):
        self.calls.append("DeleteDataset")
        self.datasets = [t for t in self.datasets if t.get("DatasetId") != getattr(request, "DatasetId", None)]
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake, models=None):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (models or FakeModels(), SimpleNamespace(TioneClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


# ---------------------------------------------------------------------------
# argument validation
# ---------------------------------------------------------------------------


def test_present_requires_name(monkeypatch):
    fake = FakeTioneClient()
    _make_module(monkeypatch, fake)
    module_args()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "name is required when state=present" in exc.value.args[0]["msg"]


def test_absent_requires_dataset_id(monkeypatch):
    fake = FakeTioneClient()
    _make_module(monkeypatch, fake)
    module_args(state="absent", name="customer-support-sft")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "dataset_id is required for safe deletion" in exc.value.args[0]["msg"]


def test_cfs_config_scene_mismatch_fails(monkeypatch):
    fake = FakeTioneClient()
    _make_module(monkeypatch, fake)
    _base(dataset_type="TYPE_DATASET_LLM", dataset_scene="CV", cfs_config={"MountPath": "/mnt"})
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "cfs_config is only valid for the LLM dataset scene" in exc.value.args[0]["msg"]


# ---------------------------------------------------------------------------
# absent flows
# ---------------------------------------------------------------------------


def test_absent_missing_dataset_is_idempotent(monkeypatch):
    fake = FakeTioneClient()
    _make_module(monkeypatch, fake)
    module_args(state="absent", dataset_id="ds-ghost")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["dataset"] is None
    assert result["dataset_id"] == "ds-ghost"
    assert list(fake.calls) == ["DescribeDatasets"]


def test_absent_requires_allow_delete(monkeypatch):
    fake = FakeTioneClient(datasets=[_dataset()])
    _make_module(monkeypatch, fake)
    module_args(state="absent", dataset_id="ds-8b0a1c2d")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "allow_delete=true" in exc.value.args[0]["msg"]


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeTioneClient(datasets=[_dataset()])
    _make_module(monkeypatch, fake)
    module_args(_ansible_check_mode=True, state="absent", dataset_id="ds-8b0a1c2d", allow_delete=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert len(fake.datasets) == 1
    assert "DeleteDataset" not in fake.calls


def test_absent_deletes_dataset(monkeypatch):
    fake = FakeTioneClient(datasets=[_dataset()])
    _make_module(monkeypatch, fake)
    module_args(state="absent", dataset_id="ds-8b0a1c2d", allow_delete=True, wait=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["dataset"] is None
    assert fake.datasets == []
    ops = list(fake.calls)
    assert "DeleteDataset" in ops


# ---------------------------------------------------------------------------
# present flows
# ---------------------------------------------------------------------------


def test_existing_dataset_is_idempotent(monkeypatch):
    fake = FakeTioneClient(datasets=[_dataset()])
    _make_module(monkeypatch, fake)
    _base(dataset_type="TYPE_DATASET_LLM", dataset_scene="LLM")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["dataset"]["DatasetId"] == "ds-8b0a1c2d"
    assert result["dataset_id"] == "ds-8b0a1c2d"
    ops = list(fake.calls)
    assert "DescribeDatasets" in ops


def test_immutable_drift_fails(monkeypatch):
    fake = FakeTioneClient(datasets=[_dataset()])
    _make_module(monkeypatch, fake)
    _base(dataset_type="TYPE_DATASET_IMAGE")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "immutable drift" in payload["msg"]
    assert "DatasetType" in payload["immutable_drift"]


def test_dataset_id_not_found_fails(monkeypatch):
    fake = FakeTioneClient()
    _make_module(monkeypatch, fake)
    module_args(state="present", name="ghost", dataset_id="ds-ghost")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "does not exist" in exc.value.args[0]["msg"]


def test_create_requires_dataset_type(monkeypatch):
    fake = FakeTioneClient()
    _make_module(monkeypatch, fake)
    _base(name="brand-new")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "dataset_type is required when creating" in exc.value.args[0]["msg"]


def test_create_dataset(monkeypatch):
    fake = FakeTioneClient()
    _make_module(monkeypatch, fake)
    _base(
        dataset_type="TYPE_DATASET_LLM",
        dataset_scene="LLM",
        storage_data_path={"Bucket": "ml-datasets-1250000000", "Region": "ap-guangzhou", "Paths": ["/support/sft/"]},
        wait=True,
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["dataset_id"].startswith("ds-new-")
    assert result["dataset"]["DatasetName"] == "customer-support-sft"
    assert result["dataset"]["DatasetType"] == "TYPE_DATASET_LLM"
    assert len(fake.datasets) == 1
    ops = list(fake.calls)
    assert ops[0] == "DescribeDatasets"
    assert "CreateDataset" in ops


def test_create_check_mode_is_dry_run(monkeypatch):
    fake = FakeTioneClient()
    _make_module(monkeypatch, fake)
    _base(_ansible_check_mode=True, dataset_type="TYPE_DATASET_LLM", dataset_scene="LLM")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["dataset_id"] is None
    assert result["dataset"]["DatasetType"] == "TYPE_DATASET_LLM"
    assert fake.datasets == []
    assert "CreateDataset" not in fake.calls


def test_multiple_matches_fail(monkeypatch):
    fake = FakeTioneClient(datasets=[_dataset(), _dataset(DatasetId="ds-dup")])
    _make_module(monkeypatch, fake)
    _base(dataset_type="TYPE_DATASET_LLM")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "Multiple TIONE dataset groups matched" in exc.value.args[0]["msg"]


# ---------------------------------------------------------------------------
# failure paths
# ---------------------------------------------------------------------------


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeDatasets(self, request):
            raise Boom("connection dropped")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    _base(dataset_type="TYPE_DATASET_LLM")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]
