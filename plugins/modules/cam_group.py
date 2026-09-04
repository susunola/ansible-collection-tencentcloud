#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type
DOCUMENTATION = r"""
---
module: cam_group
short_description: Manage Tencent Cloud CAM user groups
version_added: "0.14.0"
description: Creates, renames, updates and deletes CAM groups.
options:
  retries: {description: Number of retries for transient failures., type: int, default: 5}
  waiter_delay: {description: Seconds between polling attempts., type: int, default: 5}
  waiter_timeout: {description: Overall polling timeout in seconds., type: int, default: 120}
  user_agent: {description: User-Agent suffix., type: str, default: ansible-collection.susunola.tencentcloud}
  state: {type: str, choices: [present, absent], default: present, description: Desired state.}
  group_id: {type: int, description: Existing CAM group ID.}
  name: {type: str, description: Group name.}
  remark: {type: str, default: '', description: Group remark.}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.cam_group:
    name: platform-engineers
    remark: Platform engineering team
"""
RETURN = r"""group: {description: CAM group metadata., type: dict, returned: always}"""

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


def _load():
    from tencentcloud.cam.v20190116 import cam_client, models

    return models, cam_client


def find(module, client, models, group_id, name):
    page, matches = 1, []
    while True:
        request = models.ListGroupsRequest()
        request.Page, request.Rp = page, 200
        if name:
            request.Keyword = name
        response = module.sdk_call(client.ListGroups, request)
        items = list(response.GroupInfo or [])
        matches.extend(x._serialize(allow_none=True) for x in items if (group_id and x.GroupId == group_id) or (not group_id and x.GroupName == name))
        if len(items) < 200 or page * 200 >= int(response.TotalNum or 0):
            break
        page += 1
    if len(matches) > 1:
        module.fail_json(msg="Multiple CAM groups have the requested name", name=name)
    return matches[0] if matches else None


def run_module():
    module = TencentCloudModule(
        argument_spec={"state": {"choices": ["present", "absent"], "default": "present"}, "group_id": {"type": "int"}, "name": {}, "remark": {"default": ""}},
        required_one_of=[("group_id", "name")],
        supports_check_mode=True,
    )
    p = module.params
    if p["state"] == "present" and not p["name"]:
        module.fail_json(msg="name is required when state=present")
    module.require_sdk()
    models, cm = _load()
    client = module.create_client(cm.CamClient, "cam.tencentcloudapi.com")
    try:
        current = find(module, client, models, p["group_id"], p["name"])
        if p["state"] == "absent":
            if not current:
                module.exit_json(changed=False, group=None)
            diff = maybe_diff(module, current, None)
            if not module.check_mode:
                request = models.DeleteGroupRequest()
                request.GroupId = current["GroupId"]
                module.sdk_call(client.DeleteGroup, request)
            module.exit_json(changed=True, **(diff or {}), group=current if module.check_mode else None)
        target = {"GroupName": p["name"], "Remark": p["remark"]}
        before = {k: current.get(k) for k in target} if current else None
        if before == target:
            module.exit_json(changed=False, group=current)
        diff = maybe_diff(module, before, target)
        if not module.check_mode:
            if current:
                request = models.UpdateGroupRequest()
                request.GroupId = current["GroupId"]
                request.GroupName, request.Remark = p["name"], p["remark"]
                module.sdk_call(client.UpdateGroup, request)
                p["group_id"] = current["GroupId"]
            else:
                request = models.CreateGroupRequest()
                request.GroupName, request.Remark = p["name"], p["remark"]
                p["group_id"] = module.sdk_call(client.CreateGroup, request).GroupId
            current = find(module, client, models, p["group_id"], None)
        module.exit_json(changed=True, **(diff or {}), group=current)
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
