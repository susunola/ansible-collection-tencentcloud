#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function
__metaclass__ = type
DOCUMENTATION = r'''
---
module: dlc_user
short_description: Manage Tencent Cloud Data Lake Compute users
version_added: "0.14.0"
description:
  - Creates, discovers, updates and deletes DLC authorized users.
  - Description and user type are mutable; alias and account type are immutable.
options:
  state: {type: str, choices: [present, absent], default: present, description: Desired DLC user state.}
  user_id: {type: str, required: true, description: CAM sub-user UIN or role account identifier.}
  description: {type: str, description: Mutable user description.}
  user_type: {type: str, choices: [ADMIN, COMMON], description: Desired DLC user type; defaults to COMMON only during creation.}
  alias: {type: str, description: Creation-time user alias shorter than 50 characters.}
  principal_type: {type: str, choices: [UserAccount, RoleAccount], default: UserAccount, description: Creation-time DLC principal type.}
  account_source: {type: str, choices: [TencentAccount, EntraAccount], default: TencentAccount, description: Account source used by query, update and deletion APIs.}
  initial_policies: {type: list, elements: dict, description: Policies attached during creation; use dedicated policy resources for ongoing reconciliation.}
  initial_work_group_ids: {type: list, elements: int, description: Work groups attached during creation; use C(dlc_work_group_membership) for ongoing reconciliation.}
  allow_delete_bound: {type: bool, default: false, description: Explicitly authorize deleting a user that still has policies or work groups.}
  allow_delete: {type: bool, default: false, description: Explicitly authorize user deletion.}
  wait: {type: bool, default: true, description: Wait for mutation convergence.}
  waiter_delay: {type: int, default: 5, description: Seconds between polls.}
  waiter_timeout: {type: int, default: 120, description: Overall convergence timeout.}
  retries: {type: int, default: 5, description: Number of retries for transient failures.}
  user_agent: {type: str, default: ansible-collection.susunola.tencentcloud, description: User-Agent suffix.}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''
EXAMPLES = r'''
- susunola.tencentcloud.dlc_user:
    user_id: '100012345678'
    alias: analytics-engineer
    description: Analytics engineering account
    user_type: COMMON

- susunola.tencentcloud.dlc_user:
    user_id: '100012345678'
    state: absent
    allow_delete: true
'''
RETURN = r'''user: {description: Effective DLC user metadata., type: dict, returned: always}
user_id: {description: DLC user identifier., type: str, returned: always}'''
import json
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload
from ansible_collections.susunola.tencentcloud.plugins.module_utils.waiters import wait_for_state


def _load():
    from tencentcloud.dlc.v20210125 import models, dlc_client
    return models, dlc_client


def describe_request(models, p, offset=0):
    request = models.DescribeUsersRequest(); request.UserId = p["user_id"]
    request.Offset, request.Limit, request.AccountType = offset, 100, p["account_source"]
    return request


def find(module, client, models, p):
    offset, matches = 0, []
    while True:
        response = module.sdk_call(client.DescribeUsers, describe_request(models, p, offset)); page = response.UserSet or []
        matches.extend(x._serialize(allow_none=True) for x in page if x.UserId == p["user_id"])
        offset += len(page)
        if not page or offset >= int(response.TotalCount or 0): break
    if len(matches) > 1: module.fail_json(msg="Multiple DLC users matched the exact user_id", user_id=p["user_id"])
    return matches[0] if matches else None


def create_request(models, p):
    payload = {"UserId": p["user_id"], "UserDescription": p.get("description"), "UserType": p.get("user_type") or "COMMON",
               "UserAlias": p.get("alias"), "AccountType": p["principal_type"],
               "PolicySet": p.get("initial_policies"), "WorkGroupIds": p.get("initial_work_group_ids")}
    request = models.CreateUserRequest(); request.from_json_string(json.dumps(payload)); return request


def modify_request(models, p):
    request = models.ModifyUserRequest(); request.UserId, request.UserDescription = p["user_id"], p["description"]
    request.AccountType = p["account_source"]; return request


def type_request(models, p):
    request = models.ModifyUserTypeRequest(); request.UserId, request.UserType = p["user_id"], p["user_type"]
    request.AccountType = p["account_source"]; return request


def delete_request(models, p):
    request = models.DeleteUserRequest(); request.UserIds, request.AccountType = [p["user_id"]], p["account_source"]; return request


def wait_user(module, client, models, p, present, desired=None):
    def poll():
        current = find(module, client, models, p)
        if current is None: return "absent"
        if desired and any((current.get(key) or "") != value for key, value in desired.items()): return "pending"
        return "present"
    wait_for_state(module, poll, ["present" if present else "absent"], timeout=p["waiter_timeout"], delay=p["waiter_delay"])


def run_module():
    spec = {
        "state": {"choices": ["present", "absent"], "default": "present"}, "user_id": {"required": True},
        "description": {}, "user_type": {"choices": ["ADMIN", "COMMON"]}, "alias": {},
        "principal_type": {"choices": ["UserAccount", "RoleAccount"], "default": "UserAccount"},
        "account_source": {"choices": ["TencentAccount", "EntraAccount"], "default": "TencentAccount"},
        "initial_policies": {"type": "list", "elements": "dict"}, "initial_work_group_ids": {"type": "list", "elements": "int"},
        "allow_delete_bound": {"type": "bool", "default": False}, "allow_delete": {"type": "bool", "default": False},
        "wait": {"type": "bool", "default": True}, "waiter_delay": {"type": "int", "default": 5}, "waiter_timeout": {"type": "int", "default": 120},
    }
    module = TencentCloudModule(argument_spec=spec, supports_check_mode=True); p = module.params
    if p.get("alias") is not None and len(p["alias"]) >= 50: module.fail_json(msg="DLC user alias must be shorter than 50 characters")
    if p.get("user_type") == "ADMIN" and (p.get("initial_policies") or p.get("initial_work_group_ids")): module.fail_json(msg="ADMIN users cannot declare initial policies or work groups")
    module.require_sdk(); models, cm = _load(); client = module.create_client(cm.DlcClient, "dlc.tencentcloudapi.com")
    try:
        current = find(module, client, models, p)
        if p["state"] == "absent":
            if not current: module.exit_json(changed=False, user=None, user_id=p["user_id"])
            if current.get("IsOwner"): module.fail_json(msg="The DLC owner account cannot be deleted", user=current)
            if not p["allow_delete"]: module.fail_json(msg="set allow_delete=true to authorize deleting the DLC user", user=current)
            if (current.get("PolicySet") or current.get("WorkGroupSet")) and not p["allow_delete_bound"]: module.fail_json(msg="DLC user still has policies or work groups; set allow_delete_bound=true to authorize deletion", user=current)
            diff_value = maybe_diff(module, current, None)
            if not module.check_mode:
                module.sdk_call(client.DeleteUser, delete_request(models, p))
                if p["wait"]: wait_user(module, client, models, p, False)
            module.exit_json(changed=True, **(diff_value or {}), user=None, user_id=p["user_id"])
        if not current:
            target = {"UserId": p["user_id"], "UserDescription": p.get("description") or "", "UserType": p.get("user_type") or "COMMON", "UserAlias": p.get("alias"), "AccountType": p["principal_type"]}
            diff_value = maybe_diff(module, None, target)
            if not module.check_mode:
                module.sdk_call(client.CreateUser, create_request(models, p))
                if p["wait"]: wait_user(module, client, models, p, True)
                current = find(module, client, models, p)
            module.exit_json(changed=True, **(diff_value or {}), user=current if not module.check_mode else target, user_id=p["user_id"])
        immutable = {"UserAlias": p.get("alias")}
        drift = {key: (current.get(key), value) for key, value in immutable.items() if value is not None and current.get(key) != value}
        if drift: module.fail_json(msg="DLC user alias and account type are immutable", immutable_drift=drift)
        changes = {}
        if p.get("description") is not None and (current.get("UserDescription") or "") != p["description"]: changes["UserDescription"] = ((current.get("UserDescription") or ""), p["description"])
        if p.get("user_type") is not None and current.get("UserType") != p["user_type"]: changes["UserType"] = (current.get("UserType"), p["user_type"])
        if not changes: module.exit_json(changed=False, user=current, user_id=p["user_id"])
        after = dict(current); after.update({key: value[1] for key, value in changes.items()}); diff_value = maybe_diff(module, current, after)
        if not module.check_mode:
            if "UserDescription" in changes: module.sdk_call(client.ModifyUser, modify_request(models, p))
            if "UserType" in changes: module.sdk_call(client.ModifyUserType, type_request(models, p))
            if p["wait"]: wait_user(module, client, models, p, True, {key: value[1] for key, value in changes.items()})
            current = find(module, client, models, p)
        module.exit_json(changed=True, **(diff_value or {}), user=current if not module.check_mode else after, user_id=p["user_id"])
    except Exception as exc: module.fail_json(**sdk_error_payload(exc))


def main(): run_module()
if __name__ == "__main__": main()
