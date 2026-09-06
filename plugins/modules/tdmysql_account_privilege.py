#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r"""
---
module: tdmysql_account_privilege
short_description: Manage scoped Tencent Cloud TDSQL MySQL account privileges
version_added: "0.14.0"
description:
  - Reconciles the complete privilege set for one account at global, database or table scope.
  - An empty privilege list explicitly revokes all privileges at that scope.
options:
  instance_id: {type: str, required: true, description: Stable TDSQL MySQL instance ID.}
  username: {type: str, required: true, description: Login username.}
  host: {type: str, default: '%', description: Allowed client host paired with username.}
  scope: {type: str, choices: [global, database, table], required: true, description: Privilege scope.}
  database: {type: str, description: Database name required by database and table scopes.}
  table: {type: str, description: Table name required by table scope.}
  privileges: {type: list, elements: str, required: true, description: Full desired privilege set at the selected scope.}
  retries: {type: int, default: 5, description: Retries for transient API failures.}
  user_agent: {type: str, default: ansible-collection.susunola.tencentcloud, description: User-Agent suffix.}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.tdmysql_account_privilege:
    instance_id: tdsql3-xxxxxxxx
    username: reporting
    scope: database
    database: analytics
    privileges: [SELECT]
"""
RETURN = r"""
privilege: {description: Effective scoped privilege metadata., type: dict, returned: always}
"""

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


def _load():
    from tencentcloud.tdmysql.v20211122 import models, tdmysql_client

    return models, tdmysql_client


def describe_request(models, p):
    request = models.DescribeUserPrivilegesRequest()
    request.InstanceId, request.UserName, request.Host = p["instance_id"], p["username"], p["host"]
    if p["scope"] == "global":
        request.DbName, request.ObjectType, request.Object, request.ColName = "*", "*", "*", "*"
    elif p["scope"] == "database":
        request.DbName, request.ObjectType, request.Object, request.ColName = p["database"], "*", "*", "*"
    else:
        request.DbName, request.ObjectType, request.Object, request.ColName = p["database"], "table", p["table"], "*"
    return request


def user(models, p):
    value = models.User()
    value.UserName, value.Host = p["username"], p["host"]
    return value


def modify_request(models, p):
    request = models.ModifyUserPrivilegesRequest()
    request.InstanceId, request.Users = p["instance_id"], [user(models, p)]
    desired = sorted(set(p["privileges"]))
    if p["scope"] == "global":
        request.GlobalPrivileges = desired
    elif p["scope"] == "database":
        item = models.DatabasePrivileges()
        item.Database, item.Privileges = p["database"], desired
        request.DatabasePrivileges = [item]
    else:
        item = models.TablePrivileges()
        item.Database, item.Table, item.Privileges = p["database"], p["table"], desired
        request.TablePrivileges = [item]
    return request


def result(p, privileges):
    value = {"InstanceId": p["instance_id"], "UserName": p["username"], "Host": p["host"], "Scope": p["scope"], "Privileges": sorted(privileges or [])}
    if p["scope"] != "global":
        value["Database"] = p["database"]
    if p["scope"] == "table":
        value["Table"] = p["table"]
    return value


def run_module():
    spec = {
        "instance_id": {"required": True},
        "username": {"required": True},
        "host": {"default": "%"},
        "scope": {"required": True, "choices": ["global", "database", "table"]},
        "database": {},
        "table": {},
        "privileges": {"type": "list", "elements": "str", "required": True},
    }
    module = TencentCloudModule(argument_spec=spec, supports_check_mode=True)
    p = module.params
    if p["scope"] in ("database", "table") and not p.get("database"):
        module.fail_json(msg="database is required for database and table scope")
    if p["scope"] == "table" and not p.get("table"):
        module.fail_json(msg="table is required for table scope")
    if len(p["privileges"]) != len(set(p["privileges"])):
        module.fail_json(msg="privileges must not contain duplicates")
    module.require_sdk()
    models, cm = _load()
    client = module.create_client(cm.TdmysqlClient, "tdmysql.tencentcloudapi.com")
    try:
        response = module.sdk_call(client.DescribeUserPrivileges, describe_request(models, p))
        current = result(p, response.Privileges)
        target = result(p, p["privileges"])
        if current == target:
            module.exit_json(changed=False, privilege=current)
        diff_value = maybe_diff(module, current, target)
        if not module.check_mode:
            module.sdk_call(client.ModifyUserPrivileges, modify_request(models, p))
            response = module.sdk_call(client.DescribeUserPrivileges, describe_request(models, p))
            current = result(p, response.Privileges)
        module.exit_json(changed=True, **(diff_value or {}), privilege=current if not module.check_mode else target)
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
