"""Unit tests for the cbs_snapshot write module helpers."""

from __future__ import absolute_import, division, print_function

__metaclass__ = type
from ansible_collections.susunola.tencentcloud.plugins.modules.cbs_snapshot import (
    build_describe_request,
    find_snapshot,
    _create,
    _delete,
    _identify,
    _wait_for_available,
)


class FakeFilter(object):
    def __init__(self):
        self.Name = None
        self.Values = None


class FakeRequest(object):
    pass


class FakeModels(object):
    Filter = FakeFilter
    DescribeSnapshotsRequest = FakeRequest
    CreateSnapshotRequest = FakeRequest
    DeleteSnapshotsRequest = FakeRequest


class FakeSnapshot(object):
    def __init__(self, snapshot_id, name, state="NORMAL", disk_id="disk-1", size=100):
        self.SnapshotId = snapshot_id
        self.SnapshotName = name
        self.SnapshotState = state
        self.DiskId = disk_id
        self.DiskSize = size
        self.Percent = 100 if state == "NORMAL" else 40
        self.IsPermanent = True

    def _serialize(self, allow_none=True):
        return {
            "SnapshotId": self.SnapshotId,
            "SnapshotName": self.SnapshotName,
            "SnapshotState": self.SnapshotState,
            "DiskId": self.DiskId,
            "DiskSize": self.DiskSize,
            "Percent": self.Percent,
            "IsPermanent": self.IsPermanent,
        }


class FakeDescribeResponse(object):
    def __init__(self, snapshots):
        self.SnapshotSet = snapshots
        self.TotalCount = len(snapshots or [])


class FakeCreateResponse(object):
    def __init__(self, snapshot_id):
        self.SnapshotId = snapshot_id


class FakeClient(object):
    def __init__(self, describe_response=None, create_response=None):
        self.describe_response = describe_response
        self.create_response = create_response
        self.calls = []

    def DescribeSnapshots(self, request):
        self.calls.append(("DescribeSnapshots", request))
        return self.describe_response

    def CreateSnapshot(self, request):
        self.calls.append(("CreateSnapshot", request))
        return self.create_response

    def DeleteSnapshots(self, request):
        self.calls.append(("DeleteSnapshots", request))


class FakeModule(object):
    def __init__(self, params=None):
        self.params = params or {"retries": 2, "waiter_delay": 0, "waiter_timeout": 1}

    def sdk_call(self, operation, request):
        return operation(request)

    def fail_json(self, *args, **kwargs):
        if args:
            kwargs["msg"] = args[0]
        kwargs["failed"] = True
        raise SystemExit(kwargs)


def test_build_describe_request_by_ids():
    request = build_describe_request(FakeModels, ["snap-1", "snap-2"], None, None)
    assert request.SnapshotIds == ["snap-1", "snap-2"]
    assert request.Limit == 100
    assert not hasattr(request, "Filters") or request.Filters is None


def test_build_describe_request_by_disk_and_name():
    request = build_describe_request(FakeModels, None, "disk-1", "nightly")
    assert not hasattr(request, "SnapshotIds") or request.SnapshotIds is None
    assert request.OrderField == "CREATE_TIME"
    assert request.Order == "DESC"
    assert {f.Name for f in request.Filters} == {"disk-id", "snapshot-name"}


def test_build_describe_request_by_name_only():
    request = build_describe_request(FakeModels, None, None, "nightly")
    assert [f.Name for f in request.Filters] == ["snapshot-name"]
    assert [f.Values for f in request.Filters] == [["nightly"]]


def test_find_snapshot_returns_first_match():
    client = FakeClient(FakeDescribeResponse([FakeSnapshot("snap-1", "nightly")]))
    module = FakeModule()
    snapshot = find_snapshot(module, client, FakeModels, None, "disk-1", "nightly")
    assert snapshot["SnapshotId"] == "snap-1"
    assert len(client.calls) == 1


def test_find_snapshot_returns_none_when_absent():
    client = FakeClient(FakeDescribeResponse([]))
    module = FakeModule()
    assert find_snapshot(module, client, FakeModels, ["snap-9"], None, None) is None


def test_find_snapshot_handles_none_set():
    client = FakeClient(FakeDescribeResponse(None))
    module = FakeModule()
    assert find_snapshot(module, client, FakeModels, ["snap-9"], None, None) is None


def test_create_sends_disk_and_name():
    client = FakeClient(create_response=FakeCreateResponse("snap-9"))
    module = FakeModule()
    snapshot_id = _create(module, client, FakeModels, "disk-1", "nightly")
    assert snapshot_id == "snap-9"
    request = client.calls[-1][1]
    assert request.DiskId == "disk-1"
    assert request.SnapshotName == "nightly"


def test_delete_sends_snapshot_ids():
    client = FakeClient()
    module = FakeModule()
    _delete(module, client, FakeModels, ["snap-1", "snap-2"])
    request = client.calls[-1][1]
    assert request.SnapshotIds == ["snap-1", "snap-2"]


def test_identify_by_id():
    module = FakeModule()
    ids, disk_id, name = _identify(module, "snap-1", None, None)
    assert ids == ["snap-1"]
    assert disk_id is None
    assert name is None


def test_identify_by_disk_and_name():
    module = FakeModule()
    ids, disk_id, name = _identify(module, None, "disk-1", "nightly")
    assert ids is None
    assert disk_id == "disk-1"
    assert name == "nightly"


def test_identify_fails_when_nothing_given():
    module = FakeModule()
    try:
        _identify(module, None, None, None)
        raise AssertionError("expected failure")
    except SystemExit as exc:
        assert "required" in exc.args[0]["msg"]


def test_identify_fails_when_only_disk_given():
    module = FakeModule()
    try:
        _identify(module, None, "disk-1", None)
        raise AssertionError("expected failure")
    except SystemExit as exc:
        assert "required" in exc.args[0]["msg"]


def test_wait_for_available_polls_until_normal():
    responses = [
        FakeDescribeResponse([FakeSnapshot("snap-1", "nightly", state="CREATING")]),
        FakeDescribeResponse([FakeSnapshot("snap-1", "nightly", state="NORMAL")]),
    ]

    class SequenceClient(FakeClient):
        def __init__(self):
            super(SequenceClient, self).__init__()
            self.responses = responses

        def DescribeSnapshots(self, request):
            self.calls.append(("DescribeSnapshots", request))
            return self.responses.pop(0)

    client = SequenceClient()
    module = FakeModule()
    snapshot = _wait_for_available(module, client, FakeModels, "snap-1")
    assert snapshot["SnapshotState"] == "NORMAL"
    assert len(client.calls) == 2


def test_wait_for_available_fails_when_timed_out():
    client = FakeClient(FakeDescribeResponse(
        [FakeSnapshot("snap-1", "nightly", state="CREATING")]))
    module = FakeModule({"retries": 2, "waiter_delay": 0, "waiter_timeout": 0})
    try:
        _wait_for_available(module, client, FakeModels, "snap-1")
        raise AssertionError("expected timeout failure")
    except SystemExit as exc:
        assert "Timed out waiting" in exc.args[0]["msg"]
        assert exc.args[0]["snapshot"]["SnapshotState"] == "CREATING"
