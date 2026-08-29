#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
---
module: cynosdb_account
short_description: Manage Tencent Cloud CynosDB accounts
version_added: "0.14.0"
description: Creates, updates and deletes CynosDB cluster accounts with explicit password rotation.
options:
  state: {description: Desired state., type: str, choices: [present, absent], default: present}
  cluster_id: {description: CynosDB cluster ID., type: str, required: true}
  account_name: {description: Database account name., type: str, required: true}
  host: {description: Account host pattern., type: str, default: '%'}
  password: {description: Password used at creation or explicit rotation., type: str}
  rotate_password: {description: Explicitly reset the password during this run., type: bool, default: false}
  description: {description: Account description., type: str, default: ''}
  max_user_connections: {description: Maximum concurrent connections for the account., type: int}
  password_rotation: {description: Password rotation interval in days., type: int}
  retries: {description: Number of retries for transient failures., type: int, default: 5}
  waiter_delay: {description: Seconds between polling attempts., type: int, default: 5}
  waiter_timeout: {description: Overall polling timeout in seconds., type: int, default: 120}
  user_agent: {description: User-Agent suffix., type: str, default: ansible-collection.susunola.tencentcloud}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''
EXAMPLES = r'''
- susunola.tencentcloud.cynosdb_account:
    cluster_id: cynosdbmysql-xxxxxxxx
    account_name: app_user
    password: '{{ vault_database_password }}'
    description: Application account
'''
RETURN = r'''
account: {description: CynosDB account metadata., type: dict, returned: always}
'''

import time

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff


def _load_cynosdb():
    from tencentcloud.cynosdb.v20190107 import cynosdb_client, models
    return models, cynosdb_client


def build_describe_request(models, cluster_id, account_name, host, offset=0):
    request = models.DescribeAccountsRequest()
    request.ClusterId, request.AccountNames, request.Hosts = cluster_id, [account_name], [host]
    request.Offset, request.Limit = offset, 100
    return request


def build_create_request(models, params):
    request = models.CreateAccountsRequest()
    request.ClusterId = params["cluster_id"]
    account = models.NewAccount()
    account.AccountName, account.Host = params["account_name"], params["host"]
    account.AccountPassword, account.Description = params["password"], params["description"]
    if params.get("max_user_connections") is not None:
        account.MaxUserConnections = params["max_user_connections"]
    if params.get("password_rotation") is not None:
        account.PasswordRotation = params["password_rotation"]
    request.Accounts = [account]
    return request


def build_identity(models, params):
    account = models.InputAccount()
    account.AccountName, account.Host = params["account_name"], params["host"]
    return account


def build_delete_request(models, params):
    request = models.DeleteAccountsRequest()
    request.ClusterId, request.Accounts = params["cluster_id"], [build_identity(models, params)]
    return request


def build_description_request(models, params):
    request = models.ModifyAccountDescriptionRequest()
    request.ClusterId, request.AccountName, request.Host = params["cluster_id"], params["account_name"], params["host"]
    request.Description = params["description"]
    return request


def build_password_request(models, params):
    request = models.ResetAccountPasswordRequest()
    request.ClusterId, request.AccountName, request.Host = params["cluster_id"], params["account_name"], params["host"]
    request.AccountPassword = params["password"]
    return request


def find_account(module, client, models, params):
    response = module.sdk_call(client.DescribeAccounts, build_describe_request(models, params["cluster_id"], params["account_name"], params["host"]))
    for item in list(getattr(response, "AccountSet", None) or []):
        value = item._serialize(allow_none=True)
        if value.get("AccountName") == params["account_name"] and value.get("Host") == params["host"]:
            return value
    return None


def wait_for_account(module, client, models, params, absent=False):
    deadline = time.time() + module.params["waiter_timeout"]
    while True:
        current = find_account(module, client, models, params)
        if absent and current is None:
            return None
        if not absent and current and (current.get("Description") or "") == params["description"]:
            return current
        if time.time() >= deadline:
            module.fail_json(msg="Timed out waiting for CynosDB account convergence", account=current)
        time.sleep(module.params["waiter_delay"])


def run_module():
    module = TencentCloudModule(argument_spec={"state": {"type": "str", "choices": ["present", "absent"], "default": "present"}, "cluster_id": {"type": "str", "required": True}, "account_name": {"type": "str", "required": True}, "host": {"type": "str", "default": "%"}, "password": {"type": "str", "no_log": True}, "rotate_password": {"type": "bool", "default": False}, "description": {"type": "str", "default": ""}, "max_user_connections": {"type": "int"}, "password_rotation": {"type": "int", "no_log": False}}, supports_check_mode=True)
    p = module.params
    if p["rotate_password"] and not p["password"]:
        module.fail_json(msg="password is required when rotate_password=true")
    module.require_sdk()
    models, client_module = _load_cynosdb()
    client = module.create_client(client_module.CynosdbClient, "cynosdb.tencentcloudapi.com")
    try:
        current = find_account(module, client, models, p)
        if p["state"] == "absent":
            if current is None:
                module.exit_json(changed=False, account=None, msg="CynosDB account is absent")
            diff = maybe_diff(module, current, None)
            if module.check_mode:
                module.exit_json(changed=True, **(diff or {}), account=current, msg="Would delete CynosDB account")
            module.sdk_call(client.DeleteAccounts, build_delete_request(models, p))
            wait_for_account(module, client, models, p, absent=True)
            module.exit_json(changed=True, **(diff or {}), account=None, msg="CynosDB account deleted")
        if current is None:
            if not p["password"]:
                module.fail_json(msg="password is required when creating a CynosDB account")
            desired = {"AccountName": p["account_name"], "Host": p["host"], "Description": p["description"]}
            diff = maybe_diff(module, None, desired)
            if module.check_mode:
                module.exit_json(changed=True, **(diff or {}), account=None, msg="Would create CynosDB account")
            module.sdk_call(client.CreateAccounts, build_create_request(models, p))
            current = wait_for_account(module, client, models, p)
            module.exit_json(changed=True, **(diff or {}), account=current, msg="CynosDB account created")
        description_drift = (current.get("Description") or "") != p["description"]
        changed = description_drift or p["rotate_password"]
        if not changed:
            module.exit_json(changed=False, account=current, msg="CynosDB account is up to date")
        diff = maybe_diff(module, current, dict(current, Description=p["description"]))
        if module.check_mode:
            module.exit_json(changed=True, **(diff or {}), account=current, msg="Would update CynosDB account")
        if description_drift:
            module.sdk_call(client.ModifyAccountDescription, build_description_request(models, p))
        if p["rotate_password"]:
            module.sdk_call(client.ResetAccountPassword, build_password_request(models, p))
        current = wait_for_account(module, client, models, p)
        module.exit_json(changed=True, **(diff or {}), account=current, msg="CynosDB account updated")
    except Exception as exc:
        module.fail_json(msg="Tencent Cloud API request failed", error=str(exc), error_code=getattr(exc, "get_code", lambda: None)(), request_id=getattr(exc, "get_request_id", lambda: None)())


def main():
    run_module()


if __name__ == "__main__":
    main()
