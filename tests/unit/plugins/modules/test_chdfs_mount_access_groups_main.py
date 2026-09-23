"""Unit tests for the chdfs_mount_access_groups write module (run_module flows).

Drives ``run_module()`` against an in-memory fake CHDFS client whose
associate / disassociate operations mutate a mount-point access-group
binding store so post-write describes converge immediately. The module
reconciles the *exact* access-group ID set of one mount point.

Scenario matrix:

* no drift is idempotent
* association of missing IDs and disassociation of stale IDs
* both directions in a single run (order: disassociate then associate)
* check-mode dry run and a missing-mount-point guard
* the blanket SDK failure path
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import chdfs_mount_access_groups as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

FILE_SYSTEM_ID = "f-etl"
MOUNT_POINT_ID = "mp-2001"

MOUNT_POINT = {
    "MountPointId": MOUNT_POINT_ID,
    "AccessGroupIds": ["ag-1", "ag-2"],
}


def _point(**overrides):
    item = copy.deepcopy(MOUNT_POINT)
    item.update(overrides)
    return item


def _args(*ids):
    return module_args(file_system_id=FILE_SYSTEM_ID, mount_point_id=MOUNT_POINT_ID, access_group_ids=list(ids))


class FakeChdfsClient(object):
    """In-memory CHDFS client holding a single mount point's bindings."""

    def __init__(self, points=None):
        self.points = [copy.deepcopy(t) for t in (points or [])]
        self.calls = []

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def _binding(self):
        for point in self.points:
            if point.get("MountPointId") == MOUNT_POINT_ID:
                return point
        return None

    def DescribeMountPoints(self, request):
        self._record("DescribeMountPoints", request)
        return SimpleNamespace(MountPoints=[FakeResource(t) for t in self.points])

    def AssociateAccessGroups(self, request):
        self._record("AssociateAccessGroups", request)
        point = self._binding()
        if point is not None:
            point["AccessGroupIds"] = sorted(set(point.get("AccessGroupIds", [])) | set(getattr(request, "AccessGroupIds", None) or []))
        return SimpleNamespace(RequestId="req-fake")

    def DisassociateAccessGroups(self, request):
        self._record("DisassociateAccessGroups", request)
        point = self._binding()
        if point is not None:
            point["AccessGroupIds"] = sorted(set(point.get("AccessGroupIds", [])) - set(getattr(request, "AccessGroupIds", None) or []))
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake, models=None):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (models or FakeModels(), SimpleNamespace(ChdfsClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


def test_no_drift_is_idempotent(monkeypatch):
    fake = FakeChdfsClient(points=[_point()])
    _make_module(monkeypatch, fake)
    _args("ag-1", "ag-2")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["access_group_ids"] == ["ag-1", "ag-2"]
    assert [c for c, unused in fake.calls] == ["DescribeMountPoints"]


def test_id_order_does_not_matter(monkeypatch):
    fake = FakeChdfsClient(points=[_point()])
    _make_module(monkeypatch, fake)
    _args("ag-2", "ag-1")
    result = run(mod.run_module)
    assert result["changed"] is False


def test_associates_missing_ids(monkeypatch):
    fake = FakeChdfsClient(points=[_point()])
    _make_module(monkeypatch, fake)
    _args("ag-1", "ag-2", "ag-3")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["access_group_ids"] == ["ag-1", "ag-2", "ag-3"]
    ops = [c for c, unused in fake.calls]
    assert "AssociateAccessGroups" in ops
    assert "DisassociateAccessGroups" not in ops
    associate_call = [r for c, r in fake.calls if c == "AssociateAccessGroups"][0]
    assert sorted(associate_call.AccessGroupIds) == ["ag-3"]


def test_disassociates_stale_ids(monkeypatch):
    fake = FakeChdfsClient(points=[_point()])
    _make_module(monkeypatch, fake)
    _args("ag-1")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["access_group_ids"] == ["ag-1"]
    ops = [c for c, unused in fake.calls]
    assert "DisassociateAccessGroups" in ops
    assert "AssociateAccessGroups" not in ops
    disassociate_call = [r for c, r in fake.calls if c == "DisassociateAccessGroups"][0]
    assert sorted(disassociate_call.AccessGroupIds) == ["ag-2"]


def test_both_directions_in_one_run(monkeypatch):
    fake = FakeChdfsClient(points=[_point()])
    _make_module(monkeypatch, fake)
    _args("ag-1", "ag-9")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["access_group_ids"] == ["ag-1", "ag-9"]
    ops = [c for c, unused in fake.calls]
    disassociate_at = ops.index("DisassociateAccessGroups")
    associate_at = ops.index("AssociateAccessGroups")
    assert disassociate_at < associate_at


def test_check_mode_is_dry_run(monkeypatch):
    fake = FakeChdfsClient(points=[_point()])
    _make_module(monkeypatch, fake)
    module_args(_ansible_check_mode=True, file_system_id=FILE_SYSTEM_ID, mount_point_id=MOUNT_POINT_ID, access_group_ids=["ag-1", "ag-9"])
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["access_group_ids"] == ["ag-1", "ag-9"]
    assert fake.points[0]["AccessGroupIds"] == ["ag-1", "ag-2"]
    assert not [c for c, unused in fake.calls if c != "DescribeMountPoints"]


def test_missing_mount_point_fails(monkeypatch):
    fake = FakeChdfsClient(points=[])
    _make_module(monkeypatch, fake)
    _args("ag-1")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "CHDFS mount point was not found"
    assert payload["mount_point_id"] == MOUNT_POINT_ID


def test_duplicate_desired_ids_are_deduplicated(monkeypatch):
    fake = FakeChdfsClient(points=[_point()])
    _make_module(monkeypatch, fake)
    module_args(file_system_id=FILE_SYSTEM_ID, mount_point_id=MOUNT_POINT_ID, access_group_ids=["ag-1", "ag-2", "ag-2"])
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["access_group_ids"] == ["ag-1", "ag-2"]


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeMountPoints(self, request):
            raise Boom("connection dropped")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    _args("ag-1")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]
