#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function
__metaclass__ = type

DOCUMENTATION = r'''
---
module: teo_security_custom_rules
short_description: Manage Tencent Cloud EdgeOne web security custom rules
version_added: "0.14.0"
description: Exactly reconciles custom L7 security rules without modifying managed WAF, rate-limit, exception, or Bot policies.
options:
  zone_id: {type: str, required: true, description: EdgeOne zone ID.}
  scope: {type: str, choices: [zone, template, host], default: zone, description: Security policy scope.}
  template_id: {type: str, description: Web security template ID required for template scope.}
  host: {type: str, description: Acceleration domain required for host scope.}
  rules:
    type: list
    elements: dict
    required: true
    description: Exact custom-rule set; an empty list removes all custom rules in this scope.
    suboptions:
      rule_id: {type: str, description: Existing rule ID; otherwise an existing rule is matched by unique name.}
      name: {type: str, required: true, description: Rule name.}
      condition: {type: str, required: true, description: EdgeOne security expression.}
      action: {type: str, choices: [Deny, Monitor], default: Deny, description: Safe parameter-free enforcement action.}
      enabled: {type: bool, default: true, description: Whether the rule is enabled.}
      rule_type: {type: str, choices: [BasicAccessRule, PreciseMatchRule], default: PreciseMatchRule, description: Rule category.}
      priority: {type: int, default: 0, description: Priority from 0 through 100 for precise-match rules.}
  retries: {description: Number of retries for transient failures., type: int, default: 5}
  waiter_delay: {description: Seconds between polling attempts., type: int, default: 5}
  waiter_timeout: {description: Overall timeout in seconds for state polling., type: int, default: 120}
  user_agent: {description: User-Agent suffix., type: str, default: ansible-collection.susunola.tencentcloud}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''

EXAMPLES = r'''
- name: Block requests from a maintained security IP group
  susunola.tencentcloud.teo_security_custom_rules:
    region: ap-guangzhou
    zone_id: zone-xxxxxxxx
    scope: template
    template_id: temp-xxxxxxxx
    rules:
      - name: block_known_attackers
        condition: "$http.request.ip in '1234'"
        action: Deny
        priority: 10
'''

RETURN = r'''rules: {description: Current normalized custom security rules., type: list, returned: always}'''

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


def _load():
    from tencentcloud.teo.v20220901 import models, teo_client
    return models, teo_client


def _scope(request, p):
    request.ZoneId = p["zone_id"]; request.Entity = {"zone": "ZoneDefaultPolicy", "template": "Template", "host": "Host"}[p["scope"]]
    if p["scope"] == "template": request.TemplateId = p["template_id"]
    if p["scope"] == "host": request.Host = p["host"]
    return request


def describe_request(models, p): return _scope(models.DescribeSecurityPolicyRequest(), p)


def _normalize(values, sdk=False):
    result = []
    for value in values or []:
        action = value.get("Action") or {} if sdk else None
        result.append({"name": value.get("Name") if sdk else value["name"], "condition": value.get("Condition") if sdk else value["condition"], "action": action.get("Name") if sdk else value["action"], "enabled": (value.get("Enabled") == "on") if sdk else value["enabled"], "rule_type": (value.get("RuleType") or "PreciseMatchRule") if sdk else value["rule_type"], "priority": (value.get("Priority") or 0) if sdk else value["priority"]})
    return sorted(result, key=lambda item: (item["priority"], item["name"]))


def update_request(models, p, current=None):
    by_id = {item.get("Id"): item for item in current or [] if item.get("Id")}; by_name = {}
    for item in current or []: by_name.setdefault(item.get("Name"), []).append(item)
    rules = []
    for value in p["rules"]:
        item = models.CustomRule(); item.Name, item.Condition = value["name"], value["condition"]
        action = models.SecurityAction(); action.Name = value["action"]; item.Action = action
        item.Enabled, item.RuleType, item.Priority = "on" if value["enabled"] else "off", value["rule_type"], value["priority"]
        match = by_id.get(value.get("rule_id")); candidates = by_name.get(value["name"], [])
        if match: item.Id = match.get("Id")
        elif len(candidates) == 1: item.Id = candidates[0].get("Id")
        rules.append(item)
    custom = models.CustomRules(); custom.Rules = rules
    policy = models.SecurityPolicy(); policy.CustomRules = custom
    request = _scope(models.ModifySecurityPolicyRequest(), p); request.SecurityPolicy = policy; return request


def get_rules(module, client, models, p):
    response = module.sdk_call(client.DescribeSecurityPolicy, describe_request(models, p)); policy = response.SecurityPolicy
    if not policy or not policy.CustomRules: return [], []
    raw = [item._serialize(allow_none=True) for item in policy.CustomRules.Rules or []]; return raw, _normalize(raw, True)


def run_module():
    module = TencentCloudModule(argument_spec={"zone_id": {"required": True}, "scope": {"choices": ["zone", "template", "host"], "default": "zone"}, "template_id": {}, "host": {}, "rules": {"type": "list", "elements": "dict", "required": True, "options": {"rule_id": {}, "name": {"required": True}, "condition": {"required": True}, "action": {"choices": ["Deny", "Monitor"], "default": "Deny"}, "enabled": {"type": "bool", "default": True}, "rule_type": {"choices": ["BasicAccessRule", "PreciseMatchRule"], "default": "PreciseMatchRule"}, "priority": {"type": "int", "default": 0}}}}, supports_check_mode=True)
    p = module.params
    if p["scope"] == "template" and not p.get("template_id"): module.fail_json(msg="template_id is required for template scope")
    if p["scope"] == "host" and not p.get("host"): module.fail_json(msg="host is required for host scope")
    names = [item["name"] for item in p["rules"]]
    if len(names) != len(set(names)): module.fail_json(msg="rule names must be unique")
    for rule in p["rules"]:
        if not 0 <= rule["priority"] <= 100: module.fail_json(msg="rule priority must be between 0 and 100")
        if rule["rule_type"] == "BasicAccessRule" and rule["priority"] != 0: module.fail_json(msg="priority is only supported for PreciseMatchRule")
    module.require_sdk(); models, cm = _load(); client = module.create_client(cm.TeoClient, "teo.tencentcloudapi.com")
    try:
        raw, before = get_rules(module, client, models, p); target = _normalize(p["rules"])
        if before == target: module.exit_json(changed=False, rules=before)
        diff = maybe_diff(module, before, target)
        if not module.check_mode:
            module.sdk_call(client.ModifySecurityPolicy, update_request(models, p, raw)); raw, before = get_rules(module, client, models, p)
        module.exit_json(changed=True, **(diff or {}), rules=before if not module.check_mode else target)
    except Exception as exc: module.fail_json(**sdk_error_payload(exc))


def main(): run_module()
if __name__ == "__main__": main()
