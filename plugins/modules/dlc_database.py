#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function

__metaclass__ = type
DOCUMENTATION = r"""
---
module: dlc_database
short_description: Manage Tencent Cloud Data Lake Compute metadata databases
version_added: "0.14.0"
description:
  - Creates, discovers, waits for and deletes DLC metadata databases.
  - Database name, comment and governance policy are immutable because DLC exposes no general database update API.
options:
  state: {type: str, choices: [present, absent], default: present, description: Desired database state.}
  name: {type: str, required: true, description: Database name.}
  datasource_connection_name: {type: str, default: DataLakeCatalog, description: Catalog or data-source connection name.}
  comment: {type: str, description: Creation-time database comment.}
  govern_policy: {type: dict, description: Creation-time SDK DataGovernPolicy object; compared with readable governance metadata.}
  smart_policy: {type: dict, description: Creation-time SDK SmartPolicy object; DLC does not return it from database describe.}
  allow_delete_nonempty: {type: bool, default: false, description: Explicitly authorize deleting a database containing tables.}
  allow_delete: {type: bool, default: false, description: Explicitly authorize database deletion.}
  wait: {type: bool, default: true, description: Wait for presence or absence convergence.}
  waiter_delay: {type: int, default: 5, description: Seconds between polls.}
  waiter_timeout: {type: int, default: 300, description: Overall convergence timeout.}
  retries: {type: int, default: 5, description: Number of retries for transient failures.}
  user_agent: {type: str, default: ansible-collection.susunola.tencentcloud, description: User-Agent suffix.}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.dlc_database:
    name: analytics
    comment: Curated analytics datasets

- susunola.tencentcloud.dlc_database:
    name: analytics
    state: absent
    allow_delete: true
"""
RETURN = r"""database: {description: Effective DLC database metadata., type: dict, returned: always}
batch_id: {description: DLC asynchronous mutation batch ID., type: str, returned: when changed}"""
import json
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.errors import is_not_found
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload
from ansible_collections.susunola.tencentcloud.plugins.module_utils.waiters import wait_for_state


def _load():
    from tencentcloud.dlc.v20210125 import models, dlc_client

    return models, dlc_client


def _model(cls, value):
    item = cls()
    item.from_json_string(json.dumps(value))
    return item


def describe_request(models, p):
    request = models.DescribeDatabaseRequest()
    request.DatabaseName, request.DatasourceConnectionName = p["name"], p["datasource_connection_name"]
    return request


def find(module, client, models, p):
    try:
        response = module.sdk_call(client.DescribeDatabase, describe_request(models, p))
    except Exception as exc:
        if is_not_found(exc):
            return None
        raise
    if response.DatabaseInfo is None:
        return None
    value = response.DatabaseInfo._serialize(allow_none=True)
    return value if value.get("DatabaseName") == p["name"] else None


def table_count_request(models, p):
    request = models.DescribeTablesRequest()
    request.DatabaseName, request.DatasourceConnectionName = p["name"], p["datasource_connection_name"]
    request.Offset, request.Limit = 0, 1
    return request


def create_request(models, p):
    request = models.CreateMetaDatabaseRequest()
    request.DatasourceConnectionName = p["datasource_connection_name"]
    request.MetaDatabaseInfo = _model(models.MetaDatabaseInfo, {"DatabaseName": p["name"], "Comment": p.get("comment")})
    if p.get("govern_policy") is not None:
        request.GovernPolicy = _model(models.DataGovernPolicy, p["govern_policy"])
    if p.get("smart_policy") is not None:
        request.SmartPolicy = _model(models.SmartPolicy, p["smart_policy"])
    return request


def delete_request(models, p):
    request = models.DeleteMetaDatabaseRequest()
    request.DatabaseName, request.DatasourceConnectionName = p["name"], p["datasource_connection_name"]
    return request


def normalize(value):
    if isinstance(value, dict):
        return {key: normalize(item) for key, item in value.items() if item is not None}
    if isinstance(value, list):
        return [normalize(item) for item in value]
    return value


def immutable_drift(p, current):
    drift = {}
    if p.get("comment") is not None and (current.get("Comment") or "") != p["comment"]:
        drift["Comment"] = (current.get("Comment") or "", p["comment"])
    if p.get("govern_policy") is not None and normalize(current.get("GovernPolicy") or {}) != normalize(p["govern_policy"]):
        drift["GovernPolicy"] = (normalize(current.get("GovernPolicy") or {}), normalize(p["govern_policy"]))
    return drift


def wait_database(module, client, models, p, present):
    def poll():
        return "present" if find(module, client, models, p) else "absent"

    wait_for_state(module, poll, ["present" if present else "absent"], timeout=p["waiter_timeout"], delay=p["waiter_delay"])


def run_module():
    spec = {
        "state": {"choices": ["present", "absent"], "default": "present"},
        "name": {"required": True},
        "datasource_connection_name": {"default": "DataLakeCatalog"},
        "comment": {},
        "govern_policy": {"type": "dict"},
        "smart_policy": {"type": "dict"},
        "allow_delete_nonempty": {"type": "bool", "default": False},
        "allow_delete": {"type": "bool", "default": False},
        "wait": {"type": "bool", "default": True},
        "waiter_delay": {"type": "int", "default": 5},
        "waiter_timeout": {"type": "int", "default": 300},
    }
    module = TencentCloudModule(argument_spec=spec, supports_check_mode=True)
    p = module.params
    if p.get("comment") is not None and len(p["comment"]) > 2048:
        module.fail_json(msg="DLC database comment must not exceed 2048 characters")
    module.require_sdk()
    models, cm = _load()
    client = module.create_client(cm.DlcClient, "dlc.tencentcloudapi.com")
    try:
        current = find(module, client, models, p)
        if p["state"] == "absent":
            if not current:
                module.exit_json(changed=False, database=None, batch_id=None)
            if not p["allow_delete"]:
                module.fail_json(msg="set allow_delete=true to authorize deleting the DLC database", database=current)
            table_count = int(module.sdk_call(client.DescribeTables, table_count_request(models, p)).TotalCount or 0)
            if table_count and not p["allow_delete_nonempty"]:
                module.fail_json(msg="DLC database contains tables; set allow_delete_nonempty=true to authorize deletion", table_count=table_count)
            diff_value = maybe_diff(module, current, None)
            batch_id = None
            if not module.check_mode:
                batch_id = module.sdk_call(client.DeleteMetaDatabase, delete_request(models, p)).BatchId
                if p["wait"]:
                    wait_database(module, client, models, p, False)
            module.exit_json(changed=True, **(diff_value or {}), database=None, batch_id=batch_id)
        if not current:
            target = {"DatabaseName": p["name"], "Comment": p.get("comment") or ""}
            if p.get("govern_policy") is not None:
                target["GovernPolicy"] = normalize(p["govern_policy"])
            diff_value = maybe_diff(module, None, target)
            batch_id = None
            if not module.check_mode:
                batch_id = module.sdk_call(client.CreateMetaDatabase, create_request(models, p)).BatchId
                if p["wait"]:
                    wait_database(module, client, models, p, True)
                current = find(module, client, models, p)
            module.exit_json(changed=True, **(diff_value or {}), database=current if not module.check_mode else target, batch_id=batch_id)
        drift = immutable_drift(p, current)
        if drift:
            module.fail_json(msg="DLC database comment and governance policy are immutable; recreate the database to change them", immutable_drift=drift)
        module.exit_json(changed=False, database=current, batch_id=None)
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
