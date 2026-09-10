#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r"""
---
module: tdmysql_account
short_description: Manage Tencent Cloud TDSQL MySQL accounts
version_added: "0.14.0"
description:
  - Reconciles an account identified by the exact username and host pair, including creation, global privileges, password rotation and deletion.
  - Account descriptions are create-only in the TDSQL MySQL API and drift is surfaced explicitly.
options:
  state: {type: str, choices: [present, absent], default: present, description: Desired account presence.}
  instance_id: {type: str, required: true, description: Stable TDSQL MySQL instance ID.}
  username: {type: str, required: true, description: Login username.}
  host: {type: str, default: '%', description: Allowed client host; username and host form the identity.}
  password: {type: str, description: Plaintext password used for creation or explicit rotation.}
  encrypted_password: {type: str, description: Encrypted password used instead of plaintext.}
  rotate_password: {type: bool, default: false, description: Explicitly reset the password; this is an action on every enabled run.}
  description: {type: str, description: Create-only account description.}
  global_privileges: {type: list, elements: str, description: Full desired global privilege set.}
  allow_delete: {type: bool, default: false, description: Explicit destructive-operation guard.}
  wait: {type: bool, default: true, description: Wait for asynchronous account operations.}
  waiter_delay: {type: int, default: 5, description: Seconds between Flow checks.}
  waiter_timeout: {type: int, default: 600, description: Overall Flow timeout.}

extends_documentation_fragment:
  - susunola.tencentcloud.credentials
  - susunola.tencentcloud.region
  - susunola.tencentcloud.connection
  - susunola.tencentcloud.retry
  - susunola.tencentcloud.user_agent
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.tdmysql_account:
    instance_id: tdsql3-xxxxxxxx
    username: reporting
    host: 10.%
    password: '{{ vault_reporting_password }}'
    description: Read-only reporting account
    global_privileges: [SELECT]
"""
RETURN = r"""
account: {description: Effective account metadata., type: dict, returned: always}
"""

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload
from ansible_collections.susunola.tencentcloud.plugins.module_utils.tdmysql import _load, account_items, privileges_request, users_request
from ansible_collections.susunola.tencentcloud.plugins.module_utils.waiters import wait_for_state


def user(models, p):
    value = models.User()
    value.UserName, value.Host = p["username"], p["host"]
    return value


def create_request(models, p):
    request = models.CreateUsersRequest()
    request.InstanceId, request.Users = p["instance_id"], [user(models, p)]
    request.Password, request.EncryptedPassword, request.Description = p.get("password"), p.get("encrypted_password"), p.get("description")
    return request


def delete_request(models, p):
    request = models.DeleteUsersRequest()
    request.InstanceId, request.Users = p["instance_id"], [user(models, p)]
    return request


def reset_request(models, p):
    value = models.ResetUserPasswordInfo()
    value.UserName, value.Host = p["username"], p["host"]
    value.Password, value.EncryptedPassword = p.get("password"), p.get("encrypted_password")
    request = models.ResetUsersPasswordRequest()
    request.InstanceId, request.Users = p["instance_id"], [value]
    return request


def privileges_modify_request(models, p):
    request = models.ModifyUserPrivilegesRequest()
    request.InstanceId, request.Users = p["instance_id"], [user(models, p)]
    request.GlobalPrivileges = sorted(p["global_privileges"])
    return request


def flow_request(models, flow_id):
    request = models.DescribeFlowRequest()
    request.FlowId = flow_id
    return request


def wait_flow(module, client, models, flow_id):
    def poll():
        response = module.sdk_call(client.DescribeFlow, flow_request(models, flow_id))
        status = str(response.Status or "").lower()
        if status in ("failed", "paused"):
            module.fail_json(msg="TDSQL MySQL account operation failed", flow_id=flow_id, status=status, request_id=response.RequestId)
        return status

    wait_for_state(module, poll, ["success"], timeout=module.params["waiter_timeout"], delay=module.params["waiter_delay"])


def get(module, client, models, p):
    response = module.sdk_call(client.DescribeUsers, users_request(models, p["instance_id"]))
    values = [item for item in account_items(response) if item.get("UserName") == p["username"] and item.get("Host") == p["host"]]
    if len(values) > 1:
        module.fail_json(msg="Multiple TDSQL MySQL accounts matched the exact username and host")
    if values:
        privilege_response = module.sdk_call(client.DescribeUserPrivileges, privileges_request(models, p))
        values[0]["GlobalPrivileges"] = sorted(privilege_response.Privileges or [])
    return values[0] if values else None


def run_module():
    spec = {
        "state": {"choices": ["present", "absent"], "default": "present"},
        "instance_id": {"required": True},
        "username": {"required": True},
        "host": {"default": "%"},
        "password": {"no_log": True},
        "encrypted_password": {"no_log": True},
        "rotate_password": {"type": "bool", "default": False},
        "description": {},
        "global_privileges": {"type": "list", "elements": "str"},
        "allow_delete": {"type": "bool", "default": False},
        "wait": {"type": "bool", "default": True},
        "waiter_delay": {"type": "int", "default": 5},
        "waiter_timeout": {"type": "int", "default": 600},
    }
    module = TencentCloudModule(argument_spec=spec, supports_check_mode=True, mutually_exclusive=[("password", "encrypted_password")])
    p = module.params
    if p["rotate_password"] and not (p.get("password") or p.get("encrypted_password")):
        module.fail_json(msg="password or encrypted_password is required when rotate_password=true")
    module.require_sdk()
    models, cm = _load()
    client = module.create_client(cm.TdmysqlClient, "tdmysql.tencentcloudapi.com")
    try:
        current = get(module, client, models, p)
        if p["state"] == "absent":
            if current is None:
                module.exit_json(changed=False, account=None)
            if not p["allow_delete"]:
                module.fail_json(msg="allow_delete=true is required to delete a TDSQL MySQL account", account=current)
            diff_value = maybe_diff(module, current, None)
            if not module.check_mode:
                response = module.sdk_call(client.DeleteUsers, delete_request(models, p))
                if p["wait"]:
                    wait_flow(module, client, models, response.FlowId)
            module.exit_json(changed=True, **(diff_value or {}), account=None)
        if current is None:
            if not (p.get("password") or p.get("encrypted_password")):
                module.fail_json(msg="password or encrypted_password is required to create an account")
            target = {
                "UserName": p["username"],
                "Host": p["host"],
                "Description": p.get("description"),
                "GlobalPrivileges": sorted(p.get("global_privileges") or []),
            }
            diff_value = maybe_diff(module, None, target)
            if not module.check_mode:
                response = module.sdk_call(client.CreateUsers, create_request(models, p))
                if p["wait"]:
                    wait_flow(module, client, models, response.FlowId)
                if p.get("global_privileges") is not None:
                    module.sdk_call(client.ModifyUserPrivileges, privileges_modify_request(models, p))
                current = get(module, client, models, p)
            module.exit_json(changed=True, **(diff_value or {}), account=current if not module.check_mode else target)
        if p.get("description") is not None and current.get("Description") != p["description"]:
            module.fail_json(
                msg="TDSQL MySQL account description is create-only",
                immutable_drift={"Description": (current.get("Description"), p["description"])},
                account=current,
            )
        before = sorted(current.get("GlobalPrivileges") or [])
        desired = sorted(p["global_privileges"]) if p.get("global_privileges") is not None else before
        if before == desired and not p["rotate_password"]:
            module.exit_json(changed=False, account=current)
        target = dict(current, GlobalPrivileges=desired)
        diff_value = maybe_diff(module, current, target)
        if not module.check_mode:
            if before != desired:
                module.sdk_call(client.ModifyUserPrivileges, privileges_modify_request(models, p))
            if p["rotate_password"]:
                response = module.sdk_call(client.ResetUsersPassword, reset_request(models, p))
                if p["wait"]:
                    wait_flow(module, client, models, response.FlowId)
            current = get(module, client, models, p)
        module.exit_json(changed=True, **(diff_value or {}), account=current if not module.check_mode else target)
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
