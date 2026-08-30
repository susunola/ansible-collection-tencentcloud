#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function
__metaclass__ = type
DOCUMENTATION = r'''
---
module: waf_anti_tamper_rule
short_description: Manage Tencent Cloud WAF anti-tamper URL rules
version_added: "0.14.0"
description: Creates, updates, enables and deletes protected URL snapshots for a WAF domain.
options:
  state: {type: str, choices: [present, absent], default: present, description: Desired state.}
  domain: {type: str, required: true, description: Protected domain.}
  rule_id: {type: int, description: Existing rule ID; preferred for rename and deletion.}
  name: {type: str, description: Rule name.}
  uri: {type: str, description: URI protected against tampering.}
  enabled: {type: bool, default: true, description: Whether protection is active.}
  refresh: {type: bool, default: false, description: Refresh the cached protected content when the rule otherwise matches.}
  retries: {description: Number of retries for transient failures., type: int, default: 5}
  waiter_delay: {description: Seconds between polling attempts., type: int, default: 5}
  waiter_timeout: {description: Overall polling timeout in seconds., type: int, default: 120}
  user_agent: {description: User-Agent suffix., type: str, default: ansible-collection.susunola.tencentcloud}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''
EXAMPLES = r'''
- susunola.tencentcloud.waf_anti_tamper_rule:
    domain: www.example.com
    name: protect-homepage
    uri: /index.html
'''
RETURN = r'''rule: {description: Effective anti-tamper rule., type: dict, returned: always}'''
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


def _load():
    from tencentcloud.waf.v20180125 import models, waf_client
    return models, waf_client
def describe_request(models, p, offset=0):
    request = models.DescribeAntiFakeRulesRequest(); request.Domain, request.Offset, request.Limit = p["domain"], offset, 100; return request
def create_request(models, p):
    request = models.AddAntiFakeUrlRequest(); request.Domain, request.Name, request.Uri = p["domain"], p["name"], p["uri"]; return request
def update_request(models, p, rule_id):
    request = models.ModifyAntiFakeUrlRequest(); request.Domain, request.Name, request.Uri, request.Id = p["domain"], p["name"], p["uri"], rule_id; return request
def status_request(models, p, rule_id):
    request = models.ModifyAntiFakeUrlStatusRequest(); request.Domain, request.Status, request.Ids = p["domain"], 1 if p["enabled"] else 0, [rule_id]; return request
def refresh_request(models, p, rule_id):
    request = models.FreshAntiFakeUrlRequest(); request.Domain, request.Id = p["domain"], rule_id; return request
def delete_request(models, p, rule_id):
    request = models.DeleteAntiFakeUrlRequest(); request.Domain, request.Id = p["domain"], rule_id; return request


def find(module, client, models, p):
    offset = 0; matches = []
    while True:
        response = module.sdk_call(client.DescribeAntiFakeRules, describe_request(models, p, offset)); values = list(response.Data or [])
        for item in values:
            value = item._serialize(allow_none=True)
            if (p.get("rule_id") and str(value.get("Id")) == str(p["rule_id"])) or (not p.get("rule_id") and value.get("Name") == p.get("name")): matches.append(value)
        offset += len(values)
        if offset >= int(response.Total or 0) or not values: break
    if len(matches) > 1: module.fail_json(msg="Multiple WAF anti-tamper rules matched; specify rule_id")
    return matches[0] if matches else None
def comparable(value): return {"Name": value.get("Name"), "Uri": value.get("Uri"), "Status": int(value.get("Status") or 0)}
def desired(p): return {"Name": p["name"], "Uri": p["uri"], "Status": 1 if p["enabled"] else 0}


def run_module():
    module = TencentCloudModule(argument_spec={"state": {"choices": ["present", "absent"], "default": "present"}, "domain": {"required": True}, "rule_id": {"type": "int"}, "name": {}, "uri": {}, "enabled": {"type": "bool", "default": True}, "refresh": {"type": "bool", "default": False}}, required_one_of=[("rule_id", "name")], supports_check_mode=True)
    p = module.params
    if p["state"] == "present" and (not p.get("name") or not p.get("uri")): module.fail_json(msg="name and uri are required when state=present")
    module.require_sdk(); models, cm = _load(); client = module.create_client(cm.WafClient, "waf.tencentcloudapi.com")
    try:
        current = find(module, client, models, p)
        if p["state"] == "absent":
            if not current: module.exit_json(changed=False, rule=None)
            diff = maybe_diff(module, comparable(current), None)
            if not module.check_mode: module.sdk_call(client.DeleteAntiFakeUrl, delete_request(models, p, int(current["Id"])))
            module.exit_json(changed=True, **(diff or {}), rule=current if module.check_mode else None)
        target = desired(p); before = comparable(current) if current else None
        if before == target and not p["refresh"]: module.exit_json(changed=False, rule=current)
        diff = maybe_diff(module, before, target)
        if not module.check_mode:
            if current:
                rule_id = int(current["Id"]); module.sdk_call(client.ModifyAntiFakeUrl, update_request(models, p, rule_id))
            else:
                rule_id = int(module.sdk_call(client.AddAntiFakeUrl, create_request(models, p)).Id); p["rule_id"] = rule_id
            module.sdk_call(client.ModifyAntiFakeUrlStatus, status_request(models, p, rule_id))
            if p["refresh"]: module.sdk_call(client.FreshAntiFakeUrl, refresh_request(models, p, rule_id))
            current = find(module, client, models, p)
        module.exit_json(changed=True, **(diff or {}), rule=current)
    except Exception as exc: module.fail_json(**sdk_error_payload(exc))


def main(): run_module()
if __name__ == "__main__": main()
