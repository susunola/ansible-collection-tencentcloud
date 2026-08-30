#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type
DOCUMENTATION = r'''
---
module: mariadb_account_privilege
short_description: Manage a scoped TencentDB for MariaDB account privilege set
version_added: "0.14.0"
description:
  - Reconciles the complete privileges for one account scope such as global, database, table, view, procedure, function or column.
  - C(state=absent) clears privileges only for the selected scope.
options:
  state: {type: str, choices: [present, absent], default: present, description: Desired privilege-set state.}
  instance_id: {type: str, required: true, description: MariaDB instance ID.}
  username: {type: str, required: true, description: Account name.}
  host: {type: str, default: '%', description: Account host expression.}
  database: {type: str, default: '*', description: Database name or C(*) for global privileges.}
  object_type: {type: str, choices: ['*', table, view, proc, func], default: '*', description: Scoped object type.}
  object_name: {type: str, default: '*', description: "Table, view, procedure or function name."}
  column: {type: str, default: '*', description: Column name for table scopes or C(*) for the whole table.}
  privileges: {type: list, elements: str, default: [], description: Complete desired privilege names for this scope.}
  retries: {description: Number of retries for transient failures., type: int, default: 5}
  waiter_delay: {description: Seconds between polling attempts., type: int, default: 5}
  waiter_timeout: {description: Overall polling timeout in seconds., type: int, default: 120}
  user_agent: {description: User-Agent suffix., type: str, default: ansible-collection.susunola.tencentcloud}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''
EXAMPLES = r'''
- susunola.tencentcloud.mariadb_account_privilege:
    instance_id: tdsql-xxxxxxxx
    username: app
    database: orders
    object_type: table
    object_name: events
    privileges: [SELECT, INSERT, UPDATE]
'''
RETURN = r'''privileges: {description: Resulting normalized privilege names., type: list, elements: str, returned: always}'''

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


def _load():
    from tencentcloud.mariadb.v20170312 import mariadb_client, models
    return models, mariadb_client


def _scope(request, p):
    request.InstanceId, request.UserName, request.Host = p["instance_id"], p["username"], p["host"]
    request.DbName, request.Type, request.Object, request.ColName = p["database"], p["object_type"], p["object_name"], p["column"]
    return request


def describe_request(models, p):
    return _scope(models.DescribeAccountPrivilegesRequest(), p)


def grant_request(models, p, privileges):
    request = _scope(models.GrantAccountPrivilegesRequest(), p); request.Privileges = sorted(set(privileges)); return request


def run_module():
    module = TencentCloudModule(argument_spec={"state": {"choices": ["present", "absent"], "default": "present"}, "instance_id": {"required": True}, "username": {"required": True}, "host": {"default": "%"}, "database": {"default": "*"}, "object_type": {"choices": ["*", "table", "view", "proc", "func"], "default": "*"}, "object_name": {"default": "*"}, "column": {"default": "*"}, "privileges": {"type": "list", "elements": "str", "default": []}}, supports_check_mode=True)
    p = module.params
    if p["database"] == "*" and any(p[x] != "*" for x in ("object_type", "object_name", "column")): module.fail_json(msg="global scope requires object_type, object_name and column to be '*'")
    if p["object_type"] == "*" and (p["object_name"] != "*" or p["column"] != "*"): module.fail_json(msg="database scope requires object_name and column to be '*'")
    if p["object_type"] != "table" and p["column"] != "*": module.fail_json(msg="column can only be set for table scopes")
    module.require_sdk(); models, cm = _load(); client = module.create_client(cm.MariadbClient, "mariadb.tencentcloudapi.com")
    try:
        response = module.sdk_call(client.DescribeAccountPrivileges, describe_request(models, p)); current = sorted(set(response.Privileges or []))
        target = sorted(set(p["privileges"])) if p["state"] == "present" else []
        if current == target: module.exit_json(changed=False, privileges=current)
        diff = maybe_diff(module, current, target)
        if not module.check_mode:
            module.sdk_call(client.GrantAccountPrivileges, grant_request(models, p, target))
            current = sorted(set(module.sdk_call(client.DescribeAccountPrivileges, describe_request(models, p)).Privileges or []))
        module.exit_json(changed=True, **(diff or {}), privileges=current)
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main(): run_module()
if __name__ == "__main__": main()
