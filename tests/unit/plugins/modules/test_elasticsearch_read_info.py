"""Tests for the Elasticsearch writers: elasticsearch_index and elasticsearch_snapshot.

Both modules reconcile one named object inside an ES cluster and both talk to
``es.tencentcloudapi.com``: an index through ``DescribeIndexMeta`` /
``CreateIndex`` / ``UpdateIndex`` / ``DeleteIndex``, a snapshot through
``DescribeClusterSnapshot`` / ``CreateClusterSnapshot`` /
``DeleteClusterSnapshot``.

The two request-shape tests came first and stay as they were. Everything below
drives ``run_module()`` against an in-memory fake ``EsClient`` that stores what
the modules write, so create/update/delete/replace decisions are observable
through the requests and the returned payloads. The fixtures use the fields the
API really returns -- ``IndexMetaField`` (``IndexName``, ``IndexMetaJson``,
``IndexStatus``, ``ClusterId``, ``AppDoc``...) and the ``Snapshots`` record
(``SnapshotName``, ``Uuid``, ``Repository``, ``Indices``, ``State``,
``EsRepositoryType``, ``StorageDuration``, ``CosRetention``,
``RetainUntilDate``, ``RetentionGraceTime``, ``RemoteCos``,
``RemoteCosRegion``, ``MultiAz``, ``MaxSnapshotPerSec``, ``InstanceId``).
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
import json
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import elasticsearch_index, elasticsearch_snapshot
from ansible_collections.susunola.tencentcloud.plugins.modules.elasticsearch_index import describe_request as index_request
from ansible_collections.susunola.tencentcloud.plugins.modules.elasticsearch_snapshot import describe_request as snapshot_request
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

INSTANCE_ID = "es-9a1b2c3d"
REPOSITORY = "es-9a1b2c3d"
INDEX_NAME = "orders"
SNAPSHOT_NAME = "before-upgrade"
RETAIN_UNTIL = "2027-01-01T00:00:00Z"

METADATA = {
    "settings": {"number_of_shards": 3, "number_of_replicas": 1},
    "mappings": {"properties": {"order_id": {"type": "keyword"}}},
}
#: The same index as the service reports it: the requested metadata plus a
#: setting the service added, which the containment check has to tolerate.
SERVICE_METADATA = {
    "settings": {"number_of_shards": 3, "number_of_replicas": 1, "refresh_interval": "1s"},
    "mappings": {"properties": {"order_id": {"type": "keyword"}}, "dynamic": "true"},
}
INDEX_META = {
    "IndexType": "normal",
    "IndexName": INDEX_NAME,
    "IndexMetaJson": json.dumps(SERVICE_METADATA, sort_keys=True),
    "IndexStatus": "open",
    "IndexStorage": 4096,
    "IndexCreateTime": "2026-02-01 09:12:44",
    "ClusterId": INSTANCE_ID,
    "ClusterName": "search-prod",
    "ClusterVersion": "7.14.2",
    "AppId": 1300000000,
    "IndexDocs": 12345,
}

#: One ``Snapshots`` record with every field ``comparable`` reads.
SNAPSHOT = {
    "SnapshotName": SNAPSHOT_NAME,
    "Uuid": "8f2c0d1e",
    "Repository": REPOSITORY,
    "Version": "7.14.2",
    "Indices": ["customers", "orders"],
    "State": "SUCCESS",
    "StartTime": "2026-02-10 03:00:00",
    "EndTime": "2026-02-10 03:04:12",
    "DurationInMillis": 252000,
    "TotalShards": 6,
    "FailedShards": 0,
    "SuccessfulShards": 6,
    "EsRepositoryType": 0,
    "StorageDuration": 30,
    "CosRetention": 1,
    "RetainUntilDate": RETAIN_UNTIL,
    "RetentionGraceTime": 3,
    "RemoteCos": 1,
    "RemoteCosRegion": "ap-shanghai",
    "MultiAz": 1,
    "MaxSnapshotPerSec": "40m",
    "InstanceId": INSTANCE_ID,
}


def test_index_request_sets_exact_identity_and_credentials():
    request = index_request(FakeModels(), {"instance_id": "es-1", "index_type": "normal", "name": "orders", "username": "elastic", "password": "secret"})
    assert (request.InstanceId, request.IndexName, request.Username) == ("es-1", "orders", "elastic")


def test_snapshot_request_sets_exact_identity():
    request = snapshot_request(FakeModels(), {"instance_id": "es-1", "repository_name": "repo", "name": "daily"})
    assert (request.InstanceId, request.RepositoryName, request.SnapshotName) == ("es-1", "repo", "daily")


class FakeEsClientClass(object):
    """Stand-in for the SDK's ``EsClient`` class (both modules share it)."""


class NotFoundError(Exception):
    """Shape-compatible stand-in for the SDK's ``ResourceNotFound`` error."""

    def get_code(self):
        return "ResourceNotFound"

    def get_request_id(self):
        return "req-es-notfound"


class UnauthorizedError(Exception):
    def get_code(self):
        return "UnauthorizedOperation"

    def get_request_id(self):
        return "req-es-denied"


class FakeEsClient(object):
    """In-memory ES client holding the index and snapshot stores.

    Writes mutate the store so the module's read-back after a write converges
    on what the module just asked for, and every call is recorded with the
    request object that produced it.
    """

    def __init__(self, indexes=None, snapshots=None, error=None, fail_on=None, not_found_raises=False):
        self.indexes = {meta["IndexName"]: copy.deepcopy(meta) for meta in (indexes or [])}
        self.snapshots = [copy.deepcopy(snapshot) for snapshot in (snapshots or [])]
        self.error = error
        self.fail_on = fail_on
        #: The real API answers an unknown index either with a null
        #: ``IndexMetaField`` or with ``ResourceNotFound``; the module has to
        #: read both as "absent".
        self.not_found_raises = not_found_raises
        self.calls = []

    def _record(self, name, request):
        self.calls.append((name, request))
        if self.error is not None and (self.fail_on is None or self.fail_on == name):
            raise self.error
        return request

    @property
    def operations(self):
        return [name for name, _request in self.calls]

    def DescribeIndexMeta(self, request):
        self._record("DescribeIndexMeta", request)
        meta = self.indexes.get(request.IndexName)
        if meta is None and self.not_found_raises:
            raise NotFoundError("index %s not found" % request.IndexName)
        return SimpleNamespace(IndexMetaField=FakeResource(meta) if meta else None, RequestId="req-es")

    def CreateIndex(self, request):
        self._record("CreateIndex", request)
        self.indexes[request.IndexName] = {
            "IndexType": request.IndexType,
            "IndexName": request.IndexName,
            "IndexMetaJson": request.IndexMetaJson,
            "IndexStatus": "open",
            "IndexStorage": 0,
            "IndexCreateTime": "2026-02-11 10:00:00",
            "ClusterId": request.InstanceId,
            "ClusterName": "search-prod",
            "ClusterVersion": "7.14.2",
            "IndexDocs": 0,
        }
        return SimpleNamespace(RequestId="req-es")

    def UpdateIndex(self, request):
        self._record("UpdateIndex", request)
        self.indexes[request.IndexName]["IndexMetaJson"] = request.UpdateMetaJson
        return SimpleNamespace(RequestId="req-es")

    def DeleteIndex(self, request):
        self._record("DeleteIndex", request)
        self.indexes.pop(request.IndexName, None)
        return SimpleNamespace(RequestId="req-es")

    def DescribeClusterSnapshot(self, request):
        self._record("DescribeClusterSnapshot", request)
        snapshots = self.snapshots
        if getattr(request, "SnapshotName", None):
            snapshots = [item for item in snapshots if item["SnapshotName"] == request.SnapshotName]
        if getattr(request, "RepositoryName", None):
            snapshots = [item for item in snapshots if item["Repository"] == request.RepositoryName]
        if getattr(request, "InstanceId", None):
            snapshots = [item for item in snapshots if item["InstanceId"] == request.InstanceId]
        return SimpleNamespace(
            InstanceId=request.InstanceId,
            RepositoryName=request.RepositoryName,
            Snapshots=[FakeResource(item) for item in snapshots],
            RequestId="req-es",
        )

    def CreateClusterSnapshot(self, request):
        self._record("CreateClusterSnapshot", request)
        self.snapshots = [item for item in self.snapshots if item["SnapshotName"] != request.SnapshotName]
        self.snapshots.append({
            "SnapshotName": request.SnapshotName,
            "Uuid": "0f7a1c9d",
            "Repository": REPOSITORY,
            "Version": "7.14.2",
            "Indices": request.Indices.split(",") if request.Indices else [],
            "State": "SUCCESS",
            "StartTime": "2026-02-11 10:00:00",
            "EndTime": "2026-02-11 10:03:00",
            "DurationInMillis": 180000,
            "EsRepositoryType": request.EsRepositoryType,
            "UserEsRepository": request.UserEsRepository,
            "StorageDuration": request.StorageDuration,
            "CosRetention": request.CosRetention,
            "RetainUntilDate": request.RetainUntilDate,
            "RetentionGraceTime": request.RetentionGraceTime,
            "RemoteCos": request.RemoteCos,
            "RemoteCosRegion": request.RemoteCosRegion,
            "MultiAz": request.MultiAz,
            "MaxSnapshotPerSec": request.MaxSnapshotPerSec,
            "InstanceId": request.InstanceId,
        })
        return SimpleNamespace(RequestId="req-es")

    def DeleteClusterSnapshot(self, request):
        self._record("DeleteClusterSnapshot", request)
        self.snapshots = [
            item for item in self.snapshots
            if not (item["SnapshotName"] == request.SnapshotName and item["Repository"] == request.RepositoryName)
        ]
        return SimpleNamespace(RequestId="req-es")


class FakeModule(object):
    """Module stand-in for helper-level tests: ``find`` only needs ``sdk_call``."""

    def sdk_call(self, operation, request=None, retry=True):
        return operation(request) if request is not None else operation()


def _patch_module(monkeypatch, module, client):
    """Point ``module`` at ``client`` through its ``_load``/``create_client`` seams."""
    clients = []
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(module, "_load", lambda: (FakeModels(), SimpleNamespace(EsClient=FakeEsClientClass)))

    def create_client(self, client_class, endpoint):
        clients.append((client_class, endpoint))
        return client

    monkeypatch.setattr(TencentCloudModule, "create_client", create_client)
    return clients


def _index_args(**extra):
    """Arguments for a present-state index task (``metadata`` is required there)."""
    args = {"instance_id": INSTANCE_ID, "name": INDEX_NAME, "username": "elastic", "password": "s3cret", "metadata": METADATA}
    args.update(extra)
    return module_args(**args)


def _absent_index_args(**extra):
    """Arguments for ``state=absent``, which does not take ``metadata``."""
    args = {"instance_id": INSTANCE_ID, "name": INDEX_NAME, "username": "elastic", "password": "s3cret", "state": "absent"}
    args.update(extra)
    return module_args(**args)


def _snapshot_args(_omit=(), **extra):
    """Snapshot arguments; ``_omit`` drops keys that must stay unspecified.

    Ansible counts an explicitly passed ``None`` as specified, so a
    ``required_if`` check can only be exercised by leaving the key out.
    """
    args = {
        "instance_id": INSTANCE_ID,
        "repository_name": REPOSITORY,
        "name": SNAPSHOT_NAME,
        "indices": ["orders", "customers"],
        "storage_days": 30,
        "lock_retention": True,
        "retain_until": RETAIN_UNTIL,
        "retention_grace_days": 3,
        "remote_cos": True,
        "remote_region": "ap-shanghai",
        "multi_az": True,
        "max_snapshot_per_sec": "40m",
    }
    args.update(extra)
    for key in _omit:
        del args[key]
    return module_args(**args)


def _index_params(**extra):
    """Raw params for helper-level index tests (``_load`` is not involved)."""
    params = {"instance_id": INSTANCE_ID, "index_type": "normal", "name": INDEX_NAME, "username": "elastic", "password": "s3cret", "metadata": METADATA}
    params.update(extra)
    return params


def _operations(payload):
    return [call["operation"] for call in payload["tc_api_calls"]]


# ---------------------------------------------------------------------------
# elasticsearch_index: request builders
# ---------------------------------------------------------------------------


def test_index_describe_request_carries_type_and_credentials():
    params = {"instance_id": INSTANCE_ID, "index_type": "auto", "name": INDEX_NAME, "username": "elastic", "password": "s3cret"}
    request = elasticsearch_index.describe_request(FakeModels(), params)
    assert (request.IndexType, request.Password) == ("auto", "s3cret")


def test_index_create_request_serialises_the_metadata_compactly():
    params = {"instance_id": INSTANCE_ID, "index_type": "normal", "name": INDEX_NAME, "username": "elastic", "password": "s3cret", "metadata": METADATA}
    request = elasticsearch_index.create_request(FakeModels(), params)
    assert request.IndexMetaJson == json.dumps(METADATA, sort_keys=True, separators=(",", ":"))


def test_index_update_request_serialises_the_metadata_into_update_meta_json():
    params = {"instance_id": INSTANCE_ID, "index_type": "normal", "name": INDEX_NAME, "username": "elastic", "password": "s3cret", "metadata": METADATA}
    request = elasticsearch_index.update_request(FakeModels(), params)
    assert request.UpdateMetaJson == json.dumps(METADATA, sort_keys=True, separators=(",", ":"))


# ---------------------------------------------------------------------------
# elasticsearch_index: run_module
# ---------------------------------------------------------------------------


def test_index_present_creates_a_missing_index(monkeypatch):
    client = FakeEsClient()
    clients = _patch_module(monkeypatch, elasticsearch_index, client)
    _index_args()

    payload = run(elasticsearch_index.run_module)

    assert payload.keys() == {"changed", "index", "tc_api_calls"}
    assert payload["changed"] is True
    assert payload["index"]["IndexName"] == INDEX_NAME
    assert payload["index"]["Metadata"] == METADATA
    assert _operations(payload) == ["DescribeIndexMeta", "CreateIndex", "DescribeIndexMeta"]
    assert clients == [(FakeEsClientClass, "es.tencentcloudapi.com")]
    create_request = [request for name, request in client.calls if name == "CreateIndex"][0]
    assert (create_request.InstanceId, create_request.IndexName, create_request.Username) == (INSTANCE_ID, INDEX_NAME, "elastic")


def test_index_present_treats_a_not_found_error_as_a_missing_index(monkeypatch):
    """The API answers an unknown index with ``ResourceNotFound``."""
    client = FakeEsClient(not_found_raises=True)
    _patch_module(monkeypatch, elasticsearch_index, client)
    _index_args()

    payload = run(elasticsearch_index.run_module)

    assert payload["changed"] is True
    assert payload["index"]["IndexName"] == INDEX_NAME
    assert _operations(payload) == ["DescribeIndexMeta", "CreateIndex", "DescribeIndexMeta"]


def test_index_present_is_idempotent_when_the_service_adds_settings(monkeypatch):
    client = FakeEsClient(indexes=[INDEX_META])
    _patch_module(monkeypatch, elasticsearch_index, client)
    _index_args()

    payload = run(elasticsearch_index.run_module)

    assert payload.keys() == {"changed", "index", "tc_api_calls"}
    assert payload["changed"] is False
    assert payload["index"]["Metadata"] == SERVICE_METADATA
    assert _operations(payload) == ["DescribeIndexMeta"]


def test_index_present_updates_when_a_requested_setting_differs(monkeypatch):
    client = FakeEsClient(indexes=[INDEX_META])
    _patch_module(monkeypatch, elasticsearch_index, client)
    _index_args(metadata={"settings": {"number_of_shards": 6, "number_of_replicas": 1}})

    payload = run(elasticsearch_index.run_module)

    assert payload["changed"] is True
    assert payload["index"]["Metadata"]["settings"]["number_of_shards"] == 6
    assert _operations(payload) == ["DescribeIndexMeta", "UpdateIndex", "DescribeIndexMeta"]
    update_request = [request for name, request in client.calls if name == "UpdateIndex"][0]
    assert update_request.UpdateMetaJson == json.dumps({"settings": {"number_of_shards": 6, "number_of_replicas": 1}}, sort_keys=True, separators=(",", ":"))


def test_index_present_ignores_metadata_for_another_index(monkeypatch):
    """A response naming a different index is not this index's state."""
    other = dict(INDEX_META, IndexName="customers")
    client = FakeEsClient(indexes=[other])
    _patch_module(monkeypatch, elasticsearch_index, client)
    _index_args()

    payload = run(elasticsearch_index.run_module)

    assert payload["changed"] is True
    assert payload["index"]["IndexName"] == INDEX_NAME
    assert "CreateIndex" in client.operations


def test_index_find_returns_unparseable_metadata_verbatim():
    """A non-JSON ``IndexMetaJson`` is handed back as it came, not dropped.

    The decode branch is a read-side one, and a run that reads such an index
    updates it (the containment check cannot match a string), so the lookup is
    driven directly rather than through a run that would overwrite the value.
    """
    client = FakeEsClient(indexes=[dict(INDEX_META, IndexMetaJson="not json")])
    value = elasticsearch_index.find(FakeModule(), client, FakeModels(), _index_params())

    assert value["Metadata"] == "not json"


def test_index_find_defaults_a_missing_metadata_json_to_an_empty_mapping():
    client = FakeEsClient(indexes=[dict(INDEX_META, IndexMetaJson=None)])
    value = elasticsearch_index.find(FakeModule(), client, FakeModels(), _index_params())

    assert value["Metadata"] == {}


def test_index_absent_deletes_an_existing_index(monkeypatch):
    client = FakeEsClient(indexes=[INDEX_META])
    _patch_module(monkeypatch, elasticsearch_index, client)
    _absent_index_args()

    payload = run(elasticsearch_index.run_module)

    assert payload.keys() == {"changed", "index", "tc_api_calls"}
    assert payload["changed"] is True
    assert payload["index"] is None
    assert client.indexes == {}
    delete_request = [request for name, request in client.calls if name == "DeleteIndex"][0]
    assert (delete_request.InstanceId, delete_request.IndexName) == (INSTANCE_ID, INDEX_NAME)


def test_index_absent_missing_index_is_unchanged(monkeypatch):
    client = FakeEsClient()
    _patch_module(monkeypatch, elasticsearch_index, client)
    _absent_index_args()

    payload = run(elasticsearch_index.run_module)

    assert payload.keys() == {"changed", "index", "tc_api_calls"}
    assert payload["changed"] is False
    assert payload["index"] is None
    assert _operations(payload) == ["DescribeIndexMeta"]


def test_index_check_mode_never_writes(monkeypatch):
    client = FakeEsClient()
    _patch_module(monkeypatch, elasticsearch_index, client)
    _index_args(_ansible_check_mode=True)

    payload = run(elasticsearch_index.run_module)

    assert payload["changed"] is True
    assert payload["index"] is None
    assert payload["diff"] == {"before": None, "after": METADATA}
    assert _operations(payload) == ["DescribeIndexMeta"]


def test_index_requires_every_identity_option(monkeypatch):
    _patch_module(monkeypatch, elasticsearch_index, FakeEsClient())
    module_args()

    with pytest.raises(AnsibleFailJson) as failure:
        run(elasticsearch_index.run_module)

    assert failure.value.args[0]["msg"] == "missing required arguments: instance_id, name, password, username"


def test_index_rejects_an_unknown_index_type(monkeypatch):
    _patch_module(monkeypatch, elasticsearch_index, FakeEsClient())
    _index_args(index_type="autonomous")

    with pytest.raises(AnsibleFailJson) as failure:
        run(elasticsearch_index.run_module)

    assert failure.value.args[0]["msg"] == "value of index_type must be one of: normal, auto, got: autonomous"


def test_index_requires_the_metadata_when_present(monkeypatch):
    _patch_module(monkeypatch, elasticsearch_index, FakeEsClient())
    module_args(instance_id=INSTANCE_ID, name=INDEX_NAME, username="elastic", password="s3cret")

    with pytest.raises(AnsibleFailJson) as failure:
        run(elasticsearch_index.run_module)

    assert failure.value.args[0]["msg"] == "state is present but all of the following are missing: metadata"


def test_index_maps_an_sdk_error_to_the_failure_envelope(monkeypatch):
    client = FakeEsClient(error=UnauthorizedError("cluster credential rejected"))
    _patch_module(monkeypatch, elasticsearch_index, client)
    _index_args()

    with pytest.raises(AnsibleFailJson) as failure:
        run(elasticsearch_index.run_module)

    payload = failure.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert payload["error"] == "cluster credential rejected"
    assert payload["error_code"] == "UnauthorizedOperation"
    assert payload["request_id"] == "req-es-denied"
    assert payload["error_kind"] == "unauthorized"


# ---------------------------------------------------------------------------
# elasticsearch_snapshot: request builders
# ---------------------------------------------------------------------------


def _snapshot_params(**overrides):
    params = {
        "instance_id": INSTANCE_ID,
        "repository_name": REPOSITORY,
        "name": SNAPSHOT_NAME,
        "indices": ["*"],
        "repository_type": 0,
        "storage_days": 7,
        "lock_retention": False,
        "retain_until": None,
        "retention_grace_days": 0,
        "remote_cos": False,
        "remote_region": None,
        "multi_az": False,
        "max_snapshot_per_sec": None,
    }
    params.update(overrides)
    return params


def test_snapshot_create_request_sets_the_documented_defaults():
    request = elasticsearch_snapshot.create_request(FakeModels(), _snapshot_params())
    assert (request.InstanceId, request.SnapshotName, request.Indices) == (INSTANCE_ID, SNAPSHOT_NAME, "*")
    assert (request.EsRepositoryType, request.UserEsRepository, request.StorageDuration) == (0, None, 7)
    assert (request.CosRetention, request.RetainUntilDate, request.RetentionGraceTime) == (0, None, 0)
    assert (request.RemoteCos, request.RemoteCosRegion, request.MultiAz, request.MaxSnapshotPerSec) == (0, None, 0, None)


def test_snapshot_create_request_names_the_customer_repository_for_type_one():
    request = elasticsearch_snapshot.create_request(FakeModels(), _snapshot_params(repository_type=1))
    assert (request.EsRepositoryType, request.UserEsRepository) == (1, REPOSITORY)


def test_snapshot_create_request_sorts_the_index_selection():
    request = elasticsearch_snapshot.create_request(FakeModels(), _snapshot_params(indices=["orders", "customers", "orders"]))
    assert request.Indices == "customers,orders"


def test_snapshot_create_request_carries_lock_and_cross_region_options():
    request = elasticsearch_snapshot.create_request(FakeModels(), _snapshot_params(
        lock_retention=True,
        retain_until=RETAIN_UNTIL,
        retention_grace_days=3,
        remote_cos=True,
        remote_region="ap-shanghai",
        multi_az=True,
        max_snapshot_per_sec="40m",
    ))
    assert (request.CosRetention, request.RetainUntilDate, request.RetentionGraceTime) == (1, RETAIN_UNTIL, 3)
    assert (request.RemoteCos, request.RemoteCosRegion, request.MultiAz, request.MaxSnapshotPerSec) == (1, "ap-shanghai", 1, "40m")


def test_snapshot_delete_request_targets_the_repository_and_name():
    request = elasticsearch_snapshot.delete_request(FakeModels(), _snapshot_params())
    assert (request.InstanceId, request.RepositoryName, request.SnapshotName) == (INSTANCE_ID, REPOSITORY, SNAPSHOT_NAME)


# ---------------------------------------------------------------------------
# elasticsearch_snapshot: run_module
# ---------------------------------------------------------------------------


def test_snapshot_present_creates_a_missing_snapshot(monkeypatch):
    client = FakeEsClient()
    clients = _patch_module(monkeypatch, elasticsearch_snapshot, client)
    _snapshot_args()

    payload = run(elasticsearch_snapshot.run_module)

    assert payload.keys() == {"changed", "snapshot", "tc_api_calls"}
    assert payload["changed"] is True
    assert payload["snapshot"]["SnapshotName"] == SNAPSHOT_NAME
    assert payload["snapshot"]["Indices"] == ["customers", "orders"]
    assert payload["snapshot"]["CosRetention"] == 1
    assert payload["snapshot"]["StorageDuration"] == 30
    assert _operations(payload) == ["DescribeClusterSnapshot", "CreateClusterSnapshot", "DescribeClusterSnapshot"]
    assert clients == [(FakeEsClientClass, "es.tencentcloudapi.com")]
    create_request = [request for name, request in client.calls if name == "CreateClusterSnapshot"][0]
    assert (create_request.InstanceId, create_request.SnapshotName) == (INSTANCE_ID, SNAPSHOT_NAME)


def test_snapshot_present_is_idempotent(monkeypatch):
    client = FakeEsClient(snapshots=[SNAPSHOT])
    _patch_module(monkeypatch, elasticsearch_snapshot, client)
    _snapshot_args()

    payload = run(elasticsearch_snapshot.run_module)

    assert payload.keys() == {"changed", "snapshot", "tc_api_calls"}
    assert payload["changed"] is False
    assert payload["snapshot"] == SNAPSHOT
    assert _operations(payload) == ["DescribeClusterSnapshot"]


def test_snapshot_present_is_idempotent_for_an_unlimited_storage_window(monkeypatch):
    """``storage_days: 0`` is legal ("keep forever") and must stay idempotent.

    The API accepts ``[0, INF)`` for ``StorageDuration`` and returns the value
    it stored, so a snapshot created with 0 comes back as 0. Reading that 0 as
    "unset" would report drift on a snapshot that already matches and would
    push the operator towards ``force_replace=true`` -- which deletes and
    recreates it.
    """
    client = FakeEsClient(snapshots=[dict(SNAPSHOT, StorageDuration=0)])
    _patch_module(monkeypatch, elasticsearch_snapshot, client)
    _snapshot_args(storage_days=0)

    payload = run(elasticsearch_snapshot.run_module)

    assert payload["changed"] is False
    assert payload["snapshot"]["StorageDuration"] == 0
    assert _operations(payload) == ["DescribeClusterSnapshot"]


def test_snapshot_present_refuses_immutable_drift_without_force_replace(monkeypatch):
    client = FakeEsClient(snapshots=[SNAPSHOT])
    _patch_module(monkeypatch, elasticsearch_snapshot, client)
    _snapshot_args(indices=["orders"])

    with pytest.raises(AnsibleFailJson) as failure:
        run(elasticsearch_snapshot.run_module)

    payload = failure.value.args[0]
    assert payload["msg"] == "Elasticsearch snapshot configuration is immutable; set force_replace=true to recreate it"
    assert payload["current"]["Indices"] == ["customers", "orders"]
    assert payload["desired"]["Indices"] == ["orders"]
    assert _operations(payload) == ["DescribeClusterSnapshot"]


def test_snapshot_present_force_replace_deletes_before_creating(monkeypatch):
    client = FakeEsClient(snapshots=[SNAPSHOT])
    _patch_module(monkeypatch, elasticsearch_snapshot, client)
    _snapshot_args(indices=["orders"], force_replace=True)

    payload = run(elasticsearch_snapshot.run_module)

    assert payload["changed"] is True
    assert payload["snapshot"]["Indices"] == ["orders"]
    assert _operations(payload) == [
        "DescribeClusterSnapshot", "DeleteClusterSnapshot", "CreateClusterSnapshot", "DescribeClusterSnapshot"
    ]
    assert len(client.snapshots) == 1


def test_snapshot_absent_deletes_the_named_snapshot(monkeypatch):
    client = FakeEsClient(snapshots=[SNAPSHOT])
    _patch_module(monkeypatch, elasticsearch_snapshot, client)
    _snapshot_args(state="absent")

    payload = run(elasticsearch_snapshot.run_module)

    assert payload.keys() == {"changed", "snapshot", "tc_api_calls"}
    assert payload["changed"] is True
    assert payload["snapshot"] is None
    assert client.snapshots == []
    delete_request = [request for name, request in client.calls if name == "DeleteClusterSnapshot"][0]
    assert (delete_request.RepositoryName, delete_request.SnapshotName) == (REPOSITORY, SNAPSHOT_NAME)


def test_snapshot_absent_missing_snapshot_is_unchanged(monkeypatch):
    client = FakeEsClient()
    _patch_module(monkeypatch, elasticsearch_snapshot, client)
    _snapshot_args(state="absent")

    payload = run(elasticsearch_snapshot.run_module)

    assert payload["changed"] is False
    assert payload["snapshot"] is None
    assert _operations(payload) == ["DescribeClusterSnapshot"]


def test_snapshot_check_mode_never_writes(monkeypatch):
    client = FakeEsClient()
    _patch_module(monkeypatch, elasticsearch_snapshot, client)
    _snapshot_args(_ansible_check_mode=True)

    payload = run(elasticsearch_snapshot.run_module)

    assert payload["changed"] is True
    assert payload["snapshot"] is None
    assert payload["diff"]["before"] is None
    assert payload["diff"]["after"]["SnapshotName"] == SNAPSHOT_NAME
    assert _operations(payload) == ["DescribeClusterSnapshot"]


def test_snapshot_requires_every_identity_option(monkeypatch):
    _patch_module(monkeypatch, elasticsearch_snapshot, FakeEsClient())
    module_args()

    with pytest.raises(AnsibleFailJson) as failure:
        run(elasticsearch_snapshot.run_module)

    assert failure.value.args[0]["msg"] == "missing required arguments: instance_id, name, repository_name"


def test_snapshot_requires_retain_until_when_the_snapshot_is_locked(monkeypatch):
    _patch_module(monkeypatch, elasticsearch_snapshot, FakeEsClient())
    _snapshot_args(lock_retention=True, _omit=("retain_until",))

    with pytest.raises(AnsibleFailJson) as failure:
        run(elasticsearch_snapshot.run_module)

    assert failure.value.args[0]["msg"] == "lock_retention is True but all of the following are missing: retain_until"


def test_snapshot_requires_remote_region_for_cross_region_storage(monkeypatch):
    _patch_module(monkeypatch, elasticsearch_snapshot, FakeEsClient())
    _snapshot_args(remote_cos=True, _omit=("remote_region",))

    with pytest.raises(AnsibleFailJson) as failure:
        run(elasticsearch_snapshot.run_module)

    assert failure.value.args[0]["msg"] == "remote_cos is True but all of the following are missing: remote_region"


def test_snapshot_maps_an_sdk_error_to_the_failure_envelope(monkeypatch):
    client = FakeEsClient(error=UnauthorizedError("snapshot repository is not writable"))
    _patch_module(monkeypatch, elasticsearch_snapshot, client)
    _snapshot_args()

    with pytest.raises(AnsibleFailJson) as failure:
        run(elasticsearch_snapshot.run_module)

    payload = failure.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert payload["error"] == "snapshot repository is not writable"
    assert payload["error_code"] == "UnauthorizedOperation"
    assert payload["request_id"] == "req-es-denied"
