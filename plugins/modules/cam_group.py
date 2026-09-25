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

  state:
    description:
      - C(present) creates the group with V(CreateGroup) when it does not exist and updates it with V(UpdateGroup)
        when it differs. C(absent) deletes it with V(DeleteGroup).
    type: str
    choices: [present, absent]
    default: present
  group_id:
    description:
      - Identifies the group to manage; one of this or O(name) is required, and the module matches on the id
        when it is given.
    type: int
  name:
    description:
      - Identifies the group to manage; one of this or O(group_id) is required, and the name is only used when
        O(group_id) is not given.
    type: str
  remark:
    description:
      - Group remark.
    type: str
    default: ''
extends_documentation_fragment:
  - susunola.tencentcloud.credentials
  - susunola.tencentcloud.region
  - susunola.tencentcloud.connection
  - susunola.tencentcloud.timeout
  - susunola.tencentcloud.retry
  - susunola.tencentcloud.user_agent
  - susunola.tencentcloud.waiter
attributes:
  check_mode:
    description:
      - Can run in C(check_mode), reading the current state and predicting
        the result without issuing a write API call.
    support: full
  diff_mode:
    description:
      - Returns the difference between the observed and the requested state
        when the task runs with C(--diff).
    support: full
  idempotent:
    description:
      - Reconciles the resource against its live state, so running again
        with the same arguments leaves it unchanged and reports C(changed=false).
    support: full
seealso:
  - module: susunola.tencentcloud.cam_group_info
    description: Gather information about Tencent Cloud CAM groups.
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.cam_group:
    name: platform-engineers
    remark: Platform engineering team

- name: Delete the group
  susunola.tencentcloud.cam_group:
    state: absent
    name: platform-engineers
"""
RETURN = r"""group:
  description:
    - CAM group metadata.
  returned: always
  type: dict
  sample:
    # shape captured from this module's unit tests -- scripts/add_return_samples.py
    GroupId: 1000001
    GroupName: platform-engineers
    Remark: Platform engineering team
"""

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import fail_from_sdk_error


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
        fail_from_sdk_error(module, exc)


def main():
    run_module()


if __name__ == "__main__":
    main()
