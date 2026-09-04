"""Main-path unit tests for the cbs_snapshot module (run_module level)."""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import cbs_snapshot
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

SNAP = {
    "SnapshotId": "snap-1", "SnapshotName": "nightly", "SnapshotState": "NORMAL",
    "DiskId": "disk-1", "DiskSize": 100, "Percent": 100, "IsPermanent": True,
}


class FakeCbsClient(object):
    def __init__(self, snapshots=None, create_state="NORMAL"):
        self.snapshots = list(snapshots or [])
        self.create_state = create_state
        self.CreateSnapshot = MagicMock(side_effect=self._create)
        self.DeleteSnapshots = MagicMock(side_effect=self._delete)

    def DescribeSnapshots(self, request):
        result = self.snapshots
        if getattr(request, "SnapshotIds", None):
            ids = set(request.SnapshotIds)
            result = [s for s in result if s["SnapshotId"] in ids]
        else:
            for filt in getattr(request, "Filters", None) or []:
                if filt.Name == "disk-id":
                    result = [s for s in result if s["DiskId"] == filt.Values[0]]
                elif filt.Name == "snapshot-name":
                    result = [s for s in result if s["SnapshotName"] == filt.Values[0]]
        return SimpleNamespace(
            SnapshotSet=[FakeResource(s) for s in result], TotalCount=len(result))

    def _create(self, request):
        snapshot_id = "snap-%d" % (len(self.snapshots) + 1)
        self.snapshots.append({
            "SnapshotId": snapshot_id, "SnapshotName": request.SnapshotName,
            "DiskId": request.DiskId, "SnapshotState": self.create_state,
            "DiskSize": 100, "Percent": 40, "IsPermanent": True,
        })
        return SimpleNamespace(SnapshotId=snapshot_id)

    def _delete(self, request):
        ids = set(request.SnapshotIds or [])
        self.snapshots = [s for s in self.snapshots if s["SnapshotId"] not in ids]
        return SimpleNamespace()


@pytest.fixture
def client(monkeypatch):
    fake = FakeCbsClient()
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(
        cbs_snapshot, "_load_cbs",
        lambda: (FakeModels(), SimpleNamespace(CbsClient=object)),
    )
    monkeypatch.setattr(
        TencentCloudModule, "create_client",
        lambda self, client_class, endpoint: fake,
    )
    return fake


def test_creates_snapshot_and_waits_for_normal(client):
    module_args(disk_id="disk-1", snapshot_name="nightly")
    result = run(cbs_snapshot.run_module)
    assert result["changed"] is True
    assert result["msg"] == "Snapshot created"
    client.CreateSnapshot.assert_called_once()
    request = client.CreateSnapshot.call_args[0][0]
    assert request.DiskId == "disk-1"
    assert request.SnapshotName == "nightly"
    assert result["snapshot"]["SnapshotState"] == "NORMAL"
    assert result["snapshot"]["SnapshotId"] == "snap-1"


def test_create_with_wait_false_returns_creating(client):
    client.create_state = "CREATING"
    module_args(disk_id="disk-1", snapshot_name="nightly", wait=False)
    result = run(cbs_snapshot.run_module)
    assert result["changed"] is True
    assert result["snapshot"]["SnapshotState"] == "CREATING"


def test_second_run_is_idempotent(client):
    client.snapshots = [dict(SNAP)]
    module_args(disk_id="disk-1", snapshot_name="nightly")
    result = run(cbs_snapshot.run_module)
    assert result["changed"] is False
    assert result["msg"] == "Snapshot is up to date"
    client.CreateSnapshot.assert_not_called()


def test_present_by_snapshot_id_is_idempotent(client):
    client.snapshots = [dict(SNAP)]
    module_args(snapshot_id="snap-1")
    result = run(cbs_snapshot.run_module)
    assert result["changed"] is False
    assert result["snapshot"]["SnapshotId"] == "snap-1"
    client.CreateSnapshot.assert_not_called()


def test_absent_deletes_by_id(client):
    client.snapshots = [dict(SNAP)]
    module_args(snapshot_id="snap-1", state="absent")
    result = run(cbs_snapshot.run_module)
    assert result["changed"] is True
    assert result["msg"] == "Snapshot deleted"
    assert result["snapshot"] is None
    client.DeleteSnapshots.assert_called_once()
    request = client.DeleteSnapshots.call_args[0][0]
    assert request.SnapshotIds == ["snap-1"]


def test_absent_deletes_by_disk_and_name(client):
    client.snapshots = [dict(SNAP)]
    module_args(disk_id="disk-1", snapshot_name="nightly", state="absent")
    result = run(cbs_snapshot.run_module)
    assert result["changed"] is True
    assert [s["SnapshotId"] for s in client.snapshots] == []


def test_absent_already_absent(client):
    module_args(snapshot_id="snap-9", state="absent")
    result = run(cbs_snapshot.run_module)
    assert result["changed"] is False
    assert result["msg"] == "Snapshot already absent"
    client.DeleteSnapshots.assert_not_called()


def test_check_mode_create_does_not_write(client):
    module_args(_ansible_check_mode=True, disk_id="disk-1", snapshot_name="nightly")
    result = run(cbs_snapshot.run_module)
    assert result["changed"] is True
    assert result["msg"] == "Would create snapshot"
    client.CreateSnapshot.assert_not_called()


def test_check_mode_delete_does_not_write(client):
    client.snapshots = [dict(SNAP)]
    module_args(_ansible_check_mode=True, snapshot_id="snap-1", state="absent")
    result = run(cbs_snapshot.run_module)
    assert result["changed"] is True
    assert result["msg"] == "Would delete snapshot"
    client.DeleteSnapshots.assert_not_called()


def test_fails_when_nothing_identifies_snapshot(client):
    module_args()
    with pytest.raises(AnsibleFailJson) as exc:
        run(cbs_snapshot.run_module)
    assert "required" in exc.value.args[0]["msg"]


def test_fails_creating_without_disk_and_name(client):
    module_args(snapshot_id="snap-9")
    with pytest.raises(AnsibleFailJson) as exc:
        run(cbs_snapshot.run_module)
    assert "disk_id and snapshot_name are required" in exc.value.args[0]["msg"]


def test_wait_times_out_when_snapshot_stuck(client):
    client.create_state = "CREATING"
    module_args(disk_id="disk-1", snapshot_name="nightly",
                waiter_timeout=0, waiter_delay=0)
    with pytest.raises(AnsibleFailJson) as exc:
        run(cbs_snapshot.run_module)
    assert "Timed out waiting" in exc.value.args[0]["msg"]
