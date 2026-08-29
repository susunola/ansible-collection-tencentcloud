#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
---
module: postgresql_account
short_description: Manage TencentDB for PostgreSQL accounts
version_added: "0.14.0"
description:
  - Creates, updates and deletes PostgreSQL instance accounts.
  - Password replacement is explicit because the API never returns the current password.
options:
  state: {description: Desired state., type: str, choices: [present, absent], default: present}
  instance_id: {description: PostgreSQL instance ID., type: str, required: true}
  username: {description: Database account name., type: str, required: true}
  password: {description: Password used at creation or explicit rotation., type: str}
  rotate_password: {description: Explicitly reset the password during this run., type: bool, default: false}
  account_type: {description: Account privilege type., type: str, choices: [normal, tencentDBSuper], default: normal}
  remark: {description: Account remark., type: str, default: ''}
  cam_auth: {description: Enable CAM verification for the account., type: bool, default: false}
  retries: {description: Number of retries for transient failures., type: int, default: 5}
  waiter_delay: {description: Seconds between polling attempts., type: int, default: 5}
  waiter_timeout: {description: Overall polling timeout in seconds., type: int, default: 120}
  user_agent: {description: User-Agent suffix., type: str, default: ansible-collection.susunola.tencentcloud}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''
EXAMPLES = r'''
- susunola.tencentcloud.postgresql_account:
    instance_id: postgres-xxxxxxxx
    username: app_user
    password: '{{ vault_database_password }}'
    remark: Application account
'''
RETURN = r'''
account: {description: PostgreSQL account metadata., type: dict, returned: always}
'''

import time

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff


def _load_postgres():
    from tencentcloud.postgres.v20170312 import models, postgres_client
    return models, postgres_client


def build_describe_request(models, instance_id, offset=0):
    request = models.DescribeAccountsRequest()
    request.DBInstanceId, request.Offset, request.Limit = instance_id, offset, 100
    return request


def build_create_request(models, params):
    request = models.CreateAccountRequest()
    request.DBInstanceId, request.UserName = params["instance_id"], params["username"]
    request.Type, request.Password = params["account_type"], params["password"]
    request.Remark, request.OpenCam = params["remark"], params["cam_auth"]
    return request


def build_remark_request(models, instance_id, username, remark):
    request = models.ModifyAccountRemarkRequest()
    request.DBInstanceId, request.UserName, request.Remark = instance_id, username, remark
    return request


def build_password_request(models, instance_id, username, password):
    request = models.ResetAccountPasswordRequest()
    request.DBInstanceId, request.UserName, request.Password = instance_id, username, password
    return request


def build_delete_request(models, instance_id, username):
    request = models.DeleteAccountRequest()
    request.DBInstanceId, request.UserName = instance_id, username
    return request


def find_account(module, client, models, instance_id, username):
    offset = 0
    while True:
        response = module.sdk_call(client.DescribeAccounts, build_describe_request(models, instance_id, offset))
        items = list(getattr(response, "Details", None) or getattr(response, "AccountSet", None) or [])
        for item in items:
            value = item._serialize(allow_none=True)
            if value.get("UserName") == username:
                return value
        offset += len(items)
        if not items or offset >= int(getattr(response, "TotalCount", 0) or 0):
            return None


def wait_for_account(module, client, models, instance_id, username, remark=None, absent=False):
    deadline = time.time() + module.params["waiter_timeout"]
    while True:
        current = find_account(module, client, models, instance_id, username)
        if absent and current is None:
            return None
        if not absent and current and (remark is None or (current.get("Remark") or "") == remark):
            return current
        if time.time() >= deadline:
            module.fail_json(msg="Timed out waiting for PostgreSQL account convergence", account=current)
        time.sleep(module.params["waiter_delay"])


def run_module():
    module = TencentCloudModule(argument_spec={"state": {"type": "str", "choices": ["present", "absent"], "default": "present"}, "instance_id": {"type": "str", "required": True}, "username": {"type": "str", "required": True}, "password": {"type": "str", "no_log": True}, "rotate_password": {"type": "bool", "default": False}, "account_type": {"type": "str", "choices": ["normal", "tencentDBSuper"], "default": "normal"}, "remark": {"type": "str", "default": ""}, "cam_auth": {"type": "bool", "default": False}}, supports_check_mode=True)
    p = module.params
    if p["rotate_password"] and not p["password"]:
        module.fail_json(msg="password is required when rotate_password=true")
    module.require_sdk()
    models, client_module = _load_postgres()
    client = module.create_client(client_module.PostgresClient, "postgres.tencentcloudapi.com")
    try:
        current = find_account(module, client, models, p["instance_id"], p["username"])
        if p["state"] == "absent":
            if current is None:
                module.exit_json(changed=False, account=None, msg="PostgreSQL account is absent")
            diff = maybe_diff(module, current, None)
            if module.check_mode:
                module.exit_json(changed=True, **(diff or {}), account=current, msg="Would delete PostgreSQL account")
            module.sdk_call(client.DeleteAccount, build_delete_request(models, p["instance_id"], p["username"]))
            wait_for_account(module, client, models, p["instance_id"], p["username"], absent=True)
            module.exit_json(changed=True, **(diff or {}), account=None, msg="PostgreSQL account deleted")
        if current is None:
            if not p["password"]:
                module.fail_json(msg="password is required when creating a PostgreSQL account")
            desired = {"UserName": p["username"], "Remark": p["remark"], "UserType": p["account_type"], "OpenCam": p["cam_auth"]}
            diff = maybe_diff(module, None, desired)
            if module.check_mode:
                module.exit_json(changed=True, **(diff or {}), account=None, msg="Would create PostgreSQL account")
            module.sdk_call(client.CreateAccount, build_create_request(models, p))
            current = wait_for_account(module, client, models, p["instance_id"], p["username"], p["remark"])
            module.exit_json(changed=True, **(diff or {}), account=current, msg="PostgreSQL account created")
        remark_drift = (current.get("Remark") or "") != p["remark"]
        changed = remark_drift or p["rotate_password"]
        if not changed:
            module.exit_json(changed=False, account=current, msg="PostgreSQL account is up to date")
        desired = dict(current, Remark=p["remark"])
        diff = maybe_diff(module, current, desired)
        if module.check_mode:
            module.exit_json(changed=True, **(diff or {}), account=current, msg="Would update PostgreSQL account")
        if remark_drift:
            module.sdk_call(client.ModifyAccountRemark, build_remark_request(models, p["instance_id"], p["username"], p["remark"]))
        if p["rotate_password"]:
            module.sdk_call(client.ResetAccountPassword, build_password_request(models, p["instance_id"], p["username"], p["password"]))
        current = wait_for_account(module, client, models, p["instance_id"], p["username"], p["remark"])
        module.exit_json(changed=True, **(diff or {}), account=current, msg="PostgreSQL account updated")
    except Exception as exc:
        module.fail_json(msg="Tencent Cloud API request failed", error=str(exc), error_code=getattr(exc, "get_code", lambda: None)(), request_id=getattr(exc, "get_request_id", lambda: None)())


def main():
    run_module()


if __name__ == "__main__":
    main()
