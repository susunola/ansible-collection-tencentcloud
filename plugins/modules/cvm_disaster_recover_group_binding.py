#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function
__metaclass__ = type
DOCUMENTATION = r'''
---
module: cvm_disaster_recover_group_binding
short_description: Bind a Tencent Cloud CVM instance to a placement group
version_added: "0.14.0"
description: Adds or removes one CVM instance from a spread or partition placement group.
options:
  state: {type: str, choices: [present, absent], default: present, description: Desired binding state.}
  instance_id: {type: str, required: true, description: CVM instance ID.}
  group_id: {type: str, required: true, description: Placement-group ID.}
  partition_number: {type: int, description: Partition number for a partition placement group.}
  force_migrate: {type: bool, default: false, description: Allow host migration and instance restart when needed to establish the binding.}
  retries: {description: Number of retries for transient failures., type: int, default: 5}
  waiter_delay: {description: Seconds between polling attempts., type: int, default: 5}
  waiter_timeout: {description: Overall polling timeout in seconds., type: int, default: 120}
  user_agent: {description: User-Agent suffix., type: str, default: ansible-collection.susunola.tencentcloud}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''
EXAMPLES = r'''
- susunola.tencentcloud.cvm_disaster_recover_group_binding:
    instance_id: ins-xxxxxxxx
    group_id: ps-xxxxxxxx
    force_migrate: true
'''
RETURN = r'''binding: {description: Effective instance placement-group binding., type: dict, returned: always}'''
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


def _load():
    from tencentcloud.cvm.v20170312 import models, cvm_client
    return models, cvm_client
def describe_request(models, instance_id):
    request = models.DescribeInstancesRequest(); request.InstanceIds = [instance_id]; return request
def bind_request(models, p):
    request = models.ModifyInstancesDisasterRecoverGroupRequest(); request.InstanceIds = [p["instance_id"]]
    request.DisasterRecoverGroupIds, request.Force, request.PartitionNumber = [p["group_id"]], p["force_migrate"], p.get("partition_number"); return request
def unbind_request(models, p):
    request = models.DeleteInstancesDisasterRecoverGroupsRequest(); request.InstanceIds, request.DisasterRecoverGroupIds = [p["instance_id"]], [p["group_id"]]; return request
def find(module, client, models, p):
    response = module.sdk_call(client.DescribeInstances, describe_request(models, p["instance_id"])); values = list(response.InstanceSet or [])
    if not values: module.fail_json(msg="CVM instance was not found", instance_id=p["instance_id"])
    value = values[0]._serialize(allow_none=True); ids = value.get("DisasterRecoverGroupIds") or ([value["DisasterRecoverGroupId"]] if value.get("DisasterRecoverGroupId") else [])
    return {"InstanceId": p["instance_id"], "GroupIds": sorted(ids), "PartitionNumber": value.get("PartitionNumber")}


def run_module():
    module = TencentCloudModule(argument_spec={"state": {"choices": ["present", "absent"], "default": "present"}, "instance_id": {"required": True}, "group_id": {"required": True}, "partition_number": {"type": "int"}, "force_migrate": {"type": "bool", "default": False}}, supports_check_mode=True)
    p = module.params
    if p.get("partition_number") is not None and not 1 <= p["partition_number"] <= 30: module.fail_json(msg="partition_number must be between 1 and 30")
    module.require_sdk(); models, cm = _load(); client = module.create_client(cm.CvmClient, "cvm.tencentcloudapi.com")
    try:
        current = find(module, client, models, p); bound = p["group_id"] in current["GroupIds"]
        if p["state"] == "absent":
            if not bound: module.exit_json(changed=False, binding=None)
            diff = maybe_diff(module, current, None)
            if not module.check_mode: module.sdk_call(client.DeleteInstancesDisasterRecoverGroups, unbind_request(models, p))
            module.exit_json(changed=True, **(diff or {}), binding=current if module.check_mode else None)
        target = {"InstanceId": p["instance_id"], "GroupIds": [p["group_id"]], "PartitionNumber": p.get("partition_number")}
        matches = bound and (p.get("partition_number") is None or int(current.get("PartitionNumber") or 0) == p["partition_number"])
        if matches: module.exit_json(changed=False, binding=current)
        if current["GroupIds"] and not bound and not p["force_migrate"]: module.fail_json(msg="instance already belongs to another placement group; set force_migrate=true to move it", current_group_ids=current["GroupIds"])
        diff = maybe_diff(module, current, target)
        if not module.check_mode: module.sdk_call(client.ModifyInstancesDisasterRecoverGroup, bind_request(models, p)); current = find(module, client, models, p)
        module.exit_json(changed=True, **(diff or {}), binding=current)
    except Exception as exc: module.fail_json(**sdk_error_payload(exc))


def main(): run_module()
if __name__ == "__main__": main()
