#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type
DOCUMENTATION = r'''
---
module: organization_member
short_description: Manage Tencent Cloud Organization members
version_added: "0.14.0"
description: Creates, updates, moves and deletes organization-created members.
options:
  state: {type: str, choices: [present, absent], default: present, description: Desired state.}
  member_uin: {type: int, description: Existing member UIN.}
  name: {type: str, description: Member display name.}
  account_name: {type: str, description: Account name used when creating the member.}
  node_id: {type: int, description: Organization node ID.}
  remark: {type: str, default: '', description: Member remark.}
  permission_ids: {type: list, elements: int, default: [1, 2], description: Financial permission IDs used at creation.}
  identity_role_ids: {type: list, elements: int, default: [1], description: Access identity IDs used at creation.}
  allow_quit: {type: str, choices: [Allow, Denied], default: Denied, description: Whether the member may leave the organization.}
  retries: {description: Number of retries for transient failures., type: int, default: 5}
  waiter_delay: {description: Seconds between polling attempts., type: int, default: 5}
  waiter_timeout: {description: Overall polling timeout in seconds., type: int, default: 120}
  user_agent: {description: User-Agent suffix., type: str, default: ansible-collection.susunola.tencentcloud}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''
EXAMPLES = r'''
- susunola.tencentcloud.organization_member:
    name: production-team
    account_name: production-team
    node_id: 1001
    remark: Production account
'''
RETURN = r'''member: {description: Organization member metadata., type: dict, returned: always}'''

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


def _load():
    from tencentcloud.organization.v20210331 import models, organization_client
    return models, organization_client


def describe(models, offset=0):
    request = models.DescribeOrganizationMembersRequest(); request.Offset, request.Limit = offset, 50; return request


def create(models, p):
    request = models.CreateOrganizationMemberRequest()
    request.Name, request.AccountName, request.NodeId = p["name"], p["account_name"], p["node_id"]
    request.Remark, request.PolicyType = p["remark"], "Financial"
    request.PermissionIds, request.IdentityRoleID = sorted(p["permission_ids"]), sorted(p["identity_role_ids"])
    return request


def update(models, p, uin):
    request = models.UpdateOrganizationMemberRequest()
    request.MemberUin, request.Name, request.Remark = uin, p["name"], p["remark"]
    request.IsAllowQuit = p["allow_quit"]; return request


def move(models, node_id, uin):
    request = models.MoveOrganizationNodeMembersRequest(); request.NodeId, request.MemberUin = node_id, [uin]; return request


def delete(models, uin):
    request = models.DeleteOrganizationMembersRequest(); request.MemberUin = [uin]; return request


def find(module, client, models, p):
    offset = 0
    while True:
        response = module.sdk_call(client.DescribeOrganizationMembers, describe(models, offset)); items = list(response.Items or [])
        for item in items:
            value = item._serialize(allow_none=True)
            if (p.get("member_uin") and int(value.get("MemberUin") or 0) == p["member_uin"]) or (not p.get("member_uin") and value.get("Name") == p.get("name")): return value
        offset += len(items)
        if not items or offset >= int(response.Total or 0): return None


def desired(p, current=None):
    current = current or {}
    return {"Name": p["name"] if p["name"] is not None else current.get("Name"), "NodeId": p["node_id"] if p["node_id"] is not None else current.get("NodeId"), "Remark": p["remark"], "IsAllowQuit": p["allow_quit"]}


def comparable(value):
    return {key: value.get(key) for key in ("Name", "NodeId", "Remark", "IsAllowQuit")}


def run_module():
    module = TencentCloudModule(argument_spec={
        "state": {"choices": ["present", "absent"], "default": "present"}, "member_uin": {"type": "int"}, "name": {},
        "account_name": {}, "node_id": {"type": "int"}, "remark": {"default": ""},
        "permission_ids": {"type": "list", "elements": "int", "default": [1, 2]},
        "identity_role_ids": {"type": "list", "elements": "int", "default": [1]},
        "allow_quit": {"choices": ["Allow", "Denied"], "default": "Denied"},
    }, required_one_of=[("member_uin", "name")], supports_check_mode=True)
    p = module.params; module.require_sdk(); models, cm = _load(); client = module.create_client(cm.OrganizationClient, "organization.tencentcloudapi.com")
    try:
        current = find(module, client, models, p)
        if p["state"] == "absent":
            if not current: module.exit_json(changed=False, member=None)
            diff = maybe_diff(module, current, None)
            if not module.check_mode: module.sdk_call(client.DeleteOrganizationMembers, delete(models, current["MemberUin"]))
            module.exit_json(changed=True, **(diff or {}), member=current if module.check_mode else None)
        if not current and (not p["name"] or not p["account_name"] or p["node_id"] is None):
            module.fail_json(msg="name, account_name and node_id are required when creating an organization member")
        target, before = desired(p, current), comparable(current) if current else None
        if before == target: module.exit_json(changed=False, member=current)
        diff = maybe_diff(module, before, target)
        if not module.check_mode:
            if not current:
                response = module.sdk_call(client.CreateOrganizationMember, create(models, p)); p["member_uin"] = int(response.Uin)
            else:
                uin = int(current["MemberUin"])
                if any(before[k] != target[k] for k in ("Name", "Remark", "IsAllowQuit")): module.sdk_call(client.UpdateOrganizationMember, update(models, p, uin))
                if before["NodeId"] != target["NodeId"]:
                    if p["node_id"] is None: module.fail_json(msg="node_id cannot be cleared")
                    module.sdk_call(client.MoveOrganizationNodeMembers, move(models, p["node_id"], uin))
                p["member_uin"] = uin
            current = find(module, client, models, p)
        module.exit_json(changed=True, **(diff or {}), member=current)
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main(): run_module()
if __name__ == "__main__": main()
