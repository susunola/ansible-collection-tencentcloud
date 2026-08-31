#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type
DOCUMENTATION = r"""
---
module: dnspod_line_group
short_description: Manage DNSPod custom line groups
version_added: "0.14.0"
description: Creates, updates and deletes a domain-scoped DNSPod custom line group with exact membership.
options:
  state: {type: str, choices: [present, absent], default: present, description: Desired state.}
  domain: {type: str, description: Domain name.}
  domain_id: {type: int, description: "Domain ID, which takes precedence over domain."}
  line_group_id: {type: int, description: Existing group ID; preferred for rename and deletion.}
  name: {type: str, required: true, description: Custom line group name.}
  lines: {type: list, elements: str, description: Exact set of custom line names in the group.}
  retries: {description: Number of retries for transient failures., type: int, default: 5}
  waiter_delay: {description: Seconds between polling attempts., type: int, default: 5}
  waiter_timeout: {description: Overall polling timeout in seconds., type: int, default: 120}
  user_agent: {description: User-Agent suffix., type: str, default: ansible-collection.susunola.tencentcloud}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.dnspod_line_group:
    domain: example.com
    name: corporate-networks
    lines: [office-network, vpn-network]
"""
RETURN = r"""line_group: {description: DNSPod custom line group metadata., type: dict, returned: always}"""
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


def _load():
    from tencentcloud.dnspod.v20210323 import dnspod_client, models

    return models, dnspod_client


def _scope(request, p):
    request.Domain, request.DomainId = p.get("domain"), p.get("domain_id")
    return request


def describe_request(models, p, offset=0):
    request = _scope(models.DescribeLineGroupListRequest(), p)
    request.Offset, request.Length = offset, 100
    return request


def create_request(models, p):
    request = _scope(models.CreateLineGroupRequest(), p)
    request.Name, request.Lines = p["name"], ",".join(sorted(set(p["lines"])))
    return request


def update_request(models, p, group_id):
    request = _scope(models.ModifyLineGroupRequest(), p)
    request.Name, request.Lines, request.LineGroupId = p["name"], ",".join(sorted(set(p["lines"]))), group_id
    return request


def delete_request(models, p, group_id):
    request = _scope(models.DeleteLineGroupRequest(), p)
    request.LineGroupId = group_id
    return request


def find(module, client, models, p):
    offset = 0
    while True:
        response = module.sdk_call(client.DescribeLineGroupList, describe_request(models, p, offset))
        items = list(response.LineGroups or [])
        matches = []
        for item in items:
            value = item._serialize(allow_none=True)
            if (p.get("line_group_id") is not None and value.get("Id") == p["line_group_id"]) or (
                p.get("line_group_id") is None and value.get("Name") == p["name"]
            ):
                matches.append(value)
        if matches:
            if len(matches) > 1:
                module.fail_json(msg="multiple DNSPod line groups matched name; specify line_group_id")
            return matches[0]
        offset += len(items)
        total = int(getattr(response.Info, "Total", 0) or 0) if response.Info else 0
        if not items or offset >= total:
            return None


def comparable(value):
    return {"Name": value.get("Name"), "Lines": sorted(set(value.get("Lines") or []))}


def desired(p):
    return {"Name": p["name"], "Lines": sorted(set(p["lines"]))}


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "state": {"choices": ["present", "absent"], "default": "present"},
            "domain": {},
            "domain_id": {"type": "int"},
            "line_group_id": {"type": "int"},
            "name": {"required": True},
            "lines": {"type": "list", "elements": "str"},
        },
        required_one_of=[("domain", "domain_id")],
        required_if=[("state", "present", ["lines"])],
        supports_check_mode=True,
    )
    p = module.params
    module.require_sdk()
    models, cm = _load()
    client = module.create_client(cm.DnspodClient, "dnspod.tencentcloudapi.com")
    try:
        current = find(module, client, models, p)
        if p["state"] == "absent":
            if not current:
                module.exit_json(changed=False, line_group=None)
            diff = maybe_diff(module, current, None)
            if not module.check_mode:
                module.sdk_call(client.DeleteLineGroup, delete_request(models, p, current["Id"]))
            module.exit_json(changed=True, **(diff or {}), line_group=current if module.check_mode else None)
        target, before = desired(p), comparable(current) if current else None
        if before == target:
            module.exit_json(changed=False, line_group=current)
        diff = maybe_diff(module, before, target)
        if not current and p.get("line_group_id") is not None:
            module.fail_json(msg="DNSPod line_group_id was not found; omit it to create a new line group")
        if current and before["Name"] != target["Name"] and p.get("line_group_id") is None:
            module.fail_json(msg="line_group_id is required to rename a DNSPod line group")
        if not module.check_mode:
            if current:
                module.sdk_call(client.ModifyLineGroup, update_request(models, p, current["Id"]))
            else:
                module.sdk_call(client.CreateLineGroup, create_request(models, p))
            current = find(module, client, models, p)
        module.exit_json(changed=True, **(diff or {}), line_group=current)
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
