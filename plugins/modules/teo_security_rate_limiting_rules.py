#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function
__metaclass__ = type

DOCUMENTATION = r'''
---
module: teo_security_rate_limiting_rules
short_description: Manage Tencent Cloud EdgeOne precise rate-limiting rules
version_added: "0.14.0"
description: Exactly reconciles precise L7 rate-limiting rules without modifying other EdgeOne security policy modules.
options:
  zone_id: {type: str, required: true, description: EdgeOne zone ID.}
  scope: {type: str, choices: [zone, template, host], default: zone, description: Security policy scope.}
  template_id: {type: str, description: Web security template ID required for template scope.}
  host: {type: str, description: Acceleration domain required for host scope.}
  rules:
    type: list
    elements: dict
    required: true
    description: Exact precise rate-limiting rule set; an empty list clears these rules.
    suboptions:
      rule_id: {type: str, description: Existing rule ID; otherwise an existing rule is matched by unique name.}
      name: {type: str, required: true, description: Rule name.}
      condition: {type: str, required: true, description: EdgeOne request-matching expression.}
      mode: {type: str, choices: [Block, Throttle], default: Block, description: Block the source or only excess requests.}
      count_by: {type: list, elements: str, required: true, description: One through five request characteristics used as the counter key.}
      threshold: {type: int, required: true, description: Maximum requests allowed in the counting window.}
      counting_period: {type: str, choices: [1s, 5s, 10s, 20s, 30s, 40s, 50s, 1m, 2m, 5m, 10m, 1h], required: true, description: Counting window.}
      action_duration: {type: str, default: 60s, description: "Block action duration with s, m, h, or d suffix."}
      action: {type: str, choices: [Monitor, Deny, Challenge, Redirect], default: Deny, description: Enforcement action.}
      challenge_option: {type: str, choices: [JSChallenge, ManagedChallenge], default: ManagedChallenge, description: Challenge type when action is Challenge.}
      redirect_url: {type: str, description: Redirect destination required when action is Redirect.}
      priority: {type: int, default: 0, description: Priority from 0 through 100.}
      enabled: {type: bool, default: true, description: Whether the rule is enabled.}
  retries: {description: Number of retries for transient failures., type: int, default: 5}
  waiter_delay: {description: Seconds between polling attempts., type: int, default: 5}
  waiter_timeout: {description: Overall timeout in seconds for state polling., type: int, default: 120}
  user_agent: {description: User-Agent suffix., type: str, default: ansible-collection.susunola.tencentcloud}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''

EXAMPLES = r'''
- name: Rate-limit login attempts by client IP
  susunola.tencentcloud.teo_security_rate_limiting_rules:
    region: ap-guangzhou
    zone_id: zone-xxxxxxxx
    scope: template
    template_id: temp-xxxxxxxx
    rules:
      - name: login_limit
        condition: "$http.request.uri.path eq '/login'"
        count_by: [http.request.ip]
        threshold: 30
        counting_period: 1m
        action_duration: 10m
'''

RETURN = r'''rules: {description: Current normalized precise rate-limiting rules., type: list, returned: always}'''

import re
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
        action = (value.get("Action") or {}) if sdk else {}
        result.append({"name": value.get("Name") if sdk else value["name"], "condition": value.get("Condition") if sdk else value["condition"], "mode": (value.get("Mode") or "Block") if sdk else value["mode"], "count_by": sorted((value.get("CountBy") if sdk else value["count_by"]) or []), "threshold": value.get("MaxRequestThreshold") if sdk else value["threshold"], "counting_period": value.get("CountingPeriod") if sdk else value["counting_period"], "action_duration": (value.get("ActionDuration") or "60s") if sdk else value["action_duration"], "action": action.get("Name") if sdk else value["action"], "challenge_option": ((action.get("ChallengeActionParameters") or {}).get("ChallengeOption") or "ManagedChallenge") if sdk else value["challenge_option"], "redirect_url": ((action.get("RedirectActionParameters") or {}).get("URL") or "") if sdk else (value.get("redirect_url") or ""), "priority": (value.get("Priority") or 0) if sdk else value["priority"], "enabled": (value.get("Enabled") == "on") if sdk else value["enabled"]})
    return sorted(result, key=lambda item: (item["priority"], item["name"]))


def _action(models, value):
    action = models.SecurityAction(); action.Name = value["action"]
    if value["action"] == "Challenge":
        params = models.ChallengeActionParameters(); params.ChallengeOption = value["challenge_option"]; action.ChallengeActionParameters = params
    elif value["action"] == "Redirect":
        params = models.RedirectActionParameters(); params.URL = value["redirect_url"]; action.RedirectActionParameters = params
    return action


def update_request(models, p, current=None):
    by_id = {item.get("Id"): item for item in current or [] if item.get("Id")}; by_name = {}
    for item in current or []: by_name.setdefault(item.get("Name"), []).append(item)
    output = []
    for value in p["rules"]:
        item = models.RateLimitingRule(); item.Name, item.Condition, item.Mode = value["name"], value["condition"], value["mode"]
        item.CountBy, item.MaxRequestThreshold, item.CountingPeriod = value["count_by"], value["threshold"], value["counting_period"]
        item.ActionDuration, item.Action, item.Priority, item.Enabled = value["action_duration"], _action(models, value), value["priority"], "on" if value["enabled"] else "off"
        match = by_id.get(value.get("rule_id")); candidates = by_name.get(value["name"], [])
        if match: item.Id = match.get("Id")
        elif len(candidates) == 1: item.Id = candidates[0].get("Id")
        output.append(item)
    rules = models.RateLimitingRules(); rules.Rules = output
    policy = models.SecurityPolicy(); policy.RateLimitingRules = rules
    request = _scope(models.ModifySecurityPolicyRequest(), p); request.SecurityPolicy = policy; return request


def get_rules(module, client, models, p):
    response = module.sdk_call(client.DescribeSecurityPolicy, describe_request(models, p)); policy = response.SecurityPolicy
    if not policy or not policy.RateLimitingRules: return [], []
    raw = [item._serialize(allow_none=True) for item in policy.RateLimitingRules.Rules or []]; return raw, _normalize(raw, True)


def run_module():
    module = TencentCloudModule(argument_spec={"zone_id": {"required": True}, "scope": {"choices": ["zone", "template", "host"], "default": "zone"}, "template_id": {}, "host": {}, "rules": {"type": "list", "elements": "dict", "required": True, "options": {"rule_id": {}, "name": {"required": True}, "condition": {"required": True}, "mode": {"choices": ["Block", "Throttle"], "default": "Block"}, "count_by": {"type": "list", "elements": "str", "required": True}, "threshold": {"type": "int", "required": True}, "counting_period": {"choices": ["1s", "5s", "10s", "20s", "30s", "40s", "50s", "1m", "2m", "5m", "10m", "1h"], "required": True}, "action_duration": {"default": "60s"}, "action": {"choices": ["Monitor", "Deny", "Challenge", "Redirect"], "default": "Deny"}, "challenge_option": {"choices": ["JSChallenge", "ManagedChallenge"], "default": "ManagedChallenge"}, "redirect_url": {}, "priority": {"type": "int", "default": 0}, "enabled": {"type": "bool", "default": True}}}}, supports_check_mode=True)
    p = module.params
    if p["scope"] == "template" and not p.get("template_id"): module.fail_json(msg="template_id is required for template scope")
    if p["scope"] == "host" and not p.get("host"): module.fail_json(msg="host is required for host scope")
    names = [item["name"] for item in p["rules"]]
    if len(names) != len(set(names)): module.fail_json(msg="rate-limiting rule names must be unique")
    duration_limits = {"s": 120, "m": 120, "h": 48, "d": 30}
    for rule in p["rules"]:
        if not 1 <= len(rule["count_by"]) <= 5 or len(rule["count_by"]) != len(set(rule["count_by"])): module.fail_json(msg="count_by requires one through five unique characteristics")
        if not 1 <= rule["threshold"] <= 100000 or not 0 <= rule["priority"] <= 100: module.fail_json(msg="rate threshold or priority is outside the supported range")
        match = re.match(r"^([1-9][0-9]*)([smhd])$", rule["action_duration"])
        if not match or int(match.group(1)) > duration_limits.get(match.group(2), 0): module.fail_json(msg="action_duration is outside the supported range")
        if rule["action"] == "Redirect" and not rule.get("redirect_url"): module.fail_json(msg="redirect_url is required when action=Redirect")
    module.require_sdk(); models, cm = _load(); client = module.create_client(cm.TeoClient, "teo.tencentcloudapi.com")
    try:
        raw, before = get_rules(module, client, models, p); target = _normalize(p["rules"])
        if before == target: module.exit_json(changed=False, rules=before)
        diff = maybe_diff(module, before, target)
        if not module.check_mode: module.sdk_call(client.ModifySecurityPolicy, update_request(models, p, raw)); raw, before = get_rules(module, client, models, p)
        module.exit_json(changed=True, **(diff or {}), rules=before if not module.check_mode else target)
    except Exception as exc: module.fail_json(**sdk_error_payload(exc))


def main(): run_module()
if __name__ == "__main__": main()
