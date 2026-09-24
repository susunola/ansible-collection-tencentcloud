#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r"""
---
module: dlc_table
short_description: Manage Tencent Cloud DLC metadata tables
version_added: "0.14.0"
description:
  - Generates table DDL with DLC, submits it as an SQL task and verifies the resulting table through the catalog.
  - Table comments are updated in place; immutable schema and storage drift requires explicitly authorized replacement.
options:
  state:
    description:
      - Desired table state.
    type: str
    choices: [present, absent]
    default: present
  name:
    description:
      - Exact table name.
    type: str
    required: true
  database_name:
    description:
      - Parent database name.
    type: str
    required: true
  datasource_connection_name:
    description:
      - Catalog or data-source connection name.
    type: str
    default: DataLakeCatalog
  comment:
    description:
      - Table comment.
    type: str
  table_type:
    description:
      - Catalog table type.
    type: str
    default: TABLE
  table_format:
    description:
      - Table storage format such as HIVE, ICEBERG or LAKEFS.
    type: str
  data_format:
    description:
      - Physical data format.
    type: str
    choices: [TextFile, CSV, Json, Parquet, ORC, AVRO]
    default: Parquet
  location:
    description:
      - COS table location.
    type: str
  primary_keys:
    description:
      - T-Iceberg primary-key columns.
    type: list
    elements: str
  columns:
    type: list
    elements: dict
    description: Ordered table columns; required on creation.
    suboptions:
      name:
        description:
          - Column name.
        type: str
        required: true
      type:
        description:
          - DLC column type.
        type: str
        required: true
      comment:
        description:
          - Column comment.
        type: str
      precision:
        description:
          - Decimal precision.
        type: int
      scale:
        description:
          - Decimal scale.
        type: int
      nullable:
        description:
          - Whether the column accepts null values.
        type: bool
  partitions:
    type: list
    elements: dict
    description: Ordered partition definition.
    suboptions:
      name:
        description:
          - Partition column name.
        type: str
        required: true
      type:
        description:
          - Partition type.
        type: str
        required: true
      comment:
        description:
          - Partition comment.
        type: str
      transform:
        description:
          - Iceberg transform strategy.
        type: str
      transform_args:
        description:
          - Transform arguments.
        type: list
        elements: str
  data_engine_name:
    description:
      - Data engine used to execute generated DDL.
    type: str
  resource_group_name:
    description:
      - Spark resource group used for DDL execution.
    type: str
  allow_replace:
    description:
      - Explicitly authorize delete-and-recreate for immutable schema drift.
    type: bool
    default: false
  allow_delete:
    description:
      - Explicitly authorize table deletion.
    type: bool
    default: false
  allow_delete_data:
    description:
      - Explicitly authorize deletion or replacement when the catalog reports stored data.
    type: bool
    default: false
  wait:
    description:
      - Wait for DDL task and catalog convergence.
    type: bool
    default: true

  waiter_timeout:
    description:
      - Overall convergence timeout.
    type: int
    default: 900

extends_documentation_fragment:
  - susunola.tencentcloud.credentials
  - susunola.tencentcloud.region
  - susunola.tencentcloud.connection
  - susunola.tencentcloud.timeout
  - susunola.tencentcloud.retry
  - susunola.tencentcloud.user_agent
  - susunola.tencentcloud.waiter
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.dlc_table:
    database_name: analytics
    name: daily_sales
    comment: Curated daily sales
    table_format: ICEBERG
    data_format: Parquet
    location: cosn://analytics-bucket/daily_sales/
    columns:
      - {name: sale_date, type: date, nullable: false}
      - {name: amount, type: decimal, precision: 18, scale: 2}
    partitions:
      - {name: sale_date, type: date, transform: day}

- susunola.tencentcloud.dlc_table:
    database_name: analytics
    name: daily_sales
    state: absent
    allow_delete: true
"""
RETURN = r"""
table: {description: Effective DLC catalog table., type: dict, returned: always}
task_ids: {description: DDL task IDs submitted during creation., type: list, elements: str, returned: when created}
"""

import base64
import json
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.errors import is_not_found
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import fail_from_sdk_error
from ansible_collections.susunola.tencentcloud.plugins.module_utils.waiters import wait_for_state, wait_for_task


def _load():
    from tencentcloud.dlc.v20210125 import models, dlc_client

    return models, dlc_client


def _model(cls, value):
    item = cls()
    item.from_json_string(json.dumps(value))
    return item


def column(value, position=None):
    result = {}
    for source, target in (("name", "Name"), ("type", "Type"), ("comment", "Comment"), ("precision", "Precision"), ("scale", "Scale")):
        current = value.get(target, value.get(source))
        if current is not None:
            result[target] = current
    if "Type" in result:
        result["Type"] = str(result["Type"]).lower()
    nullable = value.get("Nullable", value.get("nullable"))
    if nullable is not None:
        result["Nullable"] = str(nullable).lower() if isinstance(nullable, bool) else str(nullable).lower()
    if position is not None:
        result["Position"] = position
    return result


def partition(value):
    result = {}
    for source, target in (("name", "Name"), ("type", "Type"), ("comment", "Comment"), ("transform", "Transform"), ("transform_args", "TransformArgs")):
        current = value.get(target, value.get(source))
        if current is not None:
            result[target] = current
    if "Type" in result:
        result["Type"] = str(result["Type"]).lower()
    return result


def pairs(values, fn):
    return [fn(item, index) if fn is column else fn(item) for index, item in enumerate(values or [])]


def normalize(value):
    result = dict(value or {})
    base = dict(result.get("TableBaseInfo") or {})
    result["TableBaseInfo"] = {
        k: v
        for k, v in base.items()
        if k in ("DatabaseName", "TableName", "DatasourceConnectionName", "TableComment", "Type", "TableFormat", "PrimaryKeys") and v is not None
    }
    for key in ("Type", "TableFormat"):
        if key in result["TableBaseInfo"]:
            result["TableBaseInfo"][key] = str(result["TableBaseInfo"][key]).upper()
    if "PrimaryKeys" in result["TableBaseInfo"]:
        result["TableBaseInfo"]["PrimaryKeys"] = sorted(result["TableBaseInfo"]["PrimaryKeys"])
    result["Columns"] = pairs(result.get("Columns"), column)
    result["Partitions"] = pairs(result.get("Partitions"), partition)
    if result.get("InputFormatShort") is not None:
        result["InputFormatShort"] = str(result["InputFormatShort"]).upper()
    return result


def describe_request(models, p):
    request = models.DescribeTableRequest()
    request.TableName, request.DatabaseName = p["name"], p["database_name"]
    request.DatasourceConnectionName = p["datasource_connection_name"]
    return request


def find(module, client, models, p):
    try:
        response = module.sdk_call(client.DescribeTable, describe_request(models, p))
    except Exception as exc:
        if is_not_found(exc):
            return None
        raise
    if response.Table is None:
        return None
    value = normalize(response.Table._serialize(allow_none=True))
    base = value.get("TableBaseInfo", {})
    return value if base.get("TableName") == p["name"] and base.get("DatabaseName") == p["database_name"] else None


def desired(p, current=None):
    result = dict(current or {})
    base = dict(result.get("TableBaseInfo") or {})
    base.update({"DatabaseName": p["database_name"], "TableName": p["name"], "DatasourceConnectionName": p["datasource_connection_name"]})
    for source, target in (("comment", "TableComment"), ("table_type", "Type"), ("table_format", "TableFormat"), ("primary_keys", "PrimaryKeys")):
        if p.get(source) is not None:
            base[target] = (
                sorted(p[source]) if source == "primary_keys" else (str(p[source]).upper() if source in ("table_type", "table_format") else p[source])
            )
    result["TableBaseInfo"] = base
    if p.get("columns") is not None:
        result["Columns"] = pairs(p["columns"], column)
    if p.get("partitions") is not None:
        result["Partitions"] = pairs(p["partitions"], partition)
    if p.get("location") is not None:
        result["Location"] = p["location"]
    if p.get("data_format") is not None:
        result["InputFormatShort"] = p["data_format"].upper()
    return result


def immutable_drift(p, current):
    target, changes = desired(p, current), {}
    for source, key in (("columns", "Columns"), ("partitions", "Partitions"), ("location", "Location")):
        if p.get(source) is not None and current.get(key) != target.get(key):
            changes[key] = (current.get(key), target.get(key))
    for source, key in (("table_type", "Type"), ("table_format", "TableFormat"), ("primary_keys", "PrimaryKeys")):
        if p.get(source) is not None and current["TableBaseInfo"].get(key) != target["TableBaseInfo"].get(key):
            changes[key] = (current["TableBaseInfo"].get(key), target["TableBaseInfo"].get(key))
    if p.get("data_format") is not None and str(current.get("InputFormatShort") or "").upper() != p["data_format"].upper():
        changes["InputFormatShort"] = (current.get("InputFormatShort"), p["data_format"].upper())
    return changes


def comment_drift(p, current):
    if p.get("comment") is None:
        return {}
    old = current.get("TableBaseInfo", {}).get("TableComment")
    return {} if old == p["comment"] else {"TableComment": (old, p["comment"])}


def generate_request(models, p):
    base = {"DatabaseName": p["database_name"], "TableName": p["name"], "DatasourceConnectionName": p["datasource_connection_name"], "Type": p["table_type"]}
    if p.get("comment") is not None:
        base["TableComment"] = p["comment"]
    if p.get("table_format") is not None:
        base["TableFormat"] = p["table_format"]
    if p.get("primary_keys") is not None:
        base["PrimaryKeys"] = p["primary_keys"]
    info = {
        "TableBaseInfo": base,
        "Columns": pairs(p["columns"], column),
        "Partitions": pairs(p.get("partitions"), partition),
        "DataFormat": {p["data_format"]: {}},
    }
    if p.get("location") is not None:
        info["Location"] = p["location"]
    request = models.CreateTableRequest()
    request.TableInfo = _model(models.TableInfo, info)
    return request


def task_request(models, p, sql):
    request = models.CreateTasksRequest()
    request.DatabaseName = p["database_name"]
    request.DatasourceConnectionName = p["datasource_connection_name"]
    if p.get("data_engine_name") is not None:
        request.DataEngineName = p["data_engine_name"]
    if p.get("resource_group_name") is not None:
        request.ResourceGroupName = p["resource_group_name"]
    request.Tasks = _model(
        models.TasksInfo, {"TaskType": "SQLTask", "FailureTolerance": "Terminate", "SQL": base64.b64encode(sql.encode("utf-8")).decode("ascii")}
    )
    return request


def task_status_request(models, task_id):
    request = models.DescribeTaskDetailRequest()
    request.TaskInstanceId = task_id
    return request


def wait_task(module, client, models, p, task_id):
    def poll():
        info = module.sdk_call(client.DescribeTaskDetail, task_status_request(models, task_id)).TaskDetail
        if info is None:
            return 0, "task not visible yet", None
        return info.State, info.OutputMessage, info._serialize(allow_none=True)

    return wait_for_task(module, poll, timeout=p["waiter_timeout"], delay=p["waiter_delay"], success_statuses=(2,), failure_statuses=(-1, -3))


def delete_request(models, p):
    request = models.DeleteTableRequest()
    request.TableBaseInfo = _model(
        models.TableBaseInfo, {"DatabaseName": p["database_name"], "TableName": p["name"], "DatasourceConnectionName": p["datasource_connection_name"]}
    )
    return request


def comment_request(models, p):
    request = models.AlterTableCommentRequest()
    request.TableBaseInfo = _model(
        models.TableBaseInfo,
        {"DatabaseName": p["database_name"], "TableName": p["name"], "DatasourceConnectionName": p["datasource_connection_name"], "TableComment": p["comment"]},
    )
    return request


def has_data(current):
    return int(current.get("StorageSize") or 0) > 0 or int(current.get("RecordCount") or 0) > 0


def wait_table(module, client, models, p, present):
    def poll():
        return "present" if find(module, client, models, p) else "absent"

    wait_for_state(module, poll, ["present" if present else "absent"], timeout=p["waiter_timeout"], delay=p["waiter_delay"])


def wait_comment(module, client, models, p):
    def poll():
        current = find(module, client, models, p)
        return "ready" if current and current.get("TableBaseInfo", {}).get("TableComment") == p["comment"] else "pending"

    wait_for_state(module, poll, ["ready"], timeout=p["waiter_timeout"], delay=p["waiter_delay"])


def create(module, client, models, p):
    generated = module.sdk_call(client.CreateTable, generate_request(models, p))
    sql = generated.Execution.SQL
    submitted = module.sdk_call(client.CreateTasks, task_request(models, p, sql))
    task_ids = submitted.TaskIdSet or []
    if p["wait"]:
        for task_id in task_ids:
            wait_task(module, client, models, p, task_id)
        wait_table(module, client, models, p, True)
    return task_ids


def run_module():
    col = {
        "name": {"required": True},
        "type": {"required": True},
        "comment": {},
        "precision": {"type": "int"},
        "scale": {"type": "int"},
        "nullable": {"type": "bool"},
    }
    part = {"name": {"required": True}, "type": {"required": True}, "comment": {}, "transform": {}, "transform_args": {"type": "list", "elements": "str"}}
    spec = {
        "state": {"choices": ["present", "absent"], "default": "present"},
        "name": {"required": True},
        "database_name": {"required": True},
        "datasource_connection_name": {"default": "DataLakeCatalog"},
        "comment": {},
        "table_type": {"default": "TABLE"},
        "table_format": {},
        "data_format": {"choices": ["TextFile", "CSV", "Json", "Parquet", "ORC", "AVRO"], "default": "Parquet"},
        "location": {},
        "primary_keys": {"type": "list", "elements": "str", "no_log": False},
        "columns": {"type": "list", "elements": "dict", "options": col},
        "partitions": {"type": "list", "elements": "dict", "options": part},
        "data_engine_name": {},
        "resource_group_name": {},
        "allow_replace": {"type": "bool", "default": False},
        "allow_delete": {"type": "bool", "default": False},
        "allow_delete_data": {"type": "bool", "default": False},
        "wait": {"type": "bool", "default": True},
        "waiter_delay": {"type": "int", "default": 5},
        "waiter_timeout": {"type": "int", "default": 900},
    }
    module = TencentCloudModule(argument_spec=spec, supports_check_mode=True)
    p = module.params
    names = [x["name"] for x in p.get("columns") or []]
    if len(names) != len(set(names)):
        module.fail_json(msg="column names must be unique")
    module.require_sdk()
    models, cm = _load()
    client = module.create_client(cm.DlcClient, "dlc.tencentcloudapi.com")
    try:
        current = find(module, client, models, p)
        if p["state"] == "absent":
            if not current:
                module.exit_json(changed=False, table=None, task_ids=[])
            if not p["allow_delete"]:
                module.fail_json(msg="set allow_delete=true to authorize deleting the DLC table", table=current)
            if has_data(current) and not p["allow_delete_data"]:
                module.fail_json(msg="DLC table contains data; set allow_delete_data=true to authorize deletion", table=current)
            diff_value = maybe_diff(module, current, None)
            if not module.check_mode:
                module.sdk_call(client.DeleteTable, delete_request(models, p))
                if p["wait"]:
                    wait_table(module, client, models, p, False)
            module.exit_json(changed=True, **(diff_value or {}), table=None, task_ids=[])
        if not current:
            if not p.get("columns"):
                module.fail_json(msg="columns are required when creating a DLC table")
            target, diff_value, task_ids = desired(p), maybe_diff(module, None, desired(p)), []
            if not module.check_mode:
                task_ids = create(module, client, models, p)
                current = find(module, client, models, p)
            module.exit_json(changed=True, **(diff_value or {}), table=current if not module.check_mode else target, task_ids=task_ids)
        changes = immutable_drift(p, current)
        mutable = comment_drift(p, current)
        if not changes and not mutable:
            module.exit_json(changed=False, table=current, task_ids=[])
        if not changes and mutable:
            after, diff_value = desired(p, current), maybe_diff(module, current, desired(p, current))
            if not module.check_mode:
                module.sdk_call(client.AlterTableComment, comment_request(models, p))
                if p["wait"]:
                    wait_comment(module, client, models, p)
                current = find(module, client, models, p)
            module.exit_json(changed=True, **(diff_value or {}), table=current if not module.check_mode else after, task_ids=[])
        if not p["allow_replace"]:
            module.fail_json(msg="DLC table schema is immutable; set allow_replace=true to authorize replacement", table=current, immutable_drift=changes)
        if has_data(current) and not p["allow_delete_data"]:
            module.fail_json(msg="DLC table contains data; set allow_delete_data=true to authorize replacement", table=current)
        if not p.get("columns"):
            module.fail_json(msg="columns are required when replacing a DLC table")
        target, diff_value, task_ids = desired(p, current), maybe_diff(module, current, desired(p, current)), []
        if not module.check_mode:
            module.sdk_call(client.DeleteTable, delete_request(models, p))
            if p["wait"]:
                wait_table(module, client, models, p, False)
            task_ids = create(module, client, models, p)
            current = find(module, client, models, p)
        module.exit_json(changed=True, **(diff_value or {}), table=current if not module.check_mode else target, task_ids=task_ids)
    except Exception as exc:
        fail_from_sdk_error(module, exc)


def main():
    run_module()


if __name__ == "__main__":
    main()
