"""Main-path (run_module) unit tests for the dlc_table_partition write module.

Complements ``test_dlc_table_partition.py`` (request-builder level) by
driving ``run_module()`` end to end against an in-memory fake DLC client whose
write operations mutate a partition store so post-write ``find`` and waiters
converge.

Scenario matrix:
* validation guards (empty values, delete_data without absent+allow_delete)
* absent flows (missing, allow_delete guard, check mode, real drop)
* creation flows (check mode and real add with wait)
* no-op when nothing drifts
* params/name/storage drift updates through AlterDMSPartition
* multiple-match and SDK failure paths
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import dlc_table_partition as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

PARTITION = {
    "DatabaseName": "analytics",
    "TableName": "daily_sales",
    "DatasourceConnectionName": "DataLakeCatalog",
    "Values": ["2026-08-31"],
    "Name": "sale_date=2026-08-31",
    "Params": [{"Key": "source", "Value": "batch"}],
    "Sds": {"Location": "cosn://analytics-bucket/daily_sales/sale_date=2026-08-31/"},
}


def _partition(**overrides):
    item = copy.deepcopy(PARTITION)
    item.update(overrides)
    return item


def _base(**overrides):
    params = {"database_name": "analytics", "table_name": "daily_sales", "values": ["2026-08-31"]}
    params.update(overrides)
    return module_args(**params)


class FakeDlcClient(object):
    """In-memory DLC client mutating a partition store."""

    def __init__(self, partitions=None):
        self.partitions = [copy.deepcopy(p) for p in (partitions or [])]
        self.calls = []

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def _matching(self, database, table, values):
        return [p for p in self.partitions if p.get("DatabaseName") == database and p.get("TableName") == table and p.get("Values") == values]

    def DescribeDMSPartitions(self, request):
        self._record("DescribeDMSPartitions", request)
        matches = self._matching(
            getattr(request, "DatabaseName", None),
            getattr(request, "TableName", None),
            list(getattr(request, "Values", None) or []),
        )
        return SimpleNamespace(Partitions=[FakeResource(copy.deepcopy(p)) for p in matches], Total=len(matches))

    def AddDMSPartitions(self, request):
        self._record("AddDMSPartitions", request)
        for partition in getattr(request, "Partitions", None) or []:
            item = {k: copy.deepcopy(v) for k, v in vars(partition).items() if not k.startswith("_")}
            item.setdefault("DatasourceConnectionName", "DataLakeCatalog")
            self.partitions.append(item)
        return SimpleNamespace(RequestId="req-fake")

    def AlterDMSPartition(self, request):
        self._record("AlterDMSPartition", request)
        target = getattr(request, "Partition", None)
        database = getattr(request, "CurrentDbName", None)
        table = getattr(request, "CurrentTableName", None)
        self.partitions = [
            p
            for p in self.partitions
            if not (
                p.get("DatabaseName") == database
                and p.get("TableName") == table
                and p.get("Values") == (getattr(target, "Values", None) or p.get("Values"))
            )
        ]
        if target is not None:
            item = {k: copy.deepcopy(v) for k, v in vars(target).items() if not k.startswith("_")}
            item.setdefault("DatasourceConnectionName", getattr(request, "DatasourceConnectionName", "DataLakeCatalog"))
            self.partitions.append(item)
        return SimpleNamespace(RequestId="req-fake")

    def DropDMSPartitions(self, request):
        self._record("DropDMSPartitions", request)
        database = getattr(request, "DatabaseName", None)
        table = getattr(request, "TableName", None)
        values = list(getattr(request, "Values", None) or [])
        self.partitions = [
            p
            for p in self.partitions
            if not (p.get("DatabaseName") == database and p.get("TableName") == table and p.get("Values") == values)
        ]
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake, models=None):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (models or FakeModels(), SimpleNamespace(DlcClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


# ---------------------------------------------------------------------------
# validation guards
# ---------------------------------------------------------------------------


def test_empty_values_fail(monkeypatch):
    fake = FakeDlcClient(partitions=[])
    _make_module(monkeypatch, fake)
    _base(values=[])
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "values must contain at least one" in exc.value.args[0]["msg"]


def test_delete_data_requires_absent_state(monkeypatch):
    fake = FakeDlcClient(partitions=[])
    _make_module(monkeypatch, fake)
    _base(state="present", delete_data=True)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "delete_data requires state=absent and allow_delete=true" in exc.value.args[0]["msg"]


def test_delete_data_requires_allow_delete(monkeypatch):
    fake = FakeDlcClient(partitions=[])
    _make_module(monkeypatch, fake)
    _base(state="absent", delete_data=True)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "delete_data requires state=absent and allow_delete=true" in exc.value.args[0]["msg"]


# ---------------------------------------------------------------------------
# absent flows
# ---------------------------------------------------------------------------


def test_absent_missing_partition_is_idempotent(monkeypatch):
    fake = FakeDlcClient(partitions=[])
    _make_module(monkeypatch, fake)
    _base(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["partition"] is None


def test_absent_requires_allow_delete(monkeypatch):
    fake = FakeDlcClient(partitions=[_partition()])
    _make_module(monkeypatch, fake)
    _base(state="absent")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "allow_delete=true" in exc.value.args[0]["msg"]


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeDlcClient(partitions=[_partition()])
    _make_module(monkeypatch, fake)
    _base(_ansible_check_mode=True, state="absent", allow_delete=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert len(fake.partitions) == 1
    assert "DropDMSPartitions" not in [c for c, unused in fake.calls]


def test_absent_drops_partition(monkeypatch):
    fake = FakeDlcClient(partitions=[_partition()])
    _make_module(monkeypatch, fake)
    _base(state="absent", allow_delete=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert fake.partitions == []
    ops = [c for c, unused in fake.calls]
    assert "DropDMSPartitions" in ops


def test_absent_drops_partition_data(monkeypatch):
    fake = FakeDlcClient(partitions=[_partition()])
    _make_module(monkeypatch, fake)
    _base(state="absent", allow_delete=True, delete_data=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert fake.partitions == []


# ---------------------------------------------------------------------------
# creation flows
# ---------------------------------------------------------------------------


def test_create_partition_check_mode(monkeypatch):
    fake = FakeDlcClient(partitions=[])
    _make_module(monkeypatch, fake)
    _base(
        _ansible_check_mode=True,
        state="present",
        name="sale_date=2026-08-31",
        params={"source": "batch"},
        storage={"location": "cosn://analytics-bucket/daily_sales/sale_date=2026-08-31/"},
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert fake.partitions == []
    assert "AddDMSPartitions" not in [c for c, unused in fake.calls]
    assert result["partition"]["Name"] == "sale_date=2026-08-31"


def test_create_partition(monkeypatch):
    fake = FakeDlcClient(partitions=[])
    _make_module(monkeypatch, fake)
    _base(
        state="present",
        name="sale_date=2026-08-31",
        params={"source": "batch"},
        storage={"location": "cosn://analytics-bucket/daily_sales/sale_date=2026-08-31/"},
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert len(fake.partitions) == 1
    ops = [c for c, unused in fake.calls]
    assert "AddDMSPartitions" in ops
    assert result["partition"]["Params"] == [{"Key": "source", "Value": "batch"}]


# ---------------------------------------------------------------------------
# existing-partition flows
# ---------------------------------------------------------------------------


def test_existing_partition_no_drift_is_idempotent(monkeypatch):
    fake = FakeDlcClient(partitions=[_partition()])
    _make_module(monkeypatch, fake)
    _base(
        state="present",
        name="sale_date=2026-08-31",
        params={"source": "batch"},
        storage={"location": "cosn://analytics-bucket/daily_sales/sale_date=2026-08-31/"},
    )
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["partition"]["Name"] == "sale_date=2026-08-31"


def test_params_drift_alters_partition(monkeypatch):
    fake = FakeDlcClient(partitions=[_partition()])
    _make_module(monkeypatch, fake)
    _base(state="present", params={"source": "realtime"}, wait=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["partition"]["Params"] == [{"Key": "source", "Value": "realtime"}]
    ops = [c for c, unused in fake.calls]
    assert "AlterDMSPartition" in ops


def test_name_drift_alters_partition(monkeypatch):
    fake = FakeDlcClient(partitions=[_partition()])
    _make_module(monkeypatch, fake)
    _base(state="present", name="sale_date=2026-08-31-v2", wait=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["partition"]["Name"] == "sale_date=2026-08-31-v2"


def test_storage_drift_alters_partition_without_current_name(monkeypatch):
    # Partition stored without a Name exercises the alter CurrentValues fallback.
    fake = FakeDlcClient(partitions=[_partition(Name=None)])
    _make_module(monkeypatch, fake)
    _base(state="present", storage={"location": "cosn://new-bucket/daily_sales/part/"}, wait=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["partition"]["Sds"]["Location"] == "cosn://new-bucket/daily_sales/part/"


def test_alter_check_mode_is_dry_run(monkeypatch):
    fake = FakeDlcClient(partitions=[_partition()])
    _make_module(monkeypatch, fake)
    _base(_ansible_check_mode=True, state="present", params={"source": "realtime"})
    result = run(mod.run_module)
    assert result["changed"] is True
    assert fake.partitions[0]["Params"] == [{"Key": "source", "Value": "batch"}]
    assert "AlterDMSPartition" not in [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# failure paths
# ---------------------------------------------------------------------------


def test_multiple_matches_fail(monkeypatch):
    class DupClient(object):
        def DescribeDMSPartitions(self, request):
            return SimpleNamespace(Partitions=[FakeResource(_partition()), FakeResource(_partition(Params=[]))], Total=2)

    fake = DupClient()
    _make_module(monkeypatch, fake)
    _base(state="present")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "Multiple DLC partitions matched" in exc.value.args[0]["msg"]


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeDMSPartitions(self, request):
            raise Boom("connection dropped")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    _base(state="present")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]


# ---------------------------------------------------------------------------
# legacy helper regression tests (folded from test_dlc_table_partition.py)
# ---------------------------------------------------------------------------


class LegacyModel(object):
    def from_json_string(self, value):
        import json

        for key, item in json.loads(value).items():
            setattr(self, key, item)


class LegacyModels(object):
    AddDMSPartitionsRequest = AlterDMSPartitionRequest = DropDMSPartitionsRequest = DescribeDMSPartitionsRequest = DMSPartition = LegacyModel


def legacy_params():
    return {
        "database_name": "analytics",
        "table_name": "sales",
        "values": ["2026-08-31"],
        "schema_name": None,
        "name": "date=2026-08-31",
        "datasource_connection_name": "DataLakeCatalog",
        "params": {"b": "2", "a": "1"},
        "storage": {"location": "cosn://bucket/date=2026-08-31", "serde_params": {"z": "9", "a": "1"}},
        "delete_data": False,
    }


def test_normalization_and_drift_are_semantic():
    p = legacy_params()
    current = mod.normalize(
        {
            "DatabaseName": "analytics",
            "TableName": "sales",
            "Values": ["2026-08-31"],
            "Name": p["name"],
            "DatasourceConnectionName": "DataLakeCatalog",
            "Params": [{"Key": "a", "Value": "1"}, {"Key": "b", "Value": "2"}],
            "Sds": {"Location": p["storage"]["location"], "SerdeParams": [{"Key": "a", "Value": "1"}, {"Key": "z", "Value": "9"}]},
        }
    )
    assert mod.kv(p["params"])[0]["Key"] == "a" and mod.storage(p["storage"])["SerdeParams"][0]["Key"] == "a"
    assert mod.drift(p, current) == {}


def test_requests_preserve_exact_identity_and_delete_data_choice():
    p = legacy_params()
    add = mod.add_request(LegacyModels, p)
    alter = mod.alter_request(LegacyModels, p, {"Name": p["name"]})
    drop = mod.drop_request(LegacyModels, p)
    listing = mod.list_request(LegacyModels, p, 100)
    assert add.Partitions[0].Values == p["values"]
    assert alter.CurrentValues == p["name"] and alter.Partition.Values == p["values"]
    assert drop.Values == p["values"] and drop.DeleteData is False
    assert listing.Values == p["values"] and listing.Offset == 100
