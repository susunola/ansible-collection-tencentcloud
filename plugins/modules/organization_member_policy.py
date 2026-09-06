#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type
DOCUMENTATION = r"""
---
module: organization_member_policy
short_description: Manage Tencent Cloud Organization member access policies
version_added: "0.14.0"
description: Creates, updates and deletes an access policy that associates an organization member with an access identity.
options:
  state: {type: str, choices: [present, absent], default: present, description: Desired state.}
  policy_id: {type: int, description: Existing policy ID.}
  member_uin: {type: int, required: true, description: Organization member UIN.}
  name: {type: str, description: Policy name. Required when creating.}
  identity_id: {type: int, description: Member access identity ID. Required when creating.}
  description: {type: str, default: '', description: Policy description.}
  retries: {description: Number of retries for transient failures., type: int, default: 5}
  waiter_delay: {description: Seconds between polling attempts., type: int, default: 5}
  waiter_timeout: {description: Overall polling timeout in seconds., type: int, default: 120}
  user_agent: {description: User-Agent suffix., type: str, default: ansible-collection.susunola.tencentcloud}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.organization_member_policy:
    member_uin: 100000000001
    name: operations-access
    identity_id: 12
    description: Operations access policy
"""
RETURN = r"""policy: {description: Organization member access policy metadata., type: dict, returned: always}"""

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import require_immutable_unchanged, sdk_error_payload


def _load():
    from tencentcloud.organization.v20210331 import models, organization_client

    return models, organization_client


def describe_request(models, member_uin, offset=0):
    request = models.DescribeOrganizationMemberPoliciesRequest()
    request.MemberUin, request.Offset, request.Limit = member_uin, offset, 50
    return request


def create_request(models, p):
    request = models.CreateOrganizationMemberPolicyRequest()
    request.MemberUin, request.PolicyName, request.IdentityId, request.Description = p["member_uin"], p["name"], p["identity_id"], p["description"]
    return request


def update_request(models, p, policy_id, wanted=None):
    wanted = wanted or desired(p)
    request = models.UpdateOrganizationMembersPolicyRequest()
    request.MemberUins, request.PolicyId, request.IdentityId, request.Description = [p["member_uin"]], policy_id, wanted["IdentityId"], wanted["Description"]
    return request


def delete_request(models, policy_id):
    request = models.DeleteOrganizationMembersPolicyRequest()
    request.PolicyId = policy_id
    return request


def find(module, client, models, p):
    offset = 0
    while True:
        response = module.sdk_call(client.DescribeOrganizationMemberPolicies, describe_request(models, p["member_uin"], offset))
        items = list(response.Items or [])
        for item in items:
            value = item._serialize(allow_none=True)
            if (p.get("policy_id") and int(value.get("PolicyId") or 0) == p["policy_id"]) or (
                not p.get("policy_id") and value.get("PolicyName") == p.get("name")
            ):
                return value
        offset += len(items)
        if not items or offset >= int(response.Total or 0):
            return None


def desired(p, current=None):
    current = current or {}
    return {
        "PolicyName": p["name"] if p["name"] is not None else current.get("PolicyName"),
        "IdentityId": p["identity_id"] if p["identity_id"] is not None else current.get("IdentityId"),
        "Description": p["description"],
    }


def comparable(value):
    return {key: value.get(key) for key in ("PolicyName", "IdentityId", "Description")}


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "state": {"choices": ["present", "absent"], "default": "present"},
            "policy_id": {"type": "int"},
            "member_uin": {"type": "int", "required": True},
            "name": {},
            "identity_id": {"type": "int"},
            "description": {"default": ""},
        },
        required_one_of=[("policy_id", "name")],
        supports_check_mode=True,
    )
    p = module.params
    module.require_sdk()
    models, cm = _load()
    client = module.create_client(cm.OrganizationClient, "organization.tencentcloudapi.com")
    try:
        current = find(module, client, models, p)
        if p["state"] == "absent":
            if not current:
                module.exit_json(changed=False, policy=None)
            diff = maybe_diff(module, current, None)
            if not module.check_mode:
                module.sdk_call(client.DeleteOrganizationMembersPolicy, delete_request(models, current["PolicyId"]))
            module.exit_json(changed=True, **(diff or {}), policy=current if module.check_mode else None)
        if not current and (not p["name"] or p["identity_id"] is None):
            module.fail_json(msg="name and identity_id are required when creating an organization member policy")
        target, before = desired(p, current), comparable(current) if current else None
        if before == target:
            module.exit_json(changed=False, policy=current)
        diff = maybe_diff(module, before, target)
        if not module.check_mode:
            if current:
                require_immutable_unchanged(module, before, target, ("PolicyName",), "organization member policy")
                module.sdk_call(client.UpdateOrganizationMembersPolicy, update_request(models, p, current["PolicyId"], target))
                p["policy_id"] = current["PolicyId"]
            else:
                p["policy_id"] = module.sdk_call(client.CreateOrganizationMemberPolicy, create_request(models, p)).PolicyId
            current = find(module, client, models, p)
        module.exit_json(changed=True, **(diff or {}), policy=current)
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
