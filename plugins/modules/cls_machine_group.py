#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type
DOCUMENTATION = r"""
---
module: cls_machine_group
short_description: Manage Tencent Cloud CLS machine groups
version_added: "0.14.0"
description: Creates, updates and deletes CLS LogListener machine groups.
options:

  state:
    description:
      - C(present) creates the machine group with V(CreateMachineGroup) when it does not exist and updates it
        with V(ModifyMachineGroup) when it differs. C(absent) deletes it with V(DeleteMachineGroup).
    type: str
    choices: [present, absent]
    default: present
  group_id:
    description:
      - Existing machine group ID.
    type: str
  name:
    description:
      - Identifies the machine group to manage; one of this or O(group_id) is required, and the name is only
        used when O(group_id) is not given.
    type: str
  group_type:
    description:
      - Machine identity type.
    type: str
    choices: [ip, label]
    default: ip
  values:
    description:
      - Exact IP addresses or labels.
    type: list
    default: []
    elements: str
  tags:
    description:
      - Exact resource tags.
    type: dict
    default: {}
  auto_update:
    description:
      - Automatically update LogListener.
    type: bool
    default: false
  update_start_time:
    description:
      - Update window start.
    type: str
    default: 00:00:00
  update_end_time:
    description:
      - Update window end.
    type: str
    default: '23:59:59'
  service_logging:
    description:
      - Enable LogListener service logs.
    type: bool
    default: false
  delay_cleanup_time:
    description:
      - Offline machine cleanup delay.
    type: int
    default: 0
  os_type:
    description:
      - Operating system type at creation.
    type: int
    choices: [0, 1]
    default: 0
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
  - module: susunola.tencentcloud.cls_machine_group_info
    description: Gather information about Tencent Cloud CLS machine groups.
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.cls_machine_group:
    name: production-web
    group_type: label
    values: [production-web]

- name: Delete the machine group
  susunola.tencentcloud.cls_machine_group:
    state: absent
    name: production-web
"""
RETURN = r"""machine_group:
  description:
    - CLS machine group metadata.
  returned: always
  type: dict"""

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import require_immutable_unchanged, fail_from_sdk_error


def _load():
    from tencentcloud.cls.v20201016 import cls_client, models

    return models, cls_client


def group_type(models, p):
    value = models.MachineGroupTypeInfo()
    value.Type, value.Values = p["group_type"], sorted(p["values"])
    return value


def tag_models(models, values):
    result = []
    for key, value in sorted(values.items()):
        item = models.Tag()
        item.Key, item.Value = str(key), str(value)
        result.append(item)
    return result


def find(module, client, models, p):
    request = models.DescribeMachineGroupsRequest()
    request.Offset, request.Limit = 0, 100
    if p["group_id"] or p["name"]:
        item = models.Filter()
        item.Key = "groupId" if p["group_id"] else "groupName"
        item.Values = [p["group_id"] or p["name"]]
        request.Filters = [item]
    items = module.sdk_call(client.DescribeMachineGroups, request).MachineGroups or []
    matches = [
        x._serialize(allow_none=True) for x in items if (p["group_id"] and x.GroupId == p["group_id"]) or (not p["group_id"] and x.GroupName == p["name"])
    ]
    if len(matches) > 1:
        module.fail_json(msg="Multiple CLS machine groups have the requested name", name=p["name"])
    return matches[0] if matches else None


def normalize(value):
    kind = value.get("MachineGroupType") or {}
    tags = {x.get("Key"): x.get("Value") for x in value.get("Tags") or []}
    return {
        "GroupName": value.get("GroupName"),
        "Type": kind.get("Type"),
        "Values": sorted(kind.get("Values") or []),
        "Tags": tags,
        "AutoUpdate": bool(value.get("AutoUpdate")),
        "UpdateStartTime": value.get("UpdateStartTime"),
        "UpdateEndTime": value.get("UpdateEndTime"),
        "ServiceLogging": bool(value.get("ServiceLogging")),
        "DelayCleanupTime": value.get("DelayCleanupTime") or 0,
    }


def wanted(p):
    return {
        "GroupName": p["name"],
        "Type": p["group_type"],
        "Values": sorted(p["values"]),
        "Tags": p["tags"],
        "AutoUpdate": p["auto_update"],
        "UpdateStartTime": p["update_start_time"],
        "UpdateEndTime": p["update_end_time"],
        "ServiceLogging": p["service_logging"],
        "DelayCleanupTime": p["delay_cleanup_time"],
    }


def apply(request, models, p, group_id=None):
    if group_id:
        request.GroupId = group_id
    request.GroupName, request.MachineGroupType = p["name"], group_type(models, p)
    request.Tags, request.AutoUpdate = tag_models(models, p["tags"]), p["auto_update"]
    request.UpdateStartTime, request.UpdateEndTime = p["update_start_time"], p["update_end_time"]
    request.ServiceLogging, request.DelayCleanupTime = p["service_logging"], p["delay_cleanup_time"]
    if not group_id:
        request.OSType = p["os_type"]
    return request


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "state": {"choices": ["present", "absent"], "default": "present"},
            "group_id": {},
            "name": {},
            "group_type": {"choices": ["ip", "label"], "default": "ip"},
            "values": {"type": "list", "elements": "str", "default": []},
            "tags": {"type": "dict", "default": {}},
            "auto_update": {"type": "bool", "default": False},
            "update_start_time": {"default": "00:00:00"},
            "update_end_time": {"default": "23:59:59"},
            "service_logging": {"type": "bool", "default": False},
            "delay_cleanup_time": {"type": "int", "default": 0},
            "os_type": {"type": "int", "choices": [0, 1], "default": 0},
        },
        required_one_of=[("group_id", "name")],
        supports_check_mode=True,
    )
    p = module.params
    if p["state"] == "present" and not p["name"]:
        module.fail_json(msg="name is required when state=present")
    module.require_sdk()
    models, cm = _load()
    client = module.create_client(cm.ClsClient, "cls.tencentcloudapi.com")
    try:
        current = find(module, client, models, p)
        if p["state"] == "absent":
            if not current:
                module.exit_json(changed=False, machine_group=None)
            diff = maybe_diff(module, current, None)
            if not module.check_mode:
                request = models.DeleteMachineGroupRequest()
                request.GroupId = current["GroupId"]
                module.sdk_call(client.DeleteMachineGroup, request)
            module.exit_json(changed=True, **(diff or {}), machine_group=current if module.check_mode else None)
        target = wanted(p)
        before = normalize(current) if current else None
        if before == target:
            module.exit_json(changed=False, machine_group=current)
        if current:
            require_immutable_unchanged(module, before, target, ("Type",), "CLS machine group")
        diff = maybe_diff(module, before, target)
        if not module.check_mode:
            operation = client.ModifyMachineGroup if current else client.CreateMachineGroup
            request = models.ModifyMachineGroupRequest() if current else models.CreateMachineGroupRequest()
            module.sdk_call(operation, apply(request, models, p, current["GroupId"] if current else None))
            p["group_id"] = current["GroupId"] if current else None
            current = find(module, client, models, p)
        module.exit_json(changed=True, **(diff or {}), machine_group=current)
    except Exception as exc:
        fail_from_sdk_error(module, exc)


def main():
    run_module()


if __name__ == "__main__":
    main()
