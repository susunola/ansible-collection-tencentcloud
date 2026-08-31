#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function
__metaclass__ = type

DOCUMENTATION = r'''
---
module: tdmysql_account_info
short_description: Gather Tencent Cloud TDSQL MySQL accounts
version_added: "0.14.0"
description:
  - Returns all accounts for an instance or one account identified by the exact username and host pair.
  - Exact mode can also include the account's global privileges.
options:
  instance_id: {type: str, required: true, description: Stable TDSQL MySQL instance ID.}
  username: {type: str, description: Exact login username.}
  host: {type: str, default: '%', description: Exact allowed client host paired with username.}
  include_global_privileges: {type: bool, default: true, description: Query global privileges in exact mode.}
  retries: {type: int, default: 5, description: Retries for transient API failures.}
  user_agent: {type: str, default: ansible-collection.susunola.tencentcloud, description: User-Agent suffix.}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''
EXAMPLES = r'''
- susunola.tencentcloud.tdmysql_account_info:
    instance_id: tdsql3-xxxxxxxx
    username: reporting
    host: 10.%
'''
RETURN = r'''
accounts: {description: Matching account metadata., type: list, elements: dict, returned: always}
request_id: {description: Request ID from the final API call., type: str, returned: always}
'''

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


def _load():
    from tencentcloud.tdmysql.v20211122 import models, tdmysql_client
    return models, tdmysql_client


def users_request(models, instance_id): request = models.DescribeUsersRequest(); request.InstanceId = instance_id; return request


def privileges_request(models, p):
    request = models.DescribeUserPrivilegesRequest(); request.InstanceId, request.UserName, request.Host = p["instance_id"], p["username"], p["host"]
    request.DbName, request.ObjectType, request.Object, request.ColName = "*", "*", "*", "*"; return request


def read_accounts(module, client, models, p):
    response = module.sdk_call(client.DescribeUsers, users_request(models, p["instance_id"])); request_id = response.RequestId
    values = [item._serialize(allow_none=True) for item in response.Users or []]
    if p.get("username") is not None: values = [item for item in values if item.get("UserName") == p["username"] and item.get("Host") == p["host"]]
    if len(values) > 1 and p.get("username") is not None: module.fail_json(msg="Multiple TDSQL MySQL accounts matched the exact username and host")
    if values and p.get("username") is not None and p["include_global_privileges"]:
        privilege_response = module.sdk_call(client.DescribeUserPrivileges, privileges_request(models, p)); request_id = privilege_response.RequestId
        values[0]["GlobalPrivileges"] = sorted(privilege_response.Privileges or [])
    return values, request_id


def run_module():
    module = TencentCloudModule(argument_spec={"instance_id": {"required": True}, "username": {}, "host": {"default": "%"}, "include_global_privileges": {"type": "bool", "default": True}}, supports_check_mode=True); p = module.params
    module.require_sdk(); models, cm = _load(); client = module.create_client(cm.TdmysqlClient, "tdmysql.tencentcloudapi.com")
    try:
        values, request_id = read_accounts(module, client, models, p); module.exit_json(changed=False, accounts=values, request_id=request_id)
    except Exception as exc: module.fail_json(**sdk_error_payload(exc))


def main(): run_module()
if __name__ == "__main__": main()
