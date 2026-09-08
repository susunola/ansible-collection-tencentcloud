"""Unit tests for the cbs_disk_backup write module (run_module flows).

Drives ``run_module()`` against an in-memory fake CBS client whose create and
delete operations mutate a backup-point store so post-write describes
converge (created backups are born in the NORMAL state).

Scenario matrix:

* absent on a missing backup point (idempotent no-op), identified by
  ``disk_backup_id`` or by ``disk_id``/``name``
* absent with a matching backup point (check-mode dry run, real delete)
* creation when missing (disk_id/name required guard, happy path with and
  without waiting, check mode)
* no-op when the matching backup point is identical
* immutable disk_id/name drift, with and without ``force_replace``
* the multiple-match guard and the blanket SDK failure path
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import cbs_disk_backup as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

DISK = "disk-8b0a1c2d"

BACKUP = {
    "DiskBackupId": "bk-8b0a1c2d",
    "DiskId": DISK,
    "DiskBackupName": "before-upgrade",
    "DiskBackupState": "NORMAL",
}


def _backup(**overrides):
    item = copy.deepcopy(BACKUP)
    item.update(overrides)
    return item


def _id_args(**overrides):
    params = {"disk_backup_id": "bk-8b0a1c2d"}
    params.update(overrides)
    return module_args(**params)


def _name_args(**overrides):
    params = {"disk_id": DISK, "name": "before-upgrade"}
    params.update(overrides)
    return module_args(**params)


class FakeCbsClient(object):
    """In-memory CBS client mutating a small disk-backup store."""

    def __init__(self, backups=None):
        self.backups = [copy.deepcopy(t) for t in (backups or [])]
        self.calls = []
        self._next = 0

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def DescribeDiskBackups(self, request):
        self._record("DescribeDiskBackups", request)
        ids = list(getattr(request, "DiskBackupIds", None) or [])
        if ids:
            matches = [t for t in self.backups if t.get("DiskBackupId") in ids]
        else:
            matches = list(self.backups)
        return SimpleNamespace(
            DiskBackupSet=[FakeResource(t) for t in matches],
            TotalCount=len(matches),
        )

    def CreateDiskBackup(self, request):
        self._record("CreateDiskBackup", request)
        self._next += 1
        item = {
            "DiskBackupId": "bk-new-%03d" % self._next,
            "DiskId": getattr(request, "DiskId", None),
            "DiskBackupName": getattr(request, "DiskBackupName", None),
            "DiskBackupState": "NORMAL",
        }
        self.backups.append(item)
        return SimpleNamespace(DiskBackupId=item["DiskBackupId"], RequestId="req-fake")

    def DeleteDiskBackups(self, request):
        self._record("DeleteDiskBackups", request)
        ids = list(getattr(request, "DiskBackupIds", None) or [])
        self.backups = [t for t in self.backups if t.get("DiskBackupId") not in ids]
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake, models=None):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (models or FakeModels(), SimpleNamespace(CbsClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


# ---------------------------------------------------------------------------
# absent flows
# ---------------------------------------------------------------------------


def test_absent_missing_by_id_is_idempotent(monkeypatch):
    fake = FakeCbsClient(backups=[])
    _make_module(monkeypatch, fake)
    _id_args(state="absent", disk_backup_id="bk-ghost")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["disk_backup"] is None
    assert [c for c, unused in fake.calls] == ["DescribeDiskBackups"]


def test_absent_missing_by_name_is_idempotent(monkeypatch):
    fake = FakeCbsClient(backups=[])
    _make_module(monkeypatch, fake)
    _name_args(state="absent", name="ghost-backup")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["disk_backup"] is None


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeCbsClient(backups=[_backup()])
    _make_module(monkeypatch, fake)
    _id_args(_ansible_check_mode=True, state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["disk_backup"]["DiskBackupId"] == BACKUP["DiskBackupId"]
    assert len(fake.backups) == 1
    assert "DeleteDiskBackups" not in [c for c, unused in fake.calls]


def test_absent_deletes_backup(monkeypatch):
    fake = FakeCbsClient(backups=[_backup()])
    _make_module(monkeypatch, fake)
    _name_args(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["disk_backup"] is None
    assert fake.backups == []
    ops = [c for c, unused in fake.calls]
    assert "DeleteDiskBackups" in ops


# ---------------------------------------------------------------------------
# creation flows
# ---------------------------------------------------------------------------


def test_present_requires_disk_id_and_name(monkeypatch):
    fake = FakeCbsClient(backups=[])
    _make_module(monkeypatch, fake)
    _id_args(state="present")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "disk_id and name are required when state=present" in exc.value.args[0]["msg"]


def test_create_backup(monkeypatch):
    fake = FakeCbsClient(backups=[])
    _make_module(monkeypatch, fake)
    _name_args(state="present", wait=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["disk_backup"]["DiskBackupId"].startswith("bk-new-")
    assert result["disk_backup"]["DiskBackupState"] == "NORMAL"
    assert len(fake.backups) == 1
    ops = [c for c, unused in fake.calls]
    assert ops[0] == "DescribeDiskBackups"
    assert "CreateDiskBackup" in ops


def test_create_backup_without_wait(monkeypatch):
    fake = FakeCbsClient(backups=[])
    _make_module(monkeypatch, fake)
    _name_args(state="present", wait=False)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["disk_backup"]["DiskBackupId"].startswith("bk-new-")


def test_create_check_mode_is_dry_run(monkeypatch):
    fake = FakeCbsClient(backups=[])
    _make_module(monkeypatch, fake)
    _name_args(_ansible_check_mode=True, state="present")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["disk_backup"] is None
    assert fake.backups == []
    assert "CreateDiskBackup" not in [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# existing-backup flows
# ---------------------------------------------------------------------------


def test_existing_backup_no_drift_is_idempotent(monkeypatch):
    fake = FakeCbsClient(backups=[_backup()])
    _make_module(monkeypatch, fake)
    _name_args(state="present")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["disk_backup"]["DiskBackupId"] == BACKUP["DiskBackupId"]
    assert "CreateDiskBackup" not in [c for c, unused in fake.calls]


def test_immutable_drift_requires_force_replace(monkeypatch):
    fake = FakeCbsClient(backups=[_backup()])
    _make_module(monkeypatch, fake)
    _id_args(state="present", disk_id=DISK, name="renamed-backup")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "set force_replace=true to recreate" in payload["msg"]
    assert "DiskBackupName" in payload["immutable_changes"]


def test_force_replace_recreates_backup(monkeypatch):
    fake = FakeCbsClient(backups=[_backup()])
    _make_module(monkeypatch, fake)
    _id_args(state="present", disk_id=DISK, name="renamed-backup", force_replace=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["disk_backup"]["DiskBackupName"] == "renamed-backup"
    assert result["disk_backup"]["DiskBackupId"] != BACKUP["DiskBackupId"]
    ops = [c for c, unused in fake.calls]
    assert "DeleteDiskBackups" in ops
    assert "CreateDiskBackup" in ops


def test_multiple_matches_fail(monkeypatch):
    fake = FakeCbsClient(backups=[_backup(), _backup(DiskBackupId="bk-dup")])
    _make_module(monkeypatch, fake)
    _name_args(state="present")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "Multiple CBS disk backup points matched" in exc.value.args[0]["msg"]


# ---------------------------------------------------------------------------
# failure paths
# ---------------------------------------------------------------------------


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeDiskBackups(self, request):
            raise Boom("connection dropped")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    _name_args(state="present")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]
