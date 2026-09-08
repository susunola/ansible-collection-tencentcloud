"""Unit tests for the cfs_snapshot write module (run_module flows).

Drives ``run_module()`` end to end against an in-memory fake CFS client
whose write operations mutate the snapshot store so post-write ``find``
refetches converge immediately.

Scenario matrix:

* absent on a missing snapshot (idempotent no-op)
* absent with a matching snapshot (check-mode dry run and real delete)
* creation when missing (with/without the mandatory name/fs pair, check mode)
* no-op when nothing drifts
* attribute updates (rename / alive-days) through ``snapshot_id``
* the immutable file-system guard with and without ``force_replace``
* the multiple-match guard and the blanket SDK-failure path
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import cfs_snapshot as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

SNAPSHOT = {
    "SnapshotId": "snap-cfs-1001",
    "FileSystemId": "cfs-abcdefgh",
    "SnapshotName": "before-upgrade",
    "AliveDay": 30,
}


def _snapshot(**overrides):
    item = copy.deepcopy(SNAPSHOT)
    item.update(overrides)
    return item


def _base(**overrides):
    # snapshot_id and name are alternatives (required_one_of); start empty.
    params = {}
    params.update(overrides)
    return module_args(**params)


class FakeCfsClient(object):
    """In-memory CFS client mutating a snapshot store."""

    def __init__(self, snapshots=None):
        self.snapshots = [copy.deepcopy(t) for t in (snapshots or [])]
        self.calls = []
        self._next = 0

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def DescribeCfsSnapshots(self, request):
        self._record("DescribeCfsSnapshots", request)
        return SimpleNamespace(
            Snapshots=[FakeResource(dict(t)) for t in self.snapshots],
            TotalCount=len(self.snapshots),
        )

    def CreateCfsSnapshot(self, request):
        self._record("CreateCfsSnapshot", request)
        self._next += 1
        self.snapshots.append({
            "SnapshotId": "snap-cfs-new-%03d" % self._next,
            "FileSystemId": request.FileSystemId,
            "SnapshotName": request.SnapshotName,
            "AliveDay": 0,
        })
        return SimpleNamespace(SnapshotId=self.snapshots[-1]["SnapshotId"], RequestId="req-fake")

    def UpdateCfsSnapshotAttribute(self, request):
        self._record("UpdateCfsSnapshotAttribute", request)
        for item in self.snapshots:
            if item.get("SnapshotId") == request.SnapshotId:
                if getattr(request, "SnapshotName", None) is not None:
                    item["SnapshotName"] = request.SnapshotName
                if getattr(request, "AliveDays", None) is not None:
                    item["AliveDay"] = request.AliveDays
        return SimpleNamespace(RequestId="req-fake")

    def DeleteCfsSnapshot(self, request):
        self._record("DeleteCfsSnapshot", request)
        self.snapshots = [t for t in self.snapshots if t.get("SnapshotId") != request.SnapshotId]
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake, models=None):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (models or FakeModels(), SimpleNamespace(CfsClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


# ---------------------------------------------------------------------------
# absent flows
# ---------------------------------------------------------------------------


def test_absent_missing_snapshot_is_idempotent(monkeypatch):
    fake = FakeCfsClient(snapshots=[])
    _make_module(monkeypatch, fake)
    _base(state="absent", snapshot_id="snap-cfs-ghost")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["snapshot"] is None
    assert [c for c, unused in fake.calls] == ["DescribeCfsSnapshots"]


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeCfsClient(snapshots=[_snapshot()])
    _make_module(monkeypatch, fake)
    _base(_ansible_check_mode=True, state="absent", snapshot_id="snap-cfs-1001")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["snapshot"]["SnapshotId"] == "snap-cfs-1001"
    assert "DeleteCfsSnapshot" not in [c for c, unused in fake.calls]


def test_absent_deletes_snapshot(monkeypatch):
    fake = FakeCfsClient(snapshots=[_snapshot()])
    _make_module(monkeypatch, fake)
    _base(state="absent", snapshot_id="snap-cfs-1001")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["snapshot"] is None
    assert fake.snapshots == []
    assert "DeleteCfsSnapshot" in [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# creation flows
# ---------------------------------------------------------------------------


def test_create_requires_name_and_file_system(monkeypatch):
    fake = FakeCfsClient(snapshots=[])
    _make_module(monkeypatch, fake)
    _base(state="present", name="before-upgrade")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "name and file_system_id are required when state=present" in exc.value.args[0]["msg"]


def test_create_snapshot(monkeypatch):
    fake = FakeCfsClient(snapshots=[])
    _make_module(monkeypatch, fake)
    _base(state="present", file_system_id="cfs-abcdefgh", name="before-upgrade", alive_days=30)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["snapshot"]["SnapshotName"] == "before-upgrade"
    assert result["snapshot"]["FileSystemId"] == "cfs-abcdefgh"
    assert len(fake.snapshots) == 1
    ops = [c for c, unused in fake.calls]
    assert ops[0] == "DescribeCfsSnapshots"
    assert "CreateCfsSnapshot" in ops


def test_create_check_mode_is_dry_run(monkeypatch):
    fake = FakeCfsClient(snapshots=[])
    _make_module(monkeypatch, fake)
    _base(_ansible_check_mode=True, state="present", file_system_id="cfs-abcdefgh", name="before-upgrade")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert fake.snapshots == []
    assert "CreateCfsSnapshot" not in [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# existing-snapshot flows
# ---------------------------------------------------------------------------


def test_existing_snapshot_no_drift_is_idempotent(monkeypatch):
    fake = FakeCfsClient(snapshots=[_snapshot()])
    _make_module(monkeypatch, fake)
    _base(state="present", snapshot_id="snap-cfs-1001", file_system_id="cfs-abcdefgh", name="before-upgrade", alive_days=30)
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["snapshot"]["SnapshotId"] == "snap-cfs-1001"


def test_update_renames_snapshot(monkeypatch):
    fake = FakeCfsClient(snapshots=[_snapshot()])
    _make_module(monkeypatch, fake)
    _base(state="present", snapshot_id="snap-cfs-1001", file_system_id="cfs-abcdefgh", name="post-upgrade", alive_days=30)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["snapshot"]["SnapshotName"] == "post-upgrade"
    ops = [c for c, unused in fake.calls]
    assert "UpdateCfsSnapshotAttribute" in ops


def test_update_alive_days(monkeypatch):
    fake = FakeCfsClient(snapshots=[_snapshot()])
    _make_module(monkeypatch, fake)
    _base(state="present", snapshot_id="snap-cfs-1001", file_system_id="cfs-abcdefgh", name="before-upgrade", alive_days=7)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["snapshot"]["AliveDay"] == 7


def test_file_system_is_immutable_without_force(monkeypatch):
    fake = FakeCfsClient(snapshots=[_snapshot()])
    _make_module(monkeypatch, fake)
    _base(state="present", snapshot_id="snap-cfs-1001", file_system_id="cfs-other123", name="before-upgrade", alive_days=30)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "file_system_id is immutable" in exc.value.args[0]["msg"]


def test_force_replace_recreates_snapshot(monkeypatch):
    fake = FakeCfsClient(snapshots=[_snapshot()])
    _make_module(monkeypatch, fake)
    _base(
        state="present",
        snapshot_id="snap-cfs-1001",
        file_system_id="cfs-other123",
        name="replacement",
        alive_days=30,
        force_replace=True,
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["snapshot"]["FileSystemId"] == "cfs-other123"
    assert result["snapshot"]["SnapshotName"] == "replacement"
    ops = [c for c, unused in fake.calls]
    assert "DeleteCfsSnapshot" in ops
    assert "CreateCfsSnapshot" in ops


# ---------------------------------------------------------------------------
# guards / failure paths
# ---------------------------------------------------------------------------


def test_multiple_matches_fail(monkeypatch):
    fake = FakeCfsClient(snapshots=[_snapshot(), _snapshot(SnapshotId="snap-cfs-2002")])
    _make_module(monkeypatch, fake)
    _base(state="present", file_system_id="cfs-abcdefgh", name="before-upgrade", alive_days=30)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "Multiple CFS snapshots matched" in exc.value.args[0]["msg"]


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeCfsSnapshots(self, request):
            raise Boom("connection dropped")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    _base(state="present", file_system_id="cfs-abcdefgh", name="before-upgrade")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]
