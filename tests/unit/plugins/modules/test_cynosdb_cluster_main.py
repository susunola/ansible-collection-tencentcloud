"""Unit tests for the cynosdb_cluster write module (run_module flows).

Drives ``run_module()`` end to end against an in-memory fake CynosDB
client whose write operations mutate the cluster store, so the module's
resolver-based ``find`` refetch and the running-state waiter converge
immediately.

Scenario matrix:

* absent on a missing cluster (idempotent no-op)
* absent with a running cluster (check-mode dry run, real isolate)
* absent on an already isolated cluster (no-op, and the purge path)
* purge authorization guard (must already be isolated)
* creation when missing (with/without the mandatory creation parameters,
  check mode)
* no-op when nothing drifts
* rename / storage expansion / slave-zone change / cynos version upgrade
* the storage-reduction and immutable-field guards
* the ambiguous-name guard and the blanket SDK-failure path
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import cynosdb_cluster as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

CLUSTER = {
    "ClusterId": "cynosdbmysql-prod01",
    "ClusterName": "production-cynosdb",
    "Status": "running",
    "DbType": "MYSQL",
    "DbVersion": "8.0",
    "Zone": "ap-guangzhou-3",
    "VpcId": "vpc-c-1111",
    "SubnetId": "subnet-c-1111",
    "StorageLimit": 100,
    "SlaveZones": [],
    "CynosVersion": "4.0",
}


def _cluster(**overrides):
    item = copy.deepcopy(CLUSTER)
    item.update(overrides)
    return item


def _base(**overrides):
    # cluster_id and name are alternatives (required_one_of); start from the
    # name and let update tests pass a cluster_id instead.
    params = {"name": "production-cynosdb"}
    params.update(overrides)
    return module_args(**params)


class FakeCynosdbClient(object):
    """In-memory CynosDB client mutating a cluster store."""

    def __init__(self, clusters=None):
        self.clusters = [copy.deepcopy(t) for t in (clusters or [])]
        self.calls = []
        self._next = 0

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def DescribeClusters(self, request):
        self._record("DescribeClusters", request)
        return SimpleNamespace(
            ClusterSet=[FakeResource(dict(t)) for t in self.clusters],
            TotalCount=len(self.clusters),
        )

    def CreateClusters(self, request):
        self._record("CreateClusters", request)
        self._next += 1
        cluster_id = "cynosdbmysql-new%03d" % self._next
        slave_zones = [request.SlaveZone] if getattr(request, "SlaveZone", None) else []
        self.clusters.append({
            "ClusterId": cluster_id,
            "ClusterName": request.ClusterName,
            "Status": "running",
            "DbType": request.DbType,
            "DbVersion": request.DbVersion,
            "Zone": request.Zone,
            "VpcId": request.VpcId,
            "SubnetId": request.SubnetId,
            "StorageLimit": request.Storage,
            "SlaveZones": slave_zones,
            "CynosVersion": getattr(request, "CynosVersion", None),
        })
        return SimpleNamespace(ClusterIds=[cluster_id], RequestId="req-fake")

    def ModifyClusterName(self, request):
        self._record("ModifyClusterName", request)
        for item in self.clusters:
            if item.get("ClusterId") == request.ClusterId:
                item["ClusterName"] = request.ClusterName
        return SimpleNamespace(RequestId="req-fake")

    def ModifyClusterStorage(self, request):
        self._record("ModifyClusterStorage", request)
        for item in self.clusters:
            if item.get("ClusterId") == request.ClusterId:
                item["StorageLimit"] = request.NewStorageLimit
        return SimpleNamespace(RequestId="req-fake")

    def ModifyClusterSlaveZone(self, request):
        self._record("ModifyClusterSlaveZone", request)
        for item in self.clusters:
            if item.get("ClusterId") == request.ClusterId:
                item["SlaveZones"] = [request.NewSlaveZone]
        return SimpleNamespace(RequestId="req-fake")

    def UpgradeClusterVersion(self, request):
        self._record("UpgradeClusterVersion", request)
        for item in self.clusters:
            if item.get("ClusterId") == request.ClusterId:
                item["CynosVersion"] = request.CynosVersion
        return SimpleNamespace(RequestId="req-fake")

    def IsolateCluster(self, request):
        self._record("IsolateCluster", request)
        for item in self.clusters:
            if item.get("ClusterId") == request.ClusterId:
                item["Status"] = "isolated"
        return SimpleNamespace(RequestId="req-fake")

    def OfflineCluster(self, request):
        self._record("OfflineCluster", request)
        self.clusters = [t for t in self.clusters if t.get("ClusterId") != request.ClusterId]
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake, models=None):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (models or FakeModels(), SimpleNamespace(CynosdbClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


# ---------------------------------------------------------------------------
# absent flows
# ---------------------------------------------------------------------------


def test_absent_missing_cluster_is_idempotent(monkeypatch):
    fake = FakeCynosdbClient(clusters=[])
    _make_module(monkeypatch, fake)
    _base(state="absent", name="ghost-cluster")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["cluster"] is None
    assert [c for c, unused in fake.calls] == ["DescribeClusters"]


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeCynosdbClient(clusters=[_cluster()])
    _make_module(monkeypatch, fake)
    _base(_ansible_check_mode=True, state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["cluster"]["ClusterId"] == "cynosdbmysql-prod01"
    assert "IsolateCluster" not in [c for c, unused in fake.calls]


def test_absent_isolates_running_cluster(monkeypatch):
    fake = FakeCynosdbClient(clusters=[_cluster()])
    _make_module(monkeypatch, fake)
    _base(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["cluster"]["ClusterId"] == "cynosdbmysql-prod01"
    ops = [c for c, unused in fake.calls]
    assert "IsolateCluster" in ops


def test_absent_isolated_cluster_is_idempotent(monkeypatch):
    fake = FakeCynosdbClient(clusters=[_cluster(Status="isolated")])
    _make_module(monkeypatch, fake)
    _base(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert "IsolateCluster" not in [c for c, unused in fake.calls]


def test_purge_requires_isolated_cluster(monkeypatch):
    fake = FakeCynosdbClient(clusters=[_cluster()])
    _make_module(monkeypatch, fake)
    _base(state="absent", purge=True)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "purge requires an already isolated" in exc.value.args[0]["msg"]


def test_purge_check_mode_is_dry_run(monkeypatch):
    fake = FakeCynosdbClient(clusters=[_cluster(Status="isolated")])
    _make_module(monkeypatch, fake)
    _base(_ansible_check_mode=True, state="absent", purge=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert len(fake.clusters) == 1
    assert "OfflineCluster" not in [c for c, unused in fake.calls]


def test_purge_isolated_cluster(monkeypatch):
    fake = FakeCynosdbClient(clusters=[_cluster(Status="isolated")])
    _make_module(monkeypatch, fake)
    _base(state="absent", purge=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert fake.clusters == []
    ops = [c for c, unused in fake.calls]
    assert "OfflineCluster" in ops


# ---------------------------------------------------------------------------
# creation flows
# ---------------------------------------------------------------------------


def test_create_requires_creation_parameters(monkeypatch):
    fake = FakeCynosdbClient(clusters=[])
    _make_module(monkeypatch, fake)
    _base(state="present", name="brand-new")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "creation parameters are required" in payload["msg"]
    assert payload["missing"] == ["zone", "vpc_id", "subnet_id", "db_version", "cpu", "memory", "storage", "admin_password"]


def test_create_cluster(monkeypatch):
    fake = FakeCynosdbClient(clusters=[])
    _make_module(monkeypatch, fake)
    _base(
        state="present",
        name="production-cynosdb",
        zone="ap-guangzhou-3",
        vpc_id="vpc-c-1111",
        subnet_id="subnet-c-1111",
        db_version="8.0",
        cpu=2,
        memory=4,
        storage=100,
        admin_password="vaulted-password",
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    cluster = result["cluster"]
    assert cluster["ClusterName"] == "production-cynosdb"
    assert cluster["StorageLimit"] == 100
    assert cluster["Status"] == "running"
    assert cluster["ClusterId"].startswith("cynosdbmysql-new")
    assert len(fake.clusters) == 1
    ops = [c for c, unused in fake.calls]
    assert ops[0] == "DescribeClusters"
    assert "CreateClusters" in ops


def test_create_check_mode_is_dry_run(monkeypatch):
    fake = FakeCynosdbClient(clusters=[])
    _make_module(monkeypatch, fake)
    _base(
        _ansible_check_mode=True,
        state="present",
        name="production-cynosdb",
        zone="ap-guangzhou-3",
        vpc_id="vpc-c-1111",
        subnet_id="subnet-c-1111",
        db_version="8.0",
        cpu=2,
        memory=4,
        storage=100,
        admin_password="vaulted-password",
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["cluster"]["ClusterName"] == "production-cynosdb"
    assert result["cluster"]["StorageLimit"] == 100
    assert fake.clusters == []
    assert "CreateClusters" not in [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# existing-cluster flows
# ---------------------------------------------------------------------------


def test_existing_cluster_no_drift_is_idempotent(monkeypatch):
    fake = FakeCynosdbClient(clusters=[_cluster()])
    _make_module(monkeypatch, fake)
    _base(state="present")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["cluster"]["ClusterId"] == "cynosdbmysql-prod01"


def test_rename_cluster(monkeypatch):
    fake = FakeCynosdbClient(clusters=[_cluster()])
    _make_module(monkeypatch, fake)
    module_args(state="present", cluster_id="cynosdbmysql-prod01", name="production-v2")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["cluster"]["ClusterName"] == "production-v2"
    ops = [c for c, unused in fake.calls]
    assert "ModifyClusterName" in ops


def test_expand_storage(monkeypatch):
    fake = FakeCynosdbClient(clusters=[_cluster()])
    _make_module(monkeypatch, fake)
    module_args(state="present", cluster_id="cynosdbmysql-prod01", name="production-cynosdb", storage=200)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["cluster"]["StorageLimit"] == 200
    ops = [c for c, unused in fake.calls]
    assert "ModifyClusterStorage" in ops


def test_storage_cannot_be_reduced(monkeypatch):
    fake = FakeCynosdbClient(clusters=[_cluster()])
    _make_module(monkeypatch, fake)
    module_args(state="present", cluster_id="cynosdbmysql-prod01", name="production-cynosdb", storage=50)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "storage cannot be reduced" in exc.value.args[0]["msg"]


def test_change_slave_zone(monkeypatch):
    fake = FakeCynosdbClient(clusters=[_cluster(SlaveZones=["ap-guangzhou-4"])])
    _make_module(monkeypatch, fake)
    module_args(state="present", cluster_id="cynosdbmysql-prod01", name="production-cynosdb", slave_zone="ap-guangzhou-5")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["cluster"]["SlaveZones"] == ["ap-guangzhou-5"]
    ops = [c for c, unused in fake.calls]
    assert "ModifyClusterSlaveZone" in ops


def test_upgrade_cynos_version(monkeypatch):
    fake = FakeCynosdbClient(clusters=[_cluster(CynosVersion="4.0")])
    _make_module(monkeypatch, fake)
    module_args(state="present", cluster_id="cynosdbmysql-prod01", name="production-cynosdb", cynos_version="5.0")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["cluster"]["CynosVersion"] == "5.0"
    ops = [c for c, unused in fake.calls]
    assert "UpgradeClusterVersion" in ops


# ---------------------------------------------------------------------------
# guards / failure paths
# ---------------------------------------------------------------------------


def test_immutable_zone_fails(monkeypatch):
    fake = FakeCynosdbClient(clusters=[_cluster()])
    _make_module(monkeypatch, fake)
    _base(state="present", zone="ap-shanghai-2")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "placement, engine and compatible version are immutable" in payload["msg"]
    assert "Zone" in payload["immutable_drift"]


def test_ambiguous_name_matches_fail(monkeypatch):
    fake = FakeCynosdbClient(clusters=[_cluster(), _cluster(ClusterId="cynosdbmysql-prod02")])
    _make_module(monkeypatch, fake)
    _base(state="present")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "Ambiguous CynosDB cluster reference" in payload["msg"]
    assert payload["ambiguous"] is True


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeClusters(self, request):
            raise Boom("connection dropped")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    _base(state="present")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]
