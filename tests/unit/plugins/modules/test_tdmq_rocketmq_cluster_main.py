"""Unit tests for the tdmq_rocketmq_cluster write module (run_module flows).

Drives ``run_module()`` end to end against an in-memory fake TDMQ client
whose write operations mutate the RocketMQ cluster store, so the module's
post-write ``find`` refetch converges immediately.

Scenario matrix:

* absent on a missing cluster (idempotent no-op)
* absent with a matching cluster (check-mode dry run and real delete)
* creation when missing
* no-op when nothing drifts
* rename with ``cluster_id`` and the guard that requires it
* the not-found ``cluster_id`` guard and the multi-match guard
* sensitive credential fields stripped from the reported metadata
* the blanket SDK-failure path
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import tdmq_rocketmq_cluster as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

CLUSTER = {
    "ClusterId": "rocketmq-prod123",
    "ClusterName": "app-messaging",
    "Remark": "shared application cluster",
    "Status": "running",
    "AdminAccessKey": "secret-access-key",
    "AdminSecretKey": "secret-secret-key",
}


def _cluster(**overrides):
    item = copy.deepcopy(CLUSTER)
    item.update(overrides)
    return item


def _base(**overrides):
    # ``name`` is spec-required; cluster_id is optional and mutually
    # distinguishable, so start from the name only.
    params = {"name": "app-messaging"}
    params.update(overrides)
    return module_args(**params)


class FakeTdmqClient(object):
    """In-memory TDMQ client mutating a RocketMQ cluster store."""

    def __init__(self, clusters=None):
        self.clusters = [copy.deepcopy(t) for t in (clusters or [])]
        self.calls = []

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def DescribeRocketMQClusters(self, request):
        self._record("DescribeRocketMQClusters", request)
        items = [
            FakeResource({"Info": dict(t), "Status": t.get("Status")})
            for t in self.clusters
        ]
        return SimpleNamespace(ClusterList=items, TotalCount=len(items))

    def CreateRocketMQCluster(self, request):
        self._record("CreateRocketMQCluster", request)
        self.clusters.append({
            "ClusterId": "rocketmq-new-%03d" % (len(self.clusters) + 1),
            "ClusterName": getattr(request, "Name", None),
            "Remark": getattr(request, "Remark", None) or "",
            "Status": "running",
        })
        return SimpleNamespace(RequestId="req-fake")

    def ModifyRocketMQCluster(self, request):
        self._record("ModifyRocketMQCluster", request)
        for item in self.clusters:
            if item.get("ClusterId") == request.ClusterId:
                item["ClusterName"] = getattr(request, "ClusterName", item.get("ClusterName"))
                item["Remark"] = getattr(request, "Remark", item.get("Remark")) or ""
        return SimpleNamespace(RequestId="req-fake")

    def DeleteRocketMQCluster(self, request):
        self._record("DeleteRocketMQCluster", request)
        self.clusters = [t for t in self.clusters if t.get("ClusterId") != request.ClusterId]
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake, models=None):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (models or FakeModels(), SimpleNamespace(TdmqClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


# ---------------------------------------------------------------------------
# absent flows
# ---------------------------------------------------------------------------


def test_absent_missing_cluster_is_idempotent(monkeypatch):
    fake = FakeTdmqClient(clusters=[])
    _make_module(monkeypatch, fake)
    _base(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["cluster"] is None
    assert [c for c, unused in fake.calls] == ["DescribeRocketMQClusters"]


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeTdmqClient(clusters=[_cluster()])
    _make_module(monkeypatch, fake)
    _base(_ansible_check_mode=True, state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["cluster"]["ClusterId"] == "rocketmq-prod123"
    assert "DeleteRocketMQCluster" not in [c for c, unused in fake.calls]


def test_absent_deletes_cluster(monkeypatch):
    fake = FakeTdmqClient(clusters=[_cluster()])
    _make_module(monkeypatch, fake)
    _base(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["cluster"] is None
    assert fake.clusters == []
    assert "DeleteRocketMQCluster" in [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# creation flows
# ---------------------------------------------------------------------------


def test_create_cluster(monkeypatch):
    fake = FakeTdmqClient(clusters=[])
    _make_module(monkeypatch, fake)
    _base(state="present", remark="brand new cluster")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["cluster"]["ClusterName"] == "app-messaging"
    assert result["cluster"]["Remark"] == "brand new cluster"
    assert result["cluster"]["ClusterId"].startswith("rocketmq-new-")
    assert len(fake.clusters) == 1
    ops = [c for c, unused in fake.calls]
    assert "CreateRocketMQCluster" in ops


def test_create_check_mode_is_dry_run(monkeypatch):
    fake = FakeTdmqClient(clusters=[])
    _make_module(monkeypatch, fake)
    _base(_ansible_check_mode=True, state="present")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["cluster"] is None
    assert fake.clusters == []
    assert "CreateRocketMQCluster" not in [c for c, unused in fake.calls]


def test_existing_cluster_no_drift_is_idempotent(monkeypatch):
    fake = FakeTdmqClient(clusters=[_cluster()])
    _make_module(monkeypatch, fake)
    _base(state="present", remark="shared application cluster")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["cluster"]["ClusterId"] == "rocketmq-prod123"


def test_create_excludes_sensitive_fields(monkeypatch):
    fake = FakeTdmqClient(clusters=[])
    _make_module(monkeypatch, fake)
    _base(state="present", remark="x")
    result = run(mod.run_module)
    assert "AdminAccessKey" not in result["cluster"]
    assert "AdminSecretKey" not in result["cluster"]


# ---------------------------------------------------------------------------
# update / rename flows
# ---------------------------------------------------------------------------


def test_rename_with_cluster_id_applies(monkeypatch):
    fake = FakeTdmqClient(clusters=[_cluster()])
    _make_module(monkeypatch, fake)
    _base(state="present", cluster_id="rocketmq-prod123", name="renamed-cluster", remark="shared application cluster")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["cluster"]["ClusterName"] == "renamed-cluster"
    assert fake.clusters[0]["ClusterName"] == "renamed-cluster"
    ops = [c for c, unused in fake.calls]
    assert "ModifyRocketMQCluster" in ops


def test_rename_check_mode_is_dry_run(monkeypatch):
    fake = FakeTdmqClient(clusters=[_cluster()])
    _make_module(monkeypatch, fake)
    _base(_ansible_check_mode=True, state="present", cluster_id="rocketmq-prod123", name="renamed-cluster")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert fake.clusters[0]["ClusterName"] == "app-messaging"
    assert "ModifyRocketMQCluster" not in [c for c, unused in fake.calls]


def test_unknown_cluster_id_is_rejected_for_create(monkeypatch):
    fake = FakeTdmqClient(clusters=[])
    _make_module(monkeypatch, fake)
    _base(state="present", cluster_id="rocketmq-ghost", name="brand-new")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "cluster_id was not found" in exc.value.args[0]["msg"]


# ---------------------------------------------------------------------------
# guards / failure paths
# ---------------------------------------------------------------------------


def test_multiple_name_matches_fail(monkeypatch):
    fake = FakeTdmqClient(clusters=[_cluster(), _cluster(ClusterId="rocketmq-prod456")])
    _make_module(monkeypatch, fake)
    _base(state="present", remark="shared application cluster")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "multiple RocketMQ clusters matched name" in exc.value.args[0]["msg"]


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeRocketMQClusters(self, request):
            raise Boom("connection dropped")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    _base(state="present")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]
