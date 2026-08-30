#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function
__metaclass__ = type
DOCUMENTATION = r'''
---
module: cbs_auto_snapshot_policy
short_description: Manage Tencent Cloud CBS automatic snapshot policies
version_added: "0.14.0"
description: Creates, updates and deletes an automatic snapshot policy and reconciles its exact set of bound cloud disks.
options:
  state: {type: str, choices: [present, absent], default: present, description: Desired state.}
  policy_id: {type: str, description: Existing policy ID; preferred for rename and deletion.}
  name: {type: str, description: Policy name.}
  schedules: {type: list, elements: dict, default: [], description: SDK-compatible Policy schedule list.}
  enabled: {type: bool, default: true, description: Whether scheduled snapshots are active.}
  permanent: {type: bool, default: false, description: Whether generated snapshots are retained permanently.}
  retention_days: {type: int, default: 7, description: Snapshot retention days when permanent is false.}
  disk_ids: {type: list, elements: str, default: [], description: Exact set of CBS cloud disks bound to the policy.}
  force_delete: {type: bool, default: false, description: Unbind all cloud disks before deleting the policy.}
  retries: {description: Number of retries for transient failures., type: int, default: 5}
  waiter_delay: {description: Seconds between polling attempts., type: int, default: 5}
  waiter_timeout: {description: Overall polling timeout in seconds., type: int, default: 120}
  user_agent: {description: User-Agent suffix., type: str, default: ansible-collection.susunola.tencentcloud}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''
EXAMPLES = r'''
- susunola.tencentcloud.cbs_auto_snapshot_policy:
    name: nightly-production
    schedules:
      - {Hour: [2], DayOfWeek: [0, 1, 2, 3, 4, 5, 6]}
    retention_days: 30
    disk_ids: [disk-xxxxxxxx, disk-yyyyyyyy]
'''
RETURN = r'''policy: {description: CBS automatic snapshot policy metadata., type: dict, returned: always}'''
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


def _load():
    from tencentcloud.cbs.v20170312 import models, cbs_client
    return models, cbs_client
def _policies(models, values):
    result = []
    for value in values: item = models.Policy(); item._deserialize(value); result.append(item)
    return result
def describe_request(models, p, offset=0):
    request = models.DescribeAutoSnapshotPoliciesRequest(); request.Offset, request.Limit = offset, 100
    if p.get("policy_id"): request.AutoSnapshotPolicyIds = [p["policy_id"]]
    return request
def create_request(models, p):
    request = models.CreateAutoSnapshotPolicyRequest(); request.Policy, request.IsActivated, request.AutoSnapshotPolicyName = _policies(models, p["schedules"]), p["enabled"], p["name"]
    request.IsPermanent, request.RetentionDays = p["permanent"], p["retention_days"]; return request
def update_request(models, p, policy_id):
    request = models.ModifyAutoSnapshotPolicyAttributeRequest(); request.AutoSnapshotPolicyId, request.IsActivated, request.AutoSnapshotPolicyName = policy_id, p["enabled"], p["name"]
    request.IsPermanent, request.RetentionDays, request.Policy = p["permanent"], p["retention_days"], _policies(models, p["schedules"]); return request
def delete_request(models, policy_id):
    request = models.DeleteAutoSnapshotPoliciesRequest(); request.AutoSnapshotPolicyIds = [policy_id]; return request
def bind_request(models, policy_id, disk_ids):
    request = models.BindAutoSnapshotPolicyRequest(); request.AutoSnapshotPolicyId, request.DiskIds = policy_id, sorted(disk_ids); return request
def unbind_request(models, policy_id, disk_ids):
    request = models.UnbindAutoSnapshotPolicyRequest(); request.AutoSnapshotPolicyId, request.DiskIds = policy_id, sorted(disk_ids); return request
def _schedule_key(value): return (tuple(value.get("Hour") or []), tuple(value.get("DayOfWeek") or []), tuple(value.get("DayOfMonth") or []), int(value.get("IntervalDays") or 0))
def _schedules(values): return sorted(values or [], key=_schedule_key)
def comparable(value): return {"AutoSnapshotPolicyName": value.get("AutoSnapshotPolicyName"), "Policy": _schedules(value.get("Policy")), "IsActivated": bool(value.get("IsActivated")), "IsPermanent": bool(value.get("IsPermanent")), "RetentionDays": int(value.get("RetentionDays") or 0), "DiskIds": sorted(value.get("DiskIdSet") or [])}
def desired(p): return {"AutoSnapshotPolicyName": p["name"], "Policy": _schedules(p["schedules"]), "IsActivated": p["enabled"], "IsPermanent": p["permanent"], "RetentionDays": p["retention_days"], "DiskIds": sorted(p["disk_ids"])}
def find(module, client, models, p):
    offset = 0; matches = []
    while True:
        response = module.sdk_call(client.DescribeAutoSnapshotPolicies, describe_request(models, p, offset)); values = list(response.AutoSnapshotPolicySet or [])
        for item in values:
            value = item._serialize(allow_none=True)
            if (p.get("policy_id") and value.get("AutoSnapshotPolicyId") == p["policy_id"]) or (not p.get("policy_id") and value.get("AutoSnapshotPolicyName") == p.get("name")): matches.append(value)
        offset += len(values)
        if offset >= int(response.TotalCount or 0) or not values: break
    if len(matches) > 1: module.fail_json(msg="Multiple CBS automatic snapshot policies matched; specify policy_id")
    return matches[0] if matches else None


def run_module():
    module = TencentCloudModule(argument_spec={"state": {"choices": ["present", "absent"], "default": "present"}, "policy_id": {}, "name": {}, "schedules": {"type": "list", "elements": "dict", "default": []}, "enabled": {"type": "bool", "default": True}, "permanent": {"type": "bool", "default": False}, "retention_days": {"type": "int", "default": 7}, "disk_ids": {"type": "list", "elements": "str", "default": []}, "force_delete": {"type": "bool", "default": False}}, required_one_of=[("policy_id", "name")], supports_check_mode=True)
    p = module.params
    if p["state"] == "present" and (not p["name"] or not p["schedules"]): module.fail_json(msg="name and schedules are required when state=present")
    module.require_sdk(); models, cm = _load(); client = module.create_client(cm.CbsClient, "cbs.tencentcloudapi.com")
    try:
        current = find(module, client, models, p)
        if p["state"] == "absent":
            if not current: module.exit_json(changed=False, policy=None)
            bound = sorted(current.get("DiskIdSet") or [])
            if bound and not p["force_delete"]: module.fail_json(msg="policy is still bound to cloud disks; set force_delete=true to unbind and delete", disk_ids=bound)
            diff = maybe_diff(module, comparable(current), None)
            if not module.check_mode:
                if bound: module.sdk_call(client.UnbindAutoSnapshotPolicy, unbind_request(models, current["AutoSnapshotPolicyId"], bound))
                module.sdk_call(client.DeleteAutoSnapshotPolicies, delete_request(models, current["AutoSnapshotPolicyId"]))
            module.exit_json(changed=True, **(diff or {}), policy=current if module.check_mode else None)
        target = desired(p); before = comparable(current) if current else None
        if before == target: module.exit_json(changed=False, policy=current)
        diff = maybe_diff(module, before, target)
        if not module.check_mode:
            if current: policy_id = current["AutoSnapshotPolicyId"]; module.sdk_call(client.ModifyAutoSnapshotPolicyAttribute, update_request(models, p, policy_id))
            else: policy_id = module.sdk_call(client.CreateAutoSnapshotPolicy, create_request(models, p)).AutoSnapshotPolicyId; p["policy_id"] = policy_id
            old_ids = set(current.get("DiskIdSet") or []) if current else set(); new_ids = set(p["disk_ids"])
            if old_ids - new_ids: module.sdk_call(client.UnbindAutoSnapshotPolicy, unbind_request(models, policy_id, old_ids - new_ids))
            if new_ids - old_ids: module.sdk_call(client.BindAutoSnapshotPolicy, bind_request(models, policy_id, new_ids - old_ids))
            current = find(module, client, models, p)
        module.exit_json(changed=True, **(diff or {}), policy=current)
    except Exception as exc: module.fail_json(**sdk_error_payload(exc))


def main(): run_module()
if __name__ == "__main__": main()
