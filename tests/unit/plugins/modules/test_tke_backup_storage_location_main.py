"""Unit tests for the tke_backup_storage_location write module (run_module flows).

Drives ``run_module()`` against an in-memory fake TKE client whose create /
delete operations mutate a backup-storage-location store so post-write
describes converge immediately.

The API exposes no update: configuration drift on an existing location
fails unless ``force_replace=true``, which deletes and recreates it.

Scenario matrix:

* absent on a missing location (idempotent no-op)
* absent with a matching location (check-mode dry run, real delete)
* creation when missing (happy path, check mode)
* no-op when the location already matches
* immutable drift fails without force_replace and replaces with it
* the required_if guard and the blanket SDK failure path
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import tke_backup_storage_location as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

LOCATION = {
    "Name": "production-backups",
    "StorageRegion": "ap-guangzhou",
    "Bucket": "tke-backup-1250000000",
    "Provider": "tencentcloud",
    "Path": "production/",
}


def _location(**overrides):
    item = copy.deepcopy(LOCATION)
    item.update(overrides)
    return item


def _present_args(**overrides):
    params = {"state": "present", "name": "production-backups", "storage_region": "ap-guangzhou", "bucket": "tke-backup-1250000000", "path": "production/"}
    params.update(overrides)
    return module_args(**params)


class FakeTkeClient(object):
    """In-memory TKE client mutating a small backup-location store."""

    def __init__(self, locations=None):
        self.locations = [copy.deepcopy(t) for t in (locations or [])]
        self.calls = []

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def DescribeBackupStorageLocations(self, request):
        self._record("DescribeBackupStorageLocations", request)
        names = set(getattr(request, "Names", None) or [])
        matches = [t for t in self.locations if t.get("Name") in names]
        return SimpleNamespace(BackupStorageLocationSet=[FakeResource(t) for t in matches])

    def CreateBackupStorageLocation(self, request):
        self._record("CreateBackupStorageLocation", request)
        item = {
            "Name": getattr(request, "Name", None),
            "StorageRegion": getattr(request, "StorageRegion", None),
            "Bucket": getattr(request, "Bucket", None),
            "Provider": getattr(request, "Provider", None) or "tencentcloud",
            "Path": getattr(request, "Path", None) or "",
        }
        self.locations = [t for t in self.locations if t.get("Name") != item["Name"]]
        self.locations.append(item)
        return SimpleNamespace(RequestId="req-fake")

    def DeleteBackupStorageLocation(self, request):
        self._record("DeleteBackupStorageLocation", request)
        name = getattr(request, "Name", None)
        self.locations = [t for t in self.locations if t.get("Name") != name]
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake, models=None):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (models or FakeModels(), SimpleNamespace(TkeClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


# ---------------------------------------------------------------------------
# absent flows
# ---------------------------------------------------------------------------


def test_absent_missing_is_idempotent(monkeypatch):
    fake = FakeTkeClient(locations=[])
    _make_module(monkeypatch, fake)
    module_args(state="absent", name="ghost-location")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["backup_storage_location"] is None
    assert [c for c, unused in fake.calls] == ["DescribeBackupStorageLocations"]


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeTkeClient(locations=[_location()])
    _make_module(monkeypatch, fake)
    module_args(_ansible_check_mode=True, state="absent", name="production-backups")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["backup_storage_location"]["Name"] == "production-backups"
    assert len(fake.locations) == 1
    assert "DeleteBackupStorageLocation" not in [c for c, unused in fake.calls]


def test_absent_deletes_location(monkeypatch):
    fake = FakeTkeClient(locations=[_location()])
    _make_module(monkeypatch, fake)
    module_args(state="absent", name="production-backups")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["backup_storage_location"] is None
    assert fake.locations == []
    assert "DeleteBackupStorageLocation" in [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# creation flows
# ---------------------------------------------------------------------------


def test_present_requires_storage_region_and_bucket(monkeypatch):
    fake = FakeTkeClient(locations=[])
    _make_module(monkeypatch, fake)
    module_args(state="present", name="production-backups")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "storage_region" in exc.value.args[0]["msg"]
    assert "bucket" in exc.value.args[0]["msg"]


def test_create_location(monkeypatch):
    fake = FakeTkeClient(locations=[])
    _make_module(monkeypatch, fake)
    _present_args()
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["backup_storage_location"]["Name"] == "production-backups"
    assert result["backup_storage_location"]["StorageRegion"] == "ap-guangzhou"
    assert result["backup_storage_location"]["Bucket"] == "tke-backup-1250000000"
    assert len(fake.locations) == 1
    ops = [c for c, unused in fake.calls]
    assert ops[0] == "DescribeBackupStorageLocations"
    assert "CreateBackupStorageLocation" in ops
    assert ops[-1] == "DescribeBackupStorageLocations"


def test_create_defaults_provider_and_path(monkeypatch):
    fake = FakeTkeClient(locations=[])
    _make_module(monkeypatch, fake)
    module_args(state="present", name="backups", storage_region="ap-shanghai", bucket="tke-bucket-1")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["backup_storage_location"]["Provider"] == "tencentcloud"
    assert result["backup_storage_location"]["Path"] == ""


def test_create_check_mode_is_dry_run(monkeypatch):
    fake = FakeTkeClient(locations=[])
    _make_module(monkeypatch, fake)
    _present_args(_ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["backup_storage_location"] is None
    assert fake.locations == []
    assert "CreateBackupStorageLocation" not in [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# existing location flows
# ---------------------------------------------------------------------------


def test_existing_no_drift_is_idempotent(monkeypatch):
    fake = FakeTkeClient(locations=[_location()])
    _make_module(monkeypatch, fake)
    _present_args()
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["backup_storage_location"]["Name"] == "production-backups"
    assert not [c for c, unused in fake.calls if c != "DescribeBackupStorageLocations"]


def test_immutable_drift_requires_force_replace(monkeypatch):
    fake = FakeTkeClient(locations=[_location()])
    _make_module(monkeypatch, fake)
    _present_args(bucket="different-bucket")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "set force_replace=true to recreate it" in payload["msg"]
    assert payload["desired"]["Bucket"] == "different-bucket"
    assert len(fake.locations) == 1
    assert "DeleteBackupStorageLocation" not in [c for c, unused in fake.calls]


def test_force_replace_recreates(monkeypatch):
    fake = FakeTkeClient(locations=[_location()])
    _make_module(monkeypatch, fake)
    _present_args(bucket="different-bucket", force_replace=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["backup_storage_location"]["Bucket"] == "different-bucket"
    assert len(fake.locations) == 1
    ops = [c for c, unused in fake.calls]
    assert ops.index("DeleteBackupStorageLocation") < ops.index("CreateBackupStorageLocation")


def test_force_replace_check_mode_is_dry_run(monkeypatch):
    fake = FakeTkeClient(locations=[_location()])
    _make_module(monkeypatch, fake)
    _present_args(_ansible_check_mode=True, bucket="different-bucket", force_replace=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["backup_storage_location"]["Bucket"] == "tke-backup-1250000000"
    assert len(fake.locations) == 1
    assert "DeleteBackupStorageLocation" not in [c for c, unused in fake.calls]
    assert "CreateBackupStorageLocation" not in [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# failure paths
# ---------------------------------------------------------------------------


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeBackupStorageLocations(self, request):
            raise Boom("connection dropped")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    _present_args()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]
