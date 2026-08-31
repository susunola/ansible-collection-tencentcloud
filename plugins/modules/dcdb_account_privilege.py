#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function

__metaclass__ = type
DOCUMENTATION = r'''
---
module: dcdb_account_privilege
short_description: Manage scoped Tencent Cloud DCDB account privileges
version_added: "0.14.0"
description: Reconciles the complete privilege set for one global, database, table or column scope.
options:
  state: {type: str, choices: [present, absent], default: present, description: Desired state.}
  instance_id: {type: str, required: true, description: DCDB instance ID.}
  username: {type: str, required: true, description: Account name.}
  host: {type: str, default: '%', description: Account host expression.}
  database: {type: str, default: '*', description: Database name or star for global privileges.}
  object_type: {type: str, choices: ['*', table], default: '*', description: Object type.}
  object_name: {type: str, default: '*', description: Table name or star.}
  column: {type: str, default: '*', description: Column name or star.}
  privileges: {type: list, elements: str, default: [], description: Complete desired privilege set.}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''
EXAMPLES = r'''
- susunola.tencentcloud.dcdb_account_privilege:
    instance_id: tdsqlshard-xxxxxxxx
    username: application
    database: orders
    object_type: table
    object_name: events
    privileges: [SELECT, INSERT, UPDATE]
'''
RETURN = r'''privileges: {description: Effective sorted privilege names., type: list, elements: str, returned: always}'''

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


def _load():
    from tencentcloud.dcdb.v20180411 import models, dcdb_client
    return models, dcdb_client


def request(models, name, params, privileges=None):
    value = getattr(models, name)(); value.InstanceId, value.UserName, value.Host = params["instance_id"], params["username"], params["host"]
    value.DbName, value.Type, value.Object, value.ColName = params["database"], params["object_type"], params["object_name"], params["column"]
    if privileges is not None: value.Privileges = sorted(set(privileges))
    return value


def run_module():
    module = TencentCloudModule(argument_spec={"state": {"choices": ["present", "absent"], "default": "present"},
        "instance_id": {"required": True}, "username": {"required": True}, "host": {"default": "%"},
        "database": {"default": "*"}, "object_type": {"choices": ["*", "table"], "default": "*"},
        "object_name": {"default": "*"}, "column": {"default": "*"},
        "privileges": {"type": "list", "elements": "str", "default": []}}, supports_check_mode=True)
    p = module.params
    if p["database"] == "*" and any(p[key] != "*" for key in ("object_type", "object_name", "column")): module.fail_json(msg="global scope requires object_type, object_name and column to be '*'")
    if p["object_type"] == "*" and (p["object_name"] != "*" or p["column"] != "*"): module.fail_json(msg="database scope requires object_name and column to be '*'")
    if p["object_type"] != "table" and p["column"] != "*": module.fail_json(msg="column can only be set for table scopes")
    module.require_sdk(); models, client_module = _load(); client = module.create_client(client_module.DcdbClient, "dcdb.tencentcloudapi.com")
    try:
        response = module.sdk_call(client.DescribeAccountPrivileges, request(models, "DescribeAccountPrivilegesRequest", p))
        current, target = sorted(set(response.Privileges or [])), sorted(set(p["privileges"])) if p["state"] == "present" else []
        if current == target: module.exit_json(changed=False, privileges=current)
        diff = maybe_diff(module, current, target)
        if not module.check_mode:
            module.sdk_call(client.GrantAccountPrivileges, request(models, "GrantAccountPrivilegesRequest", p, target))
            current = sorted(set(module.sdk_call(client.DescribeAccountPrivileges, request(models, "DescribeAccountPrivilegesRequest", p)).Privileges or []))
        module.exit_json(changed=True, **(diff or {}), privileges=current)
    except Exception as exc: module.fail_json(**sdk_error_payload(exc))


def main(): run_module()
if __name__ == "__main__": main()
