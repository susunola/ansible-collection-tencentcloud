"""Unit tests for the tke_cluster write module (run_module flows).

Drives ``run_module()`` end-to-end against an in-memory fake TKE client whose
create / modify / delete operations mutate a small cluster store so the
post-write ``DescribeClusters`` re-read converges immediately.

Scenario matrix:

* identification guard (neither ``cluster_id`` nor ``name``)
* absent on a missing cluster, by name and by id (idempotent no-op)
* absent check-mode dry run and real delete, honouring
  ``instance_delete_mode``
* absent on a deletion-protected cluster disables the protection first
* creation guards (name/vpc_id missing), create happy path and check mode
* no-drift idempotence on an existing cluster
* name/desc/project drift updates, rename by ``cluster_id`` and check mode
* resolver semantics: exact name preferred over fuzzy, ambiguous candidates
  fail
* blanket SDK failure envelope
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import tke_cluster as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

CLUSTER = {
    "ClusterId": "cls-00000001",
    "ClusterName": "prod-k8s",
    "ClusterStatus": "Running",
    "ClusterVersion": "1.28",
    "ClusterDescription": "",
    "ProjectId": 0,
    "VpcId": "vpc-00000001",
    "DeletionProtection": False,
}


def _cluster(**overrides):
    item = copy.deepcopy(CLUSTER)
    item.update(overrides)
    return item


def _args(**overrides):
    params = {"name": "prod-k8s"}
    params.update(overrides)
    return module_args(**params)


class FakeTkeClient(object):
    """In-memory TKE client mutating a small cluster store."""

    def __init__(self, clusters=None):
        self.clusters = [copy.deepcopy(t) for t in (clusters or [])]
        self.calls = []
        self._seq = 0

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def DescribeClusters(self, request):
        self._record("DescribeClusters", request)
        ids = list(getattr(request, "ClusterIds", None) or [])
        candidates = []
        if ids:
            candidates = [t for t in self.clusters if t.get("ClusterId") in ids]
        else:
            filters = getattr(request, "Filters", None) or []
            word = None
            for item in filters:
                if getattr(item, "Name", None) == "cluster-name":
                    word = (getattr(item, "Values", None) or [None])[0]
            if word is not None:
                candidates = [t for t in self.clusters if word in t.get("ClusterName", "")]
            else:
                candidates = list(self.clusters)
        return SimpleNamespace(Clusters=[FakeResource(t) for t in candidates])

    def CreateCluster(self, request):
        self._record("CreateCluster", request)
        self._seq += 1
        basic = request.ClusterBasicSettings
        item = {
            "ClusterId": "cls-fake%04d" % self._seq,
            "ClusterName": getattr(basic, "ClusterName", None),
            "ClusterType": getattr(request, "ClusterType", None),
            "VpcId": getattr(basic, "VpcId", None),
            "ClusterStatus": "Running",
            "ClusterVersion": getattr(basic, "ClusterVersion", None),
            "ClusterDescription": getattr(basic, "ClusterDescription", "") or "",
            "ProjectId": getattr(basic, "ProjectId", None) or 0,
            "DeletionProtection": bool(getattr(request, "ClusterAdvancedSettings", None)),
        }
        self.clusters.append(item)
        return SimpleNamespace(ClusterId=item["ClusterId"])

    def ModifyClusterAttribute(self, request):
        self._record("ModifyClusterAttribute", request)
        item = next((t for t in self.clusters if t.get("ClusterId") == getattr(request, "ClusterId", None)), None)
        if item is None:
            return SimpleNamespace(RequestId="req-fake")
        if getattr(request, "ClusterName", None) is not None:
            item["ClusterName"] = request.ClusterName
        if getattr(request, "ClusterDesc", None) is not None:
            item["ClusterDescription"] = request.ClusterDesc
        if getattr(request, "ProjectId", None) is not None:
            item["ProjectId"] = request.ProjectId
        property_settings = getattr(request, "ClusterProperty", None)
        if property_settings is not None:
            item["DeletionProtection"] = bool(getattr(property_settings, "DeletionProtection", False))
        return SimpleNamespace(RequestId="req-fake")

    def DeleteCluster(self, request):
        self._record("DeleteCluster", request)
        cluster_id = getattr(request, "ClusterId", None)
        self.clusters = [t for t in self.clusters if t.get("ClusterId") != cluster_id]
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load_tke", lambda: (FakeModels(), SimpleNamespace(TkeClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


# ---------------------------------------------------------------------------
# identification and absent flows
# ---------------------------------------------------------------------------


def test_no_identifier_fails(monkeypatch):
    fake = FakeTkeClient()
    _make_module(monkeypatch, fake)
    module_args(state="present")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "cluster_id or name is required" in exc.value.args[0]["msg"]
    assert fake.calls == []


def test_absent_missing_by_name_is_idempotent(monkeypatch):
    fake = FakeTkeClient(clusters=[])
    _make_module(monkeypatch, fake)
    _args(state="absent", name="ghost-cluster")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["msg"] == "TKE cluster already absent"
    assert [c for c, unused in fake.calls] == ["DescribeClusters"]


def test_absent_missing_by_id_is_idempotent(monkeypatch):
    fake = FakeTkeClient(clusters=[])
    _make_module(monkeypatch, fake)
    _args(state="absent", cluster_id="cls-nope", name=None)
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["msg"] == "TKE cluster already absent"


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeTkeClient(clusters=[_cluster()])
    _make_module(monkeypatch, fake)
    _args(_ansible_check_mode=True, state="absent", cluster_id="cls-00000001", name=None)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["msg"] == "Would delete TKE cluster"
    assert len(fake.clusters) == 1
    ops = [c for c, unused in fake.calls]
    assert "DeleteCluster" not in ops


def test_absent_deletes_cluster(monkeypatch):
    fake = FakeTkeClient(clusters=[_cluster()])
    _make_module(monkeypatch, fake)
    _args(state="absent", cluster_id="cls-00000001", name=None, instance_delete_mode="terminate")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["msg"] == "TKE cluster deleted"
    assert fake.clusters == []
    assert "DeleteCluster" in [c for c, unused in fake.calls]
    delete = next(request for op, request in fake.calls if op == "DeleteCluster")
    assert delete.ClusterId == "cls-00000001"
    assert delete.InstanceDeleteMode == "terminate"


def test_absent_disables_deletion_protection_first(monkeypatch):
    fake = FakeTkeClient(clusters=[_cluster(DeletionProtection=True)])
    _make_module(monkeypatch, fake)
    _args(state="absent", name="prod-k8s")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert fake.clusters == []
    ops = [c for c, unused in fake.calls]
    assert ops.count("ModifyClusterAttribute") == 1
    assert ops.count("DeleteCluster") == 1
    assert ops.index("ModifyClusterAttribute") < ops.index("DeleteCluster")
    modify = next(request for op, request in fake.calls if op == "ModifyClusterAttribute")
    assert modify.ClusterProperty.DeletionProtection is False


# ---------------------------------------------------------------------------
# creation flows
# ---------------------------------------------------------------------------


def test_create_requires_name_and_vpc(monkeypatch):
    fake = FakeTkeClient(clusters=[])
    _make_module(monkeypatch, fake)
    _args(state="present", cluster_id="cls-nope", name=None)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "name, vpc_id is required when creating" in exc.value.args[0]["msg"]


def test_create_cluster_happy_path(monkeypatch):
    fake = FakeTkeClient(clusters=[])
    _make_module(monkeypatch, fake)
    _args(
        state="present",
        vpc_id="vpc-00000001",
        subnet_id="subnet-00000001",
        cluster_version="1.28",
        cluster_desc="production fleet",
        project_id=7,
        cluster_type="MANAGED_CLUSTER",
        cluster_cidr="10.42.0.0/16",
        service_cidr="10.43.0.0/16",
        max_node_pod_num=64,
        tags={"env": "prod", "team": "sre"},
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["msg"] == "TKE cluster created"
    assert result["cluster"]["ClusterName"] == "prod-k8s"
    assert len(fake.clusters) == 1
    ops = [c for c, unused in fake.calls]
    assert ops[0] == "DescribeClusters"
    assert "CreateCluster" in ops
    create = next(request for op, request in fake.calls if op == "CreateCluster")
    assert create.ClusterType == "MANAGED_CLUSTER"
    assert create.ClusterBasicSettings.ClusterName == "prod-k8s"
    assert create.ClusterBasicSettings.VpcId == "vpc-00000001"
    assert create.ClusterBasicSettings.SubnetId == "subnet-00000001"
    assert create.ClusterBasicSettings.ClusterVersion == "1.28"
    assert create.ClusterBasicSettings.ClusterDescription == "production fleet"
    assert create.ClusterBasicSettings.ProjectId == 7
    assert create.ClusterCIDRSettings.ClusterCIDR == "10.42.0.0/16"
    assert create.ClusterCIDRSettings.ServiceCIDR == "10.43.0.0/16"
    assert create.ClusterCIDRSettings.MaxNodePodNum == 64
    spec = create.ClusterBasicSettings.TagSpecification[0]
    assert spec.ResourceType == "cluster"
    assert sorted((t.Key, t.Value) for t in spec.Tags) == [("env", "prod"), ("team", "sre")]


def test_create_minimal_sets_no_optionals(monkeypatch):
    fake = FakeTkeClient(clusters=[])
    _make_module(monkeypatch, fake)
    _args(state="present", name="prod-k8s", vpc_id="vpc-00000001")
    result = run(mod.run_module)
    assert result["changed"] is True
    create = next(request for op, request in fake.calls if op == "CreateCluster")
    basic = create.ClusterBasicSettings
    assert not hasattr(basic, "SubnetId")
    assert not hasattr(basic, "ClusterDescription")
    assert not hasattr(create, "ClusterCIDRSettings")
    assert not hasattr(create, "ClusterAdvancedSettings")


def test_create_check_mode_is_dry_run(monkeypatch):
    fake = FakeTkeClient(clusters=[])
    _make_module(monkeypatch, fake)
    _args(_ansible_check_mode=True, state="present", vpc_id="vpc-00000001")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["msg"] == "Would create TKE cluster"
    assert fake.clusters == []
    assert "CreateCluster" not in [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# existing-cluster flows
# ---------------------------------------------------------------------------


def test_existing_cluster_no_drift_is_idempotent(monkeypatch):
    fake = FakeTkeClient(clusters=[_cluster()])
    _make_module(monkeypatch, fake)
    _args(state="present", name="prod-k8s")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["msg"] == "TKE cluster is up to date"
    assert result["cluster"]["ClusterId"] == "cls-00000001"
    assert "ModifyClusterAttribute" not in [c for c, unused in fake.calls]


def test_name_and_description_drift_update(monkeypatch):
    fake = FakeTkeClient(clusters=[_cluster()])
    _make_module(monkeypatch, fake)
    _args(
        state="present",
        cluster_id="cls-00000001",
        name="prod-k8s-v2",
        cluster_desc="production fleet v2",
        project_id=9,
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["msg"] == "TKE cluster updated"
    assert result["cluster"]["ClusterName"] == "prod-k8s-v2"
    assert result["cluster"]["ClusterDescription"] == "production fleet v2"
    assert result["cluster"]["ProjectId"] == 9
    modify = next(request for op, request in fake.calls if op == "ModifyClusterAttribute")
    assert modify.ClusterId == "cls-00000001"
    assert modify.ClusterName == "prod-k8s-v2"
    assert modify.ClusterDesc == "production fleet v2"
    assert modify.ProjectId == 9


def test_update_check_mode_is_dry_run(monkeypatch):
    fake = FakeTkeClient(clusters=[_cluster()])
    _make_module(monkeypatch, fake)
    _args(_ansible_check_mode=True, state="present", cluster_id="cls-00000001", name="prod-k8s-v2")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["msg"] == "Would update TKE cluster"
    assert fake.clusters[0]["ClusterName"] == "prod-k8s"
    assert "ModifyClusterAttribute" not in [c for c, unused in fake.calls]


def test_rename_by_name_alone_creates_new_cluster(monkeypatch):
    # Name is a substring filter, so a renamed cluster can only be located by
    # its id; handing a brand-new name to a name search finds nothing and the
    # module goes down the creation path (guarded on vpc_id).
    fake = FakeTkeClient(clusters=[_cluster()])
    _make_module(monkeypatch, fake)
    _args(state="present", name="prod-k8s-v2", vpc_id="vpc-00000001")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["msg"] == "TKE cluster created"
    assert [c["ClusterName"] for c in fake.clusters] == ["prod-k8s", "prod-k8s-v2"]


# ---------------------------------------------------------------------------
# resolver semantics and failure paths
# ---------------------------------------------------------------------------


def test_exact_name_match_preferred_over_fuzzy(monkeypatch):
    fake = FakeTkeClient(clusters=[_cluster(), _cluster(ClusterId="cls-00000002", ClusterName="prod-k8s-v2")])
    _make_module(monkeypatch, fake)
    _args(state="present", name="prod-k8s")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["cluster"]["ClusterId"] == "cls-00000001"


def test_ambiguous_name_match_fails(monkeypatch):
    fake = FakeTkeClient(clusters=[
        _cluster(ClusterId="cls-00000002", ClusterName="prod-a"),
        _cluster(ClusterId="cls-00000003", ClusterName="prod-b"),
    ])
    _make_module(monkeypatch, fake)
    _args(state="present", name="prod")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["ambiguous"] is True
    assert "Ambiguous TKE cluster reference" in payload["msg"]


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        def get_code(self):
            # Not classified as retryable so sdk_call does not sleep through
            # its backoff curve before the module builds the error payload.
            return "UnauthorizedOperation.PermissionDenied"

    class ExplodingClient(object):
        def DescribeClusters(self, request):
            raise Boom("connection dropped")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    _args(state="present")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]
    assert payload["error_code"] == "UnauthorizedOperation.PermissionDenied"
