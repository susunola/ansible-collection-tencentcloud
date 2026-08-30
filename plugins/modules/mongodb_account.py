#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type
DOCUMENTATION = r'''
---
module: mongodb_account
short_description: Manage TencentDB for MongoDB accounts
version_added: "0.14.0"
description:
  - Creates and deletes MongoDB accounts, reconciles database roles and explicitly rotates passwords.
  - The account description is immutable after creation in the current API.
options:
  state: {type: str, choices: [present, absent], default: present, description: Desired state.}
  instance_id: {type: str, required: true, description: MongoDB instance ID.}
  username: {type: str, required: true, description: Account name.}
  password: {type: str, description: Account password for creation or explicit rotation.}
  rotate_password: {type: bool, default: false, description: Explicitly reset the account password.}
  mongo_user_password: {type: str, description: "Password of the built-in mongouser, required for create and delete."}
  description: {type: str, default: '', description: Immutable account description.}
  roles:
    type: list
    elements: dict
    description: Complete desired database role set. Required when C(state=present).
    suboptions:
      namespace: {type: str, required: true, description: Database namespace or C(*).}
      access: {type: str, choices: [none, read, read_write], required: true, description: Access level.}
  retries: {description: Number of retries for transient failures., type: int, default: 5}
  waiter_delay: {description: Seconds between polling attempts., type: int, default: 5}
  waiter_timeout: {description: Overall polling timeout in seconds., type: int, default: 120}
  user_agent: {description: User-Agent suffix., type: str, default: ansible-collection.susunola.tencentcloud}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''
EXAMPLES = r'''
- susunola.tencentcloud.mongodb_account:
    instance_id: cmgo-xxxxxxxx
    username: app
    password: '{{ vault_app_password }}'
    mongo_user_password: '{{ vault_mongouser_password }}'
    roles:
      - namespace: orders
        access: read_write
'''
RETURN = r'''account: {description: MongoDB account metadata., type: dict, returned: always}'''

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import require_immutable_unchanged, sdk_error_payload

MASKS = {"none": 0, "read": 1, "read_write": 3}


def _load():
    from tencentcloud.mongodb.v20190725 import models, mongodb_client
    return models, mongodb_client


def auth_roles(models, roles):
    result = []
    for role in roles:
        item = models.Auth(); item.NameSpace, item.Mask = role["namespace"], MASKS[role["access"]]; result.append(item)
    return result


def describe_request(models, instance_id):
    request = models.DescribeAccountUsersRequest(); request.InstanceId = instance_id; return request


def create_request(models, p):
    request = models.CreateAccountUserRequest(); request.InstanceId, request.UserName = p["instance_id"], p["username"]
    request.Password, request.MongoUserPassword, request.UserDesc = p["password"], p["mongo_user_password"], p["description"]
    request.AuthRole = auth_roles(models, p["roles"]); return request


def privilege_request(models, p):
    request = models.SetAccountUserPrivilegeRequest(); request.InstanceId, request.UserName = p["instance_id"], p["username"]
    request.AuthRole = auth_roles(models, p["roles"]); return request


def password_request(models, p):
    request = models.ResetDBInstancePasswordRequest(); request.InstanceId, request.UserName, request.Password = p["instance_id"], p["username"], p["password"]; return request


def delete_request(models, p):
    request = models.DeleteAccountUserRequest(); request.InstanceId, request.UserName, request.MongoUserPassword = p["instance_id"], p["username"], p["mongo_user_password"]; return request


def normalized_roles(values):
    result = []
    for value in values or []:
        if hasattr(value, "_serialize"): value = value._serialize(allow_none=True)
        result.append({"namespace": value.get("NameSpace"), "access": {0: "none", 1: "read", 3: "read_write"}.get(value.get("Mask"), value.get("Mask"))})
    return sorted(result, key=lambda x: (x["namespace"], str(x["access"])))


def comparable(value):
    return {"UserName": value.get("UserName"), "UserDesc": value.get("UserDesc") or "", "AuthRole": normalized_roles(value.get("AuthRole"))}


def desired(p):
    return {"UserName": p["username"], "UserDesc": p["description"], "AuthRole": normalized_roles([{"NameSpace": x["namespace"], "Mask": MASKS[x["access"]]} for x in p["roles"]])}


def find(module, client, models, p):
    response = module.sdk_call(client.DescribeAccountUsers, describe_request(models, p["instance_id"]))
    for item in list(response.Users or []):
        value = item._serialize(allow_none=True)
        if value.get("UserName") == p["username"]: return value
    return None


def run_module():
    module = TencentCloudModule(argument_spec={"state": {"choices": ["present", "absent"], "default": "present"}, "instance_id": {"required": True}, "username": {"required": True}, "password": {"no_log": True}, "rotate_password": {"type": "bool", "default": False}, "mongo_user_password": {"no_log": True}, "description": {"default": ""}, "roles": {"type": "list", "elements": "dict", "options": {"namespace": {"required": True}, "access": {"choices": ["none", "read", "read_write"], "required": True}}}}, required_if=[("state", "present", ("roles",))], supports_check_mode=True)
    p = module.params
    if p["rotate_password"] and not p["password"]: module.fail_json(msg="password is required when rotate_password=true")
    module.require_sdk(); models, cm = _load(); client = module.create_client(cm.MongodbClient, "mongodb.tencentcloudapi.com")
    try:
        current = find(module, client, models, p)
        if p["state"] == "absent":
            if not current: module.exit_json(changed=False, account=None)
            if not p["mongo_user_password"]: module.fail_json(msg="mongo_user_password is required when deleting a MongoDB account")
            diff = maybe_diff(module, current, None)
            if not module.check_mode: module.sdk_call(client.DeleteAccountUser, delete_request(models, p))
            module.exit_json(changed=True, **(diff or {}), account=current if module.check_mode else None)
        target, before = desired(p), comparable(current) if current else None
        changed = before != target or p["rotate_password"]
        if not changed: module.exit_json(changed=False, account=current)
        diff = maybe_diff(module, before, target)
        if current: require_immutable_unchanged(module, before, target, ("UserDesc",), "MongoDB account")
        if not module.check_mode:
            if not current:
                if not p["password"] or not p["mongo_user_password"]: module.fail_json(msg="password and mongo_user_password are required when creating a MongoDB account")
                module.sdk_call(client.CreateAccountUser, create_request(models, p))
            else:
                if before["AuthRole"] != target["AuthRole"]: module.sdk_call(client.SetAccountUserPrivilege, privilege_request(models, p))
                if p["rotate_password"]: module.sdk_call(client.ResetDBInstancePassword, password_request(models, p))
            current = find(module, client, models, p)
        module.exit_json(changed=True, **(diff or {}), account=current)
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main(): run_module()
if __name__ == "__main__": main()
