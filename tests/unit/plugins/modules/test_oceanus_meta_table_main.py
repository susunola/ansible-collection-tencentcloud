"""Unit tests for the oceanus_meta_table write module (run_module flows).

``run_module()`` is driven end to end against an in-memory fake Oceanus client
whose create/modify operations mutate the metadata-table store, so the
post-write ``GetMetaTable`` refetch converges immediately. The Oceanus API
does not expose metadata-table deletion, so the module manages the present
lifecycle only: create when missing, update the DDL when it drifts.

Scenario matrix:

* idempotent no-op when the table DDL already matches
* create when absent (check-mode dry run and real ``CreateMetaTable`` with
  captured request fields)
* DDL drift drives ``ModifyMetaTable`` (check mode + real, request fields
  captured)
* argument-validation failure (missing required params) before any SDK call
* the blanket ``sdk_error_payload`` failure path
* legacy helper regression tests (folded from test_oceanus_meta_table.py)
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
import json
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import oceanus_meta_table as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

DDL = "CREATE TABLE orders (id BIGINT) WITH ('connector' = 'kafka')"
UPDATED_DDL = "CREATE TABLE orders (id BIGINT, amount DECIMAL(18, 2)) WITH ('connector' = 'kafka')"


class TableNotFound(Exception):
    def get_code(self):
        return "ResourceNotFound.MetaTable"


def _table(**overrides):
    item = {
        "Catalog": "default_catalog",
        "Database": "production",
        "Table": "orders",
        "DDL": mod.encode_ddl(DDL),
        "SerialId": "meta-1001",
    }
    item.update(overrides)
    return item


def _base(**overrides):
    params = {
        "table_name": "orders",
        "database_name": "production",
        "database_id": 12,
        "catalog_name": "default_catalog",
        "catalog_id": 0,
        "workspace_id": "space-abcdefgh",
        "cluster_id": "cluster-abcdefgh",
        "flink_version": "Flink-1.17",
        "ddl": DDL,
    }
    params.update(overrides)
    return module_args(**params)


class FakeOceanusClient(object):
    """In-memory Oceanus client mutating a metadata-table store."""

    def __init__(self, tables=None):
        self.tables = [copy.deepcopy(t) for t in (tables or [])]
        self.calls = []

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def _find(self, request):
        for table in self.tables:
            if table.get("Catalog") == request.Catalog and table.get("Database") == request.Database \
                    and table.get("Table") == request.Table:
                return table
        return None

    def GetMetaTable(self, request):
        self._record("GetMetaTable", request)
        table = self._find(request)
        if table is None:
            raise TableNotFound("table not found")
        return FakeResource(dict(table))

    def CreateMetaTable(self, request):
        self._record("CreateMetaTable", request)
        payload = {k: copy.deepcopy(v) for k, v in vars(request).items() if not k.startswith("_")}
        table = {
            "Catalog": "default_catalog",
            "Database": "production",
            "Table": "orders",
            "DDL": payload.get("SqlCode"),
            "SerialId": "meta-1001",
        }
        self.tables.append(table)
        return SimpleNamespace(TableId="meta-1001", RequestId="req-fake")

    def ModifyMetaTable(self, request):
        self._record("ModifyMetaTable", request)
        for table in self.tables:
            if table.get("SerialId") == request.TableId:
                table["DDL"] = request.SqlCode
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake, models=None):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (models or FakeModels(), SimpleNamespace(OceanusClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


def _find_call(fake, operation):
    return next(request for name, request in fake.calls if name == operation)


# ---------------------------------------------------------------------------
# idempotent no-op
# ---------------------------------------------------------------------------


def test_matching_ddl_is_idempotent(monkeypatch):
    fake = FakeOceanusClient(tables=[_table()])
    _make_module(monkeypatch, fake)
    _base()
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["meta_table"]["Table"] == "orders"
    assert result["table_id"] == "meta-1001"
    assert [name for name, unused in fake.calls] == ["GetMetaTable"]


# ---------------------------------------------------------------------------
# creation flows
# ---------------------------------------------------------------------------


def test_create_table(monkeypatch):
    fake = FakeOceanusClient(tables=[])
    _make_module(monkeypatch, fake)
    _base()
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["meta_table"]["DDL"] == mod.encode_ddl(DDL)
    assert result["table_id"] == "meta-1001"
    request = _find_call(fake, "CreateMetaTable")
    assert request.WorkSpaceId == "space-abcdefgh"
    assert request.ClusterId == "cluster-abcdefgh"
    assert request.FlinkVersion == "Flink-1.17"
    assert request.SqlCode == mod.encode_ddl(DDL)
    assert request.DatabaseId == 12
    assert len(fake.tables) == 1


def test_create_check_mode_is_dry_run(monkeypatch):
    fake = FakeOceanusClient(tables=[])
    _make_module(monkeypatch, fake)
    _base(_ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["meta_table"]["DDL"] == mod.encode_ddl(DDL)
    assert fake.tables == []
    assert "CreateMetaTable" not in [name for name, unused in fake.calls]


# ---------------------------------------------------------------------------
# DDL update flows
# ---------------------------------------------------------------------------


def test_ddl_drift_updates_table(monkeypatch):
    fake = FakeOceanusClient(tables=[_table()])
    _make_module(monkeypatch, fake)
    _base(ddl=UPDATED_DDL)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["meta_table"]["DDL"] == mod.encode_ddl(UPDATED_DDL)
    assert result["table_id"] == "meta-1001"
    request = _find_call(fake, "ModifyMetaTable")
    assert request.TableId == "meta-1001"
    assert request.SqlCode == mod.encode_ddl(UPDATED_DDL)
    assert request.ClusterId == "cluster-abcdefgh"
    assert request.WorkSpaceId == "space-abcdefgh"
    assert fake.tables[0]["DDL"] == mod.encode_ddl(UPDATED_DDL)


def test_update_check_mode_is_dry_run(monkeypatch):
    fake = FakeOceanusClient(tables=[_table()])
    _make_module(monkeypatch, fake)
    _base(_ansible_check_mode=True, ddl=UPDATED_DDL)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["meta_table"]["DDL"] == mod.encode_ddl(UPDATED_DDL)
    assert fake.tables[0]["DDL"] == mod.encode_ddl(DDL)
    assert "ModifyMetaTable" not in [name for name, unused in fake.calls]


# ---------------------------------------------------------------------------
# argument validation and failure paths
# ---------------------------------------------------------------------------


def test_missing_required_arguments_fail(monkeypatch):
    fake = FakeOceanusClient(tables=[])
    _make_module(monkeypatch, fake)
    module_args(table_name="orders", database_name="production", database_id=12, workspace_id="space-1")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "ddl" in exc.value.args[0]["msg"]
    assert fake.calls == []


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def GetMetaTable(self, request):
            raise Boom("connection dropped")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    _base()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]


# ---------------------------------------------------------------------------
# legacy helper regression tests (folded from test_oceanus_meta_table.py)
# ---------------------------------------------------------------------------


class _Request(object):
    def from_json_string(self, value):
        for key, item in json.loads(value).items():
            setattr(self, key, item)


class _Models(object):
    GetMetaTableRequest = _Request
    CreateMetaTableRequest = _Request


def test_encode_ddl_is_stable_utf8_base64():
    assert mod.encode_ddl("CREATE TABLE 流 (id BIGINT)") == "Q1JFQVRFIFRBQkxFIOa1gSAoaWQgQklHSU5UKQ=="


def test_get_request_uses_fully_qualified_table_identity():
    p = {"catalog_name": "default_catalog", "database_name": "prod", "table_name": "orders", "workspace_id": "space-1"}
    request = mod.get_request(_Models, p)
    assert (request.Catalog, request.Database, request.Table, request.WorkSpaceId) == ("default_catalog", "prod", "orders", "space-1")


def test_create_request_embeds_encoded_sql_and_scope():
    p = {
        "catalog_id": 0, "database_id": 12, "cluster_id": "cluster-1", "flink_version": "Flink-1.17",
        "workspace_id": "space-1", "comment": "orders", "resource_refs": None, "async_task_id": None,
    }
    request = mod.create_request(_Models, p, "ZW5jb2RlZA==")
    payload = vars(request)
    assert payload["DatabaseId"] == 12
    assert payload["SqlCode"] == "ZW5jb2RlZA=="
    assert payload["Comment"] == "orders"
