"""Unit tests for the tsf_cluster write module.

Drives ``run_module()`` against an in-memory fake TSF client whose cluster
describe / create / modify / delete calls mutate a cluster list so
post-write describes converge immediately.

Cluster semantics: placement fields (type, VPC, CIDR, region, zone,
version) are immutable after creation. Capacity fields are accepted only at
creation. ``state=absent`` unbinds rather than destroys the underlying
container cluster when ``unbind_only`` is set.

Scenario matrix:

* present: create, mutable-field modify, check-mode dry runs,
  missing-cluster_type guard, immutable placement drift rejection
* absent: no-op, delete, unbind flag passthrough, check mode,
  rejected delete / update
* lookup ambiguity guard and the blanket SDK failure path
* legacy pure-helper assertions folded from the shallow test file
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import tsf_cluster as mod
from ansible_collections.susunola.tencentcloud.plugins.modules.tsf_cluster import comparable, desired
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

CLUSTER_NAME = "prod"
CLUSTER_TYPE = "C"

_ALL_FIELDS = ("ClusterName", "ClusterType", "ClusterDesc", "ClusterRemarkName", "VpcId", "SubnetId",
               "ClusterCIDR", "TsfRegionId", "TsfZoneId", "ClusterVersion", "MaxNodePodNum",
               "MaxClusterServiceNum", "EnableLogCollection")
_MUTABLE_FIELDS = ("ClusterName", "ClusterDesc", "ClusterRemarkName", "EnableLogCollection")


def _cluster(cluster_id, **overrides):
    value = {"ClusterId": cluster_id, "ClusterName": CLUSTER_NAME, "ClusterType": CLUSTER_TYPE,
             "ClusterDesc": "main", "VpcId": "vpc-1", "SubnetId": "subnet-1",
             "EnableLogCollection": True, "MaxNodePodNum": 64}
    value.update(overrides)
    return value


def _cluster_args(**overrides):
    params = {"name": CLUSTER_NAME, "cluster_type": CLUSTER_TYPE, "vpc_id": "vpc-1",
              "subnet_id": "subnet-1", "description": "main", "enable_log_collection": True,
              "max_node_pods": 64, "state": "present"}
    params.update(overrides)
    return module_args(**params)


class FakeTsfClient(object):
    """In-memory TSF client backed by a mutable cluster list."""

    def __init__(self, clusters=None):
        self.clusters = [dict(c) for c in clusters or []]
        self.calls = []
        self._next_id = 1

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def DescribeClusters(self, request):
        self._record("DescribeClusters", request)
        payload = [FakeResource(dict(c)) for c in self.clusters]
        return SimpleNamespace(Result=SimpleNamespace(Content=payload), RequestId="req-fake")

    def _copy_fields(self, source, target, keys):
        for key in keys:
            if hasattr(source, key):
                target[key] = getattr(source, key)

    def CreateCluster(self, request):
        self._record("CreateCluster", request)
        value = {"ClusterId": "cluster-%d" % self._next_id}
        self._next_id += 1
        self._copy_fields(request, value, _ALL_FIELDS)
        self.clusters.append(value)
        return SimpleNamespace(Result=value["ClusterId"], RequestId="req-fake")

    def ModifyCluster(self, request):
        self._record("ModifyCluster", request)
        cluster_id = getattr(request, "ClusterId", None)
        for cluster in self.clusters:
            if cluster["ClusterId"] == cluster_id:
                self._copy_fields(request, cluster, _MUTABLE_FIELDS)
        return SimpleNamespace(Result=True, RequestId="req-fake")

    def DeleteCluster(self, request):
        self._record("DeleteCluster", request)
        self.clusters = [c for c in self.clusters if c["ClusterId"] != getattr(request, "ClusterId", None)]
        return SimpleNamespace(Result=True, RequestId="req-fake")


def _make_module(monkeypatch, fake, models=None):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (models or FakeModels(), SimpleNamespace(TsfClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


def _names(fake):
    return [c for c, unused in fake.calls]


def _last_request(fake, api):
    for name, request in reversed(fake.calls):
        if name == api:
            return request
    return None


# ---------------------------------------------------------------------------
# present flows
# ---------------------------------------------------------------------------


def test_present_creates_cluster(monkeypatch):
    fake = FakeTsfClient()
    _make_module(monkeypatch, fake)
    _cluster_args()
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["cluster"]["ClusterId"] == "cluster-1"
    assert result["cluster"]["ClusterName"] == CLUSTER_NAME
    assert result["cluster"]["ClusterType"] == CLUSTER_TYPE
    assert result["cluster"]["VpcId"] == "vpc-1"
    assert "CreateCluster" in _names(fake)
    assert len(fake.clusters) == 1


def test_present_no_drift_is_idempotent(monkeypatch):
    current = _cluster("cluster-7")
    fake = FakeTsfClient(clusters=[current])
    _make_module(monkeypatch, fake)
    _cluster_args()
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["cluster"]["ClusterId"] == "cluster-7"
    assert "CreateCluster" not in _names(fake)
    assert "ModifyCluster" not in _names(fake)


def test_present_mutable_description_drift_triggers_modify(monkeypatch):
    fake = FakeTsfClient(clusters=[_cluster("cluster-7", ClusterDesc="old")])
    _make_module(monkeypatch, fake)
    _cluster_args(description="new")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["cluster"]["ClusterDesc"] == "new"
    assert "ModifyCluster" in _names(fake)
    assert fake.clusters[0]["ClusterDesc"] == "new"


def test_present_immutable_placement_drift_is_rejected(monkeypatch):
    fake = FakeTsfClient(clusters=[_cluster("cluster-7", VpcId="vpc-1")])
    _make_module(monkeypatch, fake)
    _cluster_args(vpc_id="vpc-2")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "Immutable fields cannot be changed on an existing" in payload["msg"]
    assert "VpcId" in payload["immutable_changes"]
    assert "ModifyCluster" not in _names(fake)


def test_present_missing_cluster_type_when_creating_fails(monkeypatch):
    fake = FakeTsfClient()
    _make_module(monkeypatch, fake)
    module_args(name=CLUSTER_NAME, vpc_id="vpc-1", subnet_id="subnet-1", state="present")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "cluster_type is required when creating" in exc.value.args[0]["msg"]


def test_present_check_mode_is_dry_run_for_create(monkeypatch):
    fake = FakeTsfClient()
    _make_module(monkeypatch, fake)
    _cluster_args(_ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["cluster"]["ClusterName"] == CLUSTER_NAME
    assert "ClusterId" not in result["cluster"]
    assert "CreateCluster" not in _names(fake)
    assert fake.clusters == []


def test_present_check_mode_is_dry_run_for_modify(monkeypatch):
    fake = FakeTsfClient(clusters=[_cluster("cluster-7", ClusterDesc="old")])
    _make_module(monkeypatch, fake)
    _cluster_args(_ansible_check_mode=True, description="new")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["cluster"]["ClusterDesc"] == "new"
    assert "ModifyCluster" not in _names(fake)
    assert fake.clusters[0]["ClusterDesc"] == "old"


# ---------------------------------------------------------------------------
# lookup semantics
# ---------------------------------------------------------------------------


def test_multiple_name_matches_fail(monkeypatch):
    fake = FakeTsfClient(clusters=[_cluster("cluster-1", ClusterDesc="a"), _cluster("cluster-2", ClusterDesc="b")])
    _make_module(monkeypatch, fake)
    _cluster_args()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "Multiple TSF clusters matched" in exc.value.args[0]["msg"]


# ---------------------------------------------------------------------------
# absent flows
# ---------------------------------------------------------------------------


def test_absent_unregistered_is_idempotent(monkeypatch):
    fake = FakeTsfClient(clusters=[_cluster("cluster-7", ClusterName="other")])
    _make_module(monkeypatch, fake)
    _cluster_args(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["cluster"] is None
    assert "DeleteCluster" not in _names(fake)


def test_absent_deletes_cluster(monkeypatch):
    fake = FakeTsfClient(clusters=[_cluster("cluster-7")])
    _make_module(monkeypatch, fake)
    _cluster_args(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["cluster"] is None
    assert "DeleteCluster" in _names(fake)
    assert fake.clusters == []


def test_absent_unbind_only_passes_unbind_flag(monkeypatch):
    fake = FakeTsfClient(clusters=[_cluster("cluster-7")])
    _make_module(monkeypatch, fake)
    _cluster_args(state="absent", unbind_only=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    request = _last_request(fake, "DeleteCluster")
    assert request.Unbind is True
    assert fake.clusters == []


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeTsfClient(clusters=[_cluster("cluster-7")])
    _make_module(monkeypatch, fake)
    _cluster_args(_ansible_check_mode=True, state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["cluster"] is None
    assert "DeleteCluster" not in _names(fake)
    assert len(fake.clusters) == 1


def test_rejected_delete_fails(monkeypatch):
    class RejectingClient(FakeTsfClient):
        def DeleteCluster(self, request):
            self._record("DeleteCluster", request)
            return SimpleNamespace(Result=False, RequestId="req-err")

    fake = RejectingClient(clusters=[_cluster("cluster-7")])
    _make_module(monkeypatch, fake)
    _cluster_args(state="absent")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "rejected the TSF cluster deletion" in exc.value.args[0]["msg"]


def test_rejected_update_fails(monkeypatch):
    class RejectingClient(FakeTsfClient):
        def ModifyCluster(self, request):
            self._record("ModifyCluster", request)
            return SimpleNamespace(Result=False, RequestId="req-err")

    fake = RejectingClient(clusters=[_cluster("cluster-7", ClusterDesc="old")])
    _make_module(monkeypatch, fake)
    _cluster_args(description="new")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "rejected the TSF cluster update" in exc.value.args[0]["msg"]


# ---------------------------------------------------------------------------
# failure paths
# ---------------------------------------------------------------------------


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeClusters(self, request):
            raise Boom("connection dropped")

    _make_module(monkeypatch, ExplodingClient())
    _cluster_args()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]


# ---------------------------------------------------------------------------
# legacy pure-helper assertions (folded from the shallow test file)
# ---------------------------------------------------------------------------


def test_legacy_desired_maps_creation_and_mutable_fields():
    params = {"name": "prod", "cluster_type": "C", "description": "main", "remark_name": None,
              "vpc_id": "vpc-1", "subnet_id": "subnet-1", "cluster_cidr": None, "tsf_region_id": None,
              "tsf_zone_id": None, "cluster_version": None, "max_node_pods": 64,
              "max_cluster_services": None, "enable_log_collection": True}
    assert desired(params) == {"ClusterName": "prod", "ClusterType": "C", "ClusterDesc": "main",
                               "VpcId": "vpc-1", "SubnetId": "subnet-1",
                               "MaxNodePodNum": 64, "EnableLogCollection": True}


def test_legacy_does_not_compare_create_only_capacity_fields():
    target = {"ClusterName": "prod", "MaxNodePodNum": 64}
    assert comparable({"ClusterName": "prod", "ClusterId": "c1"}, target) == {"ClusterName": "prod"}
