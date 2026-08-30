#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function
__metaclass__ = type

DOCUMENTATION = r'''
---
module: teo_security_managed_rules
short_description: Manage Tencent Cloud EdgeOne managed WAF rules
version_added: "0.14.0"
description: Exactly reconciles managed WAF configuration without modifying custom, rate-limit, exception, or Bot policies.
options:
  zone_id: {type: str, required: true, description: EdgeOne zone ID.}
  scope: {type: str, choices: [zone, template, host], default: zone, description: Security policy scope.}
  template_id: {type: str, description: Web security template ID required for template scope.}
  host: {type: str, description: Acceleration domain required for host scope.}
  enabled: {type: bool, default: true, description: Whether managed WAF protection is enabled.}
  detection_only: {type: bool, default: false, description: Force all managed rules into monitor mode.}
  semantic_analysis: {type: bool, default: false, description: Enable semantic request analysis.}
  auto_update: {type: bool, default: true, description: Automatically update to the latest managed ruleset.}
  groups:
    type: list
    elements: dict
    default: []
    description: Exact managed-rule group overrides; omitted groups use service defaults.
    suboptions:
      group_id: {type: str, required: true, description: Managed rule-group ID.}
      sensitivity: {type: str, choices: [loose, normal, strict, extreme, custom], default: normal, description: Group sensitivity.}
      action: {type: str, choices: [Deny, Monitor, Disabled], default: Deny, description: Group action for non-custom sensitivity.}
      rule_actions:
        type: list
        elements: dict
        default: []
        description: Exact per-rule actions used only with custom sensitivity.
        suboptions:
          rule_id: {type: str, required: true, description: Managed rule ID.}
          action: {type: str, choices: [Deny, Monitor, Disabled], required: true, description: Rule-specific action.}
  frequent_scanning:
    type: dict
    default: {}
    description: High-frequency managed-rule hit protection.
    suboptions:
      enabled: {type: bool, default: false, description: Whether high-frequency scanning protection is enabled.}
      action: {type: str, choices: [Deny, Monitor], default: Deny, description: Enforcement action.}
      count_by: {type: str, choices: [http.request.ip, http.request.xff_header_ip], default: http.request.ip, description: Client identity field.}
      block_threshold: {type: int, default: 100, description: Managed-rule hit threshold.}
      counting_period: {type: int, default: 60, description: Counting window in seconds.}
      action_duration: {type: int, default: 600, description: Enforcement duration in seconds.}
  retries: {description: Number of retries for transient failures., type: int, default: 5}
  waiter_delay: {description: Seconds between polling attempts., type: int, default: 5}
  waiter_timeout: {description: Overall timeout in seconds for state polling., type: int, default: 120}
  user_agent: {description: User-Agent suffix., type: str, default: ansible-collection.susunola.tencentcloud}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''

EXAMPLES = r'''
- name: Enable strict managed WAF protection on a template
  susunola.tencentcloud.teo_security_managed_rules:
    region: ap-guangzhou
    zone_id: zone-xxxxxxxx
    scope: template
    template_id: temp-xxxxxxxx
    groups:
      - group_id: OWASP
        sensitivity: strict
        action: Deny
'''

RETURN = r'''managed_rules: {description: Current normalized managed WAF configuration., type: dict, returned: always}'''

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


def _action(models, name):
    result = models.SecurityAction(); result.Name = name; return result


def update_request(models, p):
    managed = models.ManagedRules(); managed.Enabled = "on" if p["enabled"] else "off"
    managed.DetectionOnly, managed.SemanticAnalysis = "on" if p["detection_only"] else "off", "on" if p["semantic_analysis"] else "off"
    auto = models.ManagedRuleAutoUpdate(); auto.AutoUpdateToLatestVersion = "on" if p["auto_update"] else "off"; managed.AutoUpdate = auto
    managed.ManagedRuleGroups = []
    for value in p["groups"]:
        group = models.ManagedRuleGroup(); group.GroupId, group.SensitivityLevel = value["group_id"], value["sensitivity"]
        if value["sensitivity"] == "custom":
            group.RuleActions = []
            for override in value["rule_actions"]:
                item = models.ManagedRuleAction(); item.RuleId, item.Action = override["rule_id"], _action(models, override["action"]); group.RuleActions.append(item)
        else: group.Action = _action(models, value["action"])
        managed.ManagedRuleGroups.append(group)
    scan_value = p["frequent_scanning"]; scan = models.FrequentScanningProtection(); scan.Enabled = "on" if scan_value["enabled"] else "off"
    if scan_value["enabled"]:
        scan.Action, scan.CountBy, scan.BlockThreshold = _action(models, scan_value["action"]), scan_value["count_by"], scan_value["block_threshold"]
        scan.CountingPeriod, scan.ActionDuration = "%ss" % scan_value["counting_period"], "%ss" % scan_value["action_duration"]
    managed.FrequentScanningProtection = scan
    policy = models.SecurityPolicy(); policy.ManagedRules = managed
    request = _scope(models.ModifySecurityPolicyRequest(), p); request.SecurityPolicy = policy; return request


def _normalize(raw):
    raw = raw or {}; groups = []
    for value in raw.get("ManagedRuleGroups") or []:
        actions = [{"rule_id": item.get("RuleId"), "action": (item.get("Action") or {}).get("Name")} for item in value.get("RuleActions") or []]
        groups.append({"group_id": value.get("GroupId"), "sensitivity": value.get("SensitivityLevel"), "action": (value.get("Action") or {}).get("Name") or "Deny", "rule_actions": sorted(actions, key=lambda item: item["rule_id"] or "")})
    scan = raw.get("FrequentScanningProtection") or {}; scan_enabled = scan.get("Enabled") == "on"
    return {"enabled": raw.get("Enabled") == "on", "detection_only": raw.get("DetectionOnly") == "on", "semantic_analysis": raw.get("SemanticAnalysis") == "on", "auto_update": (raw.get("AutoUpdate") or {}).get("AutoUpdateToLatestVersion") == "on", "groups": sorted(groups, key=lambda item: item["group_id"] or ""), "frequent_scanning": {"enabled": scan_enabled, "action": (scan.get("Action") or {}).get("Name") or "Deny", "count_by": scan.get("CountBy") or "http.request.ip", "block_threshold": scan.get("BlockThreshold") or 100, "counting_period": int((scan.get("CountingPeriod") or "60s")[:-1]), "action_duration": int((scan.get("ActionDuration") or "600s")[:-1])}}


def desired(p):
    groups = [{"group_id": item["group_id"], "sensitivity": item["sensitivity"], "action": item["action"], "rule_actions": sorted(item["rule_actions"], key=lambda rule: rule["rule_id"])} for item in p["groups"]]
    return {"enabled": p["enabled"], "detection_only": p["detection_only"], "semantic_analysis": p["semantic_analysis"], "auto_update": p["auto_update"], "groups": sorted(groups, key=lambda item: item["group_id"]), "frequent_scanning": p["frequent_scanning"]}


def run_module():
    module = TencentCloudModule(argument_spec={"zone_id": {"required": True}, "scope": {"choices": ["zone", "template", "host"], "default": "zone"}, "template_id": {}, "host": {}, "enabled": {"type": "bool", "default": True}, "detection_only": {"type": "bool", "default": False}, "semantic_analysis": {"type": "bool", "default": False}, "auto_update": {"type": "bool", "default": True}, "groups": {"type": "list", "elements": "dict", "default": [], "options": {"group_id": {"required": True}, "sensitivity": {"choices": ["loose", "normal", "strict", "extreme", "custom"], "default": "normal"}, "action": {"choices": ["Deny", "Monitor", "Disabled"], "default": "Deny"}, "rule_actions": {"type": "list", "elements": "dict", "default": [], "options": {"rule_id": {"required": True}, "action": {"choices": ["Deny", "Monitor", "Disabled"], "required": True}}}}}, "frequent_scanning": {"type": "dict", "default": {}, "options": {"enabled": {"type": "bool", "default": False}, "action": {"choices": ["Deny", "Monitor"], "default": "Deny"}, "count_by": {"choices": ["http.request.ip", "http.request.xff_header_ip"], "default": "http.request.ip"}, "block_threshold": {"type": "int", "default": 100}, "counting_period": {"type": "int", "default": 60}, "action_duration": {"type": "int", "default": 600}}}}, supports_check_mode=True)
    p = module.params
    if p["scope"] == "template" and not p.get("template_id"): module.fail_json(msg="template_id is required for template scope")
    if p["scope"] == "host" and not p.get("host"): module.fail_json(msg="host is required for host scope")
    ids = [item["group_id"] for item in p["groups"]]
    if len(ids) != len(set(ids)): module.fail_json(msg="managed rule group IDs must be unique")
    for group in p["groups"]:
        if group["sensitivity"] == "custom" and not group["rule_actions"]: module.fail_json(msg="custom sensitivity requires rule_actions")
        rule_ids = [item["rule_id"] for item in group["rule_actions"]]
        if len(rule_ids) != len(set(rule_ids)): module.fail_json(msg="managed rule IDs must be unique within a group")
    scan = p["frequent_scanning"]
    if not 1 <= scan["block_threshold"] <= 4294967294 or not 5 <= scan["counting_period"] <= 1800 or not 60 <= scan["action_duration"] <= 86400: module.fail_json(msg="frequent_scanning thresholds or durations are outside supported ranges")
    module.require_sdk(); models, cm = _load(); client = module.create_client(cm.TeoClient, "teo.tencentcloudapi.com")
    try:
        response = module.sdk_call(client.DescribeSecurityPolicy, describe_request(models, p)); raw = response.SecurityPolicy.ManagedRules._serialize(allow_none=True) if response.SecurityPolicy and response.SecurityPolicy.ManagedRules else {}
        before, target = _normalize(raw), desired(p)
        if before == target: module.exit_json(changed=False, managed_rules=before)
        diff = maybe_diff(module, before, target)
        if not module.check_mode:
            module.sdk_call(client.ModifySecurityPolicy, update_request(models, p)); response = module.sdk_call(client.DescribeSecurityPolicy, describe_request(models, p)); before = _normalize(response.SecurityPolicy.ManagedRules._serialize(allow_none=True))
        module.exit_json(changed=True, **(diff or {}), managed_rules=before if not module.check_mode else target)
    except Exception as exc: module.fail_json(**sdk_error_payload(exc))


def main(): run_module()
if __name__ == "__main__": main()
