"""Unit tests for the oceanus_cluster write module (run_module flows).

Drives ``run_module()`` end to end against an in-memory fake Oceanus client
whose write operations mutate the dedicated-cluster store, so the post-write
describe refetch and waiters converge immediately.

Scenario matrix:

* argument validation (invalid CU values, missing cluster_id/name)
* absent on a missing cluster (idempotent) / check-mode dry run / real
  delete with and without wait
* creation when missing (missing creation parameters, check mode, real
  create)
* no-op when CU already matches
* drift updates (scale up, scale down with and without the
  allow_scale_down guard) and immutable drift failure
* the blanket ``sdk_error_payload`` failure path
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import oceanus_cluster as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

CLUSTER = {
    "ClusterId": "cluster-8b0a1c2d",
    "Name": "production-flink",
    "Status": 2,
    "CuNum": 19,
    "CuMem": 4,
    "DefaultCOSBucket": "flink-artifacts-1250000000",
}


def _cluster(**overrides):
    item = copy.deepcopy(CLUSTER)
    item.update(overrides)
    return item


def _base(**overrides):
    params = {"name": "production-flink"}
    params.update(overrides)
    return module_args(**params)


class FakeOceanusClient(object):
    """In-memory Oceanus client mutating a dedicated-cluster store."""

    def __init__(self, clusters=None):
        self.clusters = [copy.deepcopy(t) for t in (clusters or [])]
        self.calls = []
        self._next = 0

    def DescribeClusters(self, request):
        self.calls.append("DescribeClusters")
        return SimpleNamespace(ClusterSet=[FakeResource(t) for t in self.clusters], TotalCount=len(self.clusters), RequestId="req-fake")

    def CreateOceanusCluster(self, request):
        self.calls.append("CreateOceanusCluster")
        self._next += 1
        item = {
            "ClusterId": "cluster-new-%03d" % self._next,
            "Name": getattr(request, "ClusterName", None),
            "Status": 2,
            "CuNum": getattr(request, "CU", None),
            "CuMem": getattr(request, "CUMemory", None),
            "DefaultCOSBucket": getattr(request, "DefaultCOSBucket", None),
        }
        self.clusters.append(item)
        return SimpleNamespace(ClusterId=item["ClusterId"], RequestId="req-fake")

    def ScaleOceanusCluster(self, request):
        self.calls.append("ScaleOceanusCluster")
        for item in self.clusters:
            if item.get("ClusterId") == getattr(request, "ClusterId", None):
                item["CuNum"] = getattr(request, "NewCU", None)
        return SimpleNamespace(TaskExecResult="SUCCESS", RequestId="req-fake")

    def DeleteOceanusCluster(self, request):
        self.calls.append("DeleteOceanusCluster")
        self.clusters = [t for t in self.clusters if t.get("ClusterId") != getattr(request, "ClusterId", None)]
        return SimpleNamespace(TaskExecResult="SUCCESS", RequestId="req-fake")


def _make_module(monkeypatch, fake, models=None):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (models or FakeModels(), SimpleNamespace(OceanusClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


# ---------------------------------------------------------------------------
# argument validation
# ---------------------------------------------------------------------------


def test_invalid_cu_fails(monkeypatch):
    fake = FakeOceanusClient()
    _make_module(monkeypatch, fake)
    _base(cu=5)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "cu must follow 12 + 7n" in exc.value.args[0]["msg"]


def test_missing_cluster_id_and_name_fails(monkeypatch):
    fake = FakeOceanusClient()
    _make_module(monkeypatch, fake)
    module_args()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "one of the following is required" in exc.value.args[0]["msg"]


# ---------------------------------------------------------------------------
# absent flows
# ---------------------------------------------------------------------------


def test_absent_missing_cluster_is_idempotent(monkeypatch):
    fake = FakeOceanusClient()
    _make_module(monkeypatch, fake)
    _base(state="absent", name="ghost")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["cluster"] is None


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeOceanusClient(clusters=[_cluster()])
    _make_module(monkeypatch, fake)
    _base(_ansible_check_mode=True, state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert len(fake.clusters) == 1
    assert "DeleteOceanusCluster" not in fake.calls


def test_absent_deletes_cluster_without_wait(monkeypatch):
    fake = FakeOceanusClient(clusters=[_cluster()])
    _make_module(monkeypatch, fake)
    _base(state="absent", wait=False)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["cluster"] is None
    assert fake.clusters == []
    ops = list(fake.calls)
    assert "DeleteOceanusCluster" in ops
    assert ops[-1] == "DeleteOceanusCluster"


def test_absent_deletes_cluster_with_wait(monkeypatch):
    fake = FakeOceanusClient(clusters=[_cluster()])
    _make_module(monkeypatch, fake)
    _base(state="absent", wait=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert fake.clusters == []
    ops = list(fake.calls)
    assert "DeleteOceanusCluster" in ops
    assert "DescribeClusters" in ops


# ---------------------------------------------------------------------------
# creation flows
# ---------------------------------------------------------------------------


def test_create_requires_creation_parameters(monkeypatch):
    fake = FakeOceanusClient()
    _make_module(monkeypatch, fake)
    _base(name="brand-new")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "creation parameters are required" in payload["msg"]
    assert "vpc_descriptions" in payload["missing"]


def test_create_cluster(monkeypatch):
    fake = FakeOceanusClient()
    _make_module(monkeypatch, fake)
    _base(
        name="brand-new",
        region_id=1,
        zone_id=100001,
        login_password="s3cret!",
        vpc_descriptions=[{"VpcId": "vpc-1", "SubnetId": "subnet-1"}],
        default_cos_bucket="flink-artifacts-1250000000",
        cu=19,
        wait=True,
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["cluster"]["Name"] == "brand-new"
    assert result["cluster"]["CuNum"] == 19
    assert result["cluster"]["ClusterId"].startswith("cluster-new-")
    assert len(fake.clusters) == 1
    ops = list(fake.calls)
    assert ops[0] == "DescribeClusters"
    assert "CreateOceanusCluster" in ops


def test_create_check_mode_is_dry_run(monkeypatch):
    fake = FakeOceanusClient()
    _make_module(monkeypatch, fake)
    _base(
        _ansible_check_mode=True,
        name="brand-new",
        region_id=1,
        zone_id=100001,
        login_password="s3cret!",
        vpc_descriptions=[{"VpcId": "vpc-1", "SubnetId": "subnet-1"}],
        default_cos_bucket="flink-artifacts-1250000000",
        cu=19,
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["cluster"] == {"Name": "brand-new", "CuNum": 19}
    assert fake.clusters == []
    assert "CreateOceanusCluster" not in fake.calls


# ---------------------------------------------------------------------------
# existing-cluster flows
# ---------------------------------------------------------------------------


def test_existing_cluster_no_drift_is_idempotent(monkeypatch):
    fake = FakeOceanusClient(clusters=[_cluster()])
    _make_module(monkeypatch, fake)
    _base(cu=19)
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["cluster"]["ClusterId"] == "cluster-8b0a1c2d"
    ops = list(fake.calls)
    assert ops == ["DescribeClusters"]


def test_scale_up_cluster(monkeypatch):
    fake = FakeOceanusClient(clusters=[_cluster()])
    _make_module(monkeypatch, fake)
    _base(cu=26, wait=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["cluster"]["CuNum"] == 26
    ops = list(fake.calls)
    assert "ScaleOceanusCluster" in ops


def test_scale_down_requires_allow_scale_down(monkeypatch):
    fake = FakeOceanusClient(clusters=[_cluster()])
    _make_module(monkeypatch, fake)
    _base(cu=12)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "allow_scale_down=true" in exc.value.args[0]["msg"]


def test_scale_down_authorized_applies(monkeypatch):
    fake = FakeOceanusClient(clusters=[_cluster()])
    _make_module(monkeypatch, fake)
    _base(cu=12, allow_scale_down=True, wait=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["cluster"]["CuNum"] == 12
    ops = list(fake.calls)
    assert "ScaleOceanusCluster" in ops


def test_immutable_name_drift_fails(monkeypatch):
    fake = FakeOceanusClient(clusters=[_cluster()])
    _make_module(monkeypatch, fake)
    _base(cluster_id="cluster-8b0a1c2d", name="renamed")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "identity, storage and CU memory are immutable" in payload["msg"]
    assert "Name" in payload["immutable_drift"]


def test_immutable_cu_memory_drift_fails(monkeypatch):
    fake = FakeOceanusClient(clusters=[_cluster()])
    _make_module(monkeypatch, fake)
    _base(cu_memory=2, cu=19)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "CuMem" in payload["immutable_drift"]


# ---------------------------------------------------------------------------
# failure paths
# ---------------------------------------------------------------------------


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeClusters(self, request):
            raise Boom("connection dropped")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    _base(cu=19)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]
