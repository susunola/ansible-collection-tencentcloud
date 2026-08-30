#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function
__metaclass__ = type
DOCUMENTATION = r'''
---
module: dnspod_custom_line
short_description: Manage DNSPod domain custom lines
version_added: "0.14.0"
description: Creates, updates and deletes a domain-scoped DNSPod custom routing line.
options:
  state: {type: str, choices: [present, absent], default: present, description: Desired state.}
  domain: {type: str, description: Domain name.}
  domain_id: {type: int, description: "Domain ID, which takes precedence over domain."}
  name: {type: str, required: true, description: Custom line name and immutable identity.}
  area: {type: str, description: Custom line IP range expression separated with hyphens.}
  retries: {description: Number of retries for transient failures., type: int, default: 5}
  waiter_delay: {description: Seconds between polling attempts., type: int, default: 5}
  waiter_timeout: {description: Overall polling timeout in seconds., type: int, default: 120}
  user_agent: {description: User-Agent suffix., type: str, default: ansible-collection.susunola.tencentcloud}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''
EXAMPLES = r'''
- susunola.tencentcloud.dnspod_custom_line:
    domain: example.com
    name: office-network
    area: 203.0.113.1-203.0.113.254
'''
RETURN = r'''custom_line: {description: DNSPod custom line metadata., type: dict, returned: always}'''
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


def _load():
    from tencentcloud.dnspod.v20210323 import dnspod_client, models
    return models, dnspod_client


def _scope(request, p):
    request.Domain, request.DomainId = p.get("domain"), p.get("domain_id"); return request
def describe_request(models, p): return _scope(models.DescribeDomainCustomLineListRequest(), p)
def create_request(models, p):
    request = _scope(models.CreateDomainCustomLineRequest(), p); request.Name, request.Area = p["name"], p["area"]; return request
def update_request(models, p):
    request = _scope(models.ModifyDomainCustomLineRequest(), p); request.Name, request.PreName, request.Area = p["name"], p["name"], p["area"]; return request
def delete_request(models, p):
    request = _scope(models.DeleteDomainCustomLineRequest(), p); request.Name = p["name"]; return request


def find(module, client, models, p):
    response = module.sdk_call(client.DescribeDomainCustomLineList, describe_request(models, p))
    for item in response.LineList or []:
        value = item._serialize(allow_none=True)
        if value.get("Name") == p["name"]: return value
    return None


def comparable(value): return {"Name": value.get("Name"), "Area": value.get("Area")}
def desired(p): return {"Name": p["name"], "Area": p["area"]}


def run_module():
    module = TencentCloudModule(argument_spec={"state": {"choices": ["present", "absent"], "default": "present"}, "domain": {}, "domain_id": {"type": "int"}, "name": {"required": True}, "area": {}}, required_one_of=[("domain", "domain_id")], required_if=[("state", "present", ["area"])], supports_check_mode=True)
    p = module.params; module.require_sdk(); models, cm = _load(); client = module.create_client(cm.DnspodClient, "dnspod.tencentcloudapi.com")
    try:
        current = find(module, client, models, p)
        if p["state"] == "absent":
            if not current: module.exit_json(changed=False, custom_line=None)
            diff = maybe_diff(module, current, None)
            if not module.check_mode: module.sdk_call(client.DeleteDomainCustomLine, delete_request(models, p))
            module.exit_json(changed=True, **(diff or {}), custom_line=current if module.check_mode else None)
        target, before = desired(p), comparable(current) if current else None
        if before == target: module.exit_json(changed=False, custom_line=current)
        diff = maybe_diff(module, before, target)
        if not module.check_mode:
            module.sdk_call(client.ModifyDomainCustomLine if current else client.CreateDomainCustomLine, update_request(models, p) if current else create_request(models, p)); current = find(module, client, models, p)
        module.exit_json(changed=True, **(diff or {}), custom_line=current)
    except Exception as exc: module.fail_json(**sdk_error_payload(exc))


def main(): run_module()
if __name__ == "__main__": main()
