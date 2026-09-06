#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type
DOCUMENTATION = r"""
---
module: goosefs_file_system
short_description: Manage Tencent Cloud GooseFS file systems
version_added: "0.14.0"
description: Creates, expands and deletes GooseFS file systems while protecting immutable topology.
options:
  state: {type: str, choices: [present, absent], default: present, description: Desired state.}
  file_system_id: {type: str, description: Existing file system ID.}
  name: {type: str, description: File system name and immutable after creation.}
  description: {type: str, default: '', description: Creation-time description.}
  vpc_id: {type: str, description: VPC ID required for creation and immutable afterwards.}
  subnet_id: {type: str, description: Subnet ID required for creation and immutable afterwards.}
  zone: {type: str, description: Availability zone required for creation and immutable afterwards.}
  file_system_type: {type: str, description: GooseFS product type required for creation and immutable afterwards.}
  build_elements: {type: list, elements: dict, description: SDK GooseFSxBuildElement payloads required by GooseFSx products.}
  capacity: {type: int, description: Desired GooseFSx capacity; only expansion is supported.}
  security_group_id: {type: str, description: Creation-time security group ID.}
  cluster_port: {type: int, description: Creation-time cluster port.}
  tags: {type: dict, description: Creation-time tags.}
  retries: {type: int, default: 5, description: Number of retries for transient failures.}
  waiter_delay: {type: int, default: 5, description: Seconds between polling attempts.}
  waiter_timeout: {type: int, default: 120, description: Overall polling timeout in seconds.}
  user_agent: {type: str, default: ansible-collection.susunola.tencentcloud, description: User-Agent suffix.}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.goosefs_file_system:
    name: analytics-cache
    vpc_id: vpc-xxxxxxxx
    subnet_id: subnet-xxxxxxxx
    zone: ap-guangzhou-3
    file_system_type: GooseFSx
    build_elements: [{Model: GOOSFSX_C60, Capacity: 10}]
    capacity: 10
"""
RETURN = r"""file_system: {description: Effective GooseFS file system metadata., type: dict, returned: always}"""
import json
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import require_immutable_unchanged, sdk_error_payload


def _load():
    from tencentcloud.goosefs.v20220519 import models, goosefs_client

    return models, goosefs_client


def _model(cls, value):
    x = cls()
    x.from_json_string(json.dumps(value))
    return x


def describe_request(models, offset=0):
    r = models.DescribeFileSystemsRequest()
    r.Offset, r.Limit = offset, 100
    return r


def _tags(models, values):
    result = []
    for key, value in sorted((values or {}).items()):
        x = models.Tag()
        x.Key, x.Value = key, value
        result.append(x)
    return result


def create_request(models, p):
    r = models.CreateFileSystemRequest()
    r.Name, r.Description, r.VpcId, r.SubnetId, r.Zone, r.Type = p["name"], p["description"], p["vpc_id"], p["subnet_id"], p["zone"], p["file_system_type"]
    r.GooseFSxBuildElements = [_model(models.GooseFSxBuildElement, x) for x in p.get("build_elements") or []]
    r.SecurityGroupId, r.ClusterPort, r.Tag = p.get("security_group_id"), p.get("cluster_port"), _tags(models, p.get("tags"))
    return r


def expand_request(models, file_system_id, capacity):
    r = models.ExpandCapacityRequest()
    r.FileSystemId, r.ExpandedCapacity, r.ModifyType = file_system_id, capacity, "EXPAND"
    return r


def delete_request(models, file_system_id):
    r = models.DeleteFileSystemRequest()
    r.FileSystemId = file_system_id
    return r


def find(module, client, models, p):
    response = module.sdk_call(client.DescribeFileSystems, describe_request(models))
    matches = []
    for item in response.FSAttributeList or []:
        value = item._serialize(allow_none=True)
        if (p.get("file_system_id") and value.get("FileSystemId") == p["file_system_id"]) or (
            not p.get("file_system_id") and value.get("Name") == p.get("name")
        ):
            matches.append(value)
    if len(matches) > 1:
        module.fail_json(msg="Multiple GooseFS file systems matched; specify file_system_id")
    return matches[0] if matches else None


def _capacity(v):
    return (v.get("GooseFSxAttribute") or {}).get("Capacity")


def run_module():
    spec = {
        "state": {"choices": ["present", "absent"], "default": "present"},
        "file_system_id": {},
        "name": {},
        "description": {"default": ""},
        "vpc_id": {},
        "subnet_id": {},
        "zone": {},
        "file_system_type": {},
        "build_elements": {"type": "list", "elements": "dict"},
        "capacity": {"type": "int"},
        "security_group_id": {},
        "cluster_port": {"type": "int"},
        "tags": {"type": "dict"},
    }
    module = TencentCloudModule(argument_spec=spec, required_one_of=[("file_system_id", "name")], supports_check_mode=True)
    p = module.params
    module.require_sdk()
    models, cm = _load()
    client = module.create_client(cm.GoosefsClient, "goosefs.tencentcloudapi.com")
    try:
        current = find(module, client, models, p)
        if p["state"] == "absent":
            if not current:
                module.exit_json(changed=False, file_system=None)
            diff = maybe_diff(module, current, None)
            if not module.check_mode:
                module.sdk_call(client.DeleteFileSystem, delete_request(models, current["FileSystemId"]))
            module.exit_json(changed=True, **(diff or {}), file_system=None)
        if not current:
            missing = [k for k in ("name", "vpc_id", "subnet_id", "zone", "file_system_type") if not p.get(k)]
            if missing:
                module.fail_json(msg="creation parameters are required for a GooseFS file system", missing=missing)
            target = {
                "Name": p["name"],
                "VpcId": p["vpc_id"],
                "SubnetId": p["subnet_id"],
                "Zone": p["zone"],
                "Type": p["file_system_type"],
                "Capacity": p.get("capacity"),
            }
            diff = maybe_diff(module, None, target)
            if not module.check_mode:
                p["file_system_id"] = module.sdk_call(client.CreateFileSystem, create_request(models, p)).FileSystemId
                current = find(module, client, models, p)
            module.exit_json(changed=True, **(diff or {}), file_system=current if not module.check_mode else target)
        before = {
            "Name": current.get("Name"),
            "VpcId": current.get("VpcId"),
            "SubnetId": current.get("SubnetId"),
            "Zone": current.get("Zone"),
            "Type": current.get("Type"),
            "Capacity": _capacity(current),
        }
        target = {
            "Name": p.get("name") or before["Name"],
            "VpcId": p.get("vpc_id") or before["VpcId"],
            "SubnetId": p.get("subnet_id") or before["SubnetId"],
            "Zone": p.get("zone") or before["Zone"],
            "Type": p.get("file_system_type") or before["Type"],
            "Capacity": p.get("capacity") if p.get("capacity") is not None else before["Capacity"],
        }
        require_immutable_unchanged(module, before, target, ("Name", "VpcId", "SubnetId", "Zone", "Type"), "GooseFS file system")
        if before["Capacity"] is not None and target["Capacity"] is not None and target["Capacity"] < before["Capacity"]:
            module.fail_json(msg="GooseFS capacity cannot be reduced", before=before["Capacity"], after=target["Capacity"])
        if before == target:
            module.exit_json(changed=False, file_system=current)
        diff = maybe_diff(module, before, target)
        if not module.check_mode:
            module.sdk_call(client.ExpandCapacity, expand_request(models, current["FileSystemId"], target["Capacity"]))
            p["file_system_id"] = current["FileSystemId"]
            current = find(module, client, models, p)
        module.exit_json(changed=True, **(diff or {}), file_system=current)
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
