"""Unit tests for the tdcpg_cluster write module (run_module flows).

Drives ``run_module()`` end to end against an in-memory fake TDSQL-C
PostgreSQL client whose write operations mutate the cluster / member stores
so the module's post-write ``find`` refetch and ``wait_for_state`` polls
converge immediately.

Scenario matrix:

* absent on a missing cluster (idempotent no-op)
* absent on an existing cluster (isolate, check-mode dry run, purge guard and
  the real purge of an already isolated cluster)
* creation when missing (missing-parameter guard, happy path, check mode)
* no-op when nothing drifts
* drift updates (rename, scale up, scale in with/without ``allow_scale_in``,
  resize, auto-renew toggle)
* immutable placement / version guards
* validation guards (identity requirement, bad choice) and the blanket
  ``sdk_error_payload`` failure path
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import tdcpg_cluster as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

CLUSTER = {
    "ClusterId": "cluster-9c1d2e3f",
    "ClusterName": "production-tdcpg",
    "Status": "running",
    "Zone": "ap-guangzhou-3",
    "DBVersion": "13.3",
    "DBMajorVersion": "13",
    "DBKernelVersion": "pg13.3",
    "EndpointSet": [{"VpcId": "vpc-aaa111", "SubnetId": "subnet-bbb222"}],
    "AutoRenewFlag": 0,
    "PayMode": "POSTPAID_BY_HOUR",
}

MEMBERS = [
    {"ClusterId": "cluster-9c1d2e3f", "InstanceId": "tdcpg-ins-1", "CPU": 2, "Memory": 4, "Status": "running"},
    {"ClusterId": "cluster-9c1d2e3f", "InstanceId": "tdcpg-ins-2", "CPU": 2, "Memory": 4, "Status": "running"},
]


def _cluster(**overrides):
    item = dict(CLUSTER)
    item.update(overrides)
    return item


def _member(cluster_id, index, **overrides):
    item = {
        "ClusterId": cluster_id,
        "InstanceId": "tdcpg-ins-%d" % index,
        "CPU": 2,
        "Memory": 4,
        "Status": "running",
    }
    item.update(overrides)
    return item


def _base(**overrides):
    params = {}
    params.update(overrides)
    return module_args(**params)


def _id_args(**overrides):
    params = {"cluster_id": "cluster-9c1d2e3f"}
    params.update(overrides)
    return module_args(**params)


def _name_args(**overrides):
    params = {"name": "production-tdcpg"}
    params.update(overrides)
    return module_args(**params)


class FakeTdcpgClient(object):
    """In-memory TDSQL-C PostgreSQL client mutating cluster/member stores."""

    def __init__(self, clusters=None, members=None):
        self.clusters = [dict(t) for t in (clusters or [])]
        self.members = [dict(t) for t in (members or [])]
        self.calls = []
        self._next = 0

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def _match(self, request):
        matched = None
        for item in self.clusters:
            for filt in getattr(request, "Filters", None) or []:
                values = list(getattr(filt, "Values", None) or [])
                if getattr(filt, "Name", None) == "ClusterId" and str(item.get("ClusterId")) in values:
                    matched = item
                elif getattr(filt, "Name", None) == "ClusterName" and item.get("ClusterName") in values:
                    matched = item
        return matched

    def DescribeClusters(self, request):
        self._record("DescribeClusters", request)
        matched = self._match(request)
        return SimpleNamespace(
            ClusterSet=[FakeResource(matched)] if matched else [],
            TotalCount=1 if matched else 0,
            RequestId="req-describe",
        )

    def DescribeClusterInstances(self, request):
        self._record("DescribeClusterInstances", request)
        rows = [m for m in self.members if m.get("ClusterId") == getattr(request, "ClusterId", None)]
        return SimpleNamespace(InstanceSet=[FakeResource(m) for m in rows], RequestId="req-instances")

    def _members_for(self, cluster_id):
        return [m for m in self.members if m.get("ClusterId") == cluster_id]

    def CreateCluster(self, request):
        self._record("CreateCluster", request)
        self._next += 1
        cluster_id = "cluster-new-%03d" % self._next
        cluster = {
            "ClusterId": cluster_id,
            "ClusterName": getattr(request, "ClusterName", None),
            "Status": "running",
            "Zone": getattr(request, "Zone", None),
            "DBVersion": getattr(request, "DBVersion", None),
            "DBMajorVersion": getattr(request, "DBMajorVersion", None),
            "DBKernelVersion": getattr(request, "DBKernelVersion", None),
            "EndpointSet": [{"VpcId": getattr(request, "VpcId", None), "SubnetId": getattr(request, "SubnetId", None)}],
            "AutoRenewFlag": getattr(request, "AutoRenewFlag", None) or 0,
            "PayMode": getattr(request, "PayMode", None),
        }
        self.clusters.append(cluster)
        for index in range(getattr(request, "InstanceCount", None) or 1):
            self.members.append(_member(cluster_id, index + 1, CPU=getattr(request, "CPU", None), Memory=getattr(request, "Memory", None)))
        return SimpleNamespace(ClusterId=cluster_id, RequestId="req-create")

    def CreateClusterInstances(self, request):
        self._record("CreateClusterInstances", request)
        for index in range(getattr(request, "InstanceCount", 0)):
            self.members.append(
                _member(request.ClusterId, len(self._members_for(request.ClusterId)) + index + 1, CPU=request.CPU, Memory=request.Memory)
            )
        return SimpleNamespace(RequestId="req-create-instances")

    def ModifyClusterInstancesSpec(self, request):
        self._record("ModifyClusterInstancesSpec", request)
        for member in self.members:
            if member.get("InstanceId") in list(getattr(request, "InstanceIdSet", None) or []):
                member["CPU"] = getattr(request, "CPU", None)
                member["Memory"] = getattr(request, "Memory", None)
        return SimpleNamespace(RequestId="req-resize")

    def DeleteClusterInstances(self, request):
        self._record("DeleteClusterInstances", request)
        doomed = set(getattr(request, "InstanceIdSet", None) or [])
        self.members = [m for m in self.members if m.get("InstanceId") not in doomed]
        return SimpleNamespace(RequestId="req-delete-instances")

    def ModifyClusterName(self, request):
        self._record("ModifyClusterName", request)
        for item in self.clusters:
            if item.get("ClusterId") == getattr(request, "ClusterId", None):
                item["ClusterName"] = getattr(request, "ClusterName", None)
        return SimpleNamespace(RequestId="req-rename")

    def ModifyClustersAutoRenewFlag(self, request):
        self._record("ModifyClustersAutoRenewFlag", request)
        for item in self.clusters:
            if item.get("ClusterId") in list(getattr(request, "ClusterIdSet", None) or []):
                item["AutoRenewFlag"] = getattr(request, "AutoRenewFlag", None)
        return SimpleNamespace(RequestId="req-renew")

    def IsolateCluster(self, request):
        self._record("IsolateCluster", request)
        for item in self.clusters:
            if item.get("ClusterId") == getattr(request, "ClusterId", None):
                item["Status"] = "isolated"
        return SimpleNamespace(RequestId="req-isolate")

    def DeleteCluster(self, request):
        self._record("DeleteCluster", request)
        self.clusters = [c for c in self.clusters if c.get("ClusterId") != getattr(request, "ClusterId", None)]
        self.members = [m for m in self.members if m.get("ClusterId") != getattr(request, "ClusterId", None)]
        return SimpleNamespace(RequestId="req-delete")


def _make_module(monkeypatch, fake, models=None):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (models or FakeModels(), SimpleNamespace(TdcpgClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)


# ---------------------------------------------------------------------------
# absent flows
# ---------------------------------------------------------------------------


def test_absent_missing_cluster_is_idempotent(monkeypatch):
    fake = FakeTdcpgClient()
    _make_module(monkeypatch, fake)
    _name_args(state="absent", name="ghost-cluster")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["cluster"] is None
    assert [c for c, unused in fake.calls] == ["DescribeClusters"]


def test_absent_isolates_running_cluster(monkeypatch):
    fake = FakeTdcpgClient(clusters=[_cluster()], members=[_member("cluster-9c1d2e3f", 1)])
    _make_module(monkeypatch, fake)
    _id_args(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["cluster"]["ClusterId"] == "cluster-9c1d2e3f"
    assert fake.clusters[0]["Status"] == "isolated"
    assert "IsolateCluster" in [c for c, unused in fake.calls]


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeTdcpgClient(clusters=[_cluster()], members=[_member("cluster-9c1d2e3f", 1)])
    _make_module(monkeypatch, fake)
    _id_args(_ansible_check_mode=True, state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert fake.clusters[0]["Status"] == "running"
    assert "IsolateCluster" not in [c for c, unused in fake.calls]


def test_absent_already_isolated_is_idempotent(monkeypatch):
    fake = FakeTdcpgClient(clusters=[_cluster(Status="isolated")])
    _make_module(monkeypatch, fake)
    _id_args(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["cluster"]["Status"] == "isolated"


def test_absent_purge_requires_isolated_cluster(monkeypatch):
    fake = FakeTdcpgClient(clusters=[_cluster()])
    _make_module(monkeypatch, fake)
    _id_args(state="absent", purge=True)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "purge requires an already isolated" in exc.value.args[0]["msg"]


def test_absent_purge_deletes_isolated_cluster(monkeypatch):
    fake = FakeTdcpgClient(
        clusters=[_cluster(Status="isolated")],
        members=[_member("cluster-9c1d2e3f", 1)],
    )
    _make_module(monkeypatch, fake)
    _id_args(state="absent", purge=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["cluster"] is None
    assert fake.clusters == []
    assert fake.members == []
    assert "DeleteCluster" in [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# creation flows
# ---------------------------------------------------------------------------


def test_create_requires_creation_parameters(monkeypatch):
    fake = FakeTdcpgClient()
    _make_module(monkeypatch, fake)
    _name_args(state="present", name="brand-new")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "creation parameters are required" in payload["msg"]
    assert payload["missing"] == ["zone", "vpc_id", "subnet_id", "master_password", "cpu", "memory"]


def test_create_cluster(monkeypatch):
    fake = FakeTdcpgClient()
    _make_module(monkeypatch, fake)
    _base(
        state="present",
        name="brand-new",
        zone="ap-guangzhou-3",
        vpc_id="vpc-aaa111",
        subnet_id="subnet-bbb222",
        master_password="s3cret!",
        cpu=2,
        memory=4,
        instance_count=2,
        db_version="13.3",
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["cluster"]["ClusterName"] == "brand-new"
    assert result["cluster"]["ClusterId"].startswith("cluster-new-")
    assert len(fake.clusters) == 1
    assert len(fake.members) == 2
    ops = [c for c, unused in fake.calls]
    assert ops[0] == "DescribeClusters"
    assert "CreateCluster" in ops


def test_create_check_mode_is_dry_run(monkeypatch):
    fake = FakeTdcpgClient()
    _make_module(monkeypatch, fake)
    _base(
        _ansible_check_mode=True,
        state="present",
        name="brand-new",
        zone="ap-guangzhou-3",
        vpc_id="vpc-aaa111",
        subnet_id="subnet-bbb222",
        master_password="s3cret!",
        cpu=2,
        memory=4,
        instance_count=2,
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["cluster"]["ClusterName"] == "brand-new"
    assert result["cluster"]["Zone"] == "ap-guangzhou-3"
    assert "ClusterId" not in result["cluster"]
    assert fake.clusters == []
    assert "CreateCluster" not in [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# existing-cluster flows
# ---------------------------------------------------------------------------


def test_existing_cluster_no_drift_is_idempotent(monkeypatch):
    fake = FakeTdcpgClient(clusters=[_cluster()], members=[_member("cluster-9c1d2e3f", 1)])
    _make_module(monkeypatch, fake)
    _id_args(state="present")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["cluster"]["ClusterId"] == "cluster-9c1d2e3f"


def test_rename_cluster(monkeypatch):
    fake = FakeTdcpgClient(clusters=[_cluster()], members=[_member("cluster-9c1d2e3f", 1)])
    _make_module(monkeypatch, fake)
    _id_args(state="present", name="renamed-tdcpg")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["cluster"]["ClusterName"] == "renamed-tdcpg"
    assert fake.clusters[0]["ClusterName"] == "renamed-tdcpg"
    assert "ModifyClusterName" in [c for c, unused in fake.calls]


def test_scale_in_requires_allow_scale_in(monkeypatch):
    fake = FakeTdcpgClient(
        clusters=[_cluster()],
        members=[_member("cluster-9c1d2e3f", 1), _member("cluster-9c1d2e3f", 2)],
    )
    _make_module(monkeypatch, fake)
    _id_args(state="present", instance_count=1)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "allow_scale_in=true" in payload["msg"]
    assert payload["current_count"] == 2
    assert payload["desired_count"] == 1


def test_scale_in_authorized_deletes_instances(monkeypatch):
    fake = FakeTdcpgClient(
        clusters=[_cluster()],
        members=[_member("cluster-9c1d2e3f", 1), _member("cluster-9c1d2e3f", 2)],
    )
    _make_module(monkeypatch, fake)
    _id_args(state="present", instance_count=1, allow_scale_in=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert len(fake.members) == 1
    assert "DeleteClusterInstances" in [c for c, unused in fake.calls]


def test_scale_up_creates_instances(monkeypatch):
    fake = FakeTdcpgClient(clusters=[_cluster()], members=[_member("cluster-9c1d2e3f", 1)])
    _make_module(monkeypatch, fake)
    _id_args(state="present", instance_count=3)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert len(fake.members) == 3
    assert "CreateClusterInstances" in [c for c, unused in fake.calls]


def test_spec_drift_resizes_instances(monkeypatch):
    fake = FakeTdcpgClient(
        clusters=[_cluster()],
        members=[_member("cluster-9c1d2e3f", 1), _member("cluster-9c1d2e3f", 2)],
    )
    _make_module(monkeypatch, fake)
    _id_args(state="present", cpu=4, memory=8)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert all(m["CPU"] == 4 and m["Memory"] == 8 for m in fake.members)
    assert "ModifyClusterInstancesSpec" in [c for c, unused in fake.calls]


def test_auto_renew_toggle_applies(monkeypatch):
    fake = FakeTdcpgClient(clusters=[_cluster()], members=[_member("cluster-9c1d2e3f", 1)])
    _make_module(monkeypatch, fake)
    _id_args(state="present", auto_renew=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert fake.clusters[0]["AutoRenewFlag"] == 1
    assert "ModifyClustersAutoRenewFlag" in [c for c, unused in fake.calls]


def test_immutable_placement_drift_fails(monkeypatch):
    fake = FakeTdcpgClient(clusters=[_cluster()], members=[_member("cluster-9c1d2e3f", 1)])
    _make_module(monkeypatch, fake)
    _id_args(state="present", zone="ap-guangzhou-6")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "immutable" in payload["msg"]
    assert "Zone" in payload["immutable_drift"]


# ---------------------------------------------------------------------------
# validation / failure paths
# ---------------------------------------------------------------------------


def test_requires_cluster_id_or_name(monkeypatch):
    fake = FakeTdcpgClient()
    _make_module(monkeypatch, fake)
    _base(state="present")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "cluster_id" in exc.value.args[0]["msg"]
    assert "name" in exc.value.args[0]["msg"]


def test_invalid_pay_mode_fails(monkeypatch):
    fake = FakeTdcpgClient()
    _make_module(monkeypatch, fake)
    _id_args(state="absent", pay_mode="BOGUS")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "BOGUS" in exc.value.args[0]["msg"]


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeClusters(self, request):
            raise Boom("connection dropped")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    _id_args(state="present")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]
