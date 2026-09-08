"""Unit tests for the tcaplusdb_cluster write module (run_module flows).

Drives ``run_module()`` end to end against an in-memory fake TcaplusDB client
whose write operations mutate the cluster store so the post-write ``find``
and ``wait_for_state`` converge immediately.

Scenario matrix:

* absent on a missing cluster (idempotent no-op)
* absent with a matching cluster (check-mode dry run and the real delete)
* creation when missing (missing-parameter guard, check mode, waiting)
* no-op when nothing drifts
* rename drift (``ModifyClusterName``)
* password rotation (guard and happy path)
* immutable IDL/network/type drift guard
* the multiple-match guard and the blanket ``sdk_error_payload`` path
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import tcaplusdb_cluster as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

CLUSTER = {
    "ClusterId": "cluster-1a2b3c4d",
    "ClusterName": "prod-tcaplus",
    "IdlType": "TDR",
    "VpcId": "vpc-1111",
    "SubnetId": "subnet-2222",
    "ClusterStatus": 1,
    "ClusterType": 1,
    "Password": "old-secret",
}


def _cluster(**overrides):
    item = copy.deepcopy(CLUSTER)
    item.update(overrides)
    return item


def _base(**overrides):
    params = {"name": "prod-tcaplus"}
    params.update(overrides)
    return module_args(**params)


class FakeTcaplusdbClient(object):
    """In-memory TcaplusDB client mutating a small cluster store."""

    def __init__(self, clusters=None):
        self.clusters = [copy.deepcopy(t) for t in (clusters or [])]
        self.calls = []
        self._next = 0

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def _find(self, cluster_id):
        for item in self.clusters:
            if item.get("ClusterId") == cluster_id:
                return item
        return None

    def DescribeClusters(self, request):
        self._record("DescribeClusters", request)
        matched = list(self.clusters)
        cluster_ids = getattr(request, "ClusterIds", None)
        if cluster_ids:
            matched = [t for t in matched if t.get("ClusterId") in cluster_ids]
        else:
            for item in list(getattr(request, "Filters", None) or []):
                if getattr(item, "Name", None) == "ClusterName":
                    matched = [t for t in matched if t.get("ClusterName") in (item.Values or [])]
        return SimpleNamespace(Clusters=[FakeResource(t) for t in matched], TotalCount=len(matched))

    def CreateCluster(self, request):
        self._record("CreateCluster", request)
        self._next += 1
        item = {
            "ClusterId": "cluster-new-%03d" % self._next,
            "ClusterName": getattr(request, "ClusterName", None),
            "IdlType": getattr(request, "IdlType", None),
            "VpcId": getattr(request, "VpcId", None),
            "SubnetId": getattr(request, "SubnetId", None),
            "Password": getattr(request, "Password", None),
            "ClusterStatus": 1,
            "ClusterType": getattr(request, "ClusterType", None),
        }
        self.clusters.append(item)
        return SimpleNamespace(ClusterId=item["ClusterId"], RequestId="req-fake")

    def ModifyClusterName(self, request):
        self._record("ModifyClusterName", request)
        item = self._find(getattr(request, "ClusterId", None))
        if item is not None:
            item["ClusterName"] = getattr(request, "ClusterName", item.get("ClusterName"))
        return SimpleNamespace(RequestId="req-fake")

    def ModifyClusterPassword(self, request):
        self._record("ModifyClusterPassword", request)
        item = self._find(getattr(request, "ClusterId", None))
        if item is not None:
            item["Password"] = getattr(request, "NewPassword", item.get("Password"))
        return SimpleNamespace(RequestId="req-fake")

    def DeleteCluster(self, request):
        self._record("DeleteCluster", request)
        cluster_id = getattr(request, "ClusterId", None)
        self.clusters = [t for t in self.clusters if t.get("ClusterId") != cluster_id]
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake, models=None):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (models or FakeModels(), SimpleNamespace(TcaplusdbClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


# ---------------------------------------------------------------------------
# absent flows
# ---------------------------------------------------------------------------


def test_absent_missing_cluster_is_idempotent(monkeypatch):
    fake = FakeTcaplusdbClient(clusters=[])
    _make_module(monkeypatch, fake)
    _base(state="absent", name="ghost-tcaplus")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["cluster"] is None
    assert [c for c, unused in fake.calls] == ["DescribeClusters"]


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeTcaplusdbClient(clusters=[_cluster()])
    _make_module(monkeypatch, fake)
    _base(_ansible_check_mode=True, state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["cluster"] is None
    assert len(fake.clusters) == 1
    assert "DeleteCluster" not in [c for c, unused in fake.calls]


def test_absent_deletes_cluster(monkeypatch):
    fake = FakeTcaplusdbClient(clusters=[_cluster()])
    _make_module(monkeypatch, fake)
    _base(state="absent", cluster_id="cluster-1a2b3c4d", name=None)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["cluster"] is None
    assert fake.clusters == []
    ops = [c for c, unused in fake.calls]
    assert "DeleteCluster" in ops


# ---------------------------------------------------------------------------
# creation flows
# ---------------------------------------------------------------------------


def test_create_requires_creation_parameters(monkeypatch):
    fake = FakeTcaplusdbClient(clusters=[])
    _make_module(monkeypatch, fake)
    _base(state="present", name="brand-new")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "creation parameters are required for a new TcaplusDB cluster" in payload["msg"]
    assert payload["missing"] == ["vpc_id", "subnet_id", "password"]


def test_create_cluster(monkeypatch):
    fake = FakeTcaplusdbClient(clusters=[])
    _make_module(monkeypatch, fake)
    _base(
        state="present",
        name="brand-new",
        vpc_id="vpc-1",
        subnet_id="subnet-1",
        password="s3cret",
        cluster_type=1,
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["cluster"]["ClusterName"] == "brand-new"
    assert result["cluster"]["ClusterId"].startswith("cluster-new-")
    assert result["cluster"]["ClusterStatus"] == 1
    assert len(fake.clusters) == 1
    ops = [c for c, unused in fake.calls]
    assert ops[0] == "DescribeClusters"
    assert "CreateCluster" in ops


def test_create_check_mode_is_dry_run(monkeypatch):
    fake = FakeTcaplusdbClient(clusters=[])
    _make_module(monkeypatch, fake)
    _base(
        _ansible_check_mode=True,
        state="present",
        name="brand-new",
        vpc_id="vpc-1",
        subnet_id="subnet-1",
        password="s3cret",
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["cluster"]["ClusterName"] == "brand-new"
    assert fake.clusters == []
    assert "CreateCluster" not in [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# existing-cluster flows
# ---------------------------------------------------------------------------


def test_existing_cluster_no_drift_is_idempotent(monkeypatch):
    fake = FakeTcaplusdbClient(clusters=[_cluster()])
    _make_module(monkeypatch, fake)
    _base(state="present", cluster_id="cluster-1a2b3c4d", name="prod-tcaplus")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["cluster"]["ClusterId"] == "cluster-1a2b3c4d"


def test_rename_cluster(monkeypatch):
    fake = FakeTcaplusdbClient(clusters=[_cluster()])
    _make_module(monkeypatch, fake)
    _base(state="present", cluster_id="cluster-1a2b3c4d", name="renamed-tcaplus")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["cluster"]["ClusterName"] == "renamed-tcaplus"
    ops = [c for c, unused in fake.calls]
    assert "ModifyClusterName" in ops


def test_rotate_password_requires_credentials(monkeypatch):
    fake = FakeTcaplusdbClient(clusters=[_cluster()])
    _make_module(monkeypatch, fake)
    _base(state="present", cluster_id="cluster-1a2b3c4d", name="prod-tcaplus", rotate_password=True)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "password and new_password are required when rotate_password is true" in exc.value.args[0]["msg"]


def test_rotate_password(monkeypatch):
    fake = FakeTcaplusdbClient(clusters=[_cluster()])
    _make_module(monkeypatch, fake)
    _base(
        state="present",
        cluster_id="cluster-1a2b3c4d",
        name="prod-tcaplus",
        rotate_password=True,
        password="old-secret",
        new_password="new-secret",
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert fake.clusters[0]["Password"] == "new-secret"
    ops = [c for c, unused in fake.calls]
    assert "ModifyClusterPassword" in ops


def test_immutable_drift_fails(monkeypatch):
    fake = FakeTcaplusdbClient(clusters=[_cluster()])
    _make_module(monkeypatch, fake)
    _base(state="present", cluster_id="cluster-1a2b3c4d", name="prod-tcaplus", vpc_id="vpc-other")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "TcaplusDB network, IDL and cluster type are immutable"
    assert "VpcId" in payload["immutable_drift"]


def test_multiple_matches_fail(monkeypatch):
    fake = FakeTcaplusdbClient(clusters=[_cluster(), _cluster(ClusterId="cluster-dup")])
    _make_module(monkeypatch, fake)
    _base(state="present", name="prod-tcaplus")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "Multiple TcaplusDB clusters matched; specify cluster_id" in exc.value.args[0]["msg"]


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
    _base(state="present", name="prod-tcaplus")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]
