#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type
DOCUMENTATION = r"""
---
module: cfs_permission_rule
short_description: Manage Tencent Cloud CFS permission rules
version_added: "0.14.0"
description: Creates, updates and deletes one client rule in a CFS permission group.
options:
  state: {type: str, choices: [present, absent], default: present, description: Desired state.}
  permission_group_id: {type: str, required: true, description: Parent CFS permission group ID.}
  rule_id: {type: str, description: Existing rule ID; preferred when changing the client expression.}
  client_ip: {type: str, description: "Authorized client IP, CIDR or wildcard expression."}
  priority: {type: int, default: 1, description: Rule priority.}
  access: {type: str, choices: [RO, RW], default: RW, description: Read-only or read-write access.}
  user_permission:
    type: str
    choices: [all_squash, no_all_squash, root_squash, no_root_squash]
    default: no_root_squash
    description: NFS user mapping behavior.
  retries: {description: Number of retries for transient failures., type: int, default: 5}
  waiter_delay: {description: Seconds between polling attempts., type: int, default: 5}
  waiter_timeout: {description: Overall polling timeout in seconds., type: int, default: 120}
  user_agent: {description: User-Agent suffix., type: str, default: ansible-collection.susunola.tencentcloud}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.cfs_permission_rule:
    permission_group_id: pgroup-xxxxxxxx
    client_ip: 10.0.0.0/16
    access: RW
    user_permission: root_squash
    priority: 10
"""
RETURN = r"""rule: {description: CFS permission rule metadata., type: dict, returned: always}"""
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


def _load():
    from tencentcloud.cfs.v20190719 import models, cfs_client

    return models, cfs_client


def describe_request(models, group_id):
    request = models.DescribeCfsRulesRequest()
    request.PGroupId = group_id
    return request


def _apply(request, p, rule_id=None):
    request.PGroupId, request.AuthClientIp, request.Priority = p["permission_group_id"], p["client_ip"], p["priority"]
    request.RWPermission, request.UserPermission = p["access"], p["user_permission"]
    if rule_id is not None:
        request.RuleId = rule_id
    return request


def create_request(models, p):
    return _apply(models.CreateCfsRuleRequest(), p)


def update_request(models, p, rule_id):
    return _apply(models.UpdateCfsRuleRequest(), p, rule_id)


def delete_request(models, p, rule_id):
    request = models.DeleteCfsRuleRequest()
    request.PGroupId, request.RuleId = p["permission_group_id"], rule_id
    return request


def find(module, client, models, p):
    response = module.sdk_call(client.DescribeCfsRules, describe_request(models, p["permission_group_id"]))
    matches = []
    for item in list(response.RuleList or []):
        value = item._serialize(allow_none=True)
        if (p.get("rule_id") and str(value.get("RuleId")) == p["rule_id"]) or (not p.get("rule_id") and value.get("AuthClientIp") == p.get("client_ip")):
            matches.append(value)
    if len(matches) > 1:
        module.fail_json(msg="Multiple CFS permission rules matched; specify rule_id")
    return matches[0] if matches else None


def desired(p):
    return {"AuthClientIp": p["client_ip"], "Priority": p["priority"], "RWPermission": p["access"], "UserPermission": p["user_permission"]}


def comparable(value):
    return {
        "AuthClientIp": value.get("AuthClientIp"),
        "Priority": int(value.get("Priority") or 0),
        "RWPermission": value.get("RWPermission"),
        "UserPermission": value.get("UserPermission"),
    }


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "state": {"choices": ["present", "absent"], "default": "present"},
            "permission_group_id": {"required": True},
            "rule_id": {},
            "client_ip": {},
            "priority": {"type": "int", "default": 1},
            "access": {"choices": ["RO", "RW"], "default": "RW"},
            "user_permission": {"choices": ["all_squash", "no_all_squash", "root_squash", "no_root_squash"], "default": "no_root_squash"},
        },
        required_one_of=[("rule_id", "client_ip")],
        supports_check_mode=True,
    )
    p = module.params
    if p["state"] == "present" and not p["client_ip"]:
        module.fail_json(msg="client_ip is required when state=present")
    module.require_sdk()
    models, cm = _load()
    client = module.create_client(cm.CfsClient, "cfs.tencentcloudapi.com")
    try:
        current = find(module, client, models, p)
        if p["state"] == "absent":
            if not current:
                module.exit_json(changed=False, rule=None)
            diff = maybe_diff(module, comparable(current), None)
            if not module.check_mode:
                module.sdk_call(client.DeleteCfsRule, delete_request(models, p, str(current["RuleId"])))
            module.exit_json(changed=True, **(diff or {}), rule=current if module.check_mode else None)
        target = desired(p)
        before = comparable(current) if current else None
        if before == target:
            module.exit_json(changed=False, rule=current)
        diff = maybe_diff(module, before, target)
        if not module.check_mode:
            if current:
                module.sdk_call(client.UpdateCfsRule, update_request(models, p, str(current["RuleId"])))
            else:
                p["rule_id"] = str(module.sdk_call(client.CreateCfsRule, create_request(models, p)).RuleId)
            current = find(module, client, models, p)
        module.exit_json(changed=True, **(diff or {}), rule=current)
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
