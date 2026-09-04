#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type
DOCUMENTATION = r'''
---
module: cam_group_membership
short_description: Manage Tencent Cloud CAM user group membership
version_added: "0.13.0"
description: Idempotently adds a CAM sub-user to or removes it from a user group.
options:
  state: {description: Desired membership state., type: str, choices: [present, absent], default: present}
  group_id: {description: CAM user group ID., type: int, required: true}
  sub_uin: {description: CAM sub-user UIN., type: int}
  uid: {description: CAM sub-user UID., type: int}
  retries: {description: Number of retries for transient SDK failures., type: int, default: 5}
  waiter_delay: {description: Seconds between state-polling attempts., type: int, default: 5}
  waiter_timeout: {description: Overall timeout in seconds for state polling., type: int, default: 120}
  user_agent: {description: User-Agent value appended to SDK requests., type: str, default: ansible-collection.susunola.tencentcloud}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''
EXAMPLES = r'''
- susunola.tencentcloud.cam_group_membership:
    group_id: 12345
    sub_uin: 100000000001
'''
RETURN = r'''
membership:
  description: Managed user and group relationship.
  type: dict
  returned: always
'''

import time

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff


def _load_cam():
    from tencentcloud.cam.v20190116 import cam_client, models
    return models, cam_client


def build_list_request(models, params, page=1):
    request = models.ListGroupsForUserRequest()
    request.Page, request.Rp = page, 200
    request.SubUin, request.Uid = params.get("sub_uin"), params.get("uid")
    return request


def build_mutation_request(models, params, present):
    request = models.AddUserToGroupRequest() if present else models.RemoveUserFromGroupRequest()
    info = models.GroupIdOfUidInfo()
    info.GroupId, info.Uin, info.Uid = params["group_id"], params.get("sub_uin"), params.get("uid")
    request.Info = [info]
    return request


def is_member(module, client, models, params):
    page = 1
    while True:
        response = module.sdk_call(client.ListGroupsForUser, build_list_request(models, params, page))
        groups = list(getattr(response, "GroupInfo", None) or [])
        if any(int(getattr(group, "GroupId", 0)) == params["group_id"] for group in groups):
            return True
        if page * 200 >= int(getattr(response, "TotalNum", 0) or 0) or not groups:
            return False
        page += 1


def wait_for_membership(module, client, models, params, expected):
    deadline = time.time() + module.params["waiter_timeout"]
    while True:
        current = is_member(module, client, models, params)
        if current == expected:
            return current
        if time.time() >= deadline:
            module.fail_json(
                msg="Timed out waiting for CAM group membership",
                expected=expected, current=current,
            )
        time.sleep(module.params["waiter_delay"])


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "state": {"type": "str", "choices": ["present", "absent"], "default": "present"},
            "group_id": {"type": "int", "required": True},
            "sub_uin": {"type": "int"},
            "uid": {"type": "int"},
        },
        required_one_of=[("sub_uin", "uid")],
        mutually_exclusive=[("sub_uin", "uid")],
        supports_check_mode=True,
    )
    p = module.params
    module.require_sdk()
    models, cam_client = _load_cam()
    client = module.create_client(cam_client.CamClient, "cam.tencentcloudapi.com")
    try:
        current = is_member(module, client, models, p)
        desired = p["state"] == "present"
        membership = {"group_id": p["group_id"], "sub_uin": p["sub_uin"], "uid": p["uid"], "present": current}
        if current == desired:
            module.exit_json(changed=False, membership=membership, msg="CAM group membership is up to date")
        after = dict(membership, present=desired)
        diff = maybe_diff(module, membership, after)
        if module.check_mode:
            module.exit_json(changed=True, **(diff or {}), membership=membership, msg="Would update CAM group membership")
        request = build_mutation_request(models, p, desired)
        module.sdk_call(client.AddUserToGroup if desired else client.RemoveUserFromGroup, request)
        wait_for_membership(module, client, models, p, desired)
        module.exit_json(changed=True, **(diff or {}), membership=after, msg="CAM group membership updated")
    except Exception as exc:
        module.fail_json(
            msg="Tencent Cloud API request failed", error=str(exc),
            error_code=getattr(exc, "get_code", lambda: None)(),
            request_id=getattr(exc, "get_request_id", lambda: None)(),
        )


def main():
    run_module()


if __name__ == "__main__":
    main()
