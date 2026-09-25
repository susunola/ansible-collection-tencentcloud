#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r"""
---
module: tdmysql_account_info
short_description: Gather Tencent Cloud TDSQL MySQL accounts
version_added: "0.14.0"
description:
  - Returns all accounts for an instance or one account identified by the exact username and host pair.
  - Exact mode can also include the account's global privileges.
options:
  instance_id:
    description:
      - Stable TDSQL MySQL instance ID.
    type: str
    required: true
  username:
    description:
      - Exact login username.
    type: str
  host:
    description:
      - Exact allowed client host paired with username.
    type: str
    default: '%'
  include_global_privileges:
    description:
      - Query global privileges in exact mode.
    type: bool
    default: true

extends_documentation_fragment:
  - susunola.tencentcloud.credentials
  - susunola.tencentcloud.region
  - susunola.tencentcloud.connection
  - susunola.tencentcloud.timeout
  - susunola.tencentcloud.retry
  - susunola.tencentcloud.user_agent
  - susunola.tencentcloud.waiter
attributes:
  check_mode:
    description:
      - Can run in C(check_mode), reading the current state and predicting
        the result without issuing a write API call.
    support: full
  idempotent:
    description:
      - Read-only, so every run returns the current state and never changes
        the target, and a repeated run reports C(changed=false).
    support: full
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.tdmysql_account_info:
    instance_id: tdsql3-xxxxxxxx
    username: reporting
    host: 10.%
"""
RETURN = r"""
accounts:
  description:
    - Matching account metadata.
  returned: always
  type: list
  elements: dict
request_id:
  description:
    - Request ID from the final API call.
  returned: always
  type: str
"""

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import fail_from_sdk_error
from ansible_collections.susunola.tencentcloud.plugins.module_utils.tdmysql import _load, account_items, privileges_request, users_request


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "instance_id": {"required": True},
            "username": {},
            "host": {"default": "%"},
            "include_global_privileges": {"type": "bool", "default": True},
        },
        supports_check_mode=True,
    )
    p = module.params
    module.require_sdk()
    models, cm = _load()
    client = module.create_client(cm.TdmysqlClient, "tdmysql.tencentcloudapi.com")
    try:
        response = module.sdk_call(client.DescribeUsers, users_request(models, p["instance_id"]))
        request_id = response.RequestId
        values = account_items(response)
        if p.get("username") is not None:
            values = [item for item in values if item.get("UserName") == p["username"] and item.get("Host") == p["host"]]
            if len(values) > 1:
                module.fail_json(msg="Multiple TDSQL MySQL accounts matched the exact username and host")
            if values and p["include_global_privileges"]:
                privilege_response = module.sdk_call(client.DescribeUserPrivileges, privileges_request(models, p))
                request_id = privilege_response.RequestId
                values[0]["GlobalPrivileges"] = sorted(privilege_response.Privileges or [])
        module.exit_json(changed=False, accounts=values, request_id=request_id)
    except Exception as exc:
        fail_from_sdk_error(module, exc)


def main():
    run_module()


if __name__ == "__main__":
    main()
