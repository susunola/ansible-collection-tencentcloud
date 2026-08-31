#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type
DOCUMENTATION = r"""
---
module: chdfs_mount_point
short_description: Manage Tencent Cloud CHDFS mount points
version_added: "0.14.0"
description: Creates, updates and deletes CHDFS mount points.
options:
  state: {type: str, choices: [present, absent], default: present, description: Desired state.}
  mount_point_id: {type: str, description: Existing mount point ID.}
  file_system_id: {type: str, required: true, description: Parent file system ID.}
  name: {type: str, description: Mount point name.}
  status: {type: int, description: Mount point status accepted by CHDFS.}
  retries: {type: int, default: 5, description: Number of retries for transient failures.}
  waiter_delay: {type: int, default: 5, description: Seconds between polling attempts.}
  waiter_timeout: {type: int, default: 120, description: Overall polling timeout in seconds.}
  user_agent: {type: str, default: ansible-collection.susunola.tencentcloud, description: User-Agent suffix.}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.chdfs_mount_point:
    file_system_id: f-xxxxxxxx
    name: analytics-mount
    status: 1
"""
RETURN = r"""mount_point: {description: Effective CHDFS mount point metadata., type: dict, returned: always}"""
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


def _load():
    from tencentcloud.chdfs.v20201112 import models, chdfs_client

    return models, chdfs_client


def describe_request(models, file_system_id):
    r = models.DescribeMountPointsRequest()
    r.FileSystemId = file_system_id
    return r


def create_request(models, p):
    r = models.CreateMountPointRequest()
    r.MountPointName, r.FileSystemId, r.MountPointStatus = p["name"], p["file_system_id"], p.get("status")
    return r


def update_request(models, mount_point_id, target):
    r = models.ModifyMountPointRequest()
    r.MountPointId, r.MountPointName, r.MountPointStatus = mount_point_id, target["MountPointName"], target["Status"]
    return r


def delete_request(models, mount_point_id):
    r = models.DeleteMountPointRequest()
    r.MountPointId = mount_point_id
    return r


def find(module, client, models, p):
    response = module.sdk_call(client.DescribeMountPoints, describe_request(models, p["file_system_id"]))
    matches = []
    for item in response.MountPoints or []:
        value = item._serialize(allow_none=True)
        if (p.get("mount_point_id") and value.get("MountPointId") == p["mount_point_id"]) or (
            not p.get("mount_point_id") and value.get("MountPointName") == p.get("name")
        ):
            matches.append(value)
    if len(matches) > 1:
        module.fail_json(msg="Multiple CHDFS mount points matched; specify mount_point_id")
    return matches[0] if matches else None


def comparable(v):
    return {"MountPointName": v.get("MountPointName"), "Status": v.get("Status")}


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "state": {"choices": ["present", "absent"], "default": "present"},
            "mount_point_id": {},
            "file_system_id": {"required": True},
            "name": {},
            "status": {"type": "int"},
        },
        required_one_of=[("mount_point_id", "name")],
        supports_check_mode=True,
    )
    p = module.params
    module.require_sdk()
    models, cm = _load()
    client = module.create_client(cm.ChdfsClient, "chdfs.tencentcloudapi.com")
    try:
        current = find(module, client, models, p)
        if p["state"] == "absent":
            if not current:
                module.exit_json(changed=False, mount_point=None)
            diff = maybe_diff(module, current, None)
            if not module.check_mode:
                module.sdk_call(client.DeleteMountPoint, delete_request(models, current["MountPointId"]))
            module.exit_json(changed=True, **(diff or {}), mount_point=None)
        if not current and not p.get("name"):
            module.fail_json(msg="name is required to create a CHDFS mount point")
        before = comparable(current) if current else None
        old = before or {}
        target = {"MountPointName": p.get("name") or old.get("MountPointName"), "Status": p.get("status") if p.get("status") is not None else old.get("Status")}
        if before == target:
            module.exit_json(changed=False, mount_point=current)
        diff = maybe_diff(module, before, target)
        if not module.check_mode:
            response = module.sdk_call(
                client.ModifyMountPoint if current else client.CreateMountPoint,
                update_request(models, current["MountPointId"], target) if current else create_request(models, p),
            )
            p["mount_point_id"] = current["MountPointId"] if current else response.MountPoint.MountPointId
            current = find(module, client, models, p)
        module.exit_json(changed=True, **(diff or {}), mount_point=current if not module.check_mode else target)
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
