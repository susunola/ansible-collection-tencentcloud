#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function
__metaclass__ = type
DOCUMENTATION = r'''
---
module: cfs_permission_group
short_description: Manage Tencent Cloud CFS permission groups
version_added: "0.14.0"
description: Creates, updates and deletes CFS client permission groups.
options:
  state: {type: str, choices: [present, absent], default: present, description: Desired state.}
  permission_group_id: {type: str, description: Existing permission group ID; preferred for rename and deletion.}
  name: {type: str, description: Permission group name.}
  description: {type: str, default: '', description: Permission group description.}
  retries: {description: Number of retries for transient failures., type: int, default: 5}
  waiter_delay: {description: Seconds between polling attempts., type: int, default: 5}
  waiter_timeout: {description: Overall polling timeout in seconds., type: int, default: 120}
  user_agent: {description: User-Agent suffix., type: str, default: ansible-collection.susunola.tencentcloud}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''
EXAMPLES = r'''
- susunola.tencentcloud.cfs_permission_group:
    name: production-nfs-clients
    description: Production application subnets
'''
RETURN = r'''permission_group: {description: CFS permission group metadata., type: dict, returned: always}'''
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


def _load():
    from tencentcloud.cfs.v20190719 import models, cfs_client
    return models, cfs_client
def describe_request(models): return models.DescribeCfsPGroupsRequest()
def create_request(models, p):
    request = models.CreateCfsPGroupRequest(); request.Name, request.DescInfo = p["name"], p["description"]; return request
def update_request(models, p, group_id):
    request = models.UpdateCfsPGroupRequest(); request.PGroupId, request.Name, request.DescInfo = group_id, p["name"], p["description"]; return request
def delete_request(models, group_id):
    request = models.DeleteCfsPGroupRequest(); request.PGroupId = group_id; return request
def find(module, client, models, p):
    response = module.sdk_call(client.DescribeCfsPGroups, describe_request(models)); matches = []
    for item in list(response.PGroupList or []):
        value = item._serialize(allow_none=True)
        if (p.get("permission_group_id") and value.get("PGroupId") == p["permission_group_id"]) or (not p.get("permission_group_id") and value.get("Name") == p.get("name")): matches.append(value)
    if len(matches) > 1: module.fail_json(msg="Multiple CFS permission groups matched; specify permission_group_id")
    return matches[0] if matches else None
def desired(p): return {"Name": p["name"], "DescInfo": p["description"]}
def comparable(value): return {"Name": value.get("Name"), "DescInfo": value.get("DescInfo") or ""}


def run_module():
    module = TencentCloudModule(argument_spec={"state": {"choices": ["present", "absent"], "default": "present"}, "permission_group_id": {}, "name": {}, "description": {"default": ""}}, required_one_of=[("permission_group_id", "name")], supports_check_mode=True)
    p = module.params
    if p["state"] == "present" and not p["name"]: module.fail_json(msg="name is required when state=present")
    module.require_sdk(); models, cm = _load(); client = module.create_client(cm.CfsClient, "cfs.tencentcloudapi.com")
    try:
        current = find(module, client, models, p)
        if p["state"] == "absent":
            if not current: module.exit_json(changed=False, permission_group=None)
            diff = maybe_diff(module, comparable(current), None)
            if not module.check_mode: module.sdk_call(client.DeleteCfsPGroup, delete_request(models, current["PGroupId"]))
            module.exit_json(changed=True, **(diff or {}), permission_group=current if module.check_mode else None)
        target = desired(p); before = comparable(current) if current else None
        if before == target: module.exit_json(changed=False, permission_group=current)
        diff = maybe_diff(module, before, target)
        if not module.check_mode:
            if current: module.sdk_call(client.UpdateCfsPGroup, update_request(models, p, current["PGroupId"]))
            else: p["permission_group_id"] = module.sdk_call(client.CreateCfsPGroup, create_request(models, p)).PGroupId
            current = find(module, client, models, p)
        module.exit_json(changed=True, **(diff or {}), permission_group=current)
    except Exception as exc: module.fail_json(**sdk_error_payload(exc))


def main(): run_module()
if __name__ == "__main__": main()
