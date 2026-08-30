#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function
__metaclass__ = type
DOCUMENTATION = r'''
---
module: lighthouse_snapshot
short_description: Manage Tencent Cloud Lighthouse instance snapshots
version_added: "0.14.0"
description: Creates, renames, waits for and deletes Lighthouse system-disk snapshots.
options:
  state: {type: str, choices: [present, absent], default: present, description: Desired state.}
  snapshot_id: {type: str, description: Existing snapshot ID; preferred for rename and deletion.}
  instance_id: {type: str, description: Source Lighthouse instance ID used for creation and lookup.}
  name: {type: str, description: Snapshot name.}
  wait: {type: bool, default: true, description: Wait for the snapshot to reach NORMAL after creation.}
  retries: {description: Number of retries for transient failures., type: int, default: 5}
  waiter_delay: {description: Seconds between polling attempts., type: int, default: 5}
  waiter_timeout: {description: Overall timeout in seconds for state polling., type: int, default: 120}
  user_agent: {description: User-Agent suffix., type: str, default: ansible-collection.susunola.tencentcloud}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''
EXAMPLES = r'''
- susunola.tencentcloud.lighthouse_snapshot:
    instance_id: lhins-xxxxxxxx
    name: before-upgrade
'''
RETURN = r'''snapshot: {description: Lighthouse snapshot metadata., type: dict, returned: always}'''
import time
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


def _load():
    from tencentcloud.lighthouse.v20200324 import models, lighthouse_client
    return models, lighthouse_client
def describe_request(models, p, offset=0):
    request = models.DescribeSnapshotsRequest(); request.Offset, request.Limit = offset, 100
    if p.get("snapshot_id"): request.SnapshotIds = [p["snapshot_id"]]; return request
    filters = []
    for name, value in (("instance-id", p.get("instance_id")), ("snapshot-name", p.get("name"))):
        if value:
            item = models.Filter(); item.Name, item.Values = name, [value]; filters.append(item)
    if filters: request.Filters = filters
    return request
def create_request(models, p):
    request = models.CreateInstanceSnapshotRequest(); request.InstanceId, request.SnapshotName = p["instance_id"], p["name"]; return request
def update_request(models, snapshot_id, name):
    request = models.ModifySnapshotAttributeRequest(); request.SnapshotId, request.SnapshotName = snapshot_id, name; return request
def delete_request(models, snapshot_id):
    request = models.DeleteSnapshotsRequest(); request.SnapshotIds = [snapshot_id]; return request
def find(module, client, models, p):
    offset = 0; matches = []
    while True:
        response = module.sdk_call(client.DescribeSnapshots, describe_request(models, p, offset)); values = list(response.SnapshotSet or [])
        matches.extend(item._serialize(allow_none=True) for item in values); offset += len(values)
        if offset >= int(response.TotalCount or 0) or not values: break
    if len(matches) > 1: module.fail_json(msg="Multiple Lighthouse snapshots matched; specify snapshot_id")
    return matches[0] if matches else None
def wait_normal(module, client, models, p):
    deadline = time.time() + module.params["waiter_timeout"]
    while True:
        current = find(module, client, models, p); state = current and current.get("SnapshotState")
        if state == "NORMAL": return current
        if current and current.get("LatestOperationState") == "FAILED": module.fail_json(msg="Lighthouse snapshot creation failed", snapshot=current)
        if time.time() >= deadline: module.fail_json(msg="Timed out waiting for Lighthouse snapshot to reach NORMAL", snapshot=current)
        time.sleep(module.params["waiter_delay"])


def run_module():
    module = TencentCloudModule(argument_spec={"state": {"choices": ["present", "absent"], "default": "present"}, "snapshot_id": {}, "instance_id": {}, "name": {}, "wait": {"type": "bool", "default": True}}, required_one_of=[("snapshot_id", "name")], supports_check_mode=True)
    p = module.params
    if p["state"] == "present" and (not p["name"] or (not p["snapshot_id"] and not p["instance_id"])): module.fail_json(msg="name and either snapshot_id or instance_id are required when state=present")
    if p["state"] == "absent" and not p["snapshot_id"] and not p["instance_id"]: module.fail_json(msg="instance_id is required with name when state=absent")
    module.require_sdk(); models, cm = _load(); client = module.create_client(cm.LighthouseClient, "lighthouse.tencentcloudapi.com")
    try:
        current = find(module, client, models, p)
        if p["state"] == "absent":
            if not current: module.exit_json(changed=False, snapshot=None)
            diff = maybe_diff(module, {"SnapshotName": current.get("SnapshotName")}, None)
            if not module.check_mode: module.sdk_call(client.DeleteSnapshots, delete_request(models, current["SnapshotId"]))
            module.exit_json(changed=True, **(diff or {}), snapshot=current if module.check_mode else None)
        before = {"SnapshotName": current.get("SnapshotName")} if current else None; target = {"SnapshotName": p["name"]}
        if before == target: module.exit_json(changed=False, snapshot=current)
        diff = maybe_diff(module, before, target)
        if not module.check_mode:
            if current: module.sdk_call(client.ModifySnapshotAttribute, update_request(models, current["SnapshotId"], p["name"]))
            else: p["snapshot_id"] = module.sdk_call(client.CreateInstanceSnapshot, create_request(models, p)).SnapshotId
            current = wait_normal(module, client, models, p) if p["wait"] else find(module, client, models, p)
        module.exit_json(changed=True, **(diff or {}), snapshot=current)
    except Exception as exc: module.fail_json(**sdk_error_payload(exc))


def main(): run_module()
if __name__ == "__main__": main()
