#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function
__metaclass__ = type

DOCUMENTATION = r'''
---
module: teo_security_ip_group
short_description: Manage Tencent Cloud EdgeOne security IP groups
version_added: "0.14.0"
description: Creates, renames, exactly replaces and deletes EdgeOne security IP groups.
options:
  state: {type: str, choices: [present, absent], default: present, description: Desired IP-group state.}
  zone_id: {type: str, required: true, description: EdgeOne zone ID.}
  group_id: {type: int, description: Existing numeric security IP-group ID.}
  name: {type: str, description: "Security IP-group name, also used for lookup."}
  content: {type: list, elements: str, description: "Exact set of IPv4, IPv6, and CIDR entries."}
  retries: {description: Number of retries for transient failures., type: int, default: 5}
  waiter_delay: {description: Seconds between polling attempts., type: int, default: 5}
  waiter_timeout: {description: Overall timeout in seconds for state polling., type: int, default: 120}
  user_agent: {description: User-Agent suffix., type: str, default: ansible-collection.susunola.tencentcloud}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''

EXAMPLES = r'''
- name: Maintain trusted office networks
  susunola.tencentcloud.teo_security_ip_group:
    region: ap-guangzhou
    zone_id: zone-xxxxxxxx
    name: trusted-offices
    content:
      - 192.0.2.0/24
      - 2001:db8::/48
'''

RETURN = r'''ip_group: {description: EdgeOne security IP-group metadata and complete content., type: dict, returned: always}'''

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


def _load():
    from tencentcloud.teo.v20220901 import models, teo_client
    return models, teo_client


def describe_request(models, p, offset=0):
    request = models.DescribeSecurityIPGroupInfoRequest(); request.ZoneId, request.Offset, request.Limit = p["zone_id"], offset, 1000; return request


def content_request(models, p, group_id, offset=0):
    request = models.DescribeSecurityIPGroupContentRequest(); request.ZoneId, request.GroupId = p["zone_id"], group_id
    request.Offset, request.Limit = offset, 100000; return request


def _group(models, group_id, name, content):
    item = models.IPGroup(); item.GroupId, item.Name, item.Content = group_id, name, content; return item


def create_request(models, p):
    request = models.CreateSecurityIPGroupRequest(); request.ZoneId = p["zone_id"]; request.IPGroup = _group(models, 0, p["name"], p["content"]); return request


def update_request(models, p, group_id):
    request = models.ModifySecurityIPGroupRequest(); request.ZoneId, request.Mode = p["zone_id"], "update"
    request.IPGroup = _group(models, group_id, p["name"], p["content"]); return request


def delete_request(models, p, group_id):
    request = models.DeleteSecurityIPGroupRequest(); request.ZoneId, request.GroupId = p["zone_id"], group_id; return request


def _complete_content(module, client, models, p, group_id):
    offset = 0; result = []
    while True:
        response = module.sdk_call(client.DescribeSecurityIPGroupContent, content_request(models, p, group_id, offset)); values = list(response.IPList or [])
        result.extend(values); offset += len(values)
        if offset >= int(response.IPTotalCount or 0) or not values: break
    return result


def find_group(module, client, models, p):
    offset = 0; matches = []
    while True:
        response = module.sdk_call(client.DescribeSecurityIPGroupInfo, describe_request(models, p, offset)); values = list(response.IPGroups or [])
        for value in values:
            item = value._serialize(allow_none=True)
            if p.get("group_id") is not None and item.get("GroupId") == p["group_id"]: matches.append(item)
            elif p.get("group_id") is None and p.get("name") and item.get("Name") == p["name"]: matches.append(item)
        offset += len(values)
        if offset >= int(response.TotalCount or 0) or not values: break
    if len(matches) > 1: module.fail_json(msg="Multiple EdgeOne security IP groups matched; specify group_id")
    if not matches: return None
    matches[0]["Content"] = _complete_content(module, client, models, p, matches[0]["GroupId"])
    return matches[0]


def desired(p): return {"Name": p["name"], "Content": sorted(set(p["content"]))}


def run_module():
    module = TencentCloudModule(argument_spec={"state": {"choices": ["present", "absent"], "default": "present"}, "zone_id": {"required": True}, "group_id": {"type": "int"}, "name": {}, "content": {"type": "list", "elements": "str"}}, required_one_of=[("group_id", "name")], supports_check_mode=True)
    p = module.params
    if p["state"] == "present" and (not p.get("name") or not p.get("content")): module.fail_json(msg="name and at least one content entry are required when state=present")
    if p.get("content") and len(p["content"]) != len(set(p["content"])): module.fail_json(msg="content must not contain duplicate IP or CIDR entries")
    module.require_sdk(); models, cm = _load(); client = module.create_client(cm.TeoClient, "teo.tencentcloudapi.com")
    try:
        current = find_group(module, client, models, p)
        if p["state"] == "absent":
            if not current: module.exit_json(changed=False, ip_group=None)
            diff = maybe_diff(module, current, None)
            if not module.check_mode: module.sdk_call(client.DeleteSecurityIPGroup, delete_request(models, p, current["GroupId"]))
            module.exit_json(changed=True, **(diff or {}), ip_group=current if module.check_mode else None)
        target = desired(p); before = {"Name": current.get("Name"), "Content": sorted(set(current.get("Content") or []))} if current else None
        if before == target: module.exit_json(changed=False, ip_group=current)
        diff = maybe_diff(module, before, target)
        if not module.check_mode:
            if not current: p["group_id"] = module.sdk_call(client.CreateSecurityIPGroup, create_request(models, p)).GroupId
            else: module.sdk_call(client.ModifySecurityIPGroup, update_request(models, p, current["GroupId"]))
            current = find_group(module, client, models, p)
        module.exit_json(changed=True, **(diff or {}), ip_group=current)
    except Exception as exc: module.fail_json(**sdk_error_payload(exc))


def main(): run_module()
if __name__ == "__main__": main()
