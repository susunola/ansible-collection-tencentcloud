"""Tests for the Lighthouse identity writers: lighthouse_key_pair and lighthouse_snapshot.

Both modules manage one named object in a Lighthouse region and both resolve
the SDK through ``_load()``: a key pair (imported public key plus its exact
instance associations) and a snapshot (created from an instance, renamed or
deleted, and waited for).

The two request-shape tests came first and stay as they were. Everything below
drives ``run_module()`` against an in-memory fake ``LighthouseClient`` whose
writes mutate the store, so the association/import/replace decisions and the
snapshot wait are observable. The fixtures carry the fields the API really
returns -- ``KeyPair`` (``KeyId``/``KeyName``/``PublicKey``/
``AssociatedInstanceIds``/``AssociatedInstanceSet``/``CreatedTime``) and
``Snapshot`` (``SnapshotId``/``DiskUsage``/``SnapshotName``/``SnapshotState``/
``Percent``/``LatestOperation``/``LatestOperationState``/``CreatedTime``).
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import lighthouse_key_pair, lighthouse_snapshot
from ansible_collections.susunola.tencentcloud.plugins.modules.lighthouse_key_pair import describe_request as key_request
from ansible_collections.susunola.tencentcloud.plugins.modules.lighthouse_snapshot import describe_request as snapshot_request
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

KEY_ID = "lhkey-8b0a1c2d"
KEY_NAME = "production-automation"
PUBLIC_KEY = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIMockPublicKeyMaterial automation@example.com"
SNAPSHOT_ID = "lhsnap-8b0a1c2d"
SNAPSHOT_NAME = "before-upgrade"
INSTANCE_ID = "lhins-8b0a1c2d"

#: One ``KeyPair`` as ``DescribeKeyPairs`` returns it.
KEY_PAIR = {
    "KeyId": KEY_ID,
    "KeyName": KEY_NAME,
    "PublicKey": PUBLIC_KEY,
    "AssociatedInstanceIds": ["lhins-1", "lhins-2"],
    "CreatedTime": "2026-01-20T08:15:00Z",
}

#: One ``Snapshot`` as ``DescribeSnapshots`` returns it.
SNAPSHOT = {
    "SnapshotId": SNAPSHOT_ID,
    "DiskUsage": "SYSTEM_DISK",
    "DiskId": "lhdisk-1f2e3d4c",
    "DiskSize": 50,
    "SnapshotName": SNAPSHOT_NAME,
    "SnapshotState": "NORMAL",
    "Percent": 100,
    "LatestOperation": "CreateInstanceSnapshot",
    "LatestOperationState": "SUCCEEDED",
    "CreatedTime": "2026-02-10T03:00:00Z",
}
#: The API selects snapshots by ``instance-id`` but the returned ``Snapshot``
#: record carries no ``InstanceId``, so the fake tracks ownership beside the
#: store (see :class:`FakeLighthouseClient`).


def test_key_request_filters_by_id_and_paginates():
    request = key_request(FakeModels(), {"key_id": "key-1"}, 100)
    assert request.KeyIds == ["key-1"]
    assert (request.Offset, request.Limit) == (100, 100)


def test_snapshot_request_builds_instance_and_name_filters():
    request = snapshot_request(FakeModels(), {"instance_id": "lhins-1", "name": "daily"}, 0)
    assert [(item.Name, item.Values) for item in request.Filters] == [("instance-id", ["lhins-1"]), ("snapshot-name", ["daily"])]


class FakeLighthouseClientClass(object):
    """Stand-in for the SDK's ``LighthouseClient`` class (both modules share it)."""


class FakeLighthouseClient(object):
    """In-memory Lighthouse client for key pairs and snapshots.

    Reads answer the way the API does -- ``KeyIds``/``SnapshotIds`` select by
    id, ``Filters`` select snapshots by ``instance-id``/``snapshot-name``, and
    both lists paginate by ``Offset``/``Limit`` against a ``TotalCount`` --
    and writes mutate the store so a module that re-reads sees its own change.
    """

    def __init__(self, key_pairs=None, snapshots=None, owners=None, error=None, fail_on=None):
        self.key_pairs = [copy.deepcopy(key) for key in (key_pairs or [])]
        self.snapshots = [copy.deepcopy(snapshot) for snapshot in (snapshots or [])]
        #: Snapshot id -> owning instance id. ``DescribeSnapshots`` filters on
        #: it, but the record it returns has no ``InstanceId`` field, so the
        #: fake keeps the association beside the store. Seeded snapshots
        #: default to the instance under test.
        self.owners = dict(owners) if owners is not None else {
            snapshot["SnapshotId"]: INSTANCE_ID for snapshot in self.snapshots
        }
        self.error = error
        self.fail_on = fail_on
        self.calls = []

    def _record(self, name, request):
        self.calls.append((name, request))
        if self.error is not None and (self.fail_on is None or self.fail_on == name):
            raise self.error
        return request

    @property
    def operations(self):
        return [name for name, _request in self.calls]

    def _key(self, key_id):
        for key in self.key_pairs:
            if key["KeyId"] == key_id:
                return key
        return None

    def DescribeKeyPairs(self, request):
        self._record("DescribeKeyPairs", request)
        keys = self.key_pairs
        if getattr(request, "KeyIds", None):
            keys = [key for key in keys if key["KeyId"] in request.KeyIds]
        offset, limit = request.Offset or 0, request.Limit or len(keys) or 1
        page = keys[offset:offset + limit]
        return SimpleNamespace(TotalCount=len(keys), KeyPairSet=[FakeResource(key) for key in page], RequestId="req-lh")

    def ImportKeyPair(self, request):
        self._record("ImportKeyPair", request)
        key = {
            "KeyId": "lhkey-new-1",
            "KeyName": request.KeyName,
            "PublicKey": request.PublicKey,
            "AssociatedInstanceIds": [],
            "CreatedTime": "2026-02-11T09:00:00Z",
        }
        self.key_pairs.append(key)
        return SimpleNamespace(KeyId=key["KeyId"], RequestId="req-lh")

    def DeleteKeyPairs(self, request):
        self._record("DeleteKeyPairs", request)
        self.key_pairs = [key for key in self.key_pairs if key["KeyId"] not in request.KeyIds]
        return SimpleNamespace(RequestId="req-lh")

    def AssociateInstancesKeyPairs(self, request):
        self._record("AssociateInstancesKeyPairs", request)
        for key_id in request.KeyIds:
            key = self._key(key_id)
            if key is not None:
                key["AssociatedInstanceIds"] = sorted(set(key.get("AssociatedInstanceIds") or []) | set(request.InstanceIds))
        return SimpleNamespace(RequestId="req-lh")

    def DisassociateInstancesKeyPairs(self, request):
        self._record("DisassociateInstancesKeyPairs", request)
        for key_id in request.KeyIds:
            key = self._key(key_id)
            if key is not None:
                key["AssociatedInstanceIds"] = sorted(set(key.get("AssociatedInstanceIds") or []) - set(request.InstanceIds))
        return SimpleNamespace(RequestId="req-lh")

    def DescribeSnapshots(self, request):
        self._record("DescribeSnapshots", request)
        snapshots = self.snapshots
        if getattr(request, "SnapshotIds", None):
            snapshots = [item for item in snapshots if item["SnapshotId"] in request.SnapshotIds]
        for item_filter in getattr(request, "Filters", None) or []:
            if item_filter.Name == "instance-id":
                snapshots = [item for item in snapshots if self.owners.get(item["SnapshotId"]) in item_filter.Values]
            if item_filter.Name == "snapshot-name":
                snapshots = [item for item in snapshots if item["SnapshotName"] in item_filter.Values]
        offset, limit = request.Offset or 0, request.Limit or len(snapshots) or 1
        page = snapshots[offset:offset + limit]
        return SimpleNamespace(TotalCount=len(snapshots), SnapshotSet=[FakeResource(item) for item in page], RequestId="req-lh")

    def CreateInstanceSnapshot(self, request):
        self._record("CreateInstanceSnapshot", request)
        snapshot = dict(SNAPSHOT, SnapshotId="lhsnap-new-1", SnapshotName=request.SnapshotName)
        self.snapshots.append(snapshot)
        self.owners[snapshot["SnapshotId"]] = request.InstanceId
        return SimpleNamespace(SnapshotId=snapshot["SnapshotId"], RequestId="req-lh")

    def ModifySnapshotAttribute(self, request):
        self._record("ModifySnapshotAttribute", request)
        for snapshot in self.snapshots:
            if snapshot["SnapshotId"] == request.SnapshotId:
                snapshot["SnapshotName"] = request.SnapshotName
        return SimpleNamespace(RequestId="req-lh")

    def DeleteSnapshots(self, request):
        self._record("DeleteSnapshots", request)
        self.snapshots = [item for item in self.snapshots if item["SnapshotId"] not in request.SnapshotIds]
        return SimpleNamespace(RequestId="req-lh")


def _patch_module(monkeypatch, module, client):
    """Point ``module`` at ``client`` through its ``_load``/``create_client`` seams."""
    clients = []
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(module, "_load", lambda: (FakeModels(), SimpleNamespace(LighthouseClient=FakeLighthouseClientClass)))

    def create_client(self, client_class, endpoint):
        clients.append((client_class, endpoint))
        return client

    monkeypatch.setattr(TencentCloudModule, "create_client", create_client)
    return clients


def _key_args(_omit=(), **extra):
    """Key-pair arguments; ``_omit`` drops keys that must stay unspecified."""
    args = {"name": KEY_NAME, "public_key": PUBLIC_KEY, "instance_ids": ["lhins-1", "lhins-2"], "username": "root"}
    args.update(extra)
    for key in _omit:
        del args[key]
    return module_args(**args)


def _snapshot_args(_omit=(), **extra):
    args = {"instance_id": INSTANCE_ID, "name": SNAPSHOT_NAME}
    args.update(extra)
    for key in _omit:
        del args[key]
    return module_args(**args)


def _operations(payload):
    return [call["operation"] for call in payload["tc_api_calls"]]


# ---------------------------------------------------------------------------
# lighthouse_key_pair: request builders
# ---------------------------------------------------------------------------


def test_key_describe_request_omits_key_ids_without_an_id():
    request = key_request(FakeModels(), {"key_id": None})
    assert not hasattr(request, "KeyIds")
    assert (request.Offset, request.Limit) == (0, 100)


def test_key_import_request_strips_the_public_key():
    request = lighthouse_key_pair.import_request(FakeModels(), {"name": KEY_NAME, "public_key": "  %s\n" % PUBLIC_KEY})
    assert (request.KeyName, request.PublicKey) == (KEY_NAME, PUBLIC_KEY)


def test_key_associate_request_sorts_instance_ids_and_sends_the_username():
    params = {"association_type": "ONLINE", "username": "root"}
    request = lighthouse_key_pair.associate_request(FakeModels(), params, KEY_ID, {"lhins-3", "lhins-1"})
    assert (request.KeyIds, request.InstanceIds, request.AssociateType) == ([KEY_ID], ["lhins-1", "lhins-3"], "ONLINE")
    assert request.Username == "root"


def test_key_associate_request_omits_the_username_for_offline_association():
    """The API rejects ``Username`` when the association is offline."""
    params = {"association_type": "OFFLINE", "username": "root"}
    request = lighthouse_key_pair.associate_request(FakeModels(), params, KEY_ID, {"lhins-1"})
    assert request.AssociateType == "OFFLINE"
    assert not hasattr(request, "Username")


def test_key_disassociate_request_sets_the_disassociation_type():
    params = {"association_type": "ONLINE", "username": "root"}
    request = lighthouse_key_pair.disassociate_request(FakeModels(), params, KEY_ID, {"lhins-1", "lhins-2"})
    assert (request.KeyIds, request.InstanceIds, request.DisassociateType) == ([KEY_ID], ["lhins-1", "lhins-2"], "ONLINE")
    assert request.Username == "root"


# ---------------------------------------------------------------------------
# lighthouse_key_pair: run_module
# ---------------------------------------------------------------------------


def test_key_pair_present_imports_and_associates_a_missing_key(monkeypatch):
    client = FakeLighthouseClient()
    clients = _patch_module(monkeypatch, lighthouse_key_pair, client)
    _key_args()

    payload = run(lighthouse_key_pair.run_module)

    assert payload.keys() == {"changed", "key_pair", "tc_api_calls"}
    assert payload["changed"] is True
    assert payload["key_pair"]["KeyId"] == "lhkey-new-1"
    assert payload["key_pair"]["AssociatedInstanceIds"] == ["lhins-1", "lhins-2"]
    assert clients == [(FakeLighthouseClientClass, "lighthouse.tencentcloudapi.com")]
    assert _operations(payload) == [
        "DescribeKeyPairs", "ImportKeyPair", "DescribeKeyPairs", "AssociateInstancesKeyPairs", "DescribeKeyPairs",
    ]
    import_request = [request for name, request in client.calls if name == "ImportKeyPair"][0]
    assert (import_request.KeyName, import_request.PublicKey) == (KEY_NAME, PUBLIC_KEY)
    associate_request = [request for name, request in client.calls if name == "AssociateInstancesKeyPairs"][0]
    assert (associate_request.KeyIds, associate_request.InstanceIds) == (["lhkey-new-1"], ["lhins-1", "lhins-2"])


def test_key_pair_present_is_idempotent(monkeypatch):
    client = FakeLighthouseClient(key_pairs=[KEY_PAIR])
    _patch_module(monkeypatch, lighthouse_key_pair, client)
    _key_args()

    payload = run(lighthouse_key_pair.run_module)

    assert payload.keys() == {"changed", "key_pair", "tc_api_calls"}
    assert payload["changed"] is False
    assert payload["key_pair"] == KEY_PAIR
    assert _operations(payload) == ["DescribeKeyPairs"]


def test_key_pair_present_understands_the_associated_instance_set(monkeypatch):
    """The API may report associations as ``AssociatedInstanceSet`` only."""
    key = {k: v for k, v in KEY_PAIR.items() if k != "AssociatedInstanceIds"}
    key["AssociatedInstanceSet"] = [{"InstanceId": "lhins-2"}, {"InstanceId": "lhins-1"}]
    client = FakeLighthouseClient(key_pairs=[key])
    _patch_module(monkeypatch, lighthouse_key_pair, client)
    _key_args()

    payload = run(lighthouse_key_pair.run_module)

    assert payload["changed"] is False
    assert _operations(payload) == ["DescribeKeyPairs"]


def test_key_pair_present_reconciles_the_exact_instance_set(monkeypatch):
    client = FakeLighthouseClient(key_pairs=[KEY_PAIR])
    _patch_module(monkeypatch, lighthouse_key_pair, client)
    _key_args(instance_ids=["lhins-2", "lhins-3"])

    payload = run(lighthouse_key_pair.run_module)

    assert payload["changed"] is True
    assert payload["key_pair"]["AssociatedInstanceIds"] == ["lhins-2", "lhins-3"]
    assert _operations(payload) == [
        "DescribeKeyPairs", "DisassociateInstancesKeyPairs", "AssociateInstancesKeyPairs", "DescribeKeyPairs",
    ]
    disassociate = [request for name, request in client.calls if name == "DisassociateInstancesKeyPairs"][0]
    associate = [request for name, request in client.calls if name == "AssociateInstancesKeyPairs"][0]
    assert disassociate.InstanceIds == ["lhins-1"]
    assert associate.InstanceIds == ["lhins-3"]


def test_key_pair_present_refuses_an_immutable_change_without_force_replace(monkeypatch):
    client = FakeLighthouseClient(key_pairs=[KEY_PAIR])
    _patch_module(monkeypatch, lighthouse_key_pair, client)
    _key_args(public_key="ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIOtherKeyMaterial automation@example.com")

    with pytest.raises(AnsibleFailJson) as failure:
        run(lighthouse_key_pair.run_module)

    assert failure.value.args[0]["msg"] == "name and public_key are immutable; set force_replace=true to disassociate and re-import"
    assert client.operations == ["DescribeKeyPairs"]


def test_key_pair_present_force_replace_reimports_the_key(monkeypatch):
    client = FakeLighthouseClient(key_pairs=[KEY_PAIR])
    _patch_module(monkeypatch, lighthouse_key_pair, client)
    _key_args(public_key="ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIOtherKeyMaterial automation@example.com", force_replace=True)

    payload = run(lighthouse_key_pair.run_module)

    assert payload["changed"] is True
    assert payload["key_pair"]["KeyId"] == "lhkey-new-1"
    assert payload["key_pair"]["PublicKey"].endswith("automation@example.com")
    assert _operations(payload) == [
        "DescribeKeyPairs", "DisassociateInstancesKeyPairs", "DeleteKeyPairs", "ImportKeyPair",
        "DescribeKeyPairs", "AssociateInstancesKeyPairs", "DescribeKeyPairs",
    ]
    assert [key["KeyId"] for key in client.key_pairs] == ["lhkey-new-1"]


def test_key_pair_absent_refuses_to_delete_an_associated_key(monkeypatch):
    client = FakeLighthouseClient(key_pairs=[KEY_PAIR])
    _patch_module(monkeypatch, lighthouse_key_pair, client)
    _key_args(state="absent")

    with pytest.raises(AnsibleFailJson) as failure:
        run(lighthouse_key_pair.run_module)

    payload = failure.value.args[0]
    assert payload["msg"] == "key pair is associated with instances; set force_delete=true to disassociate and delete"
    assert payload["instance_ids"] == ["lhins-1", "lhins-2"]
    assert client.operations == ["DescribeKeyPairs"]


def test_key_pair_absent_force_delete_disassociates_then_deletes(monkeypatch):
    client = FakeLighthouseClient(key_pairs=[KEY_PAIR])
    _patch_module(monkeypatch, lighthouse_key_pair, client)
    _key_args(state="absent", force_delete=True)

    payload = run(lighthouse_key_pair.run_module)

    assert payload.keys() == {"changed", "key_pair", "tc_api_calls"}
    assert payload["changed"] is True
    assert payload["key_pair"] is None
    assert client.key_pairs == []
    assert _operations(payload) == ["DescribeKeyPairs", "DisassociateInstancesKeyPairs", "DeleteKeyPairs"]


def test_key_pair_absent_missing_key_is_unchanged(monkeypatch):
    client = FakeLighthouseClient()
    _patch_module(monkeypatch, lighthouse_key_pair, client)
    _key_args(state="absent")

    payload = run(lighthouse_key_pair.run_module)

    assert payload.keys() == {"changed", "key_pair", "tc_api_calls"}
    assert payload["changed"] is False
    assert payload["key_pair"] is None
    assert _operations(payload) == ["DescribeKeyPairs"]


def test_key_pair_present_looks_up_by_key_id(monkeypatch):
    """``key_id`` wins over ``name``: the id is what identifies the key."""
    client = FakeLighthouseClient(key_pairs=[KEY_PAIR])
    _patch_module(monkeypatch, lighthouse_key_pair, client)
    _key_args(key_id=KEY_ID)

    payload = run(lighthouse_key_pair.run_module)

    assert payload["changed"] is False
    assert [request.KeyIds for name, request in client.calls if name == "DescribeKeyPairs"] == [[KEY_ID]]


def test_key_pair_paginates_until_total_count(monkeypatch):
    """101 keys: the wanted one is only on the second page."""
    keys = [
        dict(KEY_PAIR, KeyId="lhkey-%03d" % index, KeyName="key-%03d" % index, AssociatedInstanceIds=["lhins-1", "lhins-2"])
        for index in range(100)
    ]
    keys.append(KEY_PAIR)
    client = FakeLighthouseClient(key_pairs=keys)
    _patch_module(monkeypatch, lighthouse_key_pair, client)
    _key_args()

    payload = run(lighthouse_key_pair.run_module)

    assert payload["changed"] is False
    assert payload["key_pair"]["KeyId"] == KEY_ID
    assert [request.Offset for name, request in client.calls if name == "DescribeKeyPairs"] == [0, 100]


def test_key_pair_fails_on_an_ambiguous_name(monkeypatch):
    duplicate = dict(KEY_PAIR, KeyId="lhkey-second")
    client = FakeLighthouseClient(key_pairs=[KEY_PAIR, duplicate])
    _patch_module(monkeypatch, lighthouse_key_pair, client)
    _key_args()

    with pytest.raises(AnsibleFailJson) as failure:
        run(lighthouse_key_pair.run_module)

    assert failure.value.args[0]["msg"] == "Multiple Lighthouse key pairs matched; specify key_id"


def test_key_pair_present_requires_the_name_and_public_key(monkeypatch):
    _patch_module(monkeypatch, lighthouse_key_pair, FakeLighthouseClient())
    _key_args(_omit=("name", "public_key"), key_id=KEY_ID)

    with pytest.raises(AnsibleFailJson) as failure:
        run(lighthouse_key_pair.run_module)

    assert failure.value.args[0]["msg"] == "name and public_key are required when state=present"


def test_key_pair_requires_the_key_id_or_the_name(monkeypatch):
    _patch_module(monkeypatch, lighthouse_key_pair, FakeLighthouseClient())
    module_args()

    with pytest.raises(AnsibleFailJson) as failure:
        run(lighthouse_key_pair.run_module)

    assert failure.value.args[0]["msg"] == "one of the following is required: key_id, name"


def test_key_pair_check_mode_never_writes(monkeypatch):
    client = FakeLighthouseClient()
    _patch_module(monkeypatch, lighthouse_key_pair, client)
    _key_args(_ansible_check_mode=True)

    payload = run(lighthouse_key_pair.run_module)

    assert payload["changed"] is True
    assert payload["key_pair"] is None
    assert payload["diff"] == {
        "before": None,
        "after": {"KeyName": KEY_NAME, "PublicKey": PUBLIC_KEY, "InstanceIds": ["lhins-1", "lhins-2"]},
    }
    assert _operations(payload) == ["DescribeKeyPairs"]
    assert client.key_pairs == []


def test_key_pair_maps_an_sdk_error_to_the_failure_envelope(monkeypatch):
    class FakeSdkException(Exception):
        def get_code(self):
            return "UnauthorizedOperation"

        def get_request_id(self):
            return "req-lh-denied"

    client = FakeLighthouseClient(error=FakeSdkException("not allowed to list key pairs"))
    _patch_module(monkeypatch, lighthouse_key_pair, client)
    _key_args()

    with pytest.raises(AnsibleFailJson) as failure:
        run(lighthouse_key_pair.run_module)

    payload = failure.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert payload["error"] == "not allowed to list key pairs"
    assert payload["error_code"] == "UnauthorizedOperation"
    assert payload["request_id"] == "req-lh-denied"
    assert payload["error_kind"] == "unauthorized"


# ---------------------------------------------------------------------------
# lighthouse_snapshot: request builders
# ---------------------------------------------------------------------------


def test_snapshot_describe_request_targets_the_snapshot_id():
    request = snapshot_request(FakeModels(), {"snapshot_id": SNAPSHOT_ID, "instance_id": None, "name": None})
    assert request.SnapshotIds == [SNAPSHOT_ID]
    assert (request.Offset, request.Limit) == (0, 100)
    assert not hasattr(request, "Filters")


def test_snapshot_describe_request_omits_empty_filters():
    request = snapshot_request(FakeModels(), {"snapshot_id": None, "instance_id": None, "name": None})
    assert not hasattr(request, "SnapshotIds")
    assert not hasattr(request, "Filters")


def test_snapshot_create_request_sets_the_instance_and_name():
    request = lighthouse_snapshot.create_request(FakeModels(), {"instance_id": INSTANCE_ID, "name": SNAPSHOT_NAME})
    assert (request.InstanceId, request.SnapshotName) == (INSTANCE_ID, SNAPSHOT_NAME)


def test_snapshot_update_request_renames_by_id():
    request = lighthouse_snapshot.update_request(FakeModels(), SNAPSHOT_ID, "after-upgrade")
    assert (request.SnapshotId, request.SnapshotName) == (SNAPSHOT_ID, "after-upgrade")


def test_snapshot_delete_request_targets_the_id():
    assert lighthouse_snapshot.delete_request(FakeModels(), SNAPSHOT_ID).SnapshotIds == [SNAPSHOT_ID]


# ---------------------------------------------------------------------------
# lighthouse_snapshot: run_module
# ---------------------------------------------------------------------------


def test_snapshot_present_creates_and_waits_for_normal(monkeypatch):
    client = FakeLighthouseClient()
    clients = _patch_module(monkeypatch, lighthouse_snapshot, client)
    _snapshot_args()

    payload = run(lighthouse_snapshot.run_module)

    assert payload.keys() == {"changed", "snapshot", "tc_api_calls"}
    assert payload["changed"] is True
    assert payload["snapshot"]["SnapshotId"] == "lhsnap-new-1"
    assert payload["snapshot"]["SnapshotState"] == "NORMAL"
    assert payload["snapshot"]["SnapshotName"] == SNAPSHOT_NAME
    # An exact key set: the record is the SDK ``Snapshot`` model, which has no
    # ``InstanceId`` field even though the lookup is made by instance.
    assert payload["snapshot"].keys() == set(SNAPSHOT)
    assert clients == [(FakeLighthouseClientClass, "lighthouse.tencentcloudapi.com")]
    assert _operations(payload) == ["DescribeSnapshots", "CreateInstanceSnapshot", "DescribeSnapshots"]
    create_request = [request for name, request in client.calls if name == "CreateInstanceSnapshot"][0]
    assert (create_request.InstanceId, create_request.SnapshotName) == (INSTANCE_ID, SNAPSHOT_NAME)


def test_snapshot_present_is_idempotent(monkeypatch):
    client = FakeLighthouseClient(snapshots=[SNAPSHOT])
    _patch_module(monkeypatch, lighthouse_snapshot, client)
    _snapshot_args()

    payload = run(lighthouse_snapshot.run_module)

    assert payload.keys() == {"changed", "snapshot", "tc_api_calls"}
    assert payload["changed"] is False
    assert payload["snapshot"] == SNAPSHOT
    assert _operations(payload) == ["DescribeSnapshots"]


def test_snapshot_present_renames_by_id(monkeypatch):
    client = FakeLighthouseClient(snapshots=[SNAPSHOT])
    _patch_module(monkeypatch, lighthouse_snapshot, client)
    _snapshot_args(snapshot_id=SNAPSHOT_ID, name="after-upgrade", _omit=("instance_id",))

    payload = run(lighthouse_snapshot.run_module)

    assert payload["changed"] is True
    assert payload["snapshot"]["SnapshotName"] == "after-upgrade"
    assert client.snapshots[0]["SnapshotId"] == SNAPSHOT_ID
    update_request = [request for name, request in client.calls if name == "ModifySnapshotAttribute"][0]
    assert (update_request.SnapshotId, update_request.SnapshotName) == (SNAPSHOT_ID, "after-upgrade")


def test_snapshot_absent_deletes_the_snapshot(monkeypatch):
    client = FakeLighthouseClient(snapshots=[SNAPSHOT])
    _patch_module(monkeypatch, lighthouse_snapshot, client)
    _snapshot_args(state="absent")

    payload = run(lighthouse_snapshot.run_module)

    assert payload.keys() == {"changed", "snapshot", "tc_api_calls"}
    assert payload["changed"] is True
    assert payload["snapshot"] is None
    assert client.snapshots == []
    delete_request = [request for name, request in client.calls if name == "DeleteSnapshots"][0]
    assert delete_request.SnapshotIds == [SNAPSHOT_ID]


def test_snapshot_absent_by_id_needs_no_instance(monkeypatch):
    client = FakeLighthouseClient(snapshots=[SNAPSHOT])
    _patch_module(monkeypatch, lighthouse_snapshot, client)
    module_args(state="absent", snapshot_id=SNAPSHOT_ID)

    payload = run(lighthouse_snapshot.run_module)

    assert payload["changed"] is True
    assert client.snapshots == []
    assert [request.SnapshotIds for name, request in client.calls if name == "DescribeSnapshots"] == [[SNAPSHOT_ID]]


def test_snapshot_absent_missing_snapshot_is_unchanged(monkeypatch):
    client = FakeLighthouseClient()
    _patch_module(monkeypatch, lighthouse_snapshot, client)
    _snapshot_args(state="absent")

    payload = run(lighthouse_snapshot.run_module)

    assert payload["changed"] is False
    assert payload["snapshot"] is None
    assert _operations(payload) == ["DescribeSnapshots"]


def test_snapshot_check_mode_never_writes(monkeypatch):
    client = FakeLighthouseClient()
    _patch_module(monkeypatch, lighthouse_snapshot, client)
    _snapshot_args(_ansible_check_mode=True)

    payload = run(lighthouse_snapshot.run_module)

    assert payload["changed"] is True
    assert payload["snapshot"] is None
    assert payload["diff"] == {"before": None, "after": {"SnapshotName": SNAPSHOT_NAME}}
    assert _operations(payload) == ["DescribeSnapshots"]
    assert client.snapshots == []


def test_snapshot_requires_the_snapshot_id_or_the_name(monkeypatch):
    _patch_module(monkeypatch, lighthouse_snapshot, FakeLighthouseClient())
    module_args()

    with pytest.raises(AnsibleFailJson) as failure:
        run(lighthouse_snapshot.run_module)

    assert failure.value.args[0]["msg"] == "one of the following is required: snapshot_id, name"


def test_snapshot_present_requires_a_lookup_target(monkeypatch):
    _patch_module(monkeypatch, lighthouse_snapshot, FakeLighthouseClient())
    module_args(name=SNAPSHOT_NAME)

    with pytest.raises(AnsibleFailJson) as failure:
        run(lighthouse_snapshot.run_module)

    assert failure.value.args[0]["msg"] == "name and either snapshot_id or instance_id are required when state=present"


def test_snapshot_absent_requires_the_instance_id_with_a_name(monkeypatch):
    _patch_module(monkeypatch, lighthouse_snapshot, FakeLighthouseClient())
    module_args(state="absent", name=SNAPSHOT_NAME)

    with pytest.raises(AnsibleFailJson) as failure:
        run(lighthouse_snapshot.run_module)

    assert failure.value.args[0]["msg"] == "instance_id is required with name when state=absent"


def test_snapshot_maps_an_sdk_error_to_the_failure_envelope(monkeypatch):
    class FakeSdkException(Exception):
        def get_code(self):
            return "ResourceNotFound.SnapshotNotFound"

        def get_request_id(self):
            return "req-lh-missing"

    client = FakeLighthouseClient(error=FakeSdkException("snapshot does not exist"))
    _patch_module(monkeypatch, lighthouse_snapshot, client)
    _snapshot_args()

    with pytest.raises(AnsibleFailJson) as failure:
        run(lighthouse_snapshot.run_module)

    payload = failure.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert payload["error"] == "snapshot does not exist"
    assert payload["error_code"] == "ResourceNotFound.SnapshotNotFound"
    assert payload["request_id"] == "req-lh-missing"
    assert payload["error_kind"] == "not_found"
