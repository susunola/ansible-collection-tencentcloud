#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type
DOCUMENTATION = r'''
---
module: cdb_account
short_description: Manage TencentDB for MySQL accounts
version_added: "0.14.0"
description: Creates, updates, rotates and deletes a CDB account identified by user and host.
options:
  state: {type: str, choices: [present, absent], default: present, description: Desired state.}
  instance_id: {type: str, required: true, description: CDB instance ID.}
  username: {type: str, required: true, description: Account name.}
  host: {type: str, default: '%', description: Account host expression.}
  password: {type: str, description: Password for creation or rotation.}
  rotate_password: {type: bool, default: false, description: Explicitly replace the account password.}
  description: {type: str, default: '', description: Account description.}
  max_user_connections: {type: int, default: 10240, description: Maximum connections for this account.}
  retries: {description: Number of retries for transient failures., type: int, default: 5}
  waiter_delay: {description: Seconds between polling attempts., type: int, default: 5}
  waiter_timeout: {description: Overall polling timeout in seconds., type: int, default: 120}
  user_agent: {description: User-Agent suffix., type: str, default: ansible-collection.susunola.tencentcloud}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''
EXAMPLES = r'''
- susunola.tencentcloud.cdb_account:
    instance_id: cdb-xxxxxxxx
    username: app
    host: 10.%
    password: '{{ vault_mysql_password }}'
    description: Application account
'''
RETURN = r'''account: {description: CDB account metadata., type: dict, returned: always}'''

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


def _load():
    from tencentcloud.cdb.v20170320 import cdb_client, models
    return models, cdb_client


def account(models, user, host):
    value = models.Account(); value.User, value.Host = user, host; return value


def describe(models, p, offset=0):
    request = models.DescribeAccountsRequest(); request.InstanceId, request.Offset, request.Limit = p["instance_id"], offset, 100; return request


def create(models, p):
    request = models.CreateAccountsRequest(); request.InstanceId = p["instance_id"]
    request.Accounts, request.Password = [account(models, p["username"], p["host"])], p["password"]
    request.Description, request.MaxUserConnections = p["description"], p["max_user_connections"]; return request


def simple(models, kind, p):
    request = getattr(models, kind + "Request")(); request.InstanceId = p["instance_id"]
    request.Accounts = [account(models, p["username"], p["host"])]; return request


def find(module, client, models, p):
    offset = 0
    while True:
        response = module.sdk_call(client.DescribeAccounts, describe(models, p, offset)); items = list(response.Items or [])
        for item in items:
            value = item._serialize(allow_none=True)
            if value.get("User") == p["username"] and value.get("Host") == p["host"]: return value
        offset += len(items)
        if not items or offset >= int(response.TotalCount or 0): return None


def desired(p):
    return {"User": p["username"], "Host": p["host"], "Notes": p["description"], "MaxUserConnections": p["max_user_connections"]}


def comparable(value):
    return {key: value.get(key) for key in ("User", "Host", "Notes", "MaxUserConnections")}


def run_module():
    module = TencentCloudModule(argument_spec={
        "state": {"choices": ["present", "absent"], "default": "present"}, "instance_id": {"required": True},
        "username": {"required": True}, "host": {"default": "%"}, "password": {"no_log": True},
        "rotate_password": {"type": "bool", "default": False}, "description": {"default": ""},
        "max_user_connections": {"type": "int", "default": 10240},
    }, supports_check_mode=True)
    p = module.params
    if p["rotate_password"] and not p["password"]: module.fail_json(msg="password is required when rotate_password=true")
    module.require_sdk(); models, cm = _load(); client = module.create_client(cm.CdbClient, "cdb.tencentcloudapi.com")
    try:
        current = find(module, client, models, p)
        if p["state"] == "absent":
            if not current: module.exit_json(changed=False, account=None)
            diff = maybe_diff(module, current, None)
            if not module.check_mode: module.sdk_call(client.DeleteAccounts, simple(models, "DeleteAccounts", p))
            module.exit_json(changed=True, **(diff or {}), account=current if module.check_mode else None)
        target, before = desired(p), comparable(current) if current else None
        changed = before != target or p["rotate_password"]
        if not changed: module.exit_json(changed=False, account=current)
        diff = maybe_diff(module, before, target)
        if not module.check_mode:
            if not current:
                if not p["password"]: module.fail_json(msg="password is required when creating a CDB account")
                module.sdk_call(client.CreateAccounts, create(models, p))
            else:
                if before["Notes"] != target["Notes"]:
                    request = simple(models, "ModifyAccountDescription", p); request.Description = p["description"]
                    module.sdk_call(client.ModifyAccountDescription, request)
                if before["MaxUserConnections"] != target["MaxUserConnections"]:
                    request = simple(models, "ModifyAccountMaxUserConnections", p); request.MaxUserConnections = p["max_user_connections"]
                    module.sdk_call(client.ModifyAccountMaxUserConnections, request)
                if p["rotate_password"]:
                    request = simple(models, "ModifyAccountPassword", p); request.NewPassword = p["password"]
                    module.sdk_call(client.ModifyAccountPassword, request)
            current = find(module, client, models, p)
        module.exit_json(changed=True, **(diff or {}), account=current)
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main(): run_module()
if __name__ == "__main__": main()
