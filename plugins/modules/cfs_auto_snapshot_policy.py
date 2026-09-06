#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type
DOCUMENTATION = r"""
---
module: cfs_auto_snapshot_policy
short_description: Manage Tencent Cloud CFS automatic snapshot policies
version_added: "0.14.0"
description: Manages an automatic snapshot schedule and its exact set of bound CFS file systems.
options:
  state: {type: str, choices: [present, absent], default: present, description: Desired state.}
  policy_id: {type: str, description: Existing policy ID; preferred for rename and deletion.}
  name: {type: str, description: Policy name.}
  hour: {type: str, default: '00', description: Comma-separated snapshot hours.}
  day_of_week: {type: str, default: '', description: Comma-separated weekdays for weekly schedules.}
  day_of_month: {type: str, default: '', description: Comma-separated month days for monthly schedules.}
  interval_days: {type: int, default: 0, description: Day interval for interval schedules.}
  alive_days: {type: int, default: 0, description: Snapshot retention in days; zero means permanent.}
  enabled: {type: bool, default: true, description: Whether automatic snapshot creation is active.}
  file_system_ids: {type: list, elements: str, default: [], description: Exact set of file systems bound to the policy.}
  force_delete: {type: bool, default: false, description: Unbind all file systems before deleting the policy.}
  retries: {description: Number of retries for transient failures., type: int, default: 5}
  waiter_delay: {description: Seconds between polling attempts., type: int, default: 5}
  waiter_timeout: {description: Overall polling timeout in seconds., type: int, default: 120}
  user_agent: {description: User-Agent suffix., type: str, default: ansible-collection.susunola.tencentcloud}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.cfs_auto_snapshot_policy:
    name: nightly-production
    hour: '02'
    day_of_week: 1,2,3,4,5,6,7
    alive_days: 30
    file_system_ids: [cfs-xxxxxxxx, cfs-yyyyyyyy]
"""
RETURN = r"""policy: {description: CFS automatic snapshot policy metadata., type: dict, returned: always}"""
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


def _load():
    from tencentcloud.cfs.v20190719 import models, cfs_client

    return models, cfs_client


def describe_request(models, p, offset=0):
    request = models.DescribeAutoSnapshotPoliciesRequest()
    request.Offset, request.Limit = offset, 100
    if p.get("policy_id"):
        request.AutoSnapshotPolicyId = p["policy_id"]
    return request


def create_request(models, p):
    request = models.CreateAutoSnapshotPolicyRequest()
    request.PolicyName, request.Hour, request.DayOfWeek, request.AliveDays, request.DayOfMonth, request.IntervalDays = (
        p["name"],
        p["hour"],
        p["day_of_week"],
        p["alive_days"],
        p["day_of_month"],
        p["interval_days"],
    )
    return request


def update_request(models, p, policy_id):
    request = models.UpdateAutoSnapshotPolicyRequest()
    request.AutoSnapshotPolicyId, request.PolicyName, request.Hour, request.DayOfWeek = policy_id, p["name"], p["hour"], p["day_of_week"]
    request.AliveDays, request.IsActivated, request.DayOfMonth, request.IntervalDays = (
        p["alive_days"],
        1 if p["enabled"] else 0,
        p["day_of_month"],
        p["interval_days"],
    )
    return request


def delete_request(models, policy_id):
    request = models.DeleteAutoSnapshotPolicyRequest()
    request.AutoSnapshotPolicyId = policy_id
    return request


def bind_request(models, policy_id, ids):
    request = models.BindAutoSnapshotPolicyRequest()
    request.AutoSnapshotPolicyId, request.FileSystemIds = policy_id, ",".join(sorted(ids))
    return request


def unbind_request(models, policy_id, ids):
    request = models.UnbindAutoSnapshotPolicyRequest()
    request.AutoSnapshotPolicyId, request.FileSystemIds = policy_id, ",".join(sorted(ids))
    return request


def find(module, client, models, p):
    offset = 0
    matches = []
    while True:
        response = module.sdk_call(client.DescribeAutoSnapshotPolicies, describe_request(models, p, offset))
        values = list(response.AutoSnapshotPolicies or [])
        for item in values:
            value = item._serialize(allow_none=True)
            if (p.get("policy_id") and value.get("AutoSnapshotPolicyId") == p["policy_id"]) or (
                not p.get("policy_id") and value.get("PolicyName") == p.get("name")
            ):
                matches.append(value)
        offset += len(values)
        if offset >= int(response.TotalCount or 0) or not values:
            break
    if len(matches) > 1:
        module.fail_json(msg="Multiple CFS auto-snapshot policies matched; specify policy_id")
    return matches[0] if matches else None


def _bound(value):
    return sorted(item.get("FileSystemId") for item in (value.get("FileSystems") or []) if item.get("FileSystemId"))


def comparable(value):
    return {
        "PolicyName": value.get("PolicyName"),
        "Hour": value.get("Hour") or "",
        "DayOfWeek": value.get("DayOfWeek") or "",
        "DayOfMonth": value.get("DayOfMonth") or "",
        "IntervalDays": int(value.get("IntervalDays") or 0),
        "AliveDays": int(value.get("AliveDays") or 0),
        "IsActivated": int(value.get("IsActivated") or 0),
        "FileSystemIds": _bound(value),
    }


def desired(p):
    return {
        "PolicyName": p["name"],
        "Hour": p["hour"],
        "DayOfWeek": p["day_of_week"],
        "DayOfMonth": p["day_of_month"],
        "IntervalDays": p["interval_days"],
        "AliveDays": p["alive_days"],
        "IsActivated": 1 if p["enabled"] else 0,
        "FileSystemIds": sorted(p["file_system_ids"]),
    }


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "state": {"choices": ["present", "absent"], "default": "present"},
            "policy_id": {},
            "name": {},
            "hour": {"default": "00"},
            "day_of_week": {"default": ""},
            "day_of_month": {"default": ""},
            "interval_days": {"type": "int", "default": 0},
            "alive_days": {"type": "int", "default": 0},
            "enabled": {"type": "bool", "default": True},
            "file_system_ids": {"type": "list", "elements": "str", "default": []},
            "force_delete": {"type": "bool", "default": False},
        },
        required_one_of=[("policy_id", "name")],
        supports_check_mode=True,
    )
    p = module.params
    if p["state"] == "present" and not p["name"]:
        module.fail_json(msg="name is required when state=present")
    module.require_sdk()
    models, cm = _load()
    client = module.create_client(cm.CfsClient, "cfs.tencentcloudapi.com")
    try:
        current = find(module, client, models, p)
        if p["state"] == "absent":
            if not current:
                module.exit_json(changed=False, policy=None)
            bound = _bound(current)
            if bound and not p["force_delete"]:
                module.fail_json(msg="policy is still bound to file systems; set force_delete=true to unbind and delete", file_system_ids=bound)
            diff = maybe_diff(module, comparable(current), None)
            if not module.check_mode:
                if bound:
                    module.sdk_call(client.UnbindAutoSnapshotPolicy, unbind_request(models, current["AutoSnapshotPolicyId"], bound))
                module.sdk_call(client.DeleteAutoSnapshotPolicy, delete_request(models, current["AutoSnapshotPolicyId"]))
            module.exit_json(changed=True, **(diff or {}), policy=current if module.check_mode else None)
        target = desired(p)
        before = comparable(current) if current else None
        if before == target:
            module.exit_json(changed=False, policy=current)
        diff = maybe_diff(module, before, target)
        if not module.check_mode:
            if current:
                policy_id = current["AutoSnapshotPolicyId"]
                module.sdk_call(client.UpdateAutoSnapshotPolicy, update_request(models, p, policy_id))
            else:
                policy_id = module.sdk_call(client.CreateAutoSnapshotPolicy, create_request(models, p)).AutoSnapshotPolicyId
                p["policy_id"] = policy_id
            old_ids = set(_bound(current)) if current else set()
            new_ids = set(p["file_system_ids"])
            if old_ids - new_ids:
                module.sdk_call(client.UnbindAutoSnapshotPolicy, unbind_request(models, policy_id, old_ids - new_ids))
            if new_ids - old_ids:
                module.sdk_call(client.BindAutoSnapshotPolicy, bind_request(models, policy_id, new_ids - old_ids))
            current = find(module, client, models, p)
        module.exit_json(changed=True, **(diff or {}), policy=current)
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
