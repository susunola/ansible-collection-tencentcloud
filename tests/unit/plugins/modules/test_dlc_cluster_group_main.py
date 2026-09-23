"""Unit tests for the dlc_cluster_group write module (run_module flows).

Drives ``run_module()`` end to end against an in-memory fake DLC client whose
write operations mutate the cluster-group store so post-write find/waiter
polls converge immediately.

Scenario matrix:

* absent on a missing group (idempotent no-op)
* absent with a matching group (requires ``allow_delete``, refuses active
  clusters without ``force_detach``, check-mode dry run, real delete)
* creation when missing (happy path, check mode)
* no-op when nothing drifts
* drift updates (description, config)
* validation guards (invalid ``config`` JSON, multiple matches)
* the blanket ``sdk_error_payload`` failure path
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import dlc_cluster_group as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

GROUP = {
    "Id": "grp-8b0a1c2d",
    "Name": "shared-ray-compute",
    "Description": "Shared managed compute group",
    "Config": '{"dispatchStrategy":"RANDOM"}',
    "Deleted": False,
}


def _group(**overrides):
    item = copy.deepcopy(GROUP)
    item.update(overrides)
    return item


def _base(**overrides):
    params = {"name": "shared-ray-compute"}
    params.update(overrides)
    return module_args(**params)


class FakeDlcClient(object):
    """In-memory DLC client mutating a small cluster-group store."""

    def __init__(self, groups=None, active_clusters=0):
        self.groups = [copy.deepcopy(t) for t in (groups or [])]
        self.active_clusters = active_clusters
        self.calls = []
        self._next = 0

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def _find(self, name):
        for item in self.groups:
            if item.get("Name") == name and not item.get("Deleted"):
                return item
        return None

    def ListClusterGroups(self, request):
        self._record("ListClusterGroups", request)
        matches = [dict(t) for t in self.groups if not t.get("Deleted")]
        return SimpleNamespace(
            Items=[FakeResource(t) for t in matches],
            TotalCount=len(matches),
            TotalPages=1,
        )

    def CreateClusterGroup(self, request):
        self._record("CreateClusterGroup", request)
        self._next += 1
        item = {
            "Id": "grp-new-%03d" % self._next,
            "Name": getattr(request, "Name", None),
            "Deleted": False,
        }
        for attr in ("Description", "Config"):
            value = getattr(request, attr, None)
            if value is not None:
                item[attr] = value
        self.groups.append(item)
        return SimpleNamespace(Id=item["Id"], RequestId="req-fake")

    def UpdateClusterGroup(self, request):
        self._record("UpdateClusterGroup", request)
        for item in self.groups:
            if item.get("Id") == getattr(request, "Id", None):
                for attr in ("Description", "Config"):
                    value = getattr(request, attr, None)
                    if value is not None:
                        item[attr] = value
        return SimpleNamespace(RequestId="req-fake")

    def DescribeClusterGroupClusters(self, request):
        self._record("DescribeClusterGroupClusters", request)
        samples = [FakeResource({"ClusterId": "cluster-active-1", "Status": "Running"})] if self.active_clusters else []
        return SimpleNamespace(Count=self.active_clusters, SampleClusters=samples)

    def DeleteClusterGroup(self, request):
        self._record("DeleteClusterGroup", request)
        self.groups = [t for t in self.groups if t.get("Id") != getattr(request, "Id", None)]
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake, models=None):
    """Wire the shared monkeypatches; returns the fake client."""
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (models or FakeModels(), SimpleNamespace(DlcClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


# ---------------------------------------------------------------------------
# absent flows
# ---------------------------------------------------------------------------


def test_absent_missing_group_is_idempotent(monkeypatch):
    fake = FakeDlcClient(groups=[])
    _make_module(monkeypatch, fake)
    _base(state="absent", name="ghost-group")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["cluster_group"] is None
    assert result["cluster_group_id"] is None
    assert [c for c, unused in fake.calls] == ["ListClusterGroups"]


def test_absent_requires_allow_delete(monkeypatch):
    fake = FakeDlcClient(groups=[_group()])
    _make_module(monkeypatch, fake)
    _base(state="absent")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "allow_delete=true" in exc.value.args[0]["msg"]
    assert exc.value.args[0]["cluster_group"]["Id"] == GROUP["Id"]


def test_absent_refuses_active_clusters_without_force_detach(monkeypatch):
    fake = FakeDlcClient(groups=[_group()], active_clusters=2)
    _make_module(monkeypatch, fake)
    _base(state="absent", allow_delete=True)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "force_detach=true" in payload["msg"]
    assert payload["active_clusters"]["count"] == 2


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeDlcClient(groups=[_group()])
    _make_module(monkeypatch, fake)
    _base(_ansible_check_mode=True, state="absent", allow_delete=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert len(fake.groups) == 1
    assert "DeleteClusterGroup" not in [c for c, unused in fake.calls]


def test_absent_deletes_group(monkeypatch):
    fake = FakeDlcClient(groups=[_group()])
    _make_module(monkeypatch, fake)
    _base(state="absent", allow_delete=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["cluster_group"] is None
    assert fake.groups == []
    ops = [c for c, unused in fake.calls]
    assert "DeleteClusterGroup" in ops


def test_absent_force_detach_detaches_and_deletes(monkeypatch):
    fake = FakeDlcClient(groups=[_group()], active_clusters=3)
    _make_module(monkeypatch, fake)
    _base(state="absent", allow_delete=True, force_detach=True, wait=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert fake.groups == []
    assert result["active_clusters"]["count"] == 3
    ops = [c for c, unused in fake.calls]
    assert "DescribeClusterGroupClusters" in ops
    assert "DeleteClusterGroup" in ops


# ---------------------------------------------------------------------------
# creation flows
# ---------------------------------------------------------------------------


def test_create_group(monkeypatch):
    fake = FakeDlcClient(groups=[])
    _make_module(monkeypatch, fake)
    _base(
        state="present",
        name="brand-new-ray",
        description="fresh group",
        config='{"dispatchStrategy":"RANDOM","maxWorkers":4}',
        wait=True,
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["cluster_group"]["Name"] == "brand-new-ray"
    assert result["cluster_group"]["Description"] == "fresh group"
    assert result["cluster_group_id"].startswith("grp-new-")
    assert len(fake.groups) == 1
    ops = [c for c, unused in fake.calls]
    assert ops[0] == "ListClusterGroups"
    assert "CreateClusterGroup" in ops


def test_create_check_mode_is_dry_run(monkeypatch):
    fake = FakeDlcClient(groups=[])
    _make_module(monkeypatch, fake)
    _base(
        _ansible_check_mode=True,
        state="present",
        name="brand-new-ray",
        description="fresh group",
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["cluster_group_id"] is None
    assert result["cluster_group"]["Name"] == "brand-new-ray"
    assert result["cluster_group"]["Description"] == "fresh group"
    assert fake.groups == []
    assert "CreateClusterGroup" not in [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# existing-group flows
# ---------------------------------------------------------------------------


def test_existing_group_no_drift_is_idempotent(monkeypatch):
    fake = FakeDlcClient(groups=[_group()])
    _make_module(monkeypatch, fake)
    _base(
        state="present",
        name="shared-ray-compute",
        description="Shared managed compute group",
        config='{"dispatchStrategy":"RANDOM"}',
    )
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["cluster_group"]["Id"] == GROUP["Id"]
    assert "UpdateClusterGroup" not in [c for c, unused in fake.calls]


def test_update_description_drift(monkeypatch):
    fake = FakeDlcClient(groups=[_group()])
    _make_module(monkeypatch, fake)
    _base(state="present", description="Renamed description", wait=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["cluster_group"]["Description"] == "Renamed description"
    ops = [c for c, unused in fake.calls]
    assert "UpdateClusterGroup" in ops


def test_update_config_drift(monkeypatch):
    fake = FakeDlcClient(groups=[_group()])
    _make_module(monkeypatch, fake)
    _base(state="present", config='{"dispatchStrategy":"DISPATCH_RANDOM"}', wait=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["cluster_group"]["Config"] == '{"dispatchStrategy":"DISPATCH_RANDOM"}'
    ops = [c for c, unused in fake.calls]
    assert "UpdateClusterGroup" in ops


# ---------------------------------------------------------------------------
# guards / validation / failure paths
# ---------------------------------------------------------------------------


def test_invalid_config_json_fails(monkeypatch):
    fake = FakeDlcClient(groups=[])
    _make_module(monkeypatch, fake)
    _base(state="absent", config="{not json")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert exc.value.args[0]["msg"] == "config must be valid JSON"


def test_multiple_matches_fail(monkeypatch):
    fake = FakeDlcClient(groups=[_group(), _group(Id="grp-dup")])
    _make_module(monkeypatch, fake)
    _base(state="present")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "Multiple active DLC cluster groups matched" in exc.value.args[0]["msg"]


def test_deleted_groups_are_ignored(monkeypatch):
    fake = FakeDlcClient(groups=[_group(Deleted=True)])
    _make_module(monkeypatch, fake)
    _base(state="absent", name="shared-ray-compute")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["cluster_group"] is None


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def ListClusterGroups(self, request):
            raise Boom("connection dropped")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    _base(state="present")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]


# ---------------------------------------------------------------------------
# legacy helper regression tests (folded from test_dlc_cluster_group.py)
# ---------------------------------------------------------------------------


class LegacyRequest(object):
    def from_json_string(self, value):
        import json

        for key, item in json.loads(value).items():
            setattr(self, key, item)


class LegacyModels(object):
    ListClusterGroupsRequest = LegacyRequest
    CreateClusterGroupRequest = LegacyRequest
    UpdateClusterGroupRequest = LegacyRequest
    DeleteClusterGroupRequest = LegacyRequest
    DescribeClusterGroupClustersRequest = LegacyRequest


def test_json_normalization_and_drift_are_semantic():
    current = mod.normalize({"Name": "compute", "Description": "old", "Config": '{"b":2,"a":1}'})
    params = {"name": "compute", "description": "new", "config": '{"a":1,"b":2}'}
    assert mod.canonical(params["config"]) == '{"a":1,"b":2}'
    assert mod.drift(params, current) == {"Description": ("old", "new")}


def test_requests_preserve_stable_identity_and_force_guard():
    create = mod.make_request(LegacyModels, {"name": "compute", "description": None, "config": '{"z":1,"a":2}'})
    update = mod.make_request(LegacyModels, {"name": "compute", "description": "managed", "config": None}, update=True, group_id="cg-1")
    delete = mod.delete_request(LegacyModels, "cg-1", True)
    listing = mod.list_request(LegacyModels, 3)
    clusters = mod.cluster_request(LegacyModels, "cg-1")
    assert create.Config == '{"a":2,"z":1}'
    assert update.Id == "cg-1" and update.Description == "managed"
    assert delete.Id == "cg-1" and delete.Force is True
    assert listing.Page == 3 and listing.PageSize == 200
    assert clusters.Id == "cg-1" and clusters.SampleLimit == 20
