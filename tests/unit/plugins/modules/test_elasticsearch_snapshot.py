"""Unit tests for the elasticsearch_snapshot write module (helpers + run_module).

Covers the create / destroy / force-replace flows of
``plugins/modules/elasticsearch_snapshot.py`` with an in-memory fake
Elasticsearch client whose write operations mutate the snapshot store, so
the module's post-write ``find`` refetch converges immediately. Snapshots
are matched by ``SnapshotName`` inside the describe ``Snapshots`` list;
``Indices`` is sent to the API as a sorted-deduped CSV string but compared
(and stored) as a sorted list. Snapshot configuration is immutable: any
drift on an existing snapshot fails unless ``force_replace=true``, which
deletes then recreates. ``required_if`` guards ``lock_retention`` ->
``retain_until`` and ``remote_cos`` -> ``remote_region``.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import elasticsearch_snapshot as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

SNAPSHOT = {
    "SnapshotName": "before-upgrade",
    "Indices": ["customers", "orders"],
    "EsRepositoryType": 0,
    "StorageDuration": 7,
    "CosRetention": 0,
    "RetainUntilDate": None,
    "RetentionGraceTime": 0,
    "RemoteCos": 0,
    "RemoteCosRegion": None,
    "MultiAz": 0,
    "MaxSnapshotPerSec": None,
}


def _snapshot(**overrides):
    """API-shaped snapshot dict isolated from the shared constant."""
    item = copy.deepcopy(SNAPSHOT)
    item.update(overrides)
    return item


def _params(**overrides):
    """Module parameters pre-filled from the argument spec defaults."""
    params = {
        "state": "present",
        "instance_id": "es-abc123",
        "repository_name": "repo-main",
        "name": "before-upgrade",
        "indices": ["orders", "customers"],  # deliberately unsorted input
        "repository_type": 0,
        "storage_days": 7,
        "lock_retention": False,
        "retain_until": None,
        "retention_grace_days": 0,
        "remote_cos": False,
        "remote_region": None,
        "multi_az": False,
        "max_snapshot_per_sec": None,
        "force_replace": False,
    }
    params.update(overrides)
    return params


def _run_args(**extra):
    """module_args() pre-filled with every module parameter (None dropped)."""
    args = dict(_params())
    args.update(extra)
    return module_args(**{k: v for k, v in args.items() if v is not None})


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


class FakeEsClient(object):
    """In-memory EsClient stand-in for cluster snapshots.

    ``DescribeClusterSnapshot`` returns the stored ``Snapshots`` list (each
    item serialized the way the module inspects them); writes mutate the
    store so post-write refetches converge. ``CreateClusterSnapshot``
    stores the API-shaped dict with ``Indices`` split back into a sorted
    list, mirroring how ``comparable`` normalises the field.
    """

    def __init__(self, snapshots=None):
        self.snapshots = [copy.deepcopy(s) for s in (snapshots or [])]
        self.calls = []

    def _record(self, name, request):
        self.calls.append((name, request))
        return request

    def DescribeClusterSnapshot(self, request):
        self._record("DescribeClusterSnapshot", request)
        return SimpleNamespace(
            Snapshots=[FakeResource(dict(s)) for s in self.snapshots],
            RequestId="req-fake",
        )

    def DeleteClusterSnapshot(self, request):
        self._record("DeleteClusterSnapshot", request)
        self.snapshots = [s for s in self.snapshots if s.get("SnapshotName") != request.SnapshotName]
        return SimpleNamespace(RequestId="req-fake")

    def CreateClusterSnapshot(self, request):
        self._record("CreateClusterSnapshot", request)
        self.snapshots.append(
            {
                "SnapshotName": request.SnapshotName,
                "Indices": sorted(set(request.Indices.split(","))),
                "EsRepositoryType": request.EsRepositoryType,
                "UserEsRepository": getattr(request, "UserEsRepository", None),
                "StorageDuration": request.StorageDuration,
                "CosRetention": request.CosRetention,
                "RetainUntilDate": getattr(request, "RetainUntilDate", None),
                "RetentionGraceTime": request.RetentionGraceTime,
                "RemoteCos": request.RemoteCos,
                "RemoteCosRegion": getattr(request, "RemoteCosRegion", None),
                "MultiAz": request.MultiAz,
                "MaxSnapshotPerSec": getattr(request, "MaxSnapshotPerSec", None),
            }
        )
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake):
    """Wire the shared monkeypatches and return the fake client."""
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(
        mod,
        "_load",
        lambda: (FakeModels(), SimpleNamespace(EsClient=object)),
    )
    monkeypatch.setattr(
        TencentCloudModule,
        "create_client",
        lambda self, client_class, endpoint: fake,
    )
    return fake


class _BoomClient(object):
    """Every SDK call raises, so the module's wrapped error path is hit."""

    def __getattr__(self, name):
        def boom(*args, **kwargs):
            raise RuntimeError("service exploded")

        return boom


# ---------------------------------------------------------------------------
# request-builder / normalisation helper tests
# ---------------------------------------------------------------------------


def test_describe_request_fields():
    request = mod.describe_request(FakeModels(), _params())
    assert request.InstanceId == "es-abc123"
    assert request.RepositoryName == "repo-main"
    assert request.SnapshotName == "before-upgrade"


def test_create_request_core_fields():
    request = mod.create_request(FakeModels(), _params())
    assert request.InstanceId == "es-abc123"
    assert request.SnapshotName == "before-upgrade"
    assert request.EsRepositoryType == 0
    assert request.UserEsRepository is None
    assert request.StorageDuration == 7
    assert request.CosRetention == 0
    assert request.RetainUntilDate is None
    assert request.RetentionGraceTime == 0
    assert request.RemoteCos == 0
    assert request.MultiAz == 0


def test_create_request_indices_csv_is_sorted_deduped():
    request = mod.create_request(FakeModels(), _params(indices=["orders", "customers", "orders"]))
    assert request.Indices == "customers,orders"
    request = mod.create_request(FakeModels(), _params(indices=["*"]))
    assert request.Indices == "*"


def test_create_request_repository_type_one_sets_user_repository():
    request = mod.create_request(FakeModels(), _params(repository_type=1))
    assert request.UserEsRepository == "repo-main"


def test_create_request_full_options():
    request = mod.create_request(
        FakeModels(),
        _params(
            storage_days=30,
            lock_retention=True,
            retain_until="2027-01-01T00:00:00Z",
            retention_grace_days=5,
            remote_cos=True,
            remote_region="ap-shanghai",
            multi_az=True,
            max_snapshot_per_sec="20mb",
        ),
    )
    assert request.StorageDuration == 30
    assert request.CosRetention == 1
    assert request.RetainUntilDate == "2027-01-01T00:00:00Z"
    assert request.RetentionGraceTime == 5
    assert request.RemoteCos == 1
    assert request.RemoteCosRegion == "ap-shanghai"
    assert request.MultiAz == 1
    assert request.MaxSnapshotPerSec == "20mb"


def test_delete_request_fields():
    request = mod.delete_request(FakeModels(), _params())
    assert request.InstanceId == "es-abc123"
    assert request.RepositoryName == "repo-main"
    assert request.SnapshotName == "before-upgrade"


def test_comparable_sorts_indices_and_applies_defaults():
    value = {
        "SnapshotName": "before-upgrade",
        "Indices": ["orders", "customers"],
        "EsRepositoryType": 1,
        "StorageDuration": 30,
        "CosRetention": 1,
        "RemoteCos": 1,
        "MultiAz": 1,
    }
    result = mod.comparable(value)
    assert result["SnapshotName"] == "before-upgrade"
    assert result["Indices"] == ["customers", "orders"]
    assert result["EsRepositoryType"] == 1
    assert result["StorageDuration"] == 30
    assert result["CosRetention"] == 1
    assert result["RetentionGraceTime"] == 0  # missing -> default 0
    assert result["RemoteCos"] == 1
    assert result["MultiAz"] == 1


def test_comparable_missing_storage_defaults_to_seven():
    result = mod.comparable({"SnapshotName": "x", "Indices": ["a"]})
    assert result["StorageDuration"] == 7
    assert result["EsRepositoryType"] == 0
    assert result["RemoteCos"] == 0


def test_desired_maps_params():
    target = mod.desired(_params())
    assert target["SnapshotName"] == "before-upgrade"
    assert target["Indices"] == ["customers", "orders"]
    assert target["EsRepositoryType"] == 0
    assert target["StorageDuration"] == 7
    assert target["CosRetention"] == 0
    assert target["RetainUntilDate"] is None
    assert target["RetentionGraceTime"] == 0
    assert target["RemoteCos"] == 0
    assert target["RemoteCosRegion"] is None
    assert target["MultiAz"] == 0
    assert target["MaxSnapshotPerSec"] is None


# ---------------------------------------------------------------------------
# find tests
# ---------------------------------------------------------------------------


def test_find_matches_snapshot_by_name(monkeypatch):
    fake = FakeEsClient([_snapshot(), _snapshot(SnapshotName="nightly", Indices=["a"])])
    _make_module(monkeypatch, fake)
    module = FakeModule()
    value = mod.find(module, fake, FakeModels(), module.params)
    assert value["SnapshotName"] == "before-upgrade"
    assert value["Indices"] == ["customers", "orders"]


def test_find_no_match_returns_none(monkeypatch):
    fake = FakeEsClient([_snapshot(SnapshotName="nightly")])
    _make_module(monkeypatch, fake)
    module = FakeModule()
    assert mod.find(module, fake, FakeModels(), module.params) is None


def test_find_empty_store_returns_none(monkeypatch):
    fake = FakeEsClient()
    _make_module(monkeypatch, fake)
    module = FakeModule()
    assert mod.find(module, fake, FakeModels(), module.params) is None


# ---------------------------------------------------------------------------
# run_module main-path tests
# ---------------------------------------------------------------------------


def test_present_creates_snapshot(monkeypatch):
    fake = FakeEsClient()
    _make_module(monkeypatch, fake)
    _run_args()
    result = run(mod.run_module)
    assert result["changed"] is True
    snapshot = result["snapshot"]
    assert snapshot["SnapshotName"] == "before-upgrade"
    assert snapshot["Indices"] == ["customers", "orders"]
    assert snapshot["EsRepositoryType"] == 0
    assert snapshot["StorageDuration"] == 7
    names = [c[0] for c in fake.calls]
    assert names.count("DescribeClusterSnapshot") == 2  # find + refetch
    assert names.count("CreateClusterSnapshot") == 1
    assert "DeleteClusterSnapshot" not in names
    create = [c for c in fake.calls if c[0] == "CreateClusterSnapshot"][0][1]
    assert create.Indices == "customers,orders"
    assert create.UserEsRepository is None


def test_present_creates_customer_repository_snapshot(monkeypatch):
    fake = FakeEsClient()
    _make_module(monkeypatch, fake)
    _run_args(repository_type=1)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["snapshot"]["EsRepositoryType"] == 1
    create = [c for c in fake.calls if c[0] == "CreateClusterSnapshot"][0][1]
    assert create.UserEsRepository == "repo-main"


def test_present_full_lock_options_round_trip(monkeypatch):
    fake = FakeEsClient()
    _make_module(monkeypatch, fake)
    _run_args(
        storage_days=30,
        lock_retention=True,
        retain_until="2027-01-01T00:00:00Z",
        remote_cos=True,
        remote_region="ap-shanghai",
        multi_az=True,
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    snapshot = result["snapshot"]
    assert snapshot["StorageDuration"] == 30
    assert snapshot["CosRetention"] == 1
    assert snapshot["RetainUntilDate"] == "2027-01-01T00:00:00Z"
    assert snapshot["RemoteCos"] == 1
    assert snapshot["RemoteCosRegion"] == "ap-shanghai"
    assert snapshot["MultiAz"] == 1


def test_present_noop_when_matching(monkeypatch):
    # params carry unsorted indices but the stored list is sorted: no drift
    fake = FakeEsClient([_snapshot()])
    _make_module(monkeypatch, fake)
    _run_args()
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["snapshot"]["SnapshotName"] == "before-upgrade"
    assert [c[0] for c in fake.calls] == ["DescribeClusterSnapshot"]


def test_present_storage_drift_is_immutable(monkeypatch):
    fake = FakeEsClient([_snapshot()])
    _make_module(monkeypatch, fake)
    _run_args(storage_days=30)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Elasticsearch snapshot configuration is immutable; set force_replace=true to recreate it"
    assert payload["current"]["StorageDuration"] == 7
    assert payload["desired"]["StorageDuration"] == 30
    assert not any("DeleteClusterSnapshot" == c[0] for c in fake.calls)


def test_present_indices_drift_is_immutable(monkeypatch):
    fake = FakeEsClient([_snapshot()])
    _make_module(monkeypatch, fake)
    _run_args(indices=["orders", "customers", "archive"])
    with pytest.raises(AnsibleFailJson):
        run(mod.run_module)


def test_present_drift_force_replace_recreates(monkeypatch):
    fake = FakeEsClient([_snapshot()])
    _make_module(monkeypatch, fake)
    _run_args(storage_days=30, force_replace=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["snapshot"]["StorageDuration"] == 30
    names = [c[0] for c in fake.calls]
    assert names == ["DescribeClusterSnapshot", "DeleteClusterSnapshot", "CreateClusterSnapshot", "DescribeClusterSnapshot"]
    assert len(fake.snapshots) == 1


def test_absent_not_found_is_noop(monkeypatch):
    fake = FakeEsClient([_snapshot(SnapshotName="nightly")])
    _make_module(monkeypatch, fake)
    _run_args(state="absent", name="ghost")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["snapshot"] is None
    assert not any("DeleteClusterSnapshot" == c[0] for c in fake.calls)


def test_absent_deletes_snapshot(monkeypatch):
    fake = FakeEsClient([_snapshot()])
    _make_module(monkeypatch, fake)
    _run_args(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["snapshot"] is None
    delete = [c for c in fake.calls if c[0] == "DeleteClusterSnapshot"][0][1]
    assert delete.SnapshotName == "before-upgrade"
    assert fake.snapshots == []


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeEsClient([_snapshot()])
    _make_module(monkeypatch, fake)
    module_args(_ansible_check_mode=True, **{k: v for k, v in _params(state="absent").items() if v is not None})
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["snapshot"]["SnapshotName"] == "before-upgrade"  # pre-change snapshot
    assert not any("DeleteClusterSnapshot" == c[0] for c in fake.calls)
    assert len(fake.snapshots) == 1


def test_check_mode_create_reports_none(monkeypatch):
    fake = FakeEsClient()
    _make_module(monkeypatch, fake)
    module_args(_ansible_check_mode=True, **{k: v for k, v in _params().items() if v is not None})
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["snapshot"] is None  # no refetch in check mode
    assert [c[0] for c in fake.calls] == ["DescribeClusterSnapshot"]
    assert not any("CreateClusterSnapshot" == c[0] for c in fake.calls)


def test_check_mode_force_replace_reports_pre_change(monkeypatch):
    fake = FakeEsClient([_snapshot()])
    _make_module(monkeypatch, fake)
    module_args(_ansible_check_mode=True, **{k: v for k, v in _params(storage_days=30, force_replace=True).items() if v is not None})
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["snapshot"]["StorageDuration"] == 7  # pre-change snapshot
    assert not any("DeleteClusterSnapshot" == c[0] for c in fake.calls)
    assert not any("CreateClusterSnapshot" == c[0] for c in fake.calls)


def test_lock_retention_requires_retain_until():
    _run_args(lock_retention=True)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "retain_until" in exc.value.args[0]["msg"]


def test_remote_cos_requires_remote_region():
    _run_args(remote_cos=True)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "remote_region" in exc.value.args[0]["msg"]


def test_sdk_error_is_reported(monkeypatch):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(
        mod,
        "_load",
        lambda: (FakeModels(), SimpleNamespace(EsClient=object)),
    )
    monkeypatch.setattr(
        TencentCloudModule,
        "create_client",
        lambda self, client_class, endpoint: _BoomClient(),
    )
    _run_args()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert payload["error"] == "service exploded"
