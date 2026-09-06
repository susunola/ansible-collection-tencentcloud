#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type
DOCUMENTATION = r"""
---
module: cfs_snapshot
short_description: Manage Tencent Cloud CFS snapshots
version_added: "0.14.0"
description: Creates, updates and deletes manual CFS file-system snapshots.
options:
  state: {type: str, choices: [present, absent], default: present, description: Desired state.}
  snapshot_id: {type: str, description: Existing snapshot ID; preferred for rename and deletion.}
  file_system_id: {type: str, description: Source CFS file system ID; immutable after creation.}
  name: {type: str, description: Snapshot name.}
  alive_days: {type: int, default: 0, description: Retention in days; zero means permanent retention.}
  force_replace: {type: bool, default: false, description: Delete and recreate when the source file system changes.}
  retries: {description: Number of retries for transient failures., type: int, default: 5}
  waiter_delay: {description: Seconds between polling attempts., type: int, default: 5}
  waiter_timeout: {description: Overall polling timeout in seconds., type: int, default: 120}
  user_agent: {description: User-Agent suffix., type: str, default: ansible-collection.susunola.tencentcloud}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.cfs_snapshot:
    file_system_id: cfs-xxxxxxxx
    name: before-upgrade
    alive_days: 30
"""
RETURN = r"""snapshot: {description: CFS snapshot metadata., type: dict, returned: always}"""
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


def _load():
    from tencentcloud.cfs.v20190719 import models, cfs_client

    return models, cfs_client


def describe_request(models, p, offset=0):
    request = models.DescribeCfsSnapshotsRequest()
    request.Offset, request.Limit = offset, 100
    if p.get("snapshot_id"):
        request.SnapshotId = p["snapshot_id"]
    if p.get("file_system_id"):
        request.FileSystemId = p["file_system_id"]
    return request


def create_request(models, p):
    request = models.CreateCfsSnapshotRequest()
    request.FileSystemId, request.SnapshotName = p["file_system_id"], p["name"]
    return request


def update_request(models, p, snapshot_id):
    request = models.UpdateCfsSnapshotAttributeRequest()
    request.SnapshotId, request.SnapshotName, request.AliveDays = snapshot_id, p["name"], p["alive_days"]
    return request


def delete_request(models, snapshot_id):
    request = models.DeleteCfsSnapshotRequest()
    request.SnapshotId = snapshot_id
    return request


def find(module, client, models, p):
    offset = 0
    matches = []
    while True:
        response = module.sdk_call(client.DescribeCfsSnapshots, describe_request(models, p, offset))
        values = list(response.Snapshots or [])
        for item in values:
            value = item._serialize(allow_none=True)
            if (p.get("snapshot_id") and value.get("SnapshotId") == p["snapshot_id"]) or (
                not p.get("snapshot_id") and value.get("FileSystemId") == p.get("file_system_id") and value.get("SnapshotName") == p.get("name")
            ):
                matches.append(value)
        offset += len(values)
        if offset >= int(response.TotalCount or 0) or not values:
            break
    if len(matches) > 1:
        module.fail_json(msg="Multiple CFS snapshots matched; specify snapshot_id")
    return matches[0] if matches else None


def desired(p):
    return {"SnapshotName": p["name"], "FileSystemId": p["file_system_id"], "AliveDay": p["alive_days"]}


def comparable(value):
    return {"SnapshotName": value.get("SnapshotName"), "FileSystemId": value.get("FileSystemId"), "AliveDay": int(value.get("AliveDay") or 0)}


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "state": {"choices": ["present", "absent"], "default": "present"},
            "snapshot_id": {},
            "file_system_id": {},
            "name": {},
            "alive_days": {"type": "int", "default": 0},
            "force_replace": {"type": "bool", "default": False},
        },
        required_one_of=[("snapshot_id", "name")],
        supports_check_mode=True,
    )
    p = module.params
    if p["state"] == "present" and (not p["name"] or not p["file_system_id"]):
        module.fail_json(msg="name and file_system_id are required when state=present")
    module.require_sdk()
    models, cm = _load()
    client = module.create_client(cm.CfsClient, "cfs.tencentcloudapi.com")
    try:
        current = find(module, client, models, p)
        if p["state"] == "absent":
            if not current:
                module.exit_json(changed=False, snapshot=None)
            diff = maybe_diff(module, comparable(current), None)
            if not module.check_mode:
                module.sdk_call(client.DeleteCfsSnapshot, delete_request(models, current["SnapshotId"]))
            module.exit_json(changed=True, **(diff or {}), snapshot=current if module.check_mode else None)
        target = desired(p)
        before = comparable(current) if current else None
        replace = bool(current and before["FileSystemId"] != target["FileSystemId"])
        if replace and not p["force_replace"]:
            module.fail_json(msg="file_system_id is immutable; set force_replace=true to recreate the snapshot")
        if before == target:
            module.exit_json(changed=False, snapshot=current)
        diff = maybe_diff(module, before, target)
        if not module.check_mode:
            if replace:
                module.sdk_call(client.DeleteCfsSnapshot, delete_request(models, current["SnapshotId"]))
                current = None
            if current:
                module.sdk_call(client.UpdateCfsSnapshotAttribute, update_request(models, p, current["SnapshotId"]))
            else:
                p["snapshot_id"] = module.sdk_call(client.CreateCfsSnapshot, create_request(models, p)).SnapshotId
            current = find(module, client, models, p)
        module.exit_json(changed=True, **(diff or {}), snapshot=current)
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
