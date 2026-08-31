#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type
DOCUMENTATION = r"""
---
module: waf_protect_group
short_description: Manage Tencent Cloud WAF protection object groups
version_added: "0.14.0"
description:
  - Creates, updates and deletes a WAF protection object group.
  - Domain membership is reconciled as an exact set.
options:
  state: {type: str, choices: [present, absent], default: present, description: Desired state.}
  group_id: {type: int, description: Existing protection group ID; preferred for rename and deletion.}
  name: {type: str, required: true, description: Protection group name.}
  domains: {type: list, elements: str, default: [], description: Exact set of WAF domains assigned to the group.}
  remark: {type: str, default: '', description: Protection group remark.}
  retries: {description: Number of retries for transient failures., type: int, default: 5}
  waiter_delay: {description: Seconds between polling attempts., type: int, default: 5}
  waiter_timeout: {description: Overall polling timeout in seconds., type: int, default: 120}
  user_agent: {description: User-Agent suffix., type: str, default: ansible-collection.susunola.tencentcloud}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.waf_protect_group:
    name: production-apps
    remark: Internet-facing applications
    domains:
      - api.example.com
      - www.example.com
"""
RETURN = r"""protect_group: {description: WAF protection object group metadata., type: dict, returned: always}"""

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


def _load():
    from tencentcloud.waf.v20180125 import models, waf_client

    return models, waf_client


def describe_request(models, p, offset=0):
    request = models.DescribeProtectGroupRequest()
    request.OffSet, request.Limit = offset, 100
    item = models.FiltersItemNew()
    item.Name = "ID" if p.get("group_id") is not None else "Name"
    item.Values, item.ExactMatch = [str(p["group_id"])] if p.get("group_id") is not None else [p["name"]], True
    request.Filter = [item]
    return request


def create_request(models, p):
    request = models.CreateProtectGroupRequest()
    request.Name, request.Domains, request.Remark = p["name"], sorted(set(p["domains"])), p["remark"]
    return request


def update_request(models, p, group_id):
    request = models.ModifyProtectGroupRequest()
    request.Name, request.GroupId, request.Remark, request.Domains = p["name"], group_id, p["remark"], sorted(set(p["domains"]))
    return request


def delete_request(models, group_id):
    request = models.DeleteProtectGroupRequest()
    request.GroupIds = [group_id]
    return request


def normalize(value):
    domains = []
    for item in value.get("Domains") or []:
        domain = item.get("Domain") if isinstance(item, dict) else None
        if domain:
            domains.append(domain)
    result = dict(value)
    result["Domains"] = sorted(set(domains))
    return result


def find(module, client, models, p):
    offset = 0
    while True:
        response = module.sdk_call(client.DescribeProtectGroup, describe_request(models, p, offset))
        items = list(response.Data or [])
        matches = []
        for item in items:
            value = normalize(item._serialize(allow_none=True))
            if (p.get("group_id") is not None and value.get("ID") == p["group_id"]) or (p.get("group_id") is None and value.get("Name") == p["name"]):
                matches.append(value)
        if matches:
            if len(matches) > 1:
                module.fail_json(msg="multiple WAF protection groups matched name; specify group_id")
            return matches[0]
        offset += len(items)
        if not items or offset >= int(response.Total or 0):
            return None


def comparable(value):
    return {"Name": value.get("Name"), "Remark": value.get("Remark") or "", "Domains": sorted(set(value.get("Domains") or []))}


def desired(p):
    return {"Name": p["name"], "Remark": p["remark"], "Domains": sorted(set(p["domains"]))}


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "state": {"choices": ["present", "absent"], "default": "present"},
            "group_id": {"type": "int"},
            "name": {"required": True},
            "domains": {"type": "list", "elements": "str", "default": []},
            "remark": {"default": ""},
        },
        supports_check_mode=True,
    )
    p = module.params
    module.require_sdk()
    models, cm = _load()
    client = module.create_client(cm.WafClient, "waf.tencentcloudapi.com")
    try:
        current = find(module, client, models, p)
        if p["state"] == "absent":
            if not current:
                module.exit_json(changed=False, protect_group=None)
            diff = maybe_diff(module, current, None)
            if not module.check_mode:
                module.sdk_call(client.DeleteProtectGroup, delete_request(models, current["ID"]))
            module.exit_json(changed=True, **(diff or {}), protect_group=current if module.check_mode else None)
        target, before = desired(p), comparable(current) if current else None
        if before == target:
            module.exit_json(changed=False, protect_group=current)
        diff = maybe_diff(module, before, target)
        if not current and p.get("group_id") is not None:
            module.fail_json(msg="WAF group_id was not found; omit group_id to create a new protection group")
        if current and before["Name"] != target["Name"] and p.get("group_id") is None:
            module.fail_json(msg="group_id is required to rename a WAF protection group")
        if not module.check_mode:
            if current:
                module.sdk_call(client.ModifyProtectGroup, update_request(models, p, current["ID"]))
            else:
                module.sdk_call(client.CreateProtectGroup, create_request(models, p))
            current = find(module, client, models, p)
        module.exit_json(changed=True, **(diff or {}), protect_group=current)
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
