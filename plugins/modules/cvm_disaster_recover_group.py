#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function
__metaclass__ = type
DOCUMENTATION = r'''
---
module: cvm_disaster_recover_group
short_description: Manage Tencent Cloud CVM placement groups
version_added: "0.14.0"
description:
  - Creates, updates and deletes CVM spread or partition placement groups.
  - Placement type, strategy and partition count are immutable; replacement is allowed only for an empty group.
options:
  state: {type: str, choices: [present, absent], default: present, description: Desired state.}
  group_id: {type: str, description: Existing placement-group ID.}
  name: {type: str, description: Placement-group name.}
  placement_type: {type: str, choices: [HOST, SW, RACK], default: HOST, description: Failure-domain level.}
  strategy: {type: str, choices: [SPREAD, PARTITION], default: SPREAD, description: Placement strategy.}
  partition_count: {type: int, description: Partition count from 2 through 30 for PARTITION strategy.}
  affinity: {type: int, default: 1, description: Placement affinity from 1 through 10.}
  force_replace: {type: bool, default: false, description: Replace an empty group when immutable properties change or affinity must decrease.}
  retries: {description: Number of retries for transient failures., type: int, default: 5}
  waiter_delay: {description: Seconds between polling attempts., type: int, default: 5}
  waiter_timeout: {description: Overall polling timeout in seconds., type: int, default: 120}
  user_agent: {description: User-Agent suffix., type: str, default: ansible-collection.susunola.tencentcloud}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''
EXAMPLES = r'''
- susunola.tencentcloud.cvm_disaster_recover_group:
    name: production-spread
    placement_type: RACK
    strategy: SPREAD
    affinity: 2
'''
RETURN = r'''placement_group: {description: Effective placement-group metadata., type: dict, returned: always}'''
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


def _load():
    from tencentcloud.cvm.v20170312 import models, cvm_client
    return models, cvm_client
def describe_request(models, p, offset=0):
    request = models.DescribeDisasterRecoverGroupsRequest(); request.Offset, request.Limit = offset, 100
    if p.get("group_id"): request.DisasterRecoverGroupIds = [p["group_id"]]
    elif p.get("name"): request.Name = p["name"]
    return request
def create_request(models, p):
    request = models.CreateDisasterRecoverGroupRequest(); request.Name, request.Type = p["name"], p["placement_type"]
    request.Strategy, request.Affinity, request.PartitionCount = p["strategy"], p["affinity"], p.get("partition_count"); return request
def update_request(models, p, group_id):
    request = models.ModifyDisasterRecoverGroupAttributeRequest(); request.DisasterRecoverGroupId, request.Name, request.Affinity = group_id, p["name"], p["affinity"]; return request
def delete_request(models, group_id):
    request = models.DeleteDisasterRecoverGroupsRequest(); request.DisasterRecoverGroupIds = [group_id]; return request


def find(module, client, models, p):
    response = module.sdk_call(client.DescribeDisasterRecoverGroups, describe_request(models, p)); matches = []
    for item in response.DisasterRecoverGroupSet or []:
        value = item._serialize(allow_none=True)
        if (p.get("group_id") and value.get("DisasterRecoverGroupId") == p["group_id"]) or (not p.get("group_id") and value.get("Name") == p.get("name")): matches.append(value)
    if len(matches) > 1: module.fail_json(msg="Multiple CVM placement groups matched; specify group_id")
    return matches[0] if matches else None
def comparable(v): return {"Name": v.get("Name"), "Type": v.get("Type"), "Strategy": v.get("Strategy") or "SPREAD", "PartitionCount": v.get("PartitionCount"), "Affinity": int(v.get("Affinity") or 1)}
def desired(p): return {"Name": p["name"], "Type": p["placement_type"], "Strategy": p["strategy"], "PartitionCount": p.get("partition_count"), "Affinity": p["affinity"]}


def run_module():
    module = TencentCloudModule(argument_spec={"state": {"choices": ["present", "absent"], "default": "present"}, "group_id": {}, "name": {}, "placement_type": {"choices": ["HOST", "SW", "RACK"], "default": "HOST"}, "strategy": {"choices": ["SPREAD", "PARTITION"], "default": "SPREAD"}, "partition_count": {"type": "int"}, "affinity": {"type": "int", "default": 1}, "force_replace": {"type": "bool", "default": False}}, required_one_of=[("group_id", "name")], supports_check_mode=True)
    p = module.params
    if p["state"] == "present" and not p.get("name"): module.fail_json(msg="name is required when state=present")
    if not 1 <= p["affinity"] <= 10: module.fail_json(msg="affinity must be between 1 and 10")
    if p["strategy"] == "PARTITION" and not (p.get("partition_count") and 2 <= p["partition_count"] <= 30): module.fail_json(msg="partition_count between 2 and 30 is required for PARTITION strategy")
    if p["strategy"] == "SPREAD" and p.get("partition_count") is not None: module.fail_json(msg="partition_count is valid only for PARTITION strategy")
    module.require_sdk(); models, cm = _load(); client = module.create_client(cm.CvmClient, "cvm.tencentcloudapi.com")
    try:
        current = find(module, client, models, p)
        if p["state"] == "absent":
            if not current: module.exit_json(changed=False, placement_group=None)
            diff = maybe_diff(module, comparable(current), None)
            if not module.check_mode: module.sdk_call(client.DeleteDisasterRecoverGroups, delete_request(models, current["DisasterRecoverGroupId"]))
            module.exit_json(changed=True, **(diff or {}), placement_group=current if module.check_mode else None)
        target = desired(p); before = comparable(current) if current else None
        immutable = bool(current and (before["Type"], before["Strategy"], before["PartitionCount"]) != (target["Type"], target["Strategy"], target["PartitionCount"]))
        affinity_decrease = bool(current and before["Affinity"] > target["Affinity"])
        replace = immutable or affinity_decrease
        if replace and not p["force_replace"]: module.fail_json(msg="immutable placement properties changed or affinity decreased; set force_replace=true to replace an empty group", current=before, desired=target)
        if replace and current.get("InstanceIds"): module.fail_json(msg="cannot replace a non-empty placement group", instance_ids=current["InstanceIds"])
        if before == target: module.exit_json(changed=False, placement_group=current)
        diff = maybe_diff(module, before, target)
        if not module.check_mode:
            if replace:
                module.sdk_call(client.DeleteDisasterRecoverGroups, delete_request(models, current["DisasterRecoverGroupId"])); current = None
            if current: module.sdk_call(client.ModifyDisasterRecoverGroupAttribute, update_request(models, p, current["DisasterRecoverGroupId"]))
            else:
                p["group_id"] = module.sdk_call(client.CreateDisasterRecoverGroup, create_request(models, p)).DisasterRecoverGroupId
            current = find(module, client, models, p)
        module.exit_json(changed=True, **(diff or {}), placement_group=current)
    except Exception as exc: module.fail_json(**sdk_error_payload(exc))


def main(): run_module()
if __name__ == "__main__": main()
