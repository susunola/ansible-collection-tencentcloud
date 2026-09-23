"""Unit tests for the tione_data_source write module (run_module flows).

Drives ``run_module()`` end to end against an in-memory fake TIONE client
whose write operations mutate the data-source store, so the module's
post-write ``find`` refetch and waiters converge immediately.

Scenario matrix:

* pre-SDK validation (identity requirements for present/absent)
* absent on a missing data source (idempotent no-op), allow_delete guard,
  check-mode dry run and the real delete path
* existing data source no-drift idempotency and immutable-drift failure
* unknown data_source_id, missing creation params, create happy path and
  its check-mode dry run
* multiple-match guard and the blanket ``sdk_error_payload`` failure path
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import tione_data_source as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

DATA_SOURCE = {
    "Id": "datasource-8b0a1c2d",
    "Name": "shared-training-cfs",
    "Type": "CFS",
    "Permission": "RW",
    "StorageId": "cfs-123",
    "MountConfigure": {"WorkDir": "/training", "MountPath": "/data"},
    "Tags": [{"TagKey": "environment", "TagValue": "production"}],
}

MOUNT_CONFIG = {"WorkDir": "/training", "MountPath": "/data"}

TAGS = [{"TagKey": "environment", "TagValue": "production"}]


def _data_source(**overrides):
    item = copy.deepcopy(DATA_SOURCE)
    item.update(overrides)
    return item


def _plain(value):
    """Recursively unwrap FakeRequest/model stand-ins into plain data."""
    if value is None or isinstance(value, bool) or isinstance(value, (str, int, float)):
        return value
    if isinstance(value, list):
        return [_plain(item) for item in value]
    if isinstance(value, tuple):
        return [_plain(item) for item in value]
    if isinstance(value, dict):
        return {key: _plain(item) for key, item in value.items()}
    return {key: _plain(item) for key, item in vars(value).items()}


class FakeTioneDataSourceClient(object):
    """In-memory TIONE client mutating a data-source store."""

    def __init__(self, sources=None):
        self.sources = [copy.deepcopy(t) for t in (sources or [])]
        self.calls = []
        self._next = 0

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def _by_id(self, data_source_id):
        for item in self.sources:
            if item.get("Id") == data_source_id:
                return item
        return None

    def DescribeDataSource(self, request):
        self._record("DescribeDataSource", request)
        source = self._by_id(getattr(request, "Id", None))
        return SimpleNamespace(DataSourceInfo=FakeResource(source) if source else None)

    def DescribeDataSources(self, request):
        self._record("DescribeDataSources", request)
        name = request.Filters[0].Values[0]
        matches = [item for item in self.sources if item.get("Name") == name]
        return SimpleNamespace(
            DataSourceInfos=[FakeResource(item) for item in matches],
            TotalCount=len(matches),
        )

    def CreateDataSource(self, request):
        self._record("CreateDataSource", request)
        self._next += 1
        item = {"Id": "datasource-new-%03d" % self._next}
        for key, value in vars(request).items():
            item[key] = _plain(value)
        self.sources.append(item)
        return SimpleNamespace(Id=item["Id"], RequestId="req-fake")

    def DeleteDataSource(self, request):
        self._record("DeleteDataSource", request)
        data_source_id = getattr(request, "Id", None)
        self.sources = [item for item in self.sources if item.get("Id") != data_source_id]
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake, models=None):
    """Wire the shared monkeypatches; returns the fake client."""
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (models or FakeModels(), SimpleNamespace(TioneClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


def _source_args(**overrides):
    params = {
        "name": "shared-training-cfs",
        "source_type": "CFS",
        "permission": "RW",
        "storage_id": "cfs-123",
        "mount_config": copy.deepcopy(MOUNT_CONFIG),
        "tags": copy.deepcopy(TAGS),
    }
    params.update(overrides)
    return module_args(**params)


# ---------------------------------------------------------------------------
# validation / absent flows
# ---------------------------------------------------------------------------


def test_present_requires_identity(monkeypatch):
    fake = FakeTioneDataSourceClient(sources=[])
    _make_module(monkeypatch, fake)
    module_args(state="present")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "name or data_source_id is required when state=present" in exc.value.args[0]["msg"]


def test_absent_requires_data_source_id(monkeypatch):
    fake = FakeTioneDataSourceClient(sources=[])
    _make_module(monkeypatch, fake)
    module_args(state="absent")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "data_source_id is required for safe deletion" in exc.value.args[0]["msg"]


def test_absent_missing_source_is_idempotent(monkeypatch):
    fake = FakeTioneDataSourceClient(sources=[])
    _make_module(monkeypatch, fake)
    module_args(state="absent", data_source_id="datasource-ghost")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["data_source"] is None
    assert result["data_source_id"] == "datasource-ghost"


def test_absent_requires_allow_delete(monkeypatch):
    fake = FakeTioneDataSourceClient(sources=[_data_source()])
    _make_module(monkeypatch, fake)
    module_args(state="absent", data_source_id="datasource-8b0a1c2d")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "allow_delete=true is required" in exc.value.args[0]["msg"]


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeTioneDataSourceClient(sources=[_data_source()])
    _make_module(monkeypatch, fake)
    module_args(_ansible_check_mode=True, state="absent", data_source_id="datasource-8b0a1c2d", allow_delete=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert len(fake.sources) == 1
    assert "DeleteDataSource" not in [c for c, unused in fake.calls]


def test_absent_deletes_source(monkeypatch):
    fake = FakeTioneDataSourceClient(sources=[_data_source()])
    _make_module(monkeypatch, fake)
    module_args(state="absent", data_source_id="datasource-8b0a1c2d", allow_delete=True, wait=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert fake.sources == []
    assert "DeleteDataSource" in [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# existing-source flows
# ---------------------------------------------------------------------------


def test_existing_source_no_drift_is_idempotent(monkeypatch):
    fake = FakeTioneDataSourceClient(sources=[_data_source()])
    _make_module(monkeypatch, fake)
    _source_args()
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["data_source"]["Id"] == "datasource-8b0a1c2d"
    assert result["data_source_id"] == "datasource-8b0a1c2d"


def test_existing_source_drift_fails(monkeypatch):
    fake = FakeTioneDataSourceClient(sources=[_data_source()])
    _make_module(monkeypatch, fake)
    _source_args(permission="RO")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "immutable drift" in payload["msg"]
    assert "Permission" in payload["immutable_drift"]


# ---------------------------------------------------------------------------
# creation flows
# ---------------------------------------------------------------------------


def test_unknown_data_source_id_fails(monkeypatch):
    fake = FakeTioneDataSourceClient(sources=[])
    _make_module(monkeypatch, fake)
    module_args(state="present", data_source_id="datasource-ghost")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "data_source_id does not exist" in exc.value.args[0]["msg"]


def test_create_requires_creation_parameters(monkeypatch):
    fake = FakeTioneDataSourceClient(sources=[])
    _make_module(monkeypatch, fake)
    module_args(state="present", name="shared-training-cfs")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "creation parameters are required" in payload["msg"]
    assert payload["missing"] == ["source_type", "permission", "storage_id"]


def test_create_data_source(monkeypatch):
    fake = FakeTioneDataSourceClient(sources=[])
    _make_module(monkeypatch, fake)
    _source_args(wait=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["data_source"]["Name"] == "shared-training-cfs"
    assert result["data_source"]["Type"] == "CFS"
    assert result["data_source_id"].startswith("datasource-new-")
    assert len(fake.sources) == 1
    ops = [c for c, unused in fake.calls]
    assert "CreateDataSource" in ops
    assert ops[-1] == "DescribeDataSource"


def test_create_check_mode_is_dry_run(monkeypatch):
    fake = FakeTioneDataSourceClient(sources=[])
    _make_module(monkeypatch, fake)
    _source_args(_ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["data_source_id"] is None
    assert result["data_source"]["Name"] == "shared-training-cfs"
    assert fake.sources == []
    assert "CreateDataSource" not in [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# guards / failure paths
# ---------------------------------------------------------------------------


def test_multiple_matches_fail(monkeypatch):
    fake = FakeTioneDataSourceClient(sources=[_data_source(), _data_source(Id="datasource-dup")])
    _make_module(monkeypatch, fake)
    _source_args()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "Multiple TIONE data sources matched" in exc.value.args[0]["msg"]


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeDataSources(self, request):
            raise Boom("metadata service down")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    _source_args()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "metadata service down" in payload["error"]
