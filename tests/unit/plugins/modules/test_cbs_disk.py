"""Unit tests for the cbs_disk write module helpers."""

from __future__ import absolute_import, division, print_function

__metaclass__ = type
from ansible_collections.susunola.tencentcloud.plugins.modules.cbs_disk import (
    build_describe_request,
    find_disk,
    _create,
    _rename,
    _resize,
    _attach,
    _detach,
    _delete,
    _wait_for_state,
)


class FakeFilter(object):
    def __init__(self):
        pass


class FakeRequest(object):
    pass


class FakePlacement(object):
    def __init__(self):
        self.Zone = None


class FakeTag(object):
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)


class FakePrepaid(object):
    def __init__(self):
        self.Period = None


class FakeModels(object):
    Filter = FakeFilter
    DescribeDisksRequest = FakeRequest
    CreateDisksRequest = FakeRequest
    ModifyDiskAttributesRequest = FakeRequest
    ResizeDiskRequest = FakeRequest
    AttachDisksRequest = FakeRequest
    DetachDisksRequest = FakeRequest
    TerminateDisksRequest = FakeRequest
    Placement = FakePlacement
    Tag = FakeTag
    DiskChargePrepaid = FakePrepaid


class FakeDisk(object):
    def __init__(self, disk_id, name, size=50, state="UNATTACHED", instance_id=None):
        self.DiskId = disk_id
        self.DiskName = name
        self.DiskSize = size
        self.DiskState = state
        self.DiskType = "CLOUD_SSD"
        self.DiskChargeType = "POSTPAID_BY_HOUR"
        self.InstanceId = instance_id

    def _serialize(self, allow_none=True):
        return {
            "DiskId": self.DiskId,
            "DiskName": self.DiskName,
            "DiskSize": self.DiskSize,
            "DiskState": self.DiskState,
            "DiskType": self.DiskType,
            "DiskChargeType": self.DiskChargeType,
            "InstanceId": self.InstanceId,
        }


class FakeDescribeResponse(object):
    def __init__(self, disks):
        self.DiskSet = disks
        self.TotalCount = len(disks or [])


class FakeCreateResponse(object):
    def __init__(self, disk_ids):
        self.DiskIdSet = disk_ids


class FakeClient(object):
    def __init__(self, describe_response=None, create_response=None, exc=None):
        self.describe_response = describe_response
        self.create_response = create_response
        self.exc = exc
        self.calls = []

    def DescribeDisks(self, request):
        self.calls.append(("DescribeDisks", request))
        if self.exc:
            raise self.exc
        return self.describe_response

    def CreateDisks(self, request):
        self.calls.append(("CreateDisks", request))
        return self.create_response

    def ModifyDiskAttributes(self, request):
        self.calls.append(("ModifyDiskAttributes", request))

    def ResizeDisk(self, request):
        self.calls.append(("ResizeDisk", request))

    def AttachDisks(self, request):
        self.calls.append(("AttachDisks", request))

    def DetachDisks(self, request):
        self.calls.append(("DetachDisks", request))

    def TerminateDisks(self, request):
        self.calls.append(("TerminateDisks", request))


class FakeModule(object):
    def __init__(self, params=None):
        self.params = params or {"retries": 2, "waiter_delay": 0, "waiter_timeout": 1}

    def sdk_call(self, operation, request):
        return operation(request)

    def fail_json(self, **kwargs):
        raise AssertionError(kwargs.get("msg"))


def test_build_describe_request_by_id():
    request = build_describe_request(FakeModels, "disk-123", None, None)
    assert request.DiskIds == ["disk-123"]
    assert request.Limit == 100
    assert not hasattr(request, "Filters") or request.Filters is None


def test_build_describe_request_by_name_and_zone():
    request = build_describe_request(FakeModels, None, "data-disk", "ap-guangzhou-3")
    names = [f.Name for f in request.Filters]
    assert "disk-name" in names
    assert "zone" in names
    assert not hasattr(request, "DiskIds") or request.DiskIds is None


def test_find_disk_returns_first_match():
    client = FakeClient(FakeDescribeResponse([FakeDisk("disk-1", "data-disk")]))
    module = FakeModule()
    disk = find_disk(module, client, FakeModels, None, "data-disk", "ap-guangzhou-3")
    assert disk["DiskId"] == "disk-1"
    assert len(client.calls) == 1


def test_find_disk_returns_none_when_absent():
    client = FakeClient(FakeDescribeResponse([]))
    module = FakeModule()
    assert find_disk(module, client, FakeModels, "disk-9", None, None) is None


def test_find_disk_handles_none_set():
    client = FakeClient(FakeDescribeResponse(None))
    module = FakeModule()
    assert find_disk(module, client, FakeModels, "disk-9", None, None) is None


def test_create_sends_all_provided_fields():
    client = FakeClient(create_response=FakeCreateResponse(["disk-9"]))
    module = FakeModule()
    disk_id = _create(module, client, FakeModels, {
        "zone": "ap-guangzhou-3",
        "name": "data-disk",
        "disk_type": "CLOUD_SSD",
        "disk_size": 50,
        "charge_type": "POSTPAID_BY_HOUR",
        "prepaid_period_months": None,
        "encrypt": False,
        "snapshot_id": None,
        "tags": {"env": "prod"},
    })
    assert disk_id == "disk-9"
    request = client.calls[-1][1]
    assert request.Placement.Zone == "ap-guangzhou-3"
    assert request.DiskName == "data-disk"
    assert request.DiskType == "CLOUD_SSD"
    assert request.DiskSize == 50
    assert request.DiskChargeType == "POSTPAID_BY_HOUR"
    assert [(t.Key, t.Value) for t in request.Tags] == [("env", "prod")]
    assert not hasattr(request, "DiskChargePrepaid")
    assert not hasattr(request, "Encrypt")
    assert not hasattr(request, "SnapshotId")


def test_create_with_prepaid_period_and_encrypt():
    client = FakeClient(create_response=FakeCreateResponse(["disk-9"]))
    module = FakeModule()
    _create(module, client, FakeModels, {
        "zone": "ap-guangzhou-3",
        "name": "data-disk",
        "disk_type": "CLOUD_SSD",
        "disk_size": 100,
        "charge_type": "PREPAID",
        "prepaid_period_months": 6,
        "encrypt": True,
        "snapshot_id": "snap-1",
        "tags": {},
    })
    request = client.calls[-1][1]
    assert request.DiskChargePrepaid.Period == 6
    assert request.Encrypt is True
    assert request.SnapshotId == "snap-1"


def test_rename_sends_disk_ids_and_name():
    client = FakeClient()
    module = FakeModule()
    _rename(module, client, FakeModels, "disk-1", "renamed")
    request = client.calls[-1][1]
    assert request.DiskIds == ["disk-1"]
    assert request.DiskName == "renamed"


def test_resize_sends_disk_id_and_size():
    client = FakeClient()
    module = FakeModule()
    _resize(module, client, FakeModels, "disk-1", 100)
    request = client.calls[-1][1]
    assert request.DiskId == "disk-1"
    assert request.DiskSize == 100


def test_attach_sends_instance_and_delete_with_instance():
    client = FakeClient()
    module = FakeModule()
    _attach(module, client, FakeModels, "disk-1", "ins-1", True)
    request = client.calls[-1][1]
    assert request.DiskIds == ["disk-1"]
    assert request.InstanceId == "ins-1"
    assert request.DeleteWithInstance is True


def test_attach_omits_delete_with_instance_when_none():
    client = FakeClient()
    module = FakeModule()
    _attach(module, client, FakeModels, "disk-1", "ins-1", None)
    request = client.calls[-1][1]
    assert request.InstanceId == "ins-1"
    assert not hasattr(request, "DeleteWithInstance")


def test_detach_sends_disk_ids_and_instance():
    client = FakeClient()
    module = FakeModule()
    _detach(module, client, FakeModels, "disk-1", "ins-1")
    request = client.calls[-1][1]
    assert request.DiskIds == ["disk-1"]
    assert request.InstanceId == "ins-1"


def test_delete_sends_disk_ids():
    client = FakeClient()
    module = FakeModule()
    _delete(module, client, FakeModels, "disk-1", False)
    request = client.calls[-1][1]
    assert request.DiskIds == ["disk-1"]
    assert not hasattr(request, "DeleteSnapshot")


def test_delete_with_delete_snapshot():
    client = FakeClient()
    module = FakeModule()
    _delete(module, client, FakeModels, "disk-1", True)
    assert client.calls[-1][1].DeleteSnapshot is True


def test_wait_for_state_polls_until_target_reached():
    responses = [
        FakeDescribeResponse([FakeDisk("disk-1", "d", state="ATTACHING")]),
        FakeDescribeResponse([FakeDisk("disk-1", "d", state="ATTACHED")]),
    ]

    class SequenceClient(FakeClient):
        def __init__(self):
            super(SequenceClient, self).__init__()
            self.responses = responses

        def DescribeDisks(self, request):
            self.calls.append(("DescribeDisks", request))
            return self.responses.pop(0)

    client = SequenceClient()
    module = FakeModule()
    disk = _wait_for_state(module, client, FakeModels, "disk-1", ["ATTACHED"])
    assert disk["DiskState"] == "ATTACHED"
    assert len(client.calls) == 2


def test_wait_for_state_fails_when_timed_out():
    client = FakeClient(FakeDescribeResponse([FakeDisk("disk-1", "d", state="ATTACHING")]))
    module = FakeModule({"retries": 2, "waiter_delay": 0, "waiter_timeout": 0})
    try:
        _wait_for_state(module, client, FakeModels, "disk-1", ["ATTACHED"])
        raise AssertionError("expected timeout failure")
    except AssertionError as exc:
        assert "Timed out waiting" in str(exc)
