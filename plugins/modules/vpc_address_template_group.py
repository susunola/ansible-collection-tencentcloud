#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type
DOCUMENTATION = r"""
---
module: vpc_address_template_group
short_description: Manage Tencent Cloud VPC address-template groups
version_added: "0.14.0"
description: Creates, updates and deletes reusable groups of VPC address templates.
options:
  state: {type: str, choices: [present, absent], default: present, description: Desired state.}
  group_id: {type: str, description: Existing address-template group ID.}
  name: {type: str, description: Group name.}
  template_ids: {type: list, elements: str, default: [], description: Exact member address-template ID set.}
  retries: {description: Number of retries for transient failures., type: int, default: 5}
  waiter_delay: {description: Seconds between polling attempts., type: int, default: 5}
  waiter_timeout: {description: Overall polling timeout in seconds., type: int, default: 120}
  user_agent: {description: User-Agent suffix., type: str, default: ansible-collection.susunola.tencentcloud}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.vpc_address_template_group:
    name: trusted-sources
    template_ids: [ipm-xxxxxxxx, ipm-yyyyyyyy]
"""
RETURN = r"""address_template_group: {description: Effective template-group metadata., type: dict, returned: always}"""
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


def _load():
    from tencentcloud.vpc.v20170312 import models, vpc_client

    return models, vpc_client


def describe_request(models, offset=0):
    request = models.DescribeAddressTemplateGroupsRequest()
    request.Offset, request.Limit, request.NeedMemberInfo = str(offset), "100", True
    return request


def create_request(models, p):
    request = models.CreateAddressTemplateGroupRequest()
    request.AddressTemplateGroupName, request.AddressTemplateIds = p["name"], sorted(p["template_ids"])
    return request


def update_request(models, p, group_id):
    request = models.ModifyAddressTemplateGroupAttributeRequest()
    request.AddressTemplateGroupId, request.AddressTemplateGroupName = group_id, p["name"]
    request.AddressTemplateIds = sorted(p["template_ids"])
    return request


def delete_request(models, group_id):
    request = models.DeleteAddressTemplateGroupRequest()
    request.AddressTemplateGroupId = group_id
    return request


def comparable(v):
    return {"AddressTemplateGroupName": v.get("AddressTemplateGroupName"), "AddressTemplateIdSet": sorted(v.get("AddressTemplateIdSet") or [])}


def desired(p):
    return {"AddressTemplateGroupName": p["name"], "AddressTemplateIdSet": sorted(p["template_ids"])}


def find(module, client, models, p):
    offset = 0
    matches = []
    while True:
        response = module.sdk_call(client.DescribeAddressTemplateGroups, describe_request(models, offset))
        values = list(response.AddressTemplateGroupSet or [])
        for item in values:
            value = item._serialize(allow_none=True)
            if (p.get("group_id") and value.get("AddressTemplateGroupId") == p["group_id"]) or (
                not p.get("group_id") and value.get("AddressTemplateGroupName") == p.get("name")
            ):
                matches.append(value)
        offset += len(values)
        if offset >= int(response.TotalCount or 0) or not values:
            break
    if len(matches) > 1:
        module.fail_json(msg="Multiple VPC address-template groups matched; specify group_id")
    return matches[0] if matches else None


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "state": {"choices": ["present", "absent"], "default": "present"},
            "group_id": {},
            "name": {},
            "template_ids": {"type": "list", "elements": "str", "default": []},
        },
        required_one_of=[("group_id", "name")],
        supports_check_mode=True,
    )
    p = module.params
    if p["state"] == "present" and (not p.get("name") or not p["template_ids"]):
        module.fail_json(msg="name and template_ids are required when state=present")
    module.require_sdk()
    models, cm = _load()
    client = module.create_client(cm.VpcClient, "vpc.tencentcloudapi.com")
    try:
        current = find(module, client, models, p)
        if p["state"] == "absent":
            if not current:
                module.exit_json(changed=False, address_template_group=None)
            diff = maybe_diff(module, comparable(current), None)
            if not module.check_mode:
                module.sdk_call(client.DeleteAddressTemplateGroup, delete_request(models, current["AddressTemplateGroupId"]))
            module.exit_json(changed=True, **(diff or {}), address_template_group=current if module.check_mode else None)
        target = desired(p)
        before = comparable(current) if current else None
        if before == target:
            module.exit_json(changed=False, address_template_group=current)
        diff = maybe_diff(module, before, target)
        if not module.check_mode:
            if current:
                module.sdk_call(client.ModifyAddressTemplateGroupAttribute, update_request(models, p, current["AddressTemplateGroupId"]))
            else:
                p["group_id"] = module.sdk_call(client.CreateAddressTemplateGroup, create_request(models, p)).AddressTemplateGroup.AddressTemplateGroupId
            current = find(module, client, models, p)
        module.exit_json(changed=True, **(diff or {}), address_template_group=current)
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
