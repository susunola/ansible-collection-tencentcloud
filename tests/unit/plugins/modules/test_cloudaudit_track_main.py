"""Unit tests for the cloudaudit_track write module (run_module flows).

Drives ``run_module()`` end to end against an in-memory fake CloudAudit
client whose write operations mutate the track store so the module's
post-write ``find_track`` refetch and ``wait_for_track`` loops converge
immediately.

Scenario matrix:

* absent on a missing track (idempotent no-op)
* absent with a matching track (check-mode dry run, real delete)
* creation when missing (check mode, happy path with storage delivery)
* no-op when nothing drifts
* drift updates (enabled flag, storage settings)
* validation guard (event_names vs resource_type) and multiple-match guard
* the blanket ``sdk_error_payload`` failure path
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import cloudaudit_track as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

STORAGE = {
    "StorageType": "cls",
    "StorageRegion": "ap-guangzhou",
    "StorageName": "topic-xxxxxxxx",
    "StoragePrefix": "",
    "Compress": 1,
}

TRACK = {
    "TrackId": 1001,
    "Name": "organization-events",
    "Status": 1,
    "ActionType": "*",
    "ResourceType": "*",
    "EventNames": ["*"],
    "TrackForAllMembers": 0,
    "Storage": dict(STORAGE),
}


def _track(**overrides):
    item = dict(TRACK)
    if "Storage" in overrides:
        storage = dict(item["Storage"])
        storage.update(overrides.pop("Storage"))
        item["Storage"] = storage
    item.update(overrides)
    return item


def _base(**overrides):
    params = {}
    params.update(overrides)
    return module_args(**params)


def _storage_params(**overrides):
    params = {
        "storage_type": "cls",
        "storage_region": "ap-guangzhou",
        "storage_name": "topic-xxxxxxxx",
    }
    params.update(overrides)
    return params


def _name_args(**overrides):
    params = {"name": "organization-events"}
    params.update(overrides)
    return module_args(**params)


def _track_id_args(**overrides):
    params = {"track_id": 1001}
    params.update(overrides)
    return module_args(**params)


class FakeCloudauditClient(object):
    """In-memory CloudAudit client mutating a small track store."""

    def __init__(self, tracks=None):
        self.tracks = [dict(t) for t in (tracks or [])]
        self.calls = []
        self._next = 0

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def _storage_dict(self, storage):
        result = {}
        for attr in (
            "StorageType", "StorageRegion", "StorageName", "StoragePrefix",
            "Compress", "StorageAccountId", "StorageAppId",
        ):
            if getattr(storage, attr, None) is not None:
                result[attr] = getattr(storage, attr)
        return result

    def DescribeAuditTracks(self, request):
        self._record("DescribeAuditTracks", request)
        return SimpleNamespace(
            Tracks=[FakeResource(t) for t in self.tracks],
            TotalCount=len(self.tracks),
            RequestId="req-list",
        )

    def DescribeAuditTrack(self, request):
        self._record("DescribeAuditTrack", request)
        for item in self.tracks:
            if item.get("TrackId") == getattr(request, "TrackId", None):
                return FakeResource(dict(item, RequestId="req-detail"))
        raise RuntimeError("track not found")

    def CreateAuditTrack(self, request):
        self._record("CreateAuditTrack", request)
        self._next += 1
        track_id = 2000 + self._next
        item = {
            "TrackId": track_id,
            "Name": getattr(request, "Name", None),
            "Status": getattr(request, "Status", None),
            "ActionType": getattr(request, "ActionType", None),
            "ResourceType": getattr(request, "ResourceType", None),
            "EventNames": list(getattr(request, "EventNames", None) or []),
            "TrackForAllMembers": getattr(request, "TrackForAllMembers", 0),
            "Storage": self._storage_dict(request.Storage),
        }
        self.tracks.append(item)
        return SimpleNamespace(TrackId=track_id, RequestId="req-create")

    def ModifyAuditTrack(self, request):
        self._record("ModifyAuditTrack", request)
        for item in self.tracks:
            if item.get("TrackId") == getattr(request, "TrackId", None):
                item["Name"] = getattr(request, "Name", None)
                item["Status"] = getattr(request, "Status", None)
                item["ActionType"] = getattr(request, "ActionType", None)
                item["ResourceType"] = getattr(request, "ResourceType", None)
                item["EventNames"] = list(getattr(request, "EventNames", None) or [])
                item["TrackForAllMembers"] = getattr(request, "TrackForAllMembers", 0)
                item["Storage"] = self._storage_dict(request.Storage)
        return SimpleNamespace(RequestId="req-modify")

    def DeleteAuditTrack(self, request):
        self._record("DeleteAuditTrack", request)
        self.tracks = [t for t in self.tracks if t.get("TrackId") != getattr(request, "TrackId", None)]
        return SimpleNamespace(RequestId="req-delete")


def _make_module(monkeypatch, fake, models=None):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load_cloudaudit", lambda: (models or FakeModels(), SimpleNamespace(CloudauditClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)


# ---------------------------------------------------------------------------
# absent flows
# ---------------------------------------------------------------------------


def test_absent_missing_track_is_idempotent(monkeypatch):
    fake = FakeCloudauditClient()
    _make_module(monkeypatch, fake)
    _name_args(state="absent", name="ghost-track")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["track"] is None
    assert [c for c, unused in fake.calls] == ["DescribeAuditTracks"]


def test_absent_deletes_track(monkeypatch):
    fake = FakeCloudauditClient(tracks=[_track()])
    _make_module(monkeypatch, fake)
    _track_id_args(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["track"] is None
    assert fake.tracks == []
    ops = [c for c, unused in fake.calls]
    assert "DescribeAuditTracks" in ops
    assert "DeleteAuditTrack" in ops


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeCloudauditClient(tracks=[_track()])
    _make_module(monkeypatch, fake)
    _track_id_args(_ansible_check_mode=True, state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert len(fake.tracks) == 1
    assert "DeleteAuditTrack" not in [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# creation flows
# ---------------------------------------------------------------------------


def test_create_track(monkeypatch):
    fake = FakeCloudauditClient()
    _make_module(monkeypatch, fake)
    _base(state="present", name="organization-events", **_storage_params())
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["track"]["Name"] == "organization-events"
    assert result["track"]["TrackId"] == 2001
    assert len(fake.tracks) == 1
    ops = [c for c, unused in fake.calls]
    assert "CreateAuditTrack" in ops


def test_create_check_mode_is_dry_run(monkeypatch):
    fake = FakeCloudauditClient()
    _make_module(monkeypatch, fake)
    _base(_ansible_check_mode=True, state="present", name="organization-events", **_storage_params())
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["track"] is None
    assert fake.tracks == []
    assert "CreateAuditTrack" not in [c for c, unused in fake.calls]


def test_create_carries_account_and_app_ids(monkeypatch):
    fake = FakeCloudauditClient()
    _make_module(monkeypatch, fake)
    _base(
        state="present",
        name="organization-events",
        storage_type="cos",
        storage_region="ap-guangzhou",
        storage_name="bucket-name",
        storage_account_id="123456789",
        storage_app_id="app-000",
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["track"]["Storage"]["StorageAccountId"] == "123456789"
    assert result["track"]["Storage"]["StorageAppId"] == "app-000"


# ---------------------------------------------------------------------------
# existing-track flows
# ---------------------------------------------------------------------------


def test_existing_track_no_drift_is_idempotent(monkeypatch):
    fake = FakeCloudauditClient(tracks=[_track()])
    _make_module(monkeypatch, fake)
    _name_args(state="present", **_storage_params())
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["track"]["TrackId"] == 1001
    assert "ModifyAuditTrack" not in [c for c, unused in fake.calls]


def test_update_track_enabled_flag(monkeypatch):
    fake = FakeCloudauditClient(tracks=[_track()])
    _make_module(monkeypatch, fake)
    _name_args(state="present", enabled=False, **_storage_params())
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["track"]["Status"] == 0
    assert fake.tracks[0]["Status"] == 0
    assert "ModifyAuditTrack" in [c for c, unused in fake.calls]


def test_update_track_storage(monkeypatch):
    fake = FakeCloudauditClient(tracks=[_track()])
    _make_module(monkeypatch, fake)
    _base(
        state="present",
        name="organization-events",
        storage_type="ckafka",
        storage_region="ap-shanghai",
        storage_name="ckafka-instance",
        action_type="Write",
        event_names=["DescribeClusters", "CreateCluster"],
        resource_type="tdcpg",
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["track"]["Storage"]["StorageType"] == "ckafka"
    assert result["track"]["Storage"]["StorageRegion"] == "ap-shanghai"
    assert result["track"]["ActionType"] == "Write"
    assert "ModifyAuditTrack" in [c for c, unused in fake.calls]


def test_update_check_mode_is_dry_run(monkeypatch):
    fake = FakeCloudauditClient(tracks=[_track()])
    _make_module(monkeypatch, fake)
    _name_args(_ansible_check_mode=True, state="present", enabled=False, **_storage_params())
    result = run(mod.run_module)
    assert result["changed"] is True
    assert fake.tracks[0]["Status"] == 1
    assert "ModifyAuditTrack" not in [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# guards / validation / failure paths
# ---------------------------------------------------------------------------


def test_resource_type_all_requires_wildcard_events(monkeypatch):
    fake = FakeCloudauditClient()
    _make_module(monkeypatch, fake)
    _name_args(state="present", event_names=["DescribeClusters"], **_storage_params())
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "event_names must be ['*']" in exc.value.args[0]["msg"]


def test_multiple_tracks_with_same_name_fail(monkeypatch):
    fake = FakeCloudauditClient(tracks=[_track(), _track(TrackId=1002)])
    _make_module(monkeypatch, fake)
    _name_args(state="present", **_storage_params())
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "Multiple CloudAudit tracks" in exc.value.args[0]["msg"]


def test_present_requires_storage_parameters(monkeypatch):
    fake = FakeCloudauditClient()
    _make_module(monkeypatch, fake)
    _name_args(state="present")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "storage_type" in exc.value.args[0]["msg"]


def test_requires_track_id_or_name(monkeypatch):
    fake = FakeCloudauditClient()
    _make_module(monkeypatch, fake)
    _base(state="absent")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "track_id" in exc.value.args[0]["msg"]


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeAuditTracks(self, request):
            raise Boom("connection dropped")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    _name_args(state="present", **_storage_params())
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]


# ---------------------------------------------------------------------------
# legacy helper regression tests (folded from test_cloudaudit_track.py)
# ---------------------------------------------------------------------------

_PARAMS = {
    "name": "events",
    "enabled": True,
    "action_type": "*",
    "resource_type": "*",
    "event_names": ["*"],
    "track_all_members": False,
    "storage_type": "cls",
    "storage_region": "ap-guangzhou",
    "storage_name": "topic-x",
    "storage_prefix": "",
    "storage_account_id": None,
    "storage_app_id": None,
    "compress": True,
}


def test_request_builders():
    models = FakeModels()
    create = mod.build_create_request(models, _PARAMS)
    assert create.Status == 1
    assert create.Storage.StorageType == "cls"
    update = mod.build_update_request(models, 12, _PARAMS)
    assert update.TrackId == 12
    assert mod.build_delete_request(models, 12).TrackId == 12
    assert mod.build_describe_request(models, 12).TrackId == 12


def test_exact_idempotency_ignores_unmanaged_storage_fields():
    desired = mod._desired(_PARAMS)
    current = dict(desired)
    current["Storage"] = dict(desired["Storage"], StorageAccountId=None)
    assert mod._matches(current, desired)
    current["Status"] = 0
    assert not mod._matches(current, desired)
