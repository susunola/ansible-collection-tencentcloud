"""Unit tests for the lighthouse_disk write module (helpers + run_module).

Covers the create / rename / attach / detach / terminate and force-replace
flows of ``plugins/modules/lighthouse_disk.py`` with an in-memory fake
Lighthouse disk client whose write operations mutate the store, so the
module's waiters converge on their first poll. The raw timeout path of
``wait_disk`` is exercised with a patched clock so no test sleeps.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import lighthouse_disk as lhd
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

DISK = {
    "DiskId": "lhdisk-8b0a1c2d",
    "DiskName": "app-data",
    "Zone": "ap-guangzhou-3",
    "DiskSize": 100,
    "DiskType": "CLOUD_SSD",
    "DiskState": "UNATTACHED",
    "LatestOperationState": "SUCCEEDED",
    "Attached": False,
    "InstanceId": None,
}

WRITE_OPS = (
    "CreateDisks",
    "ModifyDisksAttribute",
    "AttachDisks",
    "DetachDisks",
    "TerminateDisks",
)


def _disk(**overrides):
    """Return a disk fixture isolated from the shared DISK constant."""
    disk = copy.deepcopy(DISK)
    disk.update(overrides)
    return disk


def _create_params(**overrides):
    params = {
        "state": "present",
        "disk_id": None,
        "name": "app-data",
        "zone": "ap-guangzhou-3",
        "disk_size": 100,
        "disk_type": "CLOUD_SSD",
        "prepaid_period": 12,
        "renew_flag": "NOTIFY_AND_MANUAL_RENEW",
        "instance_id": None,
        "force_replace": False,
        "force_detach": False,
        "wait": True,
        "waiter_timeout": 120,
        "waiter_delay": 5,
    }
    params.update(overrides)
    return params


class FakeDiskClient(object):
    """In-memory Lighthouse disk client that mutates a small disk store."""

    def __init__(self, disks=None):
        self.disks = [copy.deepcopy(disk) for disk in (disks or [])]
        self.calls = []

    def _record(self, name, request):
        self.calls.append((name, request))
        return request

    def _by_id(self, disk_id):
        return next(disk for disk in self.disks if disk["DiskId"] == disk_id)

    def DescribeDisks(self, request):
        self._record("DescribeDisks", request)
        disks = self.disks
        if getattr(request, "DiskIds", None):
            wanted = set(request.DiskIds)
            disks = [disk for disk in disks if disk["DiskId"] in wanted]
        elif getattr(request, "Filters", None):
            wanted = set(request.Filters[0].Values)
            disks = [disk for disk in disks if disk.get("DiskName") in wanted]
        return SimpleNamespace(
            DiskSet=[FakeResource(dict(disk)) for disk in disks],
            TotalCount=len(disks),
        )

    def CreateDisks(self, request):
        self._record("CreateDisks", request)
        disk_id = "lhdisk-new-%d" % (len(self.disks) + 1)
        self.disks.append(
            {
                "DiskId": disk_id,
                "DiskName": request.DiskName,
                "Zone": request.Zone,
                "DiskSize": request.DiskSize,
                "DiskType": request.DiskType,
                "DiskState": "UNATTACHED",
                "LatestOperationState": "SUCCEEDED",
                "Attached": False,
                "InstanceId": None,
            }
        )
        return SimpleNamespace(DiskIdSet=[disk_id])

    def ModifyDisksAttribute(self, request):
        self._record("ModifyDisksAttribute", request)
        for disk_id in request.DiskIds:
            self._by_id(disk_id)["DiskName"] = request.DiskName
        return SimpleNamespace()

    def AttachDisks(self, request):
        self._record("AttachDisks", request)
        for disk_id in request.DiskIds:
            disk = self._by_id(disk_id)
            disk["InstanceId"] = request.InstanceId
            disk["Attached"] = True
            disk["DiskState"] = "ATTACHED"
        return SimpleNamespace()

    def DetachDisks(self, request):
        self._record("DetachDisks", request)
        for disk_id in request.DiskIds:
            disk = self._by_id(disk_id)
            disk["InstanceId"] = None
            disk["Attached"] = False
            disk["DiskState"] = "UNATTACHED"
        return SimpleNamespace()

    def TerminateDisks(self, request):
        self._record("TerminateDisks", request)
        removed = set(request.DiskIds)
        self.disks = [disk for disk in self.disks if disk["DiskId"] not in removed]
        return SimpleNamespace()


class FakeModule(object):
    """Minimal stand-in for helpers that need sdk_call / fail_json."""

    def __init__(self, params=None):
        self.params = params or _create_params()
        self.sdk_calls = []

    def sdk_call(self, operation, request):
        self.sdk_calls.append((operation, request))
        return operation(request)

    def fail_json(self, **kwargs):
        raise AnsibleFailJson(kwargs)


@pytest.fixture
def client(monkeypatch):
    fake = FakeDiskClient()
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(
        lhd,
        "_load",
        lambda: (FakeModels(), SimpleNamespace(LighthouseClient=object)),
    )
    monkeypatch.setattr(
        TencentCloudModule,
        "create_client",
        lambda self, client_class, endpoint: fake,
    )
    return fake


# ---------------------------------------------------------------------------
# Helper-level tests
# ---------------------------------------------------------------------------


def test_describe_request_filters_by_disk_id():
    request = lhd.describe_request(FakeModels(), {"disk_id": "lhdisk-1"}, offset=0)
    assert request.DiskIds == ["lhdisk-1"]
    assert request.Offset == 0
    assert request.Limit == 100
    assert not hasattr(request, "Filters") or request.Filters is None


def test_describe_request_filters_by_name():
    request = lhd.describe_request(FakeModels(), {"disk_id": None, "name": "app-data"})
    assert request.Filters[0].Name == "disk-name"
    assert request.Filters[0].Values == ["app-data"]
    assert not hasattr(request, "DiskIds") or request.DiskIds is None


def test_describe_request_without_lookup_has_no_filters():
    request = lhd.describe_request(FakeModels(), {"disk_id": None, "name": None})
    assert request.Offset == 0
    assert not hasattr(request, "DiskIds")
    assert not hasattr(request, "Filters")


def test_create_request_sets_fields_and_charge_prepaid():
    request = lhd.create_request(FakeModels(), _create_params())
    assert request.Zone == "ap-guangzhou-3"
    assert request.DiskSize == 100
    assert request.DiskType == "CLOUD_SSD"
    assert request.DiskName == "app-data"
    assert request.DiskCount == 1
    assert request.DiskChargePrepaid.Period == 12
    assert request.DiskChargePrepaid.RenewFlag == "NOTIFY_AND_MANUAL_RENEW"


def test_update_request_renames_disk():
    request = lhd.update_request(FakeModels(), "lhdisk-1", "new-name")
    assert request.DiskIds == ["lhdisk-1"]
    assert request.DiskName == "new-name"


def test_attach_request_sets_renew_flag():
    request = lhd.attach_request(FakeModels(), "lhdisk-1", "lhins-9", "NOTIFY_AND_AUTO_RENEW")
    assert request.DiskIds == ["lhdisk-1"]
    assert request.InstanceId == "lhins-9"
    assert request.RenewFlag == "NOTIFY_AND_AUTO_RENEW"


def test_detach_request_sets_disk_ids():
    request = lhd.detach_request(FakeModels(), "lhdisk-1")
    assert request.DiskIds == ["lhdisk-1"]


def test_delete_request_uses_terminate():
    request = lhd.delete_request(FakeModels(), "lhdisk-1")
    assert request.DiskIds == ["lhdisk-1"]


def test_find_returns_single_disk():
    module = FakeModule()
    client = FakeDiskClient(disks=[_disk()])
    found = lhd.find(module, client, FakeModels(), _create_params(disk_id="lhdisk-8b0a1c2d"))
    assert found["DiskId"] == "lhdisk-8b0a1c2d"
    assert found["DiskState"] == "UNATTACHED"


def test_find_missing_returns_none():
    module = FakeModule()
    client = FakeDiskClient()
    assert lhd.find(module, client, FakeModels(), _create_params(disk_id="lhdisk-9")) is None


def test_find_multiple_matches_fails():
    module = FakeModule()
    client = FakeDiskClient(disks=[_disk(), _disk(DiskId="lhdisk-2")])
    with pytest.raises(AnsibleFailJson) as exc:
        lhd.find(module, client, FakeModels(), _create_params(name="app-data"))
    assert "Multiple Lighthouse disks matched" in exc.value.args[0]["msg"]


def test_wait_disk_returns_when_converged():
    module = FakeModule()
    client = FakeDiskClient(disks=[_disk()])
    current = lhd.wait_disk(module, client, FakeModels(), _create_params(), {"UNATTACHED"})
    assert current["DiskId"] == "lhdisk-8b0a1c2d"


def test_wait_disk_absent_returns_none_when_gone():
    module = FakeModule()
    client = FakeDiskClient()
    assert lhd.wait_disk(module, client, FakeModels(), _create_params(), set(), absent=True) is None


def test_wait_disk_fails_on_failed_operation():
    module = FakeModule()
    client = FakeDiskClient(disks=[_disk(DiskState="CREATING", LatestOperationState="FAILED")])
    with pytest.raises(AnsibleFailJson) as exc:
        lhd.wait_disk(module, client, FakeModels(), _create_params(), {"UNATTACHED"})
    assert "operation failed" in exc.value.args[0]["msg"]


def test_wait_disk_times_out_with_patched_clock(monkeypatch):
    module = FakeModule()
    client = FakeDiskClient(disks=[_disk(DiskState="CREATING")])
    ticks = iter([1000.0, 2000.0])
    monkeypatch.setattr(lhd.time, "time", lambda: next(ticks))
    monkeypatch.setattr(lhd.time, "sleep", lambda *args, **kwargs: None)
    with pytest.raises(AnsibleFailJson) as exc:
        lhd.wait_disk(module, client, FakeModels(), _create_params(), {"UNATTACHED"})
    assert "Timed out" in exc.value.args[0]["msg"]


# ---------------------------------------------------------------------------
# run_module main-path tests
# ---------------------------------------------------------------------------


def test_disk_id_or_name_required(client):
    module_args()
    with pytest.raises(AnsibleFailJson) as exc:
        run(lhd.run_module)
    assert "required" in exc.value.args[0]["msg"]


def test_absent_missing_disk_is_unchanged(client):
    module_args(state="absent", name="app-data")
    result = run(lhd.run_module)
    assert result["changed"] is False
    assert result["disk"] is None
    assert not any(name in WRITE_OPS for name, request in client.calls)


def test_absent_deletes_unattached_disk(client):
    client.disks = [_disk()]
    module_args(state="absent", disk_id="lhdisk-8b0a1c2d")
    result = run(lhd.run_module)
    assert result["changed"] is True
    assert any(name == "TerminateDisks" for name, request in client.calls)
    assert client.disks == []


def test_absent_attached_requires_force_detach(client):
    client.disks = [_disk(Attached=True, InstanceId="lhins-9", DiskState="ATTACHED")]
    module_args(state="absent", disk_id="lhdisk-8b0a1c2d")
    with pytest.raises(AnsibleFailJson) as exc:
        run(lhd.run_module)
    assert "force_detach=true before deletion" in exc.value.args[0]["msg"]
    assert not any(name in WRITE_OPS for name, request in client.calls)


def test_absent_detaches_then_terminates_attached_disk(client):
    client.disks = [_disk(Attached=True, InstanceId="lhins-9", DiskState="ATTACHED")]
    module_args(state="absent", disk_id="lhdisk-8b0a1c2d", force_detach=True)
    result = run(lhd.run_module)
    assert result["changed"] is True
    call_names = [name for name, request in client.calls if name in WRITE_OPS]
    assert call_names == ["DetachDisks", "TerminateDisks"]
    assert client.disks == []


def test_check_mode_absent_makes_no_writes(client):
    client.disks = [_disk(Attached=True, InstanceId="lhins-9", DiskState="ATTACHED")]
    module_args(state="absent", disk_id="lhdisk-8b0a1c2d", force_detach=True, _ansible_check_mode=True)
    result = run(lhd.run_module)
    assert result["changed"] is True
    assert result["disk"]["DiskId"] == "lhdisk-8b0a1c2d"
    assert not any(name in WRITE_OPS for name, request in client.calls)


def test_present_create_requires_fields(client):
    module_args(state="present", disk_id="lhdisk-missing")
    with pytest.raises(AnsibleFailJson) as exc:
        run(lhd.run_module)
    payload = exc.value.args[0]
    assert "Required for disk creation" in payload["msg"]
    assert "zone" in payload["msg"]
    assert "disk_size" in payload["msg"]


def test_present_creates_disk(client):
    module_args(state="present", name="app-data", zone="ap-guangzhou-3", disk_size=100, disk_type="CLOUD_SSD", prepaid_period=12)
    result = run(lhd.run_module)
    assert result["changed"] is True
    assert any(name == "CreateDisks" for name, request in client.calls)
    assert len(client.disks) == 1
    assert client.disks[0]["DiskId"] == "lhdisk-new-1"
    assert result["disk"]["DiskId"] == "lhdisk-new-1"
    assert result["disk"]["DiskState"] == "UNATTACHED"


def test_present_creates_and_attaches_disk(client):
    module_args(state="present", name="app-data", zone="ap-guangzhou-3", disk_size=100, disk_type="CLOUD_SSD", prepaid_period=12, instance_id="lhins-9")
    result = run(lhd.run_module)
    assert result["changed"] is True
    call_names = [name for name, request in client.calls if name in WRITE_OPS]
    assert "CreateDisks" in call_names
    assert "AttachDisks" in call_names
    assert result["disk"]["InstanceId"] == "lhins-9"
    assert result["disk"]["Attached"] is True


def test_present_creates_without_wait(client):
    module_args(state="present", name="app-data", zone="ap-guangzhou-3", disk_size=100, disk_type="CLOUD_SSD", prepaid_period=12, wait=False)
    result = run(lhd.run_module)
    assert result["changed"] is True
    assert result["disk"]["DiskState"] == "UNATTACHED"


def test_check_mode_present_create_makes_no_writes(client):
    module_args(state="present", name="app-data", zone="ap-guangzhou-3", disk_size=100, disk_type="CLOUD_SSD", prepaid_period=12, _ansible_check_mode=True)
    result = run(lhd.run_module)
    assert result["changed"] is True
    assert result["diff"]["after"]["Zone"] == "ap-guangzhou-3"
    assert result["disk"] is None
    assert not any(name in WRITE_OPS for name, request in client.calls)


def test_present_matching_disk_is_unchanged(client):
    client.disks = [_disk()]
    module_args(state="present", name="app-data", zone="ap-guangzhou-3", disk_size=100, disk_type="CLOUD_SSD", prepaid_period=12)
    result = run(lhd.run_module)
    assert result["changed"] is False
    assert not any(name in WRITE_OPS for name, request in client.calls)


def test_present_immutable_drift_without_force_replace_fails(client):
    client.disks = [_disk()]
    module_args(state="present", disk_id="lhdisk-8b0a1c2d", zone="ap-guangzhou-2", disk_size=100, disk_type="CLOUD_SSD", prepaid_period=12)
    with pytest.raises(AnsibleFailJson) as exc:
        run(lhd.run_module)
    assert "Immutable disk attributes differ" in exc.value.args[0]["msg"]
    assert "force_replace=true" in exc.value.args[0]["msg"]


def test_present_force_replace_recreates_disk(client):
    client.disks = [_disk()]
    module_args(
        state="present",
        disk_id="lhdisk-8b0a1c2d",
        name="app-data",
        zone="ap-guangzhou-2",
        disk_size=100,
        disk_type="CLOUD_SSD",
        prepaid_period=12,
        force_replace=True,
    )
    result = run(lhd.run_module)
    assert result["changed"] is True
    call_names = [name for name, request in client.calls if name in WRITE_OPS]
    assert call_names[0] == "TerminateDisks"
    assert "CreateDisks" in call_names
    assert len(client.disks) == 1
    assert client.disks[0]["Zone"] == "ap-guangzhou-2"
    assert result["disk"]["Zone"] == "ap-guangzhou-2"


def test_present_replace_attached_requires_force_detach(client):
    client.disks = [_disk(Attached=True, InstanceId="lhins-9", DiskState="ATTACHED")]
    module_args(
        state="present",
        disk_id="lhdisk-8b0a1c2d",
        name="app-data",
        zone="ap-guangzhou-2",
        disk_size=100,
        disk_type="CLOUD_SSD",
        prepaid_period=12,
        force_replace=True,
    )
    with pytest.raises(AnsibleFailJson) as exc:
        run(lhd.run_module)
    assert "Disk replacement requires force_detach=true" in exc.value.args[0]["msg"]


def test_present_renames_disk(client):
    client.disks = [_disk()]
    module_args(state="present", disk_id="lhdisk-8b0a1c2d", name="app-data-2")
    result = run(lhd.run_module)
    assert result["changed"] is True
    assert any(name == "ModifyDisksAttribute" for name, request in client.calls)
    assert client.disks[0]["DiskName"] == "app-data-2"
    assert result["disk"]["DiskName"] == "app-data-2"


def test_check_mode_present_rename_makes_no_writes(client):
    client.disks = [_disk()]
    module_args(state="present", disk_id="lhdisk-8b0a1c2d", name="app-data-2", _ansible_check_mode=True)
    result = run(lhd.run_module)
    assert result["changed"] is True
    assert result["diff"]["before"]["DiskName"] == "app-data"
    assert result["diff"]["after"]["DiskName"] == "app-data-2"
    assert not any(name in WRITE_OPS for name, request in client.calls)


def test_present_attaches_detached_disk(client):
    client.disks = [_disk()]
    module_args(state="present", disk_id="lhdisk-8b0a1c2d", name="app-data", instance_id="lhins-9")
    result = run(lhd.run_module)
    assert result["changed"] is True
    assert any(name == "AttachDisks" for name, request in client.calls)
    assert not any(name == "DetachDisks" for name, request in client.calls)
    assert client.disks[0]["InstanceId"] == "lhins-9"
    assert result["disk"]["Attached"] is True


def test_present_detach_requires_force_detach(client):
    client.disks = [_disk(Attached=True, InstanceId="lhins-9", DiskState="ATTACHED")]
    module_args(state="present", disk_id="lhdisk-8b0a1c2d", name="app-data")
    with pytest.raises(AnsibleFailJson) as exc:
        run(lhd.run_module)
    assert "Changing disk attachment requires force_detach=true" in exc.value.args[0]["msg"]


def test_present_detaches_with_force_detach(client):
    client.disks = [_disk(Attached=True, InstanceId="lhins-9", DiskState="ATTACHED")]
    module_args(state="present", disk_id="lhdisk-8b0a1c2d", name="app-data", force_detach=True)
    result = run(lhd.run_module)
    assert result["changed"] is True
    assert any(name == "DetachDisks" for name, request in client.calls)
    assert client.disks[0]["InstanceId"] is None
    assert client.disks[0]["Attached"] is False


def test_present_switches_attachment_with_force_detach(client):
    client.disks = [_disk(Attached=True, InstanceId="lhins-9", DiskState="ATTACHED")]
    module_args(state="present", disk_id="lhdisk-8b0a1c2d", name="app-data", instance_id="lhins-10", force_detach=True)
    result = run(lhd.run_module)
    assert result["changed"] is True
    call_names = [name for name, request in client.calls if name in WRITE_OPS]
    assert call_names == ["DetachDisks", "AttachDisks"]
    assert client.disks[0]["InstanceId"] == "lhins-10"


def test_present_duplicate_name_fails(client):
    client.disks = [_disk(), _disk(DiskId="lhdisk-2")]
    module_args(state="present", name="app-data", zone="ap-guangzhou-3", disk_size=100, disk_type="CLOUD_SSD", prepaid_period=12)
    with pytest.raises(AnsibleFailJson) as exc:
        run(lhd.run_module)
    assert "Multiple Lighthouse disks matched" in exc.value.args[0]["msg"]


def test_sdk_error_on_describe_is_reported(client):
    def boom(request):
        raise RuntimeError("disk api exploded")

    client.DescribeDisks = boom
    module_args(state="present", name="app-data")
    with pytest.raises(AnsibleFailJson) as exc:
        run(lhd.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "disk api exploded" in payload["error"]
