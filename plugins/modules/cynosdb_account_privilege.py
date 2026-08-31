#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type
DOCUMENTATION = r"""
---
module: cynosdb_account_privilege
short_description: Manage Tencent Cloud CynosDB account privileges
version_added: "0.14.0"
description: Reconciles the complete global, database and table privilege set for a CynosDB account.
options:
  cluster_id: {type: str, required: true, description: CynosDB cluster ID.}
  account_name: {type: str, required: true, description: Database account name.}
  host: {type: str, default: '%', description: Account host pattern.}
  global_privileges: {type: list, elements: str, default: [], description: Exact global privilege set.}
  database_privileges:
    type: list
    elements: dict
    default: []
    description: Exact database privilege assignments.
    suboptions:
      database: {type: str, required: true, description: Database name.}
      privileges: {type: list, elements: str, required: true, description: Exact privilege set for the database.}
  table_privileges:
    type: list
    elements: dict
    default: []
    description: Exact table privilege assignments.
    suboptions:
      database: {type: str, required: true, description: Database name.}
      table: {type: str, required: true, description: Table name.}
      privileges: {type: list, elements: str, required: true, description: Exact privilege set for the table.}
  retries: {description: Number of retries for transient failures., type: int, default: 5}
  waiter_delay: {description: Seconds between polling attempts., type: int, default: 5}
  waiter_timeout: {description: Overall polling timeout in seconds., type: int, default: 120}
  user_agent: {description: User-Agent suffix., type: str, default: ansible-collection.susunola.tencentcloud}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.cynosdb_account_privilege:
    cluster_id: cynosdbmysql-xxxxxxxx
    account_name: app_user
    database_privileges:
      - database: orders
        privileges: [select, insert, update, delete]
"""
RETURN = r"""account_privileges: {description: Effective complete CynosDB account privilege set., type: dict, returned: always}"""
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


def _load():
    from tencentcloud.cynosdb.v20190107 import cynosdb_client, models

    return models, cynosdb_client


def _account(models, p):
    item = models.InputAccount()
    item.AccountName, item.Host = p["account_name"], p["host"]
    return item


def describe_request(models, p):
    request = models.DescribeAccountAllGrantPrivilegesRequest()
    request.ClusterId, request.Account = p["cluster_id"], _account(models, p)
    return request


def _databases(models, values):
    result = []
    for value in values:
        item = models.DatabasePrivileges()
        item.Db, item.Privileges = value["database"], sorted(set(value["privileges"]))
        result.append(item)
    return result


def _tables(models, values):
    result = []
    for value in values:
        item = models.TablePrivileges()
        item.Db, item.TableName, item.Privileges = value["database"], value["table"], sorted(set(value["privileges"]))
        result.append(item)
    return result


def update_request(models, p):
    request = models.ModifyAccountPrivilegesRequest()
    request.ClusterId, request.Account = p["cluster_id"], _account(models, p)
    request.GlobalPrivileges, request.DatabasePrivileges, request.TablePrivileges = (
        sorted(set(p["global_privileges"])),
        _databases(models, p["database_privileges"]),
        _tables(models, p["table_privileges"]),
    )
    return request


def _dbs(values):
    result = []
    for item in values or []:
        if hasattr(item, "_serialize"):
            item = item._serialize(allow_none=True)
        result.append({"database": item.get("Db"), "privileges": sorted(set(item.get("Privileges") or []))})
    return sorted(result, key=lambda x: x["database"])


def _tabs(values):
    result = []
    for item in values or []:
        if hasattr(item, "_serialize"):
            item = item._serialize(allow_none=True)
        result.append({"database": item.get("Db"), "table": item.get("TableName"), "privileges": sorted(set(item.get("Privileges") or []))})
    return sorted(result, key=lambda x: (x["database"], x["table"]))


def normalize(global_values, db_values, table_values):
    return {"GlobalPrivileges": sorted(set(global_values or [])), "DatabasePrivileges": _dbs(db_values), "TablePrivileges": _tabs(table_values)}


def desired(p):
    return normalize(
        p["global_privileges"],
        [{"Db": x["database"], "Privileges": x["privileges"]} for x in p["database_privileges"]],
        [{"Db": x["database"], "TableName": x["table"], "Privileges": x["privileges"]} for x in p["table_privileges"]],
    )


def run_module():
    db = {
        "type": "list",
        "elements": "dict",
        "default": [],
        "options": {"database": {"required": True}, "privileges": {"type": "list", "elements": "str", "required": True}},
    }
    table = {
        "type": "list",
        "elements": "dict",
        "default": [],
        "options": {"database": {"required": True}, "table": {"required": True}, "privileges": {"type": "list", "elements": "str", "required": True}},
    }
    module = TencentCloudModule(
        argument_spec={
            "cluster_id": {"required": True},
            "account_name": {"required": True},
            "host": {"default": "%"},
            "global_privileges": {"type": "list", "elements": "str", "default": []},
            "database_privileges": db,
            "table_privileges": table,
        },
        supports_check_mode=True,
    )
    p = module.params
    module.require_sdk()
    models, cm = _load()
    client = module.create_client(cm.CynosdbClient, "cynosdb.tencentcloudapi.com")
    try:
        response = module.sdk_call(client.DescribeAccountAllGrantPrivileges, describe_request(models, p))
        current = normalize(response.GlobalPrivileges, response.DatabasePrivileges, response.TablePrivileges)
        target = desired(p)
        if current == target:
            module.exit_json(changed=False, account_privileges=current)
        diff = maybe_diff(module, current, target)
        if not module.check_mode:
            module.sdk_call(client.ModifyAccountPrivileges, update_request(models, p))
            response = module.sdk_call(client.DescribeAccountAllGrantPrivileges, describe_request(models, p))
            current = normalize(response.GlobalPrivileges, response.DatabasePrivileges, response.TablePrivileges)
        module.exit_json(changed=True, **(diff or {}), account_privileges=current)
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
