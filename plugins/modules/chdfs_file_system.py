#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type
DOCUMENTATION = r"""
---
module: chdfs_file_system
short_description: Manage Tencent Cloud CHDFS file systems
version_added: "0.14.0"
description: Creates, updates and deletes CHDFS file systems.
options:
  state: {type: str, choices: [present, absent], default: present, description: Desired state.}
  file_system_id: {type: str, description: Existing file system ID.}
  name: {type: str, description: File system name.}
  description: {type: str, description: File system description.}
  capacity_quota: {type: int, description: Capacity quota in bytes.}
  super_users: {type: list, elements: str, description: Superuser names.}
  posix_acl: {type: bool, description: Whether POSIX ACL checks are enabled.}
  root_inode_user: {type: str, description: Creation-time root inode user.}
  root_inode_group: {type: str, description: Creation-time root inode group.}
  enable_ranger: {type: bool, description: Whether Ranger validation is enabled.}
  ranger_service_addresses: {type: list, elements: str, description: Ranger service addresses.}
  tags: {type: dict, description: Creation-time tags.}
  retries: {type: int, default: 5, description: Number of retries for transient failures.}
  waiter_delay: {type: int, default: 5, description: Seconds between polling attempts.}
  waiter_timeout: {type: int, default: 120, description: Overall polling timeout in seconds.}
  user_agent: {type: str, default: ansible-collection.susunola.tencentcloud, description: User-Agent suffix.}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.chdfs_file_system:
    name: analytics
    capacity_quota: 1099511627776
    posix_acl: true
"""
RETURN = r"""file_system: {description: Effective CHDFS file system metadata., type: dict, returned: always}"""
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


def _load():
    from tencentcloud.chdfs.v20201112 import models, chdfs_client

    return models, chdfs_client


def _tags(models, values):
    result = []
    for key, value in sorted((values or {}).items()):
        item = models.Tag()
        item.Key, item.Value = key, value
        result.append(item)
    return result


def describe_request(models, marker=None):
    r = models.DescribeFileSystemsRequest()
    r.FileSystemIdMarker = marker
    return r


def create_request(models, p):
    r = models.CreateFileSystemRequest()
    r.FileSystemName, r.PosixAcl, r.Description, r.CapacityQuota = p["name"], p.get("posix_acl"), p.get("description"), p.get("capacity_quota")
    r.SuperUsers, r.RootInodeUser, r.RootInodeGroup = p.get("super_users"), p.get("root_inode_user"), p.get("root_inode_group")
    r.EnableRanger, r.RangerServiceAddresses, r.Tags = p.get("enable_ranger"), p.get("ranger_service_addresses"), _tags(models, p.get("tags"))
    return r


def update_request(models, file_system_id, target):
    r = models.ModifyFileSystemRequest()
    r.FileSystemId = file_system_id
    r.FileSystemName, r.Description, r.CapacityQuota = target["FileSystemName"], target["Description"], target["CapacityQuota"]
    r.SuperUsers, r.PosixAcl = target["SuperUsers"], target["PosixAcl"]
    r.EnableRanger, r.RangerServiceAddresses = target["EnableRanger"], target["RangerServiceAddresses"]
    return r


def delete_request(models, file_system_id):
    r = models.DeleteFileSystemRequest()
    r.FileSystemId = file_system_id
    return r


def find(module, client, models, p):
    marker = None
    matches = []
    while True:
        response = module.sdk_call(client.DescribeFileSystems, describe_request(models, marker))
        for item in response.FileSystems or []:
            value = item._serialize(allow_none=True)
            if (p.get("file_system_id") and value.get("FileSystemId") == p["file_system_id"]) or (
                not p.get("file_system_id") and value.get("FileSystemName") == p.get("name")
            ):
                matches.append(value)
        if response.IsOver or not response.NextFileSystemIdMarker:
            break
        marker = response.NextFileSystemIdMarker
    if len(matches) > 1:
        module.fail_json(msg="Multiple CHDFS file systems matched; specify file_system_id")
    return matches[0] if matches else None


def comparable(v):
    return {k: v.get(k) for k in ("FileSystemName", "Description", "CapacityQuota", "SuperUsers", "PosixAcl", "EnableRanger", "RangerServiceAddresses")}


def run_module():
    spec = {
        "state": {"choices": ["present", "absent"], "default": "present"},
        "file_system_id": {},
        "name": {},
        "description": {},
        "capacity_quota": {"type": "int"},
        "super_users": {"type": "list", "elements": "str"},
        "posix_acl": {"type": "bool"},
        "root_inode_user": {},
        "root_inode_group": {},
        "enable_ranger": {"type": "bool"},
        "ranger_service_addresses": {"type": "list", "elements": "str"},
        "tags": {"type": "dict"},
    }
    module = TencentCloudModule(argument_spec=spec, required_one_of=[("file_system_id", "name")], supports_check_mode=True)
    p = module.params
    module.require_sdk()
    models, cm = _load()
    client = module.create_client(cm.ChdfsClient, "chdfs.tencentcloudapi.com")
    try:
        current = find(module, client, models, p)
        if p["state"] == "absent":
            if not current:
                module.exit_json(changed=False, file_system=None)
            diff = maybe_diff(module, current, None)
            if not module.check_mode:
                module.sdk_call(client.DeleteFileSystem, delete_request(models, current["FileSystemId"]))
            module.exit_json(changed=True, **(diff or {}), file_system=None)
        if not current and not p.get("name"):
            module.fail_json(msg="name is required to create a CHDFS file system")
        before = comparable(current) if current else None
        old = before or {}
        mapping = {
            "FileSystemName": "name",
            "Description": "description",
            "CapacityQuota": "capacity_quota",
            "SuperUsers": "super_users",
            "PosixAcl": "posix_acl",
            "EnableRanger": "enable_ranger",
            "RangerServiceAddresses": "ranger_service_addresses",
        }
        target = {k: (p.get(v) if p.get(v) is not None else old.get(k)) for k, v in mapping.items()}
        if before == target:
            module.exit_json(changed=False, file_system=current)
        diff = maybe_diff(module, before, target)
        if not module.check_mode:
            if current:
                module.sdk_call(client.ModifyFileSystem, update_request(models, current["FileSystemId"], target))
                p["file_system_id"] = current["FileSystemId"]
            else:
                p["file_system_id"] = module.sdk_call(client.CreateFileSystem, create_request(models, p)).FileSystem.FileSystemId
            current = find(module, client, models, p)
        module.exit_json(changed=True, **(diff or {}), file_system=current if not module.check_mode else target)
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
