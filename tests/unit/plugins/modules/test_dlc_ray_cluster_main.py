"""Unit tests for the dlc_ray_cluster write module (run_module flows).

Drives ``run_module()`` end to end against an in-memory fake DLC client whose
write operations mutate the Ray-cluster store, so the post-write list
refetch and waiters converge immediately.

Scenario matrix:

* argument validation (priority bounds, resource_config XOR
  resource_config_id, invalid JSON bodies)
* absent on a missing cluster (idempotent) / allow_delete guard /
  check-mode dry run / real delete
* creation when missing (missing creation parameters, check mode, real
  create with wait)
* no-op when nothing drifts
* drift updates (mutable fields and priority-only change)
* the multiple-match guard
* the blanket ``sdk_error_payload`` failure path
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import dlc_ray_cluster as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

CLUSTER = {
    "Id": "rc-8b0a1c2d",
    "Name": "analytics-ray",
    "Type": "CLUSTER",
    "Description": "analytics",
    "ResourcePartitionId": "rp-100",
    "Queue": "notebooks",
    "Image": "ccr.ccs.tencentyun.com/dlc/ray:latest",
    "ImagePullType": "BuiltIn",
    "Priority": 5,
    "Tags": [{"TagKey": "environment", "TagValue": "production"}],
}

CANONICAL_TARGETS = ("ResourceConfig", "Catalog", "AdvancedOptions")


def _cluster(**overrides):
    item = copy.deepcopy(CLUSTER)
    item.update(overrides)
    return item


def _base(**overrides):
    params = {"name": "analytics-ray"}
    params.update(overrides)
    return module_args(**params)


class FakeDlcClient(object):
    """In-memory DLC client mutating a small Ray-cluster store."""

    def __init__(self, clusters=None):
        self.clusters = [copy.deepcopy(t) for t in (clusters or [])]
        self.calls = []
        self._next = 0

    def _find(self, cluster_id):
        for item in self.clusters:
            if item.get("Id") == cluster_id:
                return item
        return None

    def _copy_payload(self, request):
        # make_request round-trips a JSON payload into the request object.
        data = dict(getattr(request, "__dict__", {}) or {})
        data = {k: v for k, v in data.items() if not k.startswith("_")}
        return data

    def ListRayClusters(self, request):
        self.calls.append("ListRayClusters")
        return SimpleNamespace(Items=[FakeResource(t) for t in self.clusters], TotalPages=1, RequestId="req-fake")

    def CreateRayCluster(self, request):
        self.calls.append("CreateRayCluster")
        self._next += 1
        item = self._copy_payload(request)
        item.setdefault("Name", None)
        item["Id"] = "ray-new-%03d" % self._next
        item.setdefault("Type", "CLUSTER")
        self.clusters.append(item)
        return SimpleNamespace(Id=item["Id"], RequestId="req-fake")

    def UpdateRayCluster(self, request):
        self.calls.append("UpdateRayCluster")
        item = self._find(getattr(request, "Id", None))
        if item is not None:
            for key, value in self._copy_payload(request).items():
                if key not in ("Id", "Name"):
                    item[key] = value
        return SimpleNamespace(RequestId="req-fake")

    def ModifyClusterPriority(self, request):
        self.calls.append("ModifyClusterPriority")
        item = self._find(getattr(request, "Id", None))
        if item is not None:
            item["Priority"] = getattr(request, "Priority", None)
        return SimpleNamespace(RequestId="req-fake")

    def DeleteRayCluster(self, request):
        self.calls.append("DeleteRayCluster")
        self.clusters = [t for t in self.clusters if t.get("Id") != getattr(request, "Id", None)]
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake, models=None):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (models or FakeModels(), SimpleNamespace(DlcClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


# ---------------------------------------------------------------------------
# argument validation
# ---------------------------------------------------------------------------


def test_priority_out_of_range_fails(monkeypatch):
    fake = FakeDlcClient()
    _make_module(monkeypatch, fake)
    _base(priority=10)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "priority must be between 1 and 9" in exc.value.args[0]["msg"]


def test_resource_config_mutually_exclusive(monkeypatch):
    fake = FakeDlcClient()
    _make_module(monkeypatch, fake)
    _base(resource_config='{"Cpu": 2}', resource_config_id="rc-1")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "mutually exclusive" in exc.value.args[0]["msg"]


def test_invalid_resource_config_json_fails(monkeypatch):
    fake = FakeDlcClient()
    _make_module(monkeypatch, fake)
    _base(resource_config="{not json")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "must be valid JSON" in exc.value.args[0]["msg"]


# ---------------------------------------------------------------------------
# absent flows
# ---------------------------------------------------------------------------


def test_absent_missing_cluster_is_idempotent(monkeypatch):
    fake = FakeDlcClient()
    _make_module(monkeypatch, fake)
    _base(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["ray_cluster"] is None
    assert result["ray_cluster_id"] is None
    assert list(fake.calls) == ["ListRayClusters"]


def test_absent_requires_allow_delete(monkeypatch):
    fake = FakeDlcClient(clusters=[_cluster()])
    _make_module(monkeypatch, fake)
    _base(state="absent")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "allow_delete=true" in exc.value.args[0]["msg"]


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeDlcClient(clusters=[_cluster()])
    _make_module(monkeypatch, fake)
    _base(_ansible_check_mode=True, state="absent", allow_delete=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert len(fake.clusters) == 1
    assert "DeleteRayCluster" not in fake.calls


def test_absent_deletes_cluster(monkeypatch):
    fake = FakeDlcClient(clusters=[_cluster()])
    _make_module(monkeypatch, fake)
    _base(state="absent", allow_delete=True, wait=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert fake.clusters == []
    ops = list(fake.calls)
    assert "DeleteRayCluster" in ops


# ---------------------------------------------------------------------------
# creation flows
# ---------------------------------------------------------------------------


def test_create_requires_creation_parameters(monkeypatch):
    fake = FakeDlcClient()
    _make_module(monkeypatch, fake)
    _base()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "creation parameters are required" in payload["msg"]
    assert "resource_config or resource_config_id" in payload["missing"]


def test_create_cluster(monkeypatch):
    fake = FakeDlcClient()
    _make_module(monkeypatch, fake)
    _base(
        resource_partition_id="rp-100",
        queue="notebooks",
        image="ccr.ccs.tencentyun.com/dlc/ray:latest",
        image_pull_type="BuiltIn",
        resource_config_id="rc-1",
        priority=5,
        description="analytics",
        tags=[{"key": "environment", "value": "production"}],
        wait=True,
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["ray_cluster_id"].startswith("ray-new-")
    assert result["ray_cluster"]["Name"] == "analytics-ray"
    assert result["ray_cluster"]["Queue"] == "notebooks"
    assert result["ray_cluster"]["Priority"] == 5
    assert len(fake.clusters) == 1
    ops = list(fake.calls)
    assert ops[0] == "ListRayClusters"
    assert "CreateRayCluster" in ops


def test_create_check_mode_is_dry_run(monkeypatch):
    fake = FakeDlcClient()
    _make_module(monkeypatch, fake)
    _base(
        _ansible_check_mode=True,
        resource_partition_id="rp-100",
        queue="notebooks",
        image="ccr.ccs.tencentyun.com/dlc/ray:latest",
        image_pull_type="BuiltIn",
        resource_config_id="rc-1",
        priority=5,
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["ray_cluster_id"] is None
    assert result["ray_cluster"]["Queue"] == "notebooks"
    assert fake.clusters == []
    assert "CreateRayCluster" not in fake.calls


# ---------------------------------------------------------------------------
# existing-cluster flows
# ---------------------------------------------------------------------------


def test_existing_cluster_no_drift_is_idempotent(monkeypatch):
    fake = FakeDlcClient(clusters=[_cluster()])
    _make_module(monkeypatch, fake)
    _base(description="analytics", priority=5)
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["ray_cluster"]["Id"] == "rc-8b0a1c2d"


def test_update_drift_changes_mutable_fields(monkeypatch):
    fake = FakeDlcClient(clusters=[_cluster()])
    _make_module(monkeypatch, fake)
    _base(description="renamed description", priority=5, wait=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["ray_cluster"]["Description"] == "renamed description"
    ops = list(fake.calls)
    assert "UpdateRayCluster" in ops
    assert "ModifyClusterPriority" not in ops


def test_priority_only_change(monkeypatch):
    fake = FakeDlcClient(clusters=[_cluster()])
    _make_module(monkeypatch, fake)
    _base(description="analytics", priority=8, wait=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["ray_cluster"]["Priority"] == 8
    ops = list(fake.calls)
    assert "UpdateRayCluster" not in ops
    assert "ModifyClusterPriority" in ops


def test_update_check_mode_is_dry_run(monkeypatch):
    fake = FakeDlcClient(clusters=[_cluster()])
    _make_module(monkeypatch, fake)
    _base(_ansible_check_mode=True, description="renamed description", priority=8)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["ray_cluster"]["Description"] == "renamed description"
    assert "UpdateRayCluster" not in fake.calls
    assert "ModifyClusterPriority" not in fake.calls


def test_multiple_matches_fail(monkeypatch):
    fake = FakeDlcClient(clusters=[_cluster(), _cluster(Id="rc-dup")])
    _make_module(monkeypatch, fake)
    _base()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "Multiple DLC Ray clusters matched" in exc.value.args[0]["msg"]


# ---------------------------------------------------------------------------
# failure paths
# ---------------------------------------------------------------------------


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def ListRayClusters(self, request):
            raise Boom("connection dropped")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    _base()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]
