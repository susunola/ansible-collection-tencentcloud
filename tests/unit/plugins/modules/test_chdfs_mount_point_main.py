"""Unit tests for the chdfs_mount_point write module (run_module flows).

Drives ``run_module()`` against an in-memory fake CHDFS client whose
create / modify / delete operations mutate a mount-point store so
post-write describes converge immediately.

Scenario matrix:

* absent on a missing mount point, identified by name or ``mount_point_id``
  (idempotent no-op)
* absent with a matching mount point (check-mode dry run, real delete)
* creation when missing (happy path, check mode, missing-name guard)
* no-op when the mount point already matches (name/status)
* name/status drift triggers an update, and the ambiguous-match guard
* the blanket SDK failure path
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import chdfs_mount_point as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

FILE_SYSTEM_ID = "f-etl"

MOUNT_POINT = {
    "MountPointId": "mp-2001",
    "MountPointName": "analytics-mount",
    "Status": 1,
}


def _point(**overrides):
    item = copy.deepcopy(MOUNT_POINT)
    item.update(overrides)
    return item


def _present_args(**overrides):
    params = {"state": "present", "file_system_id": FILE_SYSTEM_ID, "name": "analytics-mount", "status": 1}
    params.update(overrides)
    return module_args(**params)


class FakeChdfsClient(object):
    """In-memory CHDFS client mutating a small mount-point store."""

    def __init__(self, points=None):
        self.points = [copy.deepcopy(t) for t in (points or [])]
        self.calls = []
        self._next = 0

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def _by_id(self, point_id):
        for item in self.points:
            if item.get("MountPointId") == point_id:
                return item
        return None

    def DescribeMountPoints(self, request):
        self._record("DescribeMountPoints", request)
        return SimpleNamespace(MountPoints=[FakeResource(t) for t in self.points])

    def CreateMountPoint(self, request):
        self._record("CreateMountPoint", request)
        self._next += 1
        item = {
            "MountPointId": "mp-%d" % (3000 + self._next),
            "MountPointName": getattr(request, "MountPointName", None),
            "Status": getattr(request, "MountPointStatus", None),
        }
        self.points.append(item)
        return SimpleNamespace(MountPoint=SimpleNamespace(MountPointId=item["MountPointId"]))

    def ModifyMountPoint(self, request):
        self._record("ModifyMountPoint", request)
        item = self._by_id(getattr(request, "MountPointId", None))
        if item is not None:
            item["MountPointName"] = getattr(request, "MountPointName", item.get("MountPointName"))
            item["Status"] = getattr(request, "MountPointStatus", item.get("Status"))
        return SimpleNamespace(RequestId="req-fake")

    def DeleteMountPoint(self, request):
        self._record("DeleteMountPoint", request)
        point_id = getattr(request, "MountPointId", None)
        self.points = [t for t in self.points if t.get("MountPointId") != point_id]
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake, models=None):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (models or FakeModels(), SimpleNamespace(ChdfsClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


# ---------------------------------------------------------------------------
# absent flows
# ---------------------------------------------------------------------------


def test_absent_missing_by_name_is_idempotent(monkeypatch):
    fake = FakeChdfsClient(points=[])
    _make_module(monkeypatch, fake)
    module_args(state="absent", file_system_id=FILE_SYSTEM_ID, name="ghost-mount")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["mount_point"] is None
    assert [c for c, unused in fake.calls] == ["DescribeMountPoints"]


def test_absent_missing_by_id_is_idempotent(monkeypatch):
    fake = FakeChdfsClient(points=[])
    _make_module(monkeypatch, fake)
    module_args(state="absent", file_system_id=FILE_SYSTEM_ID, mount_point_id="mp-9999")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["mount_point"] is None


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeChdfsClient(points=[_point()])
    _make_module(monkeypatch, fake)
    module_args(_ansible_check_mode=True, state="absent", file_system_id=FILE_SYSTEM_ID, name="analytics-mount")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["mount_point"] is None
    assert len(fake.points) == 1
    assert "DeleteMountPoint" not in [c for c, unused in fake.calls]


def test_absent_deletes_mount_point(monkeypatch):
    fake = FakeChdfsClient(points=[_point()])
    _make_module(monkeypatch, fake)
    module_args(state="absent", file_system_id=FILE_SYSTEM_ID, mount_point_id="mp-2001")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["mount_point"] is None
    assert fake.points == []
    assert "DeleteMountPoint" in [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# creation flows
# ---------------------------------------------------------------------------


def test_create_requires_name(monkeypatch):
    fake = FakeChdfsClient(points=[])
    _make_module(monkeypatch, fake)
    module_args(state="present", file_system_id=FILE_SYSTEM_ID, mount_point_id="mp-9999")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "name is required to create a CHDFS mount point" in exc.value.args[0]["msg"]


def test_create_mount_point(monkeypatch):
    fake = FakeChdfsClient(points=[])
    _make_module(monkeypatch, fake)
    _present_args()
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["mount_point"]["MountPointName"] == "analytics-mount"
    assert result["mount_point"]["Status"] == 1
    assert len(fake.points) == 1
    ops = [c for c, unused in fake.calls]
    assert ops[0] == "DescribeMountPoints"
    assert "CreateMountPoint" in ops
    assert ops[-1] == "DescribeMountPoints"


def test_create_check_mode_is_dry_run(monkeypatch):
    fake = FakeChdfsClient(points=[])
    _make_module(monkeypatch, fake)
    _present_args(_ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["mount_point"] == {"MountPointName": "analytics-mount", "Status": 1}
    assert fake.points == []
    assert "CreateMountPoint" not in [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# existing mount-point flows
# ---------------------------------------------------------------------------


def test_existing_no_drift_is_idempotent(monkeypatch):
    fake = FakeChdfsClient(points=[_point()])
    _make_module(monkeypatch, fake)
    _present_args()
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["mount_point"]["MountPointId"] == "mp-2001"
    assert "ModifyMountPoint" not in [c for c, unused in fake.calls]


def test_status_drift_updates(monkeypatch):
    fake = FakeChdfsClient(points=[_point()])
    _make_module(monkeypatch, fake)
    _present_args(status=2)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["mount_point"]["Status"] == 2
    assert "ModifyMountPoint" in [c for c, unused in fake.calls]


def test_rename_by_name_alone_creates_new_point(monkeypatch):
    # Without mount_point_id the module only looks the mount point up by its
    # exact name, so handing it a brand-new name reads as a brand-new mount
    # point (the CHDFS API has no rename-by-name lookup).
    fake = FakeChdfsClient(points=[_point()])
    _make_module(monkeypatch, fake)
    _present_args(name="renamed-mount")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["mount_point"]["MountPointName"] == "renamed-mount"
    assert [p["MountPointName"] for p in fake.points] == ["analytics-mount", "renamed-mount"]


def test_rename_by_id(monkeypatch):
    fake = FakeChdfsClient(points=[_point()])
    _make_module(monkeypatch, fake)
    module_args(state="present", file_system_id=FILE_SYSTEM_ID, mount_point_id="mp-2001", name="renamed-mount", status=1)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["mount_point"]["MountPointName"] == "renamed-mount"
    assert len(fake.points) == 1


def test_ambiguous_name_match_fails(monkeypatch):
    fake = FakeChdfsClient(points=[_point(), _point(MountPointId="mp-2002")])
    _make_module(monkeypatch, fake)
    module_args(state="present", file_system_id=FILE_SYSTEM_ID, name="analytics-mount", status=1)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "specify mount_point_id" in exc.value.args[0]["msg"]


# ---------------------------------------------------------------------------
# failure paths
# ---------------------------------------------------------------------------


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeMountPoints(self, request):
            raise Boom("connection dropped")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    _present_args()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]
