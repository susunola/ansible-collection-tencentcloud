"""Unit tests for the cfs_file_system write module (run_module flows).

Drives ``run_module()`` end to end against an in-memory fake CFS client whose
create/update/delete operations mutate a file-system store so subsequent
``find_file_system`` calls observe the write.

Scenario matrix:

* absent on a missing file system (idempotent) and the missing-identifier guard
* absent with a live file system (check-mode dry run and the real delete)
* creation when missing (zone/name guards, check mode, network fields)
* no-op when the file system already matches
* drift updates (rename, size limit) through the dedicated update calls
* the inline ``fail_json`` SDK-error envelope path
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import cfs_file_system as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

FS_ID = "cfs-1a2b3c4d"


def _fs(**overrides):
    item = {
        "FileSystemId": FS_ID,
        "Name": "app-share",
        "Zone": "ap-guangzhou-3",
        "Protocol": "NFS",
        "StorageType": "SD",
        "Capacity": 100,
        "SizeLimit": 100,
        "Status": "available",
    }
    item.update(overrides)
    return item


def _base(**overrides):
    return module_args(**overrides)


class FakeCfsClient(object):
    """In-memory CFS (cfs.v20190719) file-system client."""

    def __init__(self, entries=None):
        self.entries = [copy.deepcopy(t) for t in (entries or [])]
        self.calls = []
        self._next = 0

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def DescribeCfsFileSystems(self, request):
        self._record("DescribeCfsFileSystems", request)
        fs_id = getattr(request, "FileSystemId", None)
        page = self.entries
        if fs_id:
            page = [e for e in self.entries if e.get("FileSystemId") == fs_id]
        return SimpleNamespace(
            FileSystems=[FakeResource(e) for e in page],
            TotalCount=len(page),
        )

    def CreateCfsFileSystem(self, request):
        self._record("CreateCfsFileSystem", request)
        self._next += 1
        data = request.__dict__
        entry = {
            "FileSystemId": "cfs-new-%03d" % self._next,
            "Name": data.get("FsName"),
            "Zone": data.get("Zone"),
            "Protocol": data.get("Protocol"),
            "StorageType": data.get("StorageType"),
            "Capacity": data.get("Capacity"),
            "SizeLimit": data.get("Capacity"),
            "Status": "available",
        }
        for key in ("VpcId", "SubnetId", "PGroupId"):
            if data.get(key):
                entry[key] = data[key]
        self.entries.append(entry)
        return SimpleNamespace(FileSystemId=entry["FileSystemId"])

    def UpdateCfsFileSystemName(self, request):
        self._record("UpdateCfsFileSystemName", request)
        for entry in self.entries:
            if entry.get("FileSystemId") == request.FileSystemId:
                entry["Name"] = request.FsName

    def UpdateCfsFileSystemSizeLimit(self, request):
        self._record("UpdateCfsFileSystemSizeLimit", request)
        for entry in self.entries:
            if entry.get("FileSystemId") == request.FileSystemId:
                entry["SizeLimit"] = request.FsLimit

    def DeleteCfsFileSystem(self, request):
        self._record("DeleteCfsFileSystem", request)
        self.entries = [e for e in self.entries if e.get("FileSystemId") != request.FileSystemId]
        return SimpleNamespace()


def _make_module(monkeypatch, fake):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load_cfs", lambda: (FakeModels(), SimpleNamespace(CfsClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


def _ops(fake):
    return [c for c, unused in fake.calls]


def _request(fake, op_name):
    for op, request in fake.calls:
        if op == op_name:
            return request
    return None


# ---------------------------------------------------------------------------
# absent flows
# ---------------------------------------------------------------------------


def test_absent_missing_file_system_is_idempotent(monkeypatch):
    fake = FakeCfsClient()
    _make_module(monkeypatch, fake)
    _base(state="absent", name="app-share")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["msg"] == "File system already absent"
    assert _ops(fake) == ["DescribeCfsFileSystems"]


def test_absent_requires_identifier(monkeypatch):
    fake = FakeCfsClient()
    _make_module(monkeypatch, fake)
    _base(state="absent")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "file_system_id or name is required when state=absent" in exc.value.args[0]["msg"]


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeCfsClient(entries=[_fs()])
    _make_module(monkeypatch, fake)
    _base(_ansible_check_mode=True, state="absent", file_system_id=FS_ID)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["msg"] == "Would delete file system"
    assert len(fake.entries) == 1
    assert "DeleteCfsFileSystem" not in _ops(fake)


def test_absent_deletes_file_system(monkeypatch):
    fake = FakeCfsClient(entries=[_fs()])
    _make_module(monkeypatch, fake)
    _base(state="absent", file_system_id=FS_ID)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["file_system"] is None
    assert fake.entries == []
    assert "DeleteCfsFileSystem" in _ops(fake)
    assert _request(fake, "DeleteCfsFileSystem").FileSystemId == FS_ID


# ---------------------------------------------------------------------------
# creation flows
# ---------------------------------------------------------------------------


def test_create_requires_zone(monkeypatch):
    fake = FakeCfsClient()
    _make_module(monkeypatch, fake)
    _base(state="present", name="app-share")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "zone is required when creating a file system" in exc.value.args[0]["msg"]


def test_create_requires_name(monkeypatch):
    fake = FakeCfsClient()
    _make_module(monkeypatch, fake)
    _base(state="present", zone="ap-guangzhou-3")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "name is required when creating a file system" in exc.value.args[0]["msg"]


def test_present_missing_creates_file_system(monkeypatch):
    fake = FakeCfsClient()
    _make_module(monkeypatch, fake)
    _base(state="present", name="app-share", zone="ap-guangzhou-3", capacity=100)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["msg"] == "File system created"
    created = result["file_system"]
    assert created["Name"] == "app-share"
    assert created["Zone"] == "ap-guangzhou-3"
    assert created["Protocol"] == "NFS"
    assert created["StorageType"] == "SD"
    assert len(fake.entries) == 1
    ops = _ops(fake)
    assert ops[0] == "DescribeCfsFileSystems"
    assert "CreateCfsFileSystem" in ops


def test_create_request_carries_network_fields(monkeypatch):
    fake = FakeCfsClient()
    _make_module(monkeypatch, fake)
    _base(
        state="present",
        name="app-share",
        zone="ap-guangzhou-3",
        protocol="CIFS",
        storage_type="HP",
        capacity=500,
        vpc_id="vpc-abc123",
        subnet_id="subnet-abc123",
        pgroup_id="pgroup-abc123",
    )
    run(mod.run_module)
    request = _request(fake, "CreateCfsFileSystem")
    assert request.Zone == "ap-guangzhou-3"
    assert request.Protocol == "CIFS"
    assert request.StorageType == "HP"
    assert request.Capacity == 500
    assert request.FsName == "app-share"
    assert request.VpcId == "vpc-abc123"
    assert request.SubnetId == "subnet-abc123"
    assert request.PGroupId == "pgroup-abc123"


def test_create_check_mode_is_dry_run(monkeypatch):
    fake = FakeCfsClient()
    _make_module(monkeypatch, fake)
    _base(_ansible_check_mode=True, state="present", name="app-share", zone="ap-guangzhou-3")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["msg"] == "Would create file system"
    assert fake.entries == []
    assert "CreateCfsFileSystem" not in _ops(fake)


# ---------------------------------------------------------------------------
# existing-file-system flows
# ---------------------------------------------------------------------------


def test_present_no_drift_is_noop(monkeypatch):
    fake = FakeCfsClient(entries=[_fs()])
    _make_module(monkeypatch, fake)
    _base(state="present", name="app-share", size_limit=100)
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["msg"] == "File system is up to date"
    assert result["file_system"]["FileSystemId"] == FS_ID
    assert "CreateCfsFileSystem" not in _ops(fake)


def test_rename_existing_file_system(monkeypatch):
    fake = FakeCfsClient(entries=[_fs(Name="old-share")])
    _make_module(monkeypatch, fake)
    _base(state="present", file_system_id=FS_ID, name="app-share")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["file_system"]["Name"] == "app-share"
    assert _request(fake, "UpdateCfsFileSystemName").FsName == "app-share"


def test_update_size_limit(monkeypatch):
    fake = FakeCfsClient(entries=[_fs()])
    _make_module(monkeypatch, fake)
    _base(state="present", file_system_id=FS_ID, size_limit=250)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["file_system"]["SizeLimit"] == 250
    request = _request(fake, "UpdateCfsFileSystemSizeLimit")
    assert request.FileSystemId == FS_ID
    assert request.FsLimit == 250


def test_update_size_limit_by_name_match(monkeypatch):
    fake = FakeCfsClient(entries=[_fs()])
    _make_module(monkeypatch, fake)
    _base(state="present", name="app-share", size_limit=300)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["file_system"]["SizeLimit"] == 300
    ops = _ops(fake)
    assert "UpdateCfsFileSystemName" not in ops
    assert "UpdateCfsFileSystemSizeLimit" in ops
    assert _request(fake, "UpdateCfsFileSystemSizeLimit").FsLimit == 300


def test_update_check_mode_is_dry_run(monkeypatch):
    fake = FakeCfsClient(entries=[_fs(Name="old-share")])
    _make_module(monkeypatch, fake)
    _base(_ansible_check_mode=True, state="present", file_system_id=FS_ID, name="app-share", size_limit=250)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["msg"] == "Would update file system"
    assert fake.entries[0]["Name"] == "old-share"
    assert fake.entries[0]["SizeLimit"] == 100
    assert "UpdateCfsFileSystemName" not in _ops(fake)
    assert "UpdateCfsFileSystemSizeLimit" not in _ops(fake)


# ---------------------------------------------------------------------------
# guards / failure paths
# ---------------------------------------------------------------------------


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        def get_code(self):
            return "UnsupportedOperation"

        def get_request_id(self):
            return "req-xyz"

    class ExplodingClient(object):
        def DescribeCfsFileSystems(self, request):
            raise Boom("connection dropped")

    _make_module(monkeypatch, ExplodingClient())
    _base(state="present", name="app-share", zone="ap-guangzhou-3")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]
    assert payload["error_code"] == "UnsupportedOperation"
    assert payload["request_id"] == "req-xyz"
