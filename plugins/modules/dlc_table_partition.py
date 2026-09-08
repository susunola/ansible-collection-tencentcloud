#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r"""
---
module: dlc_table_partition
short_description: Manage Tencent Cloud DLC table partition entries
version_added: "0.14.0"
description:
  - Creates, updates and drops exact DLC Data Management Service partition entries.
  - Partition values form the stable identity; parameters and storage descriptors are reconciled semantically.
options:
  state: {type: str, choices: [present, absent], default: present, description: Desired partition state.}
  database_name: {type: str, required: true, description: Parent database name.}
  table_name: {type: str, required: true, description: Parent table name.}
  values: {type: list, elements: str, required: true, description: Ordered exact partition values and stable identity.}
  schema_name: {type: str, description: Catalog schema name.}
  name: {type: str, description: Partition display name.}
  datasource_connection_name: {type: str, default: DataLakeCatalog, description: Data-source connection name.}
  params: {type: dict, description: Exact partition parameter map.}
  storage: {type: dict, description: DMSSds-compatible storage descriptor.}
  allow_delete: {type: bool, default: false, description: Explicitly authorize dropping the partition entry.}
  delete_data: {type: bool, default: false, description: Also delete partition data when dropping the entry.}
  wait: {type: bool, default: true, description: Wait for lifecycle and field convergence.}
  waiter_delay: {type: int, default: 3, description: Seconds between polls.}
  waiter_timeout: {type: int, default: 180, description: Overall convergence timeout.}

extends_documentation_fragment:
  - susunola.tencentcloud.credentials
  - susunola.tencentcloud.region
  - susunola.tencentcloud.connection
  - susunola.tencentcloud.retry
  - susunola.tencentcloud.user_agent
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.dlc_table_partition:
    database_name: analytics
    table_name: daily_sales
    values: ['2026-08-31']
    name: sale_date=2026-08-31
    params: {source: batch}
    storage:
      location: cosn://analytics-bucket/daily_sales/sale_date=2026-08-31/

- susunola.tencentcloud.dlc_table_partition:
    database_name: analytics
    table_name: daily_sales
    values: ['2026-08-31']
    state: absent
    allow_delete: true
"""
RETURN = r"""
partition: {description: Effective DLC table partition., type: dict, returned: always}
partition_identity: {description: Stable database, table and values identity., type: dict, returned: always}
"""

import json
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload
from ansible_collections.susunola.tencentcloud.plugins.module_utils.waiters import wait_for_state


def _load():
    from tencentcloud.dlc.v20210125 import models, dlc_client

    return models, dlc_client


def _model(cls, value):
    item = cls()
    item.from_json_string(json.dumps(value))
    return item


def kv(value):
    if isinstance(value, dict):
        items = value.items()
    else:
        items = ((x.get("Key", x.get("key")), x.get("Value", x.get("value"))) for x in (value or []))
    return [{"Key": key, "Value": item} for key, item in sorted(items)]


def storage(value):
    if value is None:
        return None
    mapping = {
        "location": "Location",
        "input_format": "InputFormat",
        "output_format": "OutputFormat",
        "num_buckets": "NumBuckets",
        "compressed": "Compressed",
        "stored_as_sub_directories": "StoredAsSubDirectories",
        "serde_lib": "SerdeLib",
        "serde_name": "SerdeName",
        "bucket_cols": "BucketCols",
        "serde_params": "SerdeParams",
        "params": "Params",
        "cols": "Cols",
        "sort_columns": "SortColumns",
    }
    result = {}
    for source, target in mapping.items():
        current = value.get(target, value.get(source))
        if current is not None:
            result[target] = kv(current) if target in ("SerdeParams", "Params") else current
    return result


def normalize(value):
    result = dict(value or {})
    result["Params"] = kv(result.get("Params"))
    if result.get("Sds") is not None:
        result["Sds"] = storage(result["Sds"])
    return result


def identity(p):
    return {
        "database_name": p["database_name"],
        "table_name": p["table_name"],
        "values": p["values"],
        "schema_name": p.get("schema_name"),
        "datasource_connection_name": p["datasource_connection_name"],
    }


def list_request(models, p, offset=0):
    request = models.DescribeDMSPartitionsRequest()
    request.DatabaseName, request.TableName = p["database_name"], p["table_name"]
    request.Values, request.Offset, request.Limit = p["values"], offset, 100
    request.DatasourceConnectionName = p["datasource_connection_name"]
    if p.get("schema_name") is not None:
        request.SchemaName = p["schema_name"]
    return request


def find(module, client, models, p):
    offset, matches = 0, []
    while True:
        response = module.sdk_call(client.DescribeDMSPartitions, list_request(models, p, offset))
        items = response.Partitions or []
        matches.extend(
            x._serialize(allow_none=True)
            for x in items
            if list(x.Values or []) == p["values"] and x.DatabaseName == p["database_name"] and x.TableName == p["table_name"]
        )
        offset += len(items)
        if not items or offset >= int(response.Total or 0):
            break
    if len(matches) > 1:
        module.fail_json(msg="Multiple DLC partitions matched the exact values", partition_identity=identity(p))
    return normalize(matches[0]) if matches else None


def desired(p, current=None):
    result = dict(current or {})
    result.update(
        {"DatabaseName": p["database_name"], "TableName": p["table_name"], "Values": p["values"], "DatasourceConnectionName": p["datasource_connection_name"]}
    )
    if p.get("schema_name") is not None:
        result["SchemaName"] = p["schema_name"]
    if p.get("name") is not None:
        result["Name"] = p["name"]
    if p.get("params") is not None:
        result["Params"] = kv(p["params"])
    if p.get("storage") is not None:
        result["Sds"] = storage(p["storage"])
    return result


def drift(p, current):
    target, changes = desired(p, current), {}
    for source, key in (("name", "Name"), ("params", "Params"), ("storage", "Sds")):
        if p.get(source) is not None and current.get(key) != target.get(key):
            changes[key] = (current.get(key), target.get(key))
    return changes


def add_request(models, p):
    request = models.AddDMSPartitionsRequest()
    request.Partitions = [_model(models.DMSPartition, desired(p))]
    return request


def alter_request(models, p, current):
    request = models.AlterDMSPartitionRequest()
    request.CurrentDbName, request.CurrentTableName = p["database_name"], p["table_name"]
    request.CurrentValues = current.get("Name") or "/".join(p["values"])
    request.Partition = _model(models.DMSPartition, desired(p, current))
    request.DatasourceConnectionName = p["datasource_connection_name"]
    return request


def drop_request(models, p):
    request = models.DropDMSPartitionsRequest()
    request.DatabaseName, request.TableName, request.Values = p["database_name"], p["table_name"], p["values"]
    request.DatasourceConnectionName, request.DeleteData = p["datasource_connection_name"], p["delete_data"]
    if p.get("schema_name") is not None:
        request.SchemaName = p["schema_name"]
    if p.get("name") is not None:
        request.Name = p["name"]
    return request


def wait_partition(module, client, models, p, absent=False, expected=None):
    def poll():
        current = find(module, client, models, p)
        if absent:
            return "absent" if current is None else "pending"
        if current is None:
            return "absent"
        if expected and any(current.get(k) != v for k, v in expected.items()):
            return "pending"
        return "ready"

    wait_for_state(module, poll, ["absent" if absent else "ready"], timeout=p["waiter_timeout"], delay=p["waiter_delay"])


def run_module():
    spec = {
        "state": {"choices": ["present", "absent"], "default": "present"},
        "database_name": {"required": True},
        "table_name": {"required": True},
        "values": {"type": "list", "elements": "str", "required": True},
        "schema_name": {},
        "name": {},
        "datasource_connection_name": {"default": "DataLakeCatalog"},
        "params": {"type": "dict"},
        "storage": {"type": "dict"},
        "allow_delete": {"type": "bool", "default": False},
        "delete_data": {"type": "bool", "default": False},
        "wait": {"type": "bool", "default": True},
        "waiter_delay": {"type": "int", "default": 3},
        "waiter_timeout": {"type": "int", "default": 180},
    }
    module = TencentCloudModule(argument_spec=spec, supports_check_mode=True)
    p = module.params
    if not p["values"]:
        module.fail_json(msg="values must contain at least one partition value")
    if p["delete_data"] and (p["state"] != "absent" or not p["allow_delete"]):
        module.fail_json(msg="delete_data requires state=absent and allow_delete=true")
    module.require_sdk()
    models, cm = _load()
    client = module.create_client(cm.DlcClient, "dlc.tencentcloudapi.com")
    try:
        current = find(module, client, models, p)
        if p["state"] == "absent":
            if not current:
                module.exit_json(changed=False, partition=None, partition_identity=identity(p))
            if not p["allow_delete"]:
                module.fail_json(msg="set allow_delete=true to authorize dropping the DLC partition", partition=current)
            diff_value = maybe_diff(module, current, None)
            if not module.check_mode:
                module.sdk_call(client.DropDMSPartitions, drop_request(models, p))
                if p["wait"]:
                    wait_partition(module, client, models, p, absent=True)
            module.exit_json(changed=True, **(diff_value or {}), partition=None, partition_identity=identity(p))
        if not current:
            target, diff_value = desired(p), maybe_diff(module, None, desired(p))
            if not module.check_mode:
                module.sdk_call(client.AddDMSPartitions, add_request(models, p))
                if p["wait"]:
                    wait_partition(module, client, models, p, expected={k: v for k, v in target.items() if k in ("Name", "Params", "Sds")})
                current = find(module, client, models, p)
            module.exit_json(changed=True, **(diff_value or {}), partition=current if not module.check_mode else target, partition_identity=identity(p))
        changes = drift(p, current)
        if not changes:
            module.exit_json(changed=False, partition=current, partition_identity=identity(p))
        after, diff_value = desired(p, current), maybe_diff(module, current, desired(p, current))
        if not module.check_mode:
            module.sdk_call(client.AlterDMSPartition, alter_request(models, p, current))
            if p["wait"]:
                wait_partition(module, client, models, p, expected={k: v[1] for k, v in changes.items()})
            current = find(module, client, models, p)
        module.exit_json(changed=True, **(diff_value or {}), partition=current if not module.check_mode else after, partition_identity=identity(p))
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
