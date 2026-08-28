#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
---
module: cam_policy_attachment
short_description: Manage a Tencent Cloud CAM policy attachment
version_added: "0.13.0"
description:
  - Idempotently attaches or detaches a CAM policy to a user, role or group.
options:
  state:
    description: Whether the attachment should exist.
    type: str
    choices: [present, absent]
    default: present
  policy_id:
    description: Numeric ID of the CAM policy.
    type: int
    required: true
  target_type:
    description: Type of CAM identity receiving the policy.
    type: str
    choices: [user, role, group]
    required: true
  target_id:
    description: UIN, role ID, or group ID of the target.
    type: raw
  target_name:
    description: Role name; used only when O(target_type=role).
    type: str
  retries: {description: Number of retries for transient SDK failures., type: int, default: 5}
  waiter_delay: {description: Seconds between state-polling attempts., type: int, default: 5}
  waiter_timeout: {description: Overall timeout in seconds for state polling., type: int, default: 120}
  user_agent: {description: User-Agent value appended to SDK requests., type: str, default: ansible-collection.susunola.tencentcloud}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''
EXAMPLES = r'''
- susunola.tencentcloud.cam_policy_attachment:
    policy_id: 123456
    target_type: role
    target_name: deployment-role
'''
RETURN = r'''
attachment:
  description: The normalized policy attachment.
  type: dict
  returned: always
'''

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff


def _load_cam():
    from tencentcloud.cam.v20190116 import cam_client, models

    return models, cam_client


def build_list_request(models, params, page=1, page_size=200):
    kind = params["target_type"]
    if kind == "user":
        request = models.ListAttachedUserPoliciesRequest()
        request.TargetUin, request.Page, request.Rp = params["target_id"], page, page_size
    elif kind == "role":
        request = models.ListAttachedRolePoliciesRequest()
        request.RoleId, request.RoleName, request.Page, request.Rp = params["target_id"], params["target_name"], page, page_size
    else:
        request = models.ListAttachedGroupPoliciesRequest()
        request.TargetGroupId, request.Page, request.Rp = params["target_id"], page, page_size
    return request


def is_attached(module, client, models, params):
    method = getattr(client, "ListAttached%sPolicies" % params["target_type"].capitalize())
    page, page_size = 1, 200
    while True:
        response = module.sdk_call(method, build_list_request(models, params, page, page_size))
        policies = getattr(response, "List", None) or getattr(response, "Policies", None) or []
        if any(int(getattr(item, "PolicyId", -1)) == params["policy_id"] for item in policies):
            return True
        total = int(getattr(response, "TotalNum", 0) or 0)
        if page * page_size >= total or not policies:
            return False
        page += 1


def build_mutation_request(models, params, attach):
    kind, policy_id = params["target_type"], params["policy_id"]
    if kind == "user":
        request = models.AttachUserPolicyRequest() if attach else models.DetachUserPolicyRequest()
    elif kind == "role":
        request = models.AttachRolePolicyRequest() if attach else models.DetachRolePolicyRequest()
    else:
        request = models.AttachGroupPolicyRequest() if attach else models.DetachGroupPolicyRequest()
    request.PolicyId = policy_id
    prefix = "Attach" if attach else "Detach"
    if kind == "user":
        setattr(request, prefix + "Uin", params["target_id"])
    elif kind == "group":
        setattr(request, prefix + "GroupId", params["target_id"])
    else:
        setattr(request, prefix + "RoleId", str(params["target_id"]) if params["target_id"] is not None else None)
        setattr(request, prefix + "RoleName", params["target_name"])
    return request


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "state": {"type": "str", "choices": ["present", "absent"], "default": "present"},
            "policy_id": {"type": "int", "required": True},
            "target_type": {"type": "str", "choices": ["user", "role", "group"], "required": True},
            "target_id": {"type": "raw"},
            "target_name": {"type": "str"},
        },
        supports_check_mode=True,
    )
    p = module.params
    if p["target_type"] in ("user", "group") and p["target_id"] is None:
        module.fail_json(msg="target_id is required for user and group attachments")
    if p["target_type"] == "role" and p["target_id"] is None and not p["target_name"]:
        module.fail_json(msg="target_id or target_name is required for role attachments")
    module.require_sdk()
    models, cam_client = _load_cam()
    client = module.create_client(cam_client.CamClient, "cam.tencentcloudapi.com")
    try:
        attached = is_attached(module, client, models, p)
        desired = p["state"] == "present"
        attachment = {"policy_id": p["policy_id"], "target_type": p["target_type"], "target_id": p["target_id"], "target_name": p["target_name"]}
        if attached == desired:
            module.exit_json(changed=False, attachment=attachment if attached else None, msg="CAM policy attachment is up to date")
        diff = maybe_diff(module, None if desired else attachment, attachment if desired else None)
        if module.check_mode:
            module.exit_json(changed=True, **(diff or {}), attachment=attachment if attached else None, msg="Would change CAM policy attachment")
        method = {
            ("user", True): client.AttachUserPolicy,
            ("role", True): client.AttachRolePolicy,
            ("group", True): client.AttachGroupPolicy,
            ("user", False): client.DetachUserPolicy,
            ("role", False): client.DetachRolePolicy,
            ("group", False): client.DetachGroupPolicy,
        }[(p["target_type"], desired)]
        module.sdk_call(method, build_mutation_request(models, p, desired))
        module.exit_json(changed=True, **(diff or {}), attachment=attachment if desired else None, msg="CAM policy attachment updated")
    except Exception as exc:
        module.fail_json(
            msg="Tencent Cloud API request failed",
            error=str(exc),
            error_code=getattr(exc, "get_code", lambda: None)(),
            request_id=getattr(exc, "get_request_id", lambda: None)(),
        )


def main():
    run_module()


if __name__ == "__main__":
    main()
