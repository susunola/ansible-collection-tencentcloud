"""Main-path (run_module) unit tests for the dlc_table write module.

Complements ``test_dlc_table.py`` (request-builder level) by driving
``run_module()`` end to end against an in-memory fake DLC client whose write
operations mutate the metadata-table store so the module's post-write
``find`` refetch and waiters converge immediately.

Scenario matrix:
* absent on a missing table (idempotent no-op)
* absent with a matching table (requires ``allow_delete``, ``has_data``
  guard, check-mode dry run, real delete and delete-with-data)
* creation when missing (columns guard, with/without wait, check mode)
* no-op when nothing drifts
* comment-only update (mutable) and schema/location drift (immutable)
* replacement when ``allow_replace`` authorizes it
* the blanket ``sdk_error_payload`` failure path
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import dlc_table as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

COLUMNS = [
    {"name": "sale_date", "type": "date", "comment": "the date", "nullable": False},
    {"name": "amount", "type": "decimal(18,2)", "precision": 18, "scale": 2},
]

PARTITIONS = [{"name": "sale_date", "type": "date", "comment": "partitioned by date", "transform": "day", "transform_args": ["x"]}]

# Raw table as the DLC catalog would return it (fixed point of normalize()).
TABLE = {
    "TableBaseInfo": {
        "DatabaseName": "analytics",
        "TableName": "daily_sales",
        "DatasourceConnectionName": "DataLakeCatalog",
        "TableComment": "Curated daily sales",
        "Type": "TABLE",
        "TableFormat": "ICEBERG",
        "PrimaryKeys": ["k1"],
    },
    "Columns": [
        {"Name": "sale_date", "Type": "date", "Comment": "the date", "Nullable": False},
        {"Name": "amount", "Type": "decimal(18,2)", "Precision": 18, "Scale": 2},
    ],
    "Partitions": [{"Name": "sale_date", "Type": "date", "Comment": "partitioned by date", "Transform": "day", "TransformArgs": ["x"]}],
    "Location": "cosn://analytics-bucket/daily_sales/",
    "InputFormatShort": "PARQUET",
    "StorageSize": 0,
    "RecordCount": 0,
}


def _table(**overrides):
    item = copy.deepcopy(TABLE)
    item.update(overrides)
    return item


def _base(**overrides):
    params = {"name": "daily_sales", "database_name": "analytics"}
    params.update(overrides)
    return module_args(**params)


class FakeDlcClient(object):
    """In-memory DLC metadata client mutating a table store."""

    def __init__(self, tables=None):
        self.tables = [copy.deepcopy(t) for t in (tables or [])]
        self.calls = []

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def _find(self, database, table, connection):
        for item in self.tables:
            base = item.get("TableBaseInfo") or {}
            if base.get("DatabaseName") == database and base.get("TableName") == table and base.get("DatasourceConnectionName") == connection:
                return item
        return None

    def DescribeTable(self, request):
        self._record("DescribeTable", request)
        item = self._find(
            getattr(request, "DatabaseName", None),
            getattr(request, "TableName", None),
            getattr(request, "DatasourceConnectionName", None),
        )
        return SimpleNamespace(Table=FakeResource(copy.deepcopy(item)) if item else None)

    def CreateTable(self, request):
        self._record("CreateTable", request)
        info = request.TableInfo
        item = {
            "TableBaseInfo": copy.deepcopy(dict(getattr(info, "TableBaseInfo", None) or {})),
            "Columns": copy.deepcopy(list(getattr(info, "Columns", None) or [])),
            "Partitions": copy.deepcopy(list(getattr(info, "Partitions", None) or [])),
            "StorageSize": 0,
            "RecordCount": 0,
        }
        location = getattr(info, "Location", None)
        if location is not None:
            item["Location"] = location
        data_format = getattr(info, "DataFormat", None)
        if data_format:
            item["InputFormatShort"] = next(iter(data_format), None)
        self.tables.append(item)
        return SimpleNamespace(Execution=SimpleNamespace(SQL="CREATE TABLE daily_sales (sale_date date)"), RequestId="req-fake")

    def CreateTasks(self, request):
        self._record("CreateTasks", request)
        return SimpleNamespace(TaskIdSet=["task-1"], RequestId="req-fake")

    def DescribeTaskDetail(self, request):
        self._record("DescribeTaskDetail", request)
        return SimpleNamespace(
            TaskDetail=FakeResource({"State": 2, "OutputMessage": "ok", "TaskId": getattr(request, "TaskInstanceId", None)}),
            RequestId="req-fake",
        )

    def AlterTableComment(self, request):
        self._record("AlterTableComment", request)
        base = getattr(request, "TableBaseInfo", None)
        comment = getattr(base, "TableComment", None)
        for item in self.tables:
            existing = item.get("TableBaseInfo") or {}
            if existing.get("TableName") == getattr(base, "TableName", None) and existing.get("DatabaseName") == getattr(base, "DatabaseName", None):
                existing["TableComment"] = comment
        return SimpleNamespace(RequestId="req-fake")

    def DeleteTable(self, request):
        self._record("DeleteTable", request)
        base = getattr(request, "TableBaseInfo", None)
        kept = []
        for item in self.tables:
            existing = item.get("TableBaseInfo") or {}
            if existing.get("TableName") == getattr(base, "TableName", None) and existing.get("DatabaseName") == getattr(base, "DatabaseName", None):
                continue
            kept.append(item)
        self.tables = kept
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake, models=None):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (models or FakeModels(), SimpleNamespace(DlcClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


# ---------------------------------------------------------------------------
# absent flows
# ---------------------------------------------------------------------------


def test_absent_missing_table_is_idempotent(monkeypatch):
    fake = FakeDlcClient(tables=[])
    _make_module(monkeypatch, fake)
    _base(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["table"] is None
    assert [c for c, unused in fake.calls] == ["DescribeTable"]


def test_absent_requires_allow_delete(monkeypatch):
    fake = FakeDlcClient(tables=[_table()])
    _make_module(monkeypatch, fake)
    _base(state="absent")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "allow_delete=true" in exc.value.args[0]["msg"]


def test_absent_with_data_requires_allow_delete_data(monkeypatch):
    fake = FakeDlcClient(tables=[_table(StorageSize=4096)])
    _make_module(monkeypatch, fake)
    _base(state="absent", allow_delete=True)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "allow_delete_data=true" in exc.value.args[0]["msg"]


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeDlcClient(tables=[_table()])
    _make_module(monkeypatch, fake)
    _base(_ansible_check_mode=True, state="absent", allow_delete=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert len(fake.tables) == 1
    assert "DeleteTable" not in [c for c, unused in fake.calls]


def test_absent_deletes_table(monkeypatch):
    fake = FakeDlcClient(tables=[_table()])
    _make_module(monkeypatch, fake)
    _base(state="absent", allow_delete=True, wait=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["table"] is None
    assert fake.tables == []
    ops = [c for c, unused in fake.calls]
    assert "DeleteTable" in ops


def test_absent_deletes_table_with_data_authorized(monkeypatch):
    fake = FakeDlcClient(tables=[_table(StorageSize=4096, RecordCount=10)])
    _make_module(monkeypatch, fake)
    _base(state="absent", allow_delete=True, allow_delete_data=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert fake.tables == []


# ---------------------------------------------------------------------------
# creation flows
# ---------------------------------------------------------------------------


def test_create_requires_columns(monkeypatch):
    fake = FakeDlcClient(tables=[])
    _make_module(monkeypatch, fake)
    _base(state="present")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "columns are required when creating" in exc.value.args[0]["msg"]


def test_create_table(monkeypatch):
    fake = FakeDlcClient(tables=[])
    _make_module(monkeypatch, fake)
    _base(
        state="present",
        comment="Curated daily sales",
        table_format="ICEBERG",
        location="cosn://analytics-bucket/daily_sales/",
        primary_keys=["k1"],
        columns=COLUMNS,
        partitions=PARTITIONS,
        wait=True,
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["task_ids"] == ["task-1"]
    assert len(fake.tables) == 1
    ops = [c for c, unused in fake.calls]
    assert "CreateTable" in ops
    assert "CreateTasks" in ops
    assert "DescribeTaskDetail" in ops
    assert result["table"]["TableBaseInfo"]["TableName"] == "daily_sales"


def test_create_check_mode_is_dry_run(monkeypatch):
    fake = FakeDlcClient(tables=[])
    _make_module(monkeypatch, fake)
    _base(
        _ansible_check_mode=True,
        state="present",
        columns=COLUMNS,
        partitions=PARTITIONS,
        location="cosn://analytics-bucket/daily_sales/",
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert fake.tables == []
    assert "CreateTable" not in [c for c, unused in fake.calls]
    assert result["table"]["TableBaseInfo"]["TableName"] == "daily_sales"


# ---------------------------------------------------------------------------
# existing-table flows
# ---------------------------------------------------------------------------


def test_existing_table_no_drift_is_idempotent(monkeypatch):
    fake = FakeDlcClient(tables=[_table()])
    _make_module(monkeypatch, fake)
    _base(
        state="present",
        comment="Curated daily sales",
        table_type="TABLE",
        table_format="ICEBERG",
        data_format="Parquet",
        location="cosn://analytics-bucket/daily_sales/",
        primary_keys=["k1"],
        columns=COLUMNS,
        partitions=PARTITIONS,
    )
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["table"]["TableBaseInfo"]["TableName"] == "daily_sales"


def test_comment_only_drift_updates_comment(monkeypatch):
    fake = FakeDlcClient(tables=[_table()])
    _make_module(monkeypatch, fake)
    _base(state="present", comment="Updated table comment", wait=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["table"]["TableBaseInfo"]["TableComment"] == "Updated table comment"
    ops = [c for c, unused in fake.calls]
    assert "AlterTableComment" in ops


def test_comment_only_drift_check_mode(monkeypatch):
    fake = FakeDlcClient(tables=[_table()])
    _make_module(monkeypatch, fake)
    _base(_ansible_check_mode=True, state="present", comment="New comment")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert "AlterTableComment" not in [c for c, unused in fake.calls]
    assert result["table"]["TableBaseInfo"]["TableComment"] == "New comment"


def test_schema_drift_requires_allow_replace(monkeypatch):
    fake = FakeDlcClient(tables=[_table()])
    _make_module(monkeypatch, fake)
    _base(
        state="present",
        columns=[{"name": "extra_column", "type": "string"}],
    )
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "allow_replace=true" in payload["msg"]
    assert "Columns" in payload["immutable_drift"]


def test_location_drift_requires_allow_replace(monkeypatch):
    fake = FakeDlcClient(tables=[_table()])
    _make_module(monkeypatch, fake)
    _base(state="present", location="cosn://other-bucket/sales/")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "Location" in exc.value.args[0]["immutable_drift"]


def test_replace_with_data_requires_allow_delete_data(monkeypatch):
    fake = FakeDlcClient(tables=[_table(StorageSize=8192)])
    _make_module(monkeypatch, fake)
    _base(state="present", allow_replace=True, columns=[{"name": "extra_column", "type": "string"}])
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "allow_delete_data=true" in exc.value.args[0]["msg"]


def test_replace_requires_columns(monkeypatch):
    fake = FakeDlcClient(tables=[_table()])
    _make_module(monkeypatch, fake)
    _base(state="present", data_format="ORC", allow_replace=True, allow_delete_data=True)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "columns are required when replacing" in exc.value.args[0]["msg"]


def test_authorized_replace_recreates_table(monkeypatch):
    fake = FakeDlcClient(tables=[_table()])
    _make_module(monkeypatch, fake)
    _base(
        state="present",
        allow_replace=True,
        allow_delete_data=True,
        columns=[{"name": "extra_column", "type": "string"}],
        location="cosn://analytics-bucket/daily_sales/",
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert len(fake.tables) == 1
    ops = [c for c, unused in fake.calls]
    assert "DeleteTable" in ops
    assert "CreateTable" in ops


# ---------------------------------------------------------------------------
# validation / failure paths
# ---------------------------------------------------------------------------


def test_duplicate_column_names_fail(monkeypatch):
    fake = FakeDlcClient(tables=[])
    _make_module(monkeypatch, fake)
    _base(state="present", columns=[{"name": "a", "type": "string"}, {"name": "a", "type": "int"}])
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "column names must be unique" in exc.value.args[0]["msg"]


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeTable(self, request):
            raise Boom("connection dropped")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    _base(state="present")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]
