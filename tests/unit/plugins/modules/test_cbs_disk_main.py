"""Unit tests for the cbs_disk write module (run_module flows).

Drives ``run_module()`` end to end against an in-memory fake CBS client whose
write operations mutate the disk store so post-write ``find_disk`` refetches
and the state pollers converge immediately.

Scenario matrix:

* absent on a missing disk (idempotent no-op)
* absent with a matching disk (check-mode dry run, real terminate)
* creation when missing (missing-parameter guard, check mode, happy path)
* no-op when nothing drifts
* drift updates (rename, grow-only resize, attach / detach / reattach)
* identity validation guard and the blanket ``sdk_error_payload`` read path
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import cbs_disk as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

DISK = {
    "DiskId": "disk-8b0a1c2d",
    "DiskName": "data-disk",
    "DiskSize": 50,
    "DiskType": "CLOUD_SSD",
    "DiskState": "UNATTACHED",
    "DiskChargeType": "POSTPAID_BY_HOUR",
    "InstanceId": "",
    "Zone": "ap-guangzhou-3",
}


def _disk(**overrides):
    item = dict(DISK)
    item.update(overrides)
    return item


def _base(**overrides):
    params = {}
    params.update(overrides)
    return module_args(**params)


def _disk_id_args(**overrides):
    params = {"disk_id": "disk-8b0a1c2d"}
    params.update(overrides)
    return module_args(**params)


def _name_args(**overrides):
    params = {"name": "data-disk"}
    params.update(overrides)
    return module_args(**params)


class FakeCbsClient(object):
    """In-memory CBS client mutating a small disk store."""

    def __init__(self, disks=None):
        self.disks = [dict(t) for t in (disks or [])]
        self.calls = []
        self._next = 0

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def _rows(self, request):
        if getattr(request, "DiskIds", None):
            return [d for d in self.disks if d.get("DiskId") in request.DiskIds]
        rows = [dict(d) for d in self.disks]
        for filt in getattr(request, "Filters", None) or []:
            name = getattr(filt, "Name", None)
            values = getattr(filt, "Values", None) or []
            if not values:
                continue
            if name == "disk-name":
                rows = [d for d in rows if d.get("DiskName") == values[0]]
            elif name == "zone":
                rows = [d for d in rows if d.get("Zone") == values[0]]
        return rows

    def DescribeDisks(self, request):
        self._record("DescribeDisks", request)
        return SimpleNamespace(DiskSet=[FakeResource(d) for d in self._rows(request)], RequestId="req-describe")

    def CreateDisks(self, request):
        self._record("CreateDisks", request)
        self._next += 1
        disk_id = "disk-new-%03d" % self._next
        item = {
            "DiskId": disk_id,
            "DiskName": getattr(request, "DiskName", None) or "disk-%d" % self._next,
            "DiskSize": getattr(request, "DiskSize", None),
            "DiskType": getattr(request, "DiskType", None),
            "DiskState": "UNATTACHED",
            "DiskChargeType": getattr(request, "DiskChargeType", None),
            "InstanceId": "",
            "Zone": getattr(getattr(request, "Placement", None), "Zone", None),
        }
        self.disks.append(item)
        return SimpleNamespace(DiskIdSet=[disk_id], RequestId="req-create")

    def ModifyDiskAttributes(self, request):
        self._record("ModifyDiskAttributes", request)
        for disk in self.disks:
            if disk.get("DiskId") in list(getattr(request, "DiskIds", None) or []):
                disk["DiskName"] = getattr(request, "DiskName", None)
        return SimpleNamespace(RequestId="req-modify")

    def ResizeDisk(self, request):
        self._record("ResizeDisk", request)
        for disk in self.disks:
            if disk.get("DiskId") == getattr(request, "DiskId", None):
                disk["DiskSize"] = getattr(request, "DiskSize", None)
        return SimpleNamespace(RequestId="req-resize")

    def AttachDisks(self, request):
        self._record("AttachDisks", request)
        for disk in self.disks:
            if disk.get("DiskId") in list(getattr(request, "DiskIds", None) or []):
                disk["InstanceId"] = getattr(request, "InstanceId", None)
                disk["DiskState"] = "ATTACHED"
        return SimpleNamespace(RequestId="req-attach")

    def DetachDisks(self, request):
        self._record("DetachDisks", request)
        for disk in self.disks:
            if disk.get("DiskId") in list(getattr(request, "DiskIds", None) or []):
                disk["InstanceId"] = ""
                disk["DiskState"] = "UNATTACHED"
        return SimpleNamespace(RequestId="req-detach")

    def TerminateDisks(self, request):
        self._record("TerminateDisks", request)
        self.disks = [d for d in self.disks if d.get("DiskId") not in list(getattr(request, "DiskIds", None) or [])]
        return SimpleNamespace(RequestId="req-terminate")


def _make_module(monkeypatch, fake, models=None):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load_cbs", lambda: (models or FakeModels(), SimpleNamespace(CbsClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)


# ---------------------------------------------------------------------------
# absent flows
# ---------------------------------------------------------------------------


def test_absent_missing_disk_is_idempotent(monkeypatch):
    fake = FakeCbsClient()
    _make_module(monkeypatch, fake)
    _name_args(state="absent", zone="ap-guangzhou-3")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert [c for c, unused in fake.calls] == ["DescribeDisks"]


def test_absent_terminates_disk(monkeypatch):
    fake = FakeCbsClient(disks=[_disk()])
    _make_module(monkeypatch, fake)
    _disk_id_args(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["disk"] is None
    assert fake.disks == []
    assert "TerminateDisks" in [c for c, unused in fake.calls]


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeCbsClient(disks=[_disk()])
    _make_module(monkeypatch, fake)
    _disk_id_args(_ansible_check_mode=True, state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert len(fake.disks) == 1
    assert "TerminateDisks" not in [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# creation flows
# ---------------------------------------------------------------------------


def test_create_requires_creation_parameters(monkeypatch):
    fake = FakeCbsClient()
    _make_module(monkeypatch, fake)
    _name_args(state="present", zone="ap-guangzhou-3")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "disk_type" in exc.value.args[0]["msg"]
    assert "disk_size" in exc.value.args[0]["msg"]


def test_create_disk(monkeypatch):
    fake = FakeCbsClient()
    _make_module(monkeypatch, fake)
    _base(
        state="present",
        name="data-disk",
        zone="ap-guangzhou-3",
        disk_type="CLOUD_SSD",
        disk_size=50,
        tags={"env": "prod"},
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["disk"]["DiskName"] == "data-disk"
    assert result["disk"]["DiskId"].startswith("disk-new-")
    assert len(fake.disks) == 1
    assert "CreateDisks" in [c for c, unused in fake.calls]


def test_create_prepaid_disk(monkeypatch):
    fake = FakeCbsClient()
    _make_module(monkeypatch, fake)
    _base(
        state="present",
        name="data-disk",
        zone="ap-guangzhou-3",
        disk_type="CLOUD_PREMIUM",
        disk_size=100,
        charge_type="PREPAID",
        prepaid_period_months=3,
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["disk"]["DiskChargeType"] == "PREPAID"
    assert "CreateDisks" in [c for c, unused in fake.calls]


def test_create_check_mode_is_dry_run(monkeypatch):
    fake = FakeCbsClient()
    _make_module(monkeypatch, fake)
    _name_args(
        _ansible_check_mode=True,
        state="present",
        zone="ap-guangzhou-3",
        disk_type="CLOUD_SSD",
        disk_size=50,
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert fake.disks == []
    assert "CreateDisks" not in [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# existing-disk flows
# ---------------------------------------------------------------------------


def test_existing_disk_no_drift_is_idempotent(monkeypatch):
    fake = FakeCbsClient(disks=[_disk()])
    _make_module(monkeypatch, fake)
    _disk_id_args(state="present", name="data-disk")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["disk"]["DiskId"] == "disk-8b0a1c2d"


def test_rename_disk(monkeypatch):
    fake = FakeCbsClient(disks=[_disk()])
    _make_module(monkeypatch, fake)
    _disk_id_args(state="present", name="renamed-disk")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["disk"]["DiskName"] == "renamed-disk"
    assert fake.disks[0]["DiskName"] == "renamed-disk"
    assert "ModifyDiskAttributes" in [c for c, unused in fake.calls]


def test_resize_disk_grows_capacity(monkeypatch):
    fake = FakeCbsClient(disks=[_disk()])
    _make_module(monkeypatch, fake)
    _disk_id_args(state="present", disk_size=200)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["disk"]["DiskSize"] == 200
    assert "ResizeDisk" in [c for c, unused in fake.calls]


def test_shrink_size_is_ignored(monkeypatch):
    fake = FakeCbsClient(disks=[_disk()])
    _make_module(monkeypatch, fake)
    _disk_id_args(state="present", disk_size=10)
    result = run(mod.run_module)
    assert result["changed"] is False
    assert "ResizeDisk" not in [c for c, unused in fake.calls]


def test_attach_disk_to_instance(monkeypatch):
    fake = FakeCbsClient(disks=[_disk()])
    _make_module(monkeypatch, fake)
    _disk_id_args(state="present", instance_id="ins-attach")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["disk"]["InstanceId"] == "ins-attach"
    assert result["disk"]["DiskState"] == "ATTACHED"
    assert "AttachDisks" in [c for c, unused in fake.calls]


def test_detach_disk(monkeypatch):
    fake = FakeCbsClient(disks=[_disk(InstanceId="ins-1", DiskState="ATTACHED")])
    _make_module(monkeypatch, fake)
    _disk_id_args(state="present", detach=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["disk"]["InstanceId"] == ""
    assert result["disk"]["DiskState"] == "UNATTACHED"
    assert "DetachDisks" in [c for c, unused in fake.calls]


def test_reassign_disk_detaches_then_attaches(monkeypatch):
    fake = FakeCbsClient(disks=[_disk(InstanceId="ins-1", DiskState="ATTACHED")])
    _make_module(monkeypatch, fake)
    _disk_id_args(state="present", instance_id="ins-2")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["disk"]["InstanceId"] == "ins-2"
    ops = [c for c, unused in fake.calls]
    assert "DetachDisks" in ops
    assert "AttachDisks" in ops


def test_update_check_mode_is_dry_run(monkeypatch):
    fake = FakeCbsClient(disks=[_disk()])
    _make_module(monkeypatch, fake)
    _disk_id_args(_ansible_check_mode=True, state="present", disk_size=200)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert fake.disks[0]["DiskSize"] == 50
    assert "ResizeDisk" not in [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# validation / failure paths
# ---------------------------------------------------------------------------


def test_requires_disk_id_or_name(monkeypatch):
    fake = FakeCbsClient()
    _make_module(monkeypatch, fake)
    _base(state="present")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "disk_id or name is required" in exc.value.args[0]["msg"]


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeDisks(self, request):
            raise Boom("connection dropped")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    _disk_id_args(state="present")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]
