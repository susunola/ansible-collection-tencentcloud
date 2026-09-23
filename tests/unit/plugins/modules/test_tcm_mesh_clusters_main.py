"""Unit tests for the tcm_mesh_clusters write module (run_module flows).

``tcm_mesh_clusters`` reconciles the exact set of clusters linked to a TCM
mesh: clusters absent remotely are linked, stale clusters are unlinked,
and clusters whose payload drifted are relinked. The fake TCM client
stores the mesh's cluster list and mutates it on Link/Unlink.

Scenario matrix:

* exact-set no-drift idempotence
* mesh-not-found guard and malformed cluster spec guard
* link an added cluster / unlink a stale cluster (real, check mode)
* drift on a shared ClusterId relinks the cluster
* blanket SDK failure path
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import tcm_mesh_clusters as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

MESH_ID = "mesh-abc123"

CLUSTERS = [
    {"ClusterId": "cls-abc123", "Region": "ap-guangzhou", "Role": "REMOTE"},
    {"ClusterId": "cls-def456", "Region": "ap-shanghai", "Role": "REMOTE"},
]


def _cluster(**overrides):
    item = copy.deepcopy(CLUSTERS[0])
    item.update(overrides)
    return item


def _m_args(**overrides):
    params = {"mesh_id": MESH_ID}
    params.update(overrides)
    return module_args(**params)


class FakeTcmClient(object):
    """In-memory TCM client mutating a mesh cluster list."""

    def __init__(self, clusters=None):
        self.clusters = [copy.deepcopy(c) for c in (clusters or [])]
        self.calls = []

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def DescribeMesh(self, request):
        self._record("DescribeMesh", request)
        if request.MeshId != MESH_ID:
            return SimpleNamespace(Mesh=None)
        return SimpleNamespace(Mesh=SimpleNamespace(
            ClusterList=[FakeResource(dict(c)) for c in self.clusters],
        ))

    def LinkClusterList(self, request):
        self._record("LinkClusterList", request)
        for cluster in request.ClusterList:
            value = copy.deepcopy(cluster.__dict__)
            self.clusters = [c for c in self.clusters if c["ClusterId"] != value["ClusterId"]]
            self.clusters.append(value)
        return SimpleNamespace()

    def UnlinkCluster(self, request):
        self._record("UnlinkCluster", request)
        self.clusters = [c for c in self.clusters if c["ClusterId"] != request.ClusterId]
        return SimpleNamespace()


def _make_module(monkeypatch, fake):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (FakeModels(), SimpleNamespace(TcmClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


# ---------------------------------------------------------------------------
# idempotence and guards
# ---------------------------------------------------------------------------


def test_exact_set_no_drift_is_idempotent(monkeypatch):
    fake = FakeTcmClient(clusters=CLUSTERS)
    _make_module(monkeypatch, fake)
    _m_args(clusters=CLUSTERS)
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["clusters"] == sorted(CLUSTERS, key=lambda x: x["ClusterId"])
    ops = [c for c, unused in fake.calls]
    assert "LinkClusterList" not in ops
    assert "UnlinkCluster" not in ops


def test_mesh_not_found_fails(monkeypatch):
    fake = FakeTcmClient(clusters=[])
    _make_module(monkeypatch, fake)
    _m_args(mesh_id="mesh-ghost999", clusters=CLUSTERS)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "TCM mesh was not found" in exc.value.args[0]["msg"]


def test_missing_or_duplicate_cluster_id_fails(monkeypatch):
    fake = FakeTcmClient(clusters=[])
    _make_module(monkeypatch, fake)
    _m_args(clusters=[{"Region": "ap-guangzhou"}])
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "unique ClusterId" in exc.value.args[0]["msg"]


# ---------------------------------------------------------------------------
# link / unlink flows
# ---------------------------------------------------------------------------


def test_links_added_cluster(monkeypatch):
    fake = FakeTcmClient(clusters=[_cluster()])
    _make_module(monkeypatch, fake)
    wanted = [_cluster(), _cluster(ClusterId="cls-new999", Region="ap-beijing")]
    _m_args(clusters=wanted)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert {c["ClusterId"] for c in result["clusters"]} == {"cls-abc123", "cls-new999"}
    assert {c["ClusterId"] for c in fake.clusters} == {"cls-abc123", "cls-new999"}
    ops = [c for c, unused in fake.calls]
    assert "LinkClusterList" in ops
    assert "UnlinkCluster" not in ops


def test_link_check_mode_is_dry_run(monkeypatch):
    fake = FakeTcmClient(clusters=[_cluster()])
    _make_module(monkeypatch, fake)
    _m_args(_ansible_check_mode=True, clusters=[_cluster(), _cluster(ClusterId="cls-new999")])
    result = run(mod.run_module)
    assert result["changed"] is True
    assert {c["ClusterId"] for c in result["clusters"]} == {"cls-abc123", "cls-new999"}
    assert {c["ClusterId"] for c in fake.clusters} == {"cls-abc123"}
    assert "LinkClusterList" not in [c for c, unused in fake.calls]


def test_unlinks_stale_cluster(monkeypatch):
    fake = FakeTcmClient(clusters=[_cluster(), _cluster(ClusterId="cls-def456")])
    _make_module(monkeypatch, fake)
    _m_args(clusters=[_cluster()])
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["clusters"] == [_cluster()]
    assert fake.clusters == [_cluster()]
    ops = [c for c, unused in fake.calls]
    assert "UnlinkCluster" in ops


def test_drifted_cluster_is_relinked(monkeypatch):
    fake = FakeTcmClient(clusters=[_cluster()])
    _make_module(monkeypatch, fake)
    drifted = _cluster(Region="ap-beijing", Role="REMOTE")
    _m_args(clusters=[drifted])
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["clusters"] == [drifted]
    assert fake.clusters == [drifted]
    ops = [c for c, unused in fake.calls]
    assert "UnlinkCluster" in ops
    assert "LinkClusterList" in ops


# ---------------------------------------------------------------------------
# failure paths
# ---------------------------------------------------------------------------


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeMesh(self, request):
            raise Boom("connection dropped")

    _make_module(monkeypatch, ExplodingClient())
    _m_args(clusters=CLUSTERS)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]
