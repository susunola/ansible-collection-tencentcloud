"""Unit tests for the lighthouse_snapshot write module (helpers + run_module).

Covers the create / rename / delete / wait flows of
``plugins/modules/lighthouse_snapshot.py`` with an in-memory fake Lighthouse
snapshot client whose write operations mutate the store, so the module's
post-write polls converge on the first attempt. The raw timeout path of
``wait_normal`` is exercised with a patched clock so no test sleeps.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
import itertools
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import lighthouse_snapshot as lls
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

SNAPSHOT = {
    "SnapshotId": "lhsnap-8b0a1c2d",
    "SnapshotName": "before-upgrade",
    "SnapshotState": "NORMAL",
    "LatestOperationState": "SUCCEEDED",
    "InstanceId": "lhins-8b0a1c2d",
}

WRITE_OPS = (
    "CreateInstanceSnapshot",
    "ModifySnapshotAttribute",
    "DeleteSnapshots",
)


def _snapshot(**overrides):
    """Return a snapshot fixture isolated from the shared SNAPSHOT constant."""
    snapshot = copy.deepcopy(SNAPSHOT)
    snapshot.update(overrides)
    return snapshot


def _params(**overrides):
    params = {
        "state": "present",
        "snapshot_id": None,
        "instance_id": "lhins-8b0a1c2d",
        "name": "before-upgrade",
        "wait": True,
        "waiter_timeout": 120,
        "waiter_delay": 5,
    }
    params.update(overrides)
    return params


class FakeSnapshotClient(object):
    """In-memory Lighthouse snapshot client that mutates a small store."""

    def __init__(self, snapshots=None):
        self.snapshots = [copy.deepcopy(s) for s in (snapshots or [])]
        self.calls = []

    def _record(self, name, request):
        self.calls.append((name, request))
        return request

    def DescribeSnapshots(self, request):
        self._record("DescribeSnapshots", request)
        snaps = self.snapshots
        if getattr(request, "SnapshotIds", None):
            wanted = set(request.SnapshotIds)
            snaps = [s for s in snaps if s["SnapshotId"] in wanted]
        elif getattr(request, "Filters", None):
            by_instance = next((f.Values[0] for f in request.Filters if f.Name == "instance-id"), None)
            by_name = next((f.Values[0] for f in request.Filters if f.Name == "snapshot-name"), None)
            if by_instance:
                snaps = [s for s in snaps if s["InstanceId"] == by_instance]
            if by_name:
                snaps = [s for s in snaps if s["SnapshotName"] == by_name]
        offset = request.Offset or 0
        limit = request.Limit or len(snaps)
        page = snaps[offset:offset + limit]
        return SimpleNamespace(
            SnapshotSet=[FakeResource(dict(s)) for s in page],
            TotalCount=len(snaps),
        )

    def CreateInstanceSnapshot(self, request):
        self._record("CreateInstanceSnapshot", request)
        snapshot_id = "lhsnap-new-%d" % (len(self.snapshots) + 1)
        self.snapshots.append(
            {
                "SnapshotId": snapshot_id,
                "SnapshotName": request.SnapshotName,
                "SnapshotState": "NORMAL",
                "LatestOperationState": "SUCCEEDED",
                "InstanceId": request.InstanceId,
            }
        )
        return SimpleNamespace(SnapshotId=snapshot_id)

    def ModifySnapshotAttribute(self, request):
        self._record("ModifySnapshotAttribute", request)
        for snapshot in self.snapshots:
            if snapshot["SnapshotId"] == request.SnapshotId:
                snapshot["SnapshotName"] = request.SnapshotName
        return SimpleNamespace()

    def DeleteSnapshots(self, request):
        self._record("DeleteSnapshots", request)
        removed = set(request.SnapshotIds)
        self.snapshots = [s for s in self.snapshots if s["SnapshotId"] not in removed]
        return SimpleNamespace()


class FakeModule(object):
    """Minimal stand-in for helpers that need sdk_call / fail_json."""

    def __init__(self, params=None):
        self.params = params or _params()
        self.sdk_calls = []

    def sdk_call(self, operation, request):
        self.sdk_calls.append((operation, request))
        return operation(request)

    def fail_json(self, **kwargs):
        raise AnsibleFailJson(kwargs)


@pytest.fixture
def client(monkeypatch):
    fake = FakeSnapshotClient()
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(
        lls,
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


def test_describe_request_filters_by_snapshot_id():
    request = lls.describe_request(FakeModels(), _params(snapshot_id="lhsnap-1"), offset=0)
    assert request.SnapshotIds == ["lhsnap-1"]
    assert request.Offset == 0
    assert request.Limit == 100
    assert not hasattr(request, "Filters") or request.Filters is None


def test_describe_request_filters_by_instance_and_name():
    request = lls.describe_request(FakeModels(), _params(snapshot_id=None), offset=10)
    assert request.Offset == 10
    assert not hasattr(request, "SnapshotIds") or request.SnapshotIds is None
    assert [(f.Name, f.Values) for f in request.Filters] == [
        ("instance-id", ["lhins-8b0a1c2d"]),
        ("snapshot-name", ["before-upgrade"]),
    ]


def test_describe_request_omits_empty_filters():
    request = lls.describe_request(FakeModels(), _params(snapshot_id=None, instance_id=None, name=None))
    assert not hasattr(request, "SnapshotIds")
    assert not hasattr(request, "Filters")


def test_create_request_sets_instance_and_name():
    request = lls.create_request(FakeModels(), _params())
    assert request.InstanceId == "lhins-8b0a1c2d"
    assert request.SnapshotName == "before-upgrade"


def test_update_request_sets_snapshot_id_and_name():
    request = lls.update_request(FakeModels(), "lhsnap-1", "renamed")
    assert request.SnapshotId == "lhsnap-1"
    assert request.SnapshotName == "renamed"


def test_delete_request_sets_snapshot_ids():
    request = lls.delete_request(FakeModels(), "lhsnap-1")
    assert request.SnapshotIds == ["lhsnap-1"]


def test_find_returns_single_snapshot_by_id():
    module = FakeModule()
    client = FakeSnapshotClient(snapshots=[_snapshot(), _snapshot(SnapshotId="lhsnap-2", SnapshotName="other")])
    found = lls.find(module, client, FakeModels(), _params(snapshot_id="lhsnap-8b0a1c2d"))
    assert found["SnapshotId"] == "lhsnap-8b0a1c2d"
    assert found["SnapshotState"] == "NORMAL"


def test_find_returns_single_snapshot_by_instance_and_name():
    module = FakeModule()
    client = FakeSnapshotClient(snapshots=[_snapshot()])
    found = lls.find(module, client, FakeModels(), _params(snapshot_id=None))
    assert found["SnapshotId"] == "lhsnap-8b0a1c2d"


def test_find_missing_returns_none():
    module = FakeModule()
    client = FakeSnapshotClient()
    assert lls.find(module, client, FakeModels(), _params(snapshot_id="lhsnap-9")) is None


def test_find_multiple_matches_fails():
    module = FakeModule()
    client = FakeSnapshotClient(snapshots=[_snapshot(), _snapshot(SnapshotId="lhsnap-2")])
    with pytest.raises(AnsibleFailJson) as exc:
        lls.find(module, client, FakeModels(), _params(snapshot_id=None))
    assert "Multiple Lighthouse snapshots matched" in exc.value.args[0]["msg"]


def test_find_paginates_across_pages_before_failing():
    module = FakeModule()
    snapshots = [_snapshot(SnapshotId="lhsnap-%03d" % i, SnapshotName="dupe") for i in range(101)]
    client = FakeSnapshotClient(snapshots=snapshots)
    with pytest.raises(AnsibleFailJson) as exc:
        lls.find(module, client, FakeModels(), _params(snapshot_id=None, name="dupe"))
    assert "Multiple Lighthouse snapshots matched" in exc.value.args[0]["msg"]
    offsets = [request.Offset for name, request in client.calls if name == "DescribeSnapshots"]
    assert offsets == [0, 100]


def test_wait_normal_returns_when_converged():
    module = FakeModule()
    client = FakeSnapshotClient(snapshots=[_snapshot()])
    current = lls.wait_normal(module, client, FakeModels(), _params(snapshot_id="lhsnap-8b0a1c2d"))
    assert current["SnapshotId"] == "lhsnap-8b0a1c2d"


def test_wait_normal_polls_until_normal_with_patched_clock(monkeypatch):
    module = FakeModule()
    client = FakeSnapshotClient(snapshots=[_snapshot(SnapshotState="CREATING")])
    ticks = iter([1000.0, 1005.0, 1006.0])
    monkeypatch.setattr(lls.time, "time", lambda: next(ticks))
    sleeps = []
    monkeypatch.setattr(lls.time, "sleep", lambda *args, **kwargs: sleeps.append(args))

    real_describe = client.DescribeSnapshots

    def describe_advances_state(request):
        result = real_describe(request)
        client.snapshots[0]["SnapshotState"] = "NORMAL"
        return result

    client.DescribeSnapshots = describe_advances_state
    current = lls.wait_normal(module, client, FakeModels(), _params(snapshot_id="lhsnap-8b0a1c2d"))
    assert current["SnapshotState"] == "NORMAL"
    assert sleeps == [(5,)]


def test_wait_normal_fails_on_failed_operation():
    module = FakeModule()
    client = FakeSnapshotClient(snapshots=[_snapshot(SnapshotState="CREATING", LatestOperationState="FAILED")])
    with pytest.raises(AnsibleFailJson) as exc:
        lls.wait_normal(module, client, FakeModels(), _params(snapshot_id="lhsnap-8b0a1c2d"))
    assert "Lighthouse snapshot creation failed" in exc.value.args[0]["msg"]


def test_wait_normal_times_out_with_patched_clock(monkeypatch):
    module = FakeModule()
    client = FakeSnapshotClient(snapshots=[_snapshot(SnapshotState="CREATING")])
    ticks = iter([1000.0, 2000.0])
    monkeypatch.setattr(lls.time, "time", lambda: next(ticks))
    monkeypatch.setattr(lls.time, "sleep", lambda *args, **kwargs: None)
    with pytest.raises(AnsibleFailJson) as exc:
        lls.wait_normal(module, client, FakeModels(), _params(snapshot_id="lhsnap-8b0a1c2d"))
    assert "Timed out waiting for Lighthouse snapshot" in exc.value.args[0]["msg"]


# ---------------------------------------------------------------------------
# run_module main-path tests
# ---------------------------------------------------------------------------


def test_snapshot_id_or_name_required(client):
    module_args()
    with pytest.raises(AnsibleFailJson) as exc:
        run(lls.run_module)
    assert "required" in exc.value.args[0]["msg"]


def test_present_name_without_lookup_target_fails(client):
    module_args(state="present", name="before-upgrade")
    with pytest.raises(AnsibleFailJson) as exc:
        run(lls.run_module)
    assert "name and either snapshot_id or instance_id are required" in exc.value.args[0]["msg"]


def test_absent_name_without_lookup_target_fails(client):
    module_args(state="absent", name="before-upgrade")
    with pytest.raises(AnsibleFailJson) as exc:
        run(lls.run_module)
    assert "instance_id is required with name when state=absent" in exc.value.args[0]["msg"]


def test_absent_missing_snapshot_is_unchanged(client):
    module_args(state="absent", instance_id="lhins-8b0a1c2d", name="missing")
    result = run(lls.run_module)
    assert result["changed"] is False
    assert result["snapshot"] is None
    assert not any(name in WRITE_OPS for name, request in client.calls)


def test_absent_deletes_snapshot_by_id(client):
    client.snapshots = [_snapshot()]
    module_args(state="absent", snapshot_id="lhsnap-8b0a1c2d")
    result = run(lls.run_module)
    assert result["changed"] is True
    assert any(name == "DeleteSnapshots" for name, request in client.calls)
    assert client.snapshots == []


def test_absent_deletes_snapshot_by_instance_and_name(client):
    client.snapshots = [_snapshot()]
    module_args(state="absent", instance_id="lhins-8b0a1c2d", name="before-upgrade")
    result = run(lls.run_module)
    assert result["changed"] is True
    assert any(name == "DeleteSnapshots" for name, request in client.calls)
    assert client.snapshots == []


def test_check_mode_absent_makes_no_writes(client):
    client.snapshots = [_snapshot()]
    module_args(state="absent", snapshot_id="lhsnap-8b0a1c2d", _ansible_check_mode=True)
    result = run(lls.run_module)
    assert result["changed"] is True
    assert result["snapshot"]["SnapshotId"] == "lhsnap-8b0a1c2d"
    assert result["diff"]["before"]["SnapshotName"] == "before-upgrade"
    assert result["diff"]["after"] is None
    assert not any(name in WRITE_OPS for name, request in client.calls)


def test_present_creates_snapshot(client):
    module_args(state="present", instance_id="lhins-8b0a1c2d", name="before-upgrade")
    result = run(lls.run_module)
    assert result["changed"] is True
    assert any(name == "CreateInstanceSnapshot" for name, request in client.calls)
    assert len(client.snapshots) == 1
    assert client.snapshots[0]["SnapshotId"] == "lhsnap-new-1"
    assert result["snapshot"]["SnapshotId"] == "lhsnap-new-1"
    assert result["snapshot"]["SnapshotState"] == "NORMAL"


def test_present_creates_without_wait(client):
    module_args(state="present", instance_id="lhins-8b0a1c2d", name="before-upgrade", wait=False)
    result = run(lls.run_module)
    assert result["changed"] is True
    assert any(name == "CreateInstanceSnapshot" for name, request in client.calls)
    assert result["snapshot"]["SnapshotState"] == "NORMAL"


def test_check_mode_present_create_makes_no_writes(client):
    module_args(state="present", instance_id="lhins-8b0a1c2d", name="before-upgrade", _ansible_check_mode=True)
    result = run(lls.run_module)
    assert result["changed"] is True
    assert result["diff"]["before"] is None
    assert result["diff"]["after"]["SnapshotName"] == "before-upgrade"
    assert result["snapshot"] is None
    assert not any(name in WRITE_OPS for name, request in client.calls)


def test_present_matching_snapshot_is_unchanged(client):
    client.snapshots = [_snapshot()]
    module_args(state="present", instance_id="lhins-8b0a1c2d", name="before-upgrade")
    result = run(lls.run_module)
    assert result["changed"] is False
    assert result["snapshot"]["SnapshotId"] == "lhsnap-8b0a1c2d"
    assert not any(name in WRITE_OPS for name, request in client.calls)


def test_present_renames_snapshot(client):
    client.snapshots = [_snapshot()]
    module_args(state="present", snapshot_id="lhsnap-8b0a1c2d", name="after-upgrade")
    result = run(lls.run_module)
    assert result["changed"] is True
    assert any(name == "ModifySnapshotAttribute" for name, request in client.calls)
    assert client.snapshots[0]["SnapshotName"] == "after-upgrade"
    assert result["snapshot"]["SnapshotName"] == "after-upgrade"


def test_check_mode_present_rename_makes_no_writes(client):
    client.snapshots = [_snapshot()]
    module_args(state="present", snapshot_id="lhsnap-8b0a1c2d", name="after-upgrade", _ansible_check_mode=True)
    result = run(lls.run_module)
    assert result["changed"] is True
    assert result["diff"]["before"]["SnapshotName"] == "before-upgrade"
    assert result["diff"]["after"]["SnapshotName"] == "after-upgrade"
    assert not any(name in WRITE_OPS for name, request in client.calls)


def test_present_rename_waits_and_fails_on_failed_operation(client):
    client.snapshots = [_snapshot(SnapshotState="CREATING", LatestOperationState="FAILED")]
    module_args(state="present", snapshot_id="lhsnap-8b0a1c2d", name="after-upgrade")
    with pytest.raises(AnsibleFailJson) as exc:
        run(lls.run_module)
    assert "Lighthouse snapshot creation failed" in exc.value.args[0]["msg"]


def test_present_wait_times_out_with_patched_clock(client, monkeypatch):
    module_args(state="present", instance_id="lhins-8b0a1c2d", name="before-upgrade")
    # sdk_call (base.py) records call duration against the shared ``time``
    # module, so the ticker must be unbounded rather than a fixed pair.
    ticks = itertools.count(1000.0, 500.0)
    monkeypatch.setattr(lls.time, "time", lambda: next(ticks))
    monkeypatch.setattr(lls.time, "sleep", lambda *args, **kwargs: None)

    def create_stays_pending(request):
        snapshot_id = "lhsnap-new-1"
        client.snapshots.append(
            {
                "SnapshotId": snapshot_id,
                "SnapshotName": request.SnapshotName,
                "SnapshotState": "CREATING",
                "LatestOperationState": "SUCCEEDED",
                "InstanceId": request.InstanceId,
            }
        )
        return SimpleNamespace(SnapshotId=snapshot_id)

    client.CreateInstanceSnapshot = create_stays_pending
    with pytest.raises(AnsibleFailJson) as exc:
        run(lls.run_module)
    assert "Timed out waiting for Lighthouse snapshot" in exc.value.args[0]["msg"]


def test_present_multiple_matches_fails(client):
    client.snapshots = [_snapshot(), _snapshot(SnapshotId="lhsnap-2")]
    module_args(state="present", instance_id="lhins-8b0a1c2d", name="before-upgrade")
    with pytest.raises(AnsibleFailJson) as exc:
        run(lls.run_module)
    assert "Multiple Lighthouse snapshots matched" in exc.value.args[0]["msg"]


def test_sdk_error_on_describe_is_reported(client):
    def boom(request):
        raise RuntimeError("lighthouse api exploded")

    client.DescribeSnapshots = boom
    module_args(state="present", instance_id="lhins-8b0a1c2d", name="before-upgrade")
    with pytest.raises(AnsibleFailJson) as exc:
        run(lls.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "lighthouse api exploded" in payload["error"]
