#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type
DOCUMENTATION = r'''
---
module: cdb_account_privilege
short_description: Manage TencentDB for MySQL account privileges
version_added: "0.14.0"
description:
  - Reconciles the complete global, database, table and column privilege set for one CDB account.
  - C(state=absent) revokes all managed privileges without deleting the account.
options:
  state: {type: str, choices: [present, absent], default: present, description: Desired privilege-set state.}
  instance_id: {type: str, required: true, description: CDB instance ID.}
  username: {type: str, required: true, description: Account name.}
  host: {type: str, default: '%', description: Account host expression.}
  global_privileges: {type: list, elements: str, default: [], description: Global privilege names.}
  database_privileges:
    type: list
    elements: dict
    default: []
    description: Per-database privilege sets.
    suboptions:
      database: {type: str, required: true, description: Database name.}
      privileges: {type: list, elements: str, required: true, description: Privilege names.}
  table_privileges:
    type: list
    elements: dict
    default: []
    description: Per-table privilege sets.
    suboptions:
      database: {type: str, required: true, description: Database name.}
      table: {type: str, required: true, description: Table name.}
      privileges: {type: list, elements: str, required: true, description: Privilege names.}
  column_privileges:
    type: list
    elements: dict
    default: []
    description: Per-column privilege sets.
    suboptions:
      database: {type: str, required: true, description: Database name.}
      table: {type: str, required: true, description: Table name.}
      column: {type: str, required: true, description: Column name.}
      privileges: {type: list, elements: str, required: true, description: Privilege names.}
  retries: {description: Number of retries for transient failures., type: int, default: 5}
  waiter_delay: {description: Seconds between polling attempts., type: int, default: 5}
  waiter_timeout: {description: Overall polling timeout in seconds., type: int, default: 120}
  user_agent: {description: User-Agent suffix., type: str, default: ansible-collection.susunola.tencentcloud}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''
EXAMPLES = r'''
- susunola.tencentcloud.cdb_account_privilege:
    instance_id: cdb-xxxxxxxx
    username: app
    global_privileges: [SELECT]
    database_privileges:
      - database: orders
        privileges: [SELECT, INSERT, UPDATE]
'''
RETURN = r'''privileges: {description: Normalized account privilege set., type: dict, returned: always}'''

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


def _load():
    from tencentcloud.cdb.v20170320 import cdb_client, models
    return models, cdb_client


def describe_request(models, p):
    request = models.DescribeAccountPrivilegesRequest()
    request.InstanceId, request.User, request.Host = p["instance_id"], p["username"], p["host"]
    return request


def _objects(models, class_name, values, keys):
    result = []
    for value in values:
        item = getattr(models, class_name)()
        for source, target in keys: setattr(item, target, sorted(value[source]) if source == "privileges" else value[source])
        result.append(item)
    return result


def modify_request(models, p, wanted):
    request = models.ModifyAccountPrivilegesRequest(); request.InstanceId = p["instance_id"]
    account = models.Account(); account.User, account.Host = p["username"], p["host"]; request.Accounts = [account]
    request.GlobalPrivileges = wanted["GlobalPrivileges"]
    request.DatabasePrivileges = _objects(models, "DatabasePrivilege", wanted["DatabasePrivileges"], (("database", "Database"), ("privileges", "Privileges")))
    request.TablePrivileges = _objects(models, "TablePrivilege", wanted["TablePrivileges"], (("database", "Database"), ("table", "Table"), ("privileges", "Privileges")))
    request.ColumnPrivileges = _objects(models, "ColumnPrivilege", wanted["ColumnPrivileges"], (("database", "Database"), ("table", "Table"), ("column", "Column"), ("privileges", "Privileges")))
    return request


def _normalize_items(values, identity):
    result = []
    for value in values or []:
        if hasattr(value, "_serialize"): value = value._serialize(allow_none=True)
        item = {name.lower(): value.get(name) for name in identity}
        item["privileges"] = sorted(value.get("Privileges") or [])
        result.append(item)
    return sorted(result, key=lambda x: tuple(x[name.lower()] for name in identity))


def normalize(value):
    return {
        "GlobalPrivileges": sorted(value.get("GlobalPrivileges") or []),
        "DatabasePrivileges": _normalize_items(value.get("DatabasePrivileges"), ("Database",)),
        "TablePrivileges": _normalize_items(value.get("TablePrivileges"), ("Database", "Table")),
        "ColumnPrivileges": _normalize_items(value.get("ColumnPrivileges"), ("Database", "Table", "Column")),
    }


def desired(p):
    return normalize({"GlobalPrivileges": p["global_privileges"], "DatabasePrivileges": [{"Database": x["database"], "Privileges": x["privileges"]} for x in p["database_privileges"]], "TablePrivileges": [{"Database": x["database"], "Table": x["table"], "Privileges": x["privileges"]} for x in p["table_privileges"]], "ColumnPrivileges": [{"Database": x["database"], "Table": x["table"], "Column": x["column"], "Privileges": x["privileges"]} for x in p["column_privileges"]]})


def fetch(module, client, models, p):
    response = module.sdk_call(client.DescribeAccountPrivileges, describe_request(models, p))
    return normalize(response._serialize(allow_none=True))


def run_module():
    privilege = {"type": "list", "elements": "str", "required": True}
    module = TencentCloudModule(argument_spec={
        "state": {"choices": ["present", "absent"], "default": "present"}, "instance_id": {"required": True}, "username": {"required": True}, "host": {"default": "%"},
        "global_privileges": {"type": "list", "elements": "str", "default": []},
        "database_privileges": {"type": "list", "elements": "dict", "default": [], "options": {"database": {"required": True}, "privileges": privilege}},
        "table_privileges": {"type": "list", "elements": "dict", "default": [], "options": {"database": {"required": True}, "table": {"required": True}, "privileges": privilege}},
        "column_privileges": {"type": "list", "elements": "dict", "default": [], "options": {"database": {"required": True}, "table": {"required": True}, "column": {"required": True}, "privileges": privilege}},
    }, supports_check_mode=True)
    p = module.params; module.require_sdk(); models, cm = _load(); client = module.create_client(cm.CdbClient, "cdb.tencentcloudapi.com")
    try:
        current = fetch(module, client, models, p); target = desired(p) if p["state"] == "present" else desired(dict(p, global_privileges=[], database_privileges=[], table_privileges=[], column_privileges=[]))
        if current == target: module.exit_json(changed=False, privileges=current)
        diff = maybe_diff(module, current, target)
        if not module.check_mode:
            module.sdk_call(client.ModifyAccountPrivileges, modify_request(models, p, target)); current = fetch(module, client, models, p)
        module.exit_json(changed=True, **(diff or {}), privileges=current)
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main(): run_module()
if __name__ == "__main__": main()
