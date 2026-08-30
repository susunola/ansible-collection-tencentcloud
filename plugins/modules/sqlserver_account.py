#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type
DOCUMENTATION = r'''
---
module: sqlserver_account
short_description: Manage TencentDB for SQL Server accounts
version_added: "0.14.0"
description: Creates and deletes accounts, reconciles database privileges and remarks, and explicitly rotates passwords.
options:
  state: {type: str, choices: [present, absent], default: present, description: Desired state.}
  instance_id: {type: str, required: true, description: SQL Server instance ID.}
  username: {type: str, required: true, description: Account name.}
  password: {type: str, description: Password for creation or explicit rotation.}
  rotate_password: {type: bool, default: false, description: Explicitly replace the account password.}
  remark: {type: str, default: '', description: Account remark.}
  account_type: {type: str, choices: [L0, L1, L2, L3], default: L3, description: Account privilege tier.}
  database_privileges:
    type: list
    elements: dict
    default: []
    description: Complete desired database privilege set.
    suboptions:
      database: {type: str, required: true, description: Database name.}
      privilege: {type: str, choices: [ReadWrite, ReadOnly, DBOwner], required: true, description: Database privilege.}
  retries: {description: Number of retries for transient failures., type: int, default: 5}
  waiter_delay: {description: Seconds between polling attempts., type: int, default: 5}
  waiter_timeout: {description: Overall polling timeout in seconds., type: int, default: 120}
  user_agent: {description: User-Agent suffix., type: str, default: ansible-collection.susunola.tencentcloud}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''
EXAMPLES = r'''
- susunola.tencentcloud.sqlserver_account:
    instance_id: mssql-xxxxxxxx
    username: app
    password: '{{ vault_sqlserver_password }}'
    database_privileges:
      - database: orders
        privilege: ReadWrite
'''
RETURN = r'''account: {description: SQL Server account metadata., type: dict, returned: always}'''

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


def _load():
    from tencentcloud.sqlserver.v20180328 import models, sqlserver_client
    return models, sqlserver_client


def _db_privileges(models, values, modify=False):
    result = []
    for value in values:
        item = (models.DBPrivilegeModifyInfo() if modify else models.DBPrivilege())
        item.DBName, item.Privilege = value["database"], value["privilege"]; result.append(item)
    return result


def describe_request(models, p, offset=0):
    request = models.DescribeAccountsRequest(); request.InstanceId, request.Offset, request.Limit, request.Name = p["instance_id"], offset, 100, p["username"]; return request


def create_request(models, p):
    request = models.CreateAccountRequest(); request.InstanceId = p["instance_id"]
    account = models.AccountCreateInfo(); account.UserName, account.Password, account.Remark, account.AccountType = p["username"], p["password"], p["remark"], p["account_type"]
    account.DBPrivileges = _db_privileges(models, p["database_privileges"]); request.Accounts = [account]; return request


def privilege_request(models, p, changes):
    request = models.ModifyAccountPrivilegeRequest(); request.InstanceId = p["instance_id"]
    account = models.AccountPrivilegeModifyInfo(); account.UserName, account.AccountType = p["username"], p["account_type"]
    account.DBPrivileges = _db_privileges(models, changes, True); request.Accounts = [account]; return request


def remark_request(models, p):
    request = models.ModifyAccountRemarkRequest(); request.InstanceId = p["instance_id"]
    account = models.AccountRemark(); account.UserName, account.Remark = p["username"], p["remark"]; request.Accounts = [account]; return request


def password_request(models, p):
    request = models.ResetAccountPasswordRequest(); request.InstanceId = p["instance_id"]
    account = models.AccountPassword(); account.UserName, account.Password = p["username"], p["password"]; request.Accounts = [account]; return request


def delete_request(models, p):
    request = models.DeleteAccountRequest(); request.InstanceId, request.UserNames = p["instance_id"], [p["username"]]; return request


def privileges(values):
    result = []
    for value in values or []:
        if hasattr(value, "_serialize"): value = value._serialize(allow_none=True)
        result.append({"database": value.get("DBName"), "privilege": value.get("Privilege")})
    return sorted(result, key=lambda x: x["database"])


def comparable(value):
    return {"Name": value.get("Name"), "Remark": value.get("Remark") or "", "AccountType": value.get("AccountType"), "Dbs": privileges(value.get("Dbs"))}


def desired(p):
    return {"Name": p["username"], "Remark": p["remark"], "AccountType": p["account_type"], "Dbs": privileges([{"DBName": x["database"], "Privilege": x["privilege"]} for x in p["database_privileges"]])}


def find(module, client, models, p):
    offset = 0
    while True:
        response = module.sdk_call(client.DescribeAccounts, describe_request(models, p, offset)); items = list(response.Accounts or [])
        for item in items:
            value = item._serialize(allow_none=True)
            if value.get("Name") == p["username"]: return value
        offset += len(items)
        if not items or offset >= int(response.TotalCount or 0): return None


def privilege_changes(before, target):
    old = {x["database"]: x["privilege"] for x in before}; new = {x["database"]: x["privilege"] for x in target}
    return [{"database": name, "privilege": new.get(name, "Delete")} for name in sorted(set(old) | set(new)) if old.get(name) != new.get(name)]


def run_module():
    module = TencentCloudModule(argument_spec={"state": {"choices": ["present", "absent"], "default": "present"}, "instance_id": {"required": True}, "username": {"required": True}, "password": {"no_log": True}, "rotate_password": {"type": "bool", "default": False}, "remark": {"default": ""}, "account_type": {"choices": ["L0", "L1", "L2", "L3"], "default": "L3"}, "database_privileges": {"type": "list", "elements": "dict", "default": [], "options": {"database": {"required": True}, "privilege": {"choices": ["ReadWrite", "ReadOnly", "DBOwner"], "required": True}}}}, supports_check_mode=True)
    p = module.params
    if p["rotate_password"] and not p["password"]: module.fail_json(msg="password is required when rotate_password=true")
    module.require_sdk(); models, cm = _load(); client = module.create_client(cm.SqlserverClient, "sqlserver.tencentcloudapi.com")
    try:
        current = find(module, client, models, p)
        if p["state"] == "absent":
            if not current: module.exit_json(changed=False, account=None)
            diff = maybe_diff(module, current, None)
            if not module.check_mode: module.sdk_call(client.DeleteAccount, delete_request(models, p))
            module.exit_json(changed=True, **(diff or {}), account=current if module.check_mode else None)
        target, before = desired(p), comparable(current) if current else None
        if before == target and not p["rotate_password"]: module.exit_json(changed=False, account=current)
        diff = maybe_diff(module, before, target)
        if not module.check_mode:
            if not current:
                if not p["password"]: module.fail_json(msg="password is required when creating a SQL Server account")
                module.sdk_call(client.CreateAccount, create_request(models, p))
            else:
                changes = privilege_changes(before["Dbs"], target["Dbs"])
                if changes or before["AccountType"] != target["AccountType"]: module.sdk_call(client.ModifyAccountPrivilege, privilege_request(models, p, changes))
                if before["Remark"] != target["Remark"]: module.sdk_call(client.ModifyAccountRemark, remark_request(models, p))
                if p["rotate_password"]: module.sdk_call(client.ResetAccountPassword, password_request(models, p))
            current = find(module, client, models, p)
        module.exit_json(changed=True, **(diff or {}), account=current)
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main(): run_module()
if __name__ == "__main__": main()
