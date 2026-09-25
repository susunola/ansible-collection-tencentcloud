#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type
DOCUMENTATION = r"""
---
module: cbs_disk_backup
short_description: Manage Tencent Cloud CBS disk backup points
version_added: "0.14.0"
description: Creates, waits for and deletes persistent CBS cloud-disk backup points.
options:
  state:
    description:
      - C(present) creates the disk backup with V(CreateDiskBackup) when it does not exist. C(absent) deletes
        it with V(DeleteDiskBackups).
      - The module waits for the change to be observable before returning, bounded by O(waiter_timeout).
    type: str
    choices: [present, absent]
    default: present
  disk_backup_id:
    description:
      - Existing backup point ID; preferred for deletion.
    type: str
  disk_id:
    description:
      - Source CBS cloud disk ID; immutable after creation.
    type: str
  name:
    description:
      - Backup point name; immutable after creation.
    type: str
  force_replace:
    description:
      - Delete and recreate when immutable source disk or name differs.
    type: bool
    default: false
  wait:
    description:
      - Wait for the backup point to reach NORMAL after creation.
    type: bool
    default: true

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
  - module: susunola.tencentcloud.cbs_disk_backup_info
    description: Gather information about Tencent Cloud CBS disk backups.
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.cbs_disk_backup:
    disk_id: disk-xxxxxxxx
    name: before-database-upgrade

- name: Delete the disk backup
  susunola.tencentcloud.cbs_disk_backup:
    state: absent
    name: before-database-upgrade
"""
RETURN = r"""disk_backup:
  description:
    - CBS disk backup point metadata.
  returned: always
  type: dict
  sample:
    # shape captured from this module's unit tests -- scripts/add_return_samples.py
    DiskBackupId: bk-8b0a1c2d
    DiskId: disk-8b0a1c2d
    DiskBackupName: before-upgrade
    DiskBackupState: NORMAL
"""
import time
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import fail_from_sdk_error


def _load():
    from tencentcloud.cbs.v20170312 import models, cbs_client

    return models, cbs_client


def describe_request(models, p, offset=0):
    request = models.DescribeDiskBackupsRequest()
    request.Offset, request.Limit, request.OrderField, request.Order = offset, 100, "CREATE_TIME", "DESC"
    if p.get("disk_backup_id"):
        request.DiskBackupIds = [p["disk_backup_id"]]
    return request


def create_request(models, p):
    request = models.CreateDiskBackupRequest()
    request.DiskId, request.DiskBackupName = p["disk_id"], p["name"]
    return request


def delete_request(models, backup_id):
    request = models.DeleteDiskBackupsRequest()
    request.DiskBackupIds = [backup_id]
    return request


def find(module, client, models, p):
    offset = 0
    matches = []
    while True:
        response = module.sdk_call(client.DescribeDiskBackups, describe_request(models, p, offset))
        values = list(response.DiskBackupSet or [])
        for item in values:
            value = item._serialize(allow_none=True)
            if (p.get("disk_backup_id") and value.get("DiskBackupId") == p["disk_backup_id"]) or (
                not p.get("disk_backup_id") and value.get("DiskId") == p.get("disk_id") and value.get("DiskBackupName") == p.get("name")
            ):
                matches.append(value)
        offset += len(values)
        if offset >= int(response.TotalCount or 0) or not values:
            break
    if len(matches) > 1:
        module.fail_json(msg="Multiple CBS disk backup points matched; specify disk_backup_id")
    return matches[0] if matches else None


def comparable(value):
    return {"DiskId": value.get("DiskId"), "DiskBackupName": value.get("DiskBackupName")}


def desired(p):
    return {"DiskId": p["disk_id"], "DiskBackupName": p["name"]}


def wait_normal(module, client, models, p):
    deadline = time.time() + module.params["waiter_timeout"]
    while True:
        current = find(module, client, models, p)
        state = current and current.get("DiskBackupState")
        if state == "NORMAL":
            return current
        if time.time() >= deadline:
            module.fail_json(msg="Timed out waiting for CBS disk backup point to reach NORMAL", disk_backup=current)
        time.sleep(module.params["waiter_delay"])


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "state": {"choices": ["present", "absent"], "default": "present"},
            "disk_backup_id": {},
            "disk_id": {},
            "name": {},
            "force_replace": {"type": "bool", "default": False},
            "wait": {"type": "bool", "default": True},
        },
        required_one_of=[("disk_backup_id", "name")],
        supports_check_mode=True,
    )
    p = module.params
    if p["state"] == "present" and (not p["disk_id"] or not p["name"]):
        module.fail_json(msg="disk_id and name are required when state=present")
    module.require_sdk()
    models, cm = _load()
    client = module.create_client(cm.CbsClient, "cbs.tencentcloudapi.com")
    try:
        current = find(module, client, models, p)
        if p["state"] == "absent":
            if not current:
                module.exit_json(changed=False, disk_backup=None)
            diff = maybe_diff(module, comparable(current), None)
            if not module.check_mode:
                module.sdk_call(client.DeleteDiskBackups, delete_request(models, current["DiskBackupId"]))
            module.exit_json(changed=True, **(diff or {}), disk_backup=current if module.check_mode else None)
        target = desired(p)
        before = comparable(current) if current else None
        replace = bool(current and before != target)
        if replace and not p["force_replace"]:
            module.fail_json(
                msg="disk_id and name are immutable; set force_replace=true to recreate the backup point",
                immutable_changes={k: {"before": before[k], "after": target[k]} for k in target if before[k] != target[k]},
            )
        if before == target:
            module.exit_json(changed=False, disk_backup=current)
        diff = maybe_diff(module, before, target)
        if not module.check_mode:
            if replace:
                module.sdk_call(client.DeleteDiskBackups, delete_request(models, current["DiskBackupId"]))
                current = None
            p["disk_backup_id"] = module.sdk_call(client.CreateDiskBackup, create_request(models, p)).DiskBackupId
            current = wait_normal(module, client, models, p) if p["wait"] else find(module, client, models, p)
        module.exit_json(changed=True, **(diff or {}), disk_backup=current)
    except Exception as exc:
        fail_from_sdk_error(module, exc)


def main():
    run_module()


if __name__ == "__main__":
    main()
