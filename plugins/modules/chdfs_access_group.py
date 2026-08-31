#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type
DOCUMENTATION = r"""
---
module: chdfs_access_group
short_description: Manage Tencent Cloud CHDFS access groups
version_added: "0.14.0"
description: Creates, updates and deletes CHDFS access groups.
options:
  state: {type: str, choices: [present, absent], default: present, description: Desired state.}
  access_group_id: {type: str, description: Existing access group ID.}
  name: {type: str, description: Access group name.}
  vpc_type: {type: int, description: Creation-time VPC type.}
  vpc_id: {type: str, description: Creation-time VPC ID.}
  description: {type: str, description: Access group description.}
  retries: {type: int, default: 5, description: Number of retries for transient failures.}
  waiter_delay: {type: int, default: 5, description: Seconds between polling attempts.}
  waiter_timeout: {type: int, default: 120, description: Overall polling timeout in seconds.}
  user_agent: {type: str, default: ansible-collection.susunola.tencentcloud, description: User-Agent suffix.}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.chdfs_access_group:
    name: analytics-access
    vpc_type: 1
    vpc_id: vpc-xxxxxxxx
"""
RETURN = r"""access_group: {description: Effective CHDFS access group metadata., type: dict, returned: always}"""
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import require_immutable_unchanged, sdk_error_payload


def _load():
    from tencentcloud.chdfs.v20201112 import models, chdfs_client

    return models, chdfs_client


def describe_request(models, marker=None):
    r = models.DescribeAccessGroupsRequest()
    r.AccessGroupIdMarker = marker
    return r


def create_request(models, p):
    r = models.CreateAccessGroupRequest()
    r.AccessGroupName, r.VpcType, r.VpcId, r.Description = p["name"], p["vpc_type"], p["vpc_id"], p.get("description")
    return r


def update_request(models, access_group_id, target):
    r = models.ModifyAccessGroupRequest()
    r.AccessGroupId, r.AccessGroupName, r.Description = access_group_id, target["AccessGroupName"], target["Description"]
    return r


def delete_request(models, access_group_id):
    r = models.DeleteAccessGroupRequest()
    r.AccessGroupId = access_group_id
    return r


def find(module, client, models, p):
    marker = None
    matches = []
    while True:
        response = module.sdk_call(client.DescribeAccessGroups, describe_request(models, marker))
        for item in response.AccessGroups or []:
            value = item._serialize(allow_none=True)
            if (p.get("access_group_id") and value.get("AccessGroupId") == p["access_group_id"]) or (
                not p.get("access_group_id") and value.get("AccessGroupName") == p.get("name")
            ):
                matches.append(value)
        if response.IsOver or not response.NextAccessGroupIdMarker:
            break
        marker = response.NextAccessGroupIdMarker
    if len(matches) > 1:
        module.fail_json(msg="Multiple CHDFS access groups matched; specify access_group_id")
    return matches[0] if matches else None


def comparable(v):
    return {k: v.get(k) for k in ("AccessGroupName", "Description", "VpcType", "VpcId")}


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "state": {"choices": ["present", "absent"], "default": "present"},
            "access_group_id": {},
            "name": {},
            "vpc_type": {"type": "int"},
            "vpc_id": {},
            "description": {},
        },
        required_one_of=[("access_group_id", "name")],
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
                module.exit_json(changed=False, access_group=None)
            diff = maybe_diff(module, current, None)
            if not module.check_mode:
                module.sdk_call(client.DeleteAccessGroup, delete_request(models, current["AccessGroupId"]))
            module.exit_json(changed=True, **(diff or {}), access_group=None)
        if not current:
            missing = [k for k in ("name", "vpc_type", "vpc_id") if p.get(k) is None]
            if missing:
                module.fail_json(msg="creation parameters are required for a CHDFS access group", missing=missing)
        before = comparable(current) if current else None
        old = before or {}
        target = {
            "AccessGroupName": p.get("name") or old.get("AccessGroupName"),
            "Description": p.get("description") if p.get("description") is not None else old.get("Description"),
            "VpcType": p.get("vpc_type") if p.get("vpc_type") is not None else old.get("VpcType"),
            "VpcId": p.get("vpc_id") or old.get("VpcId"),
        }
        if before == target:
            module.exit_json(changed=False, access_group=current)
        if current:
            require_immutable_unchanged(module, before, target, ("VpcType", "VpcId"), "CHDFS access group")
        diff = maybe_diff(module, before, target)
        if not module.check_mode:
            response = module.sdk_call(
                client.ModifyAccessGroup if current else client.CreateAccessGroup,
                update_request(models, current["AccessGroupId"], target) if current else create_request(models, p),
            )
            p["access_group_id"] = current["AccessGroupId"] if current else response.AccessGroup.AccessGroupId
            current = find(module, client, models, p)
        module.exit_json(changed=True, **(diff or {}), access_group=current if not module.check_mode else target)
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
