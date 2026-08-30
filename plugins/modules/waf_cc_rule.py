#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function
__metaclass__ = type
DOCUMENTATION = r'''
---
module: waf_cc_rule
short_description: Manage Tencent Cloud WAF CC protection rules
version_added: "0.14.0"
description: Creates, updates and deletes a domain-level WAF CC rate-protection rule.
options:
  state: {type: str, choices: [present, absent], default: present, description: Desired state.}
  domain: {type: str, required: true, description: Protected domain.}
  rule_id: {type: int, description: Existing CC rule ID; preferred for rename and deletion.}
  name: {type: str, description: Rule name.}
  edition: {type: str, choices: [sparta-waf, clb-waf], default: sparta-waf, description: WAF edition.}
  enabled: {type: bool, default: true, description: Whether the rule is enabled.}
  threshold: {type: int, default: 60, description: Maximum requests in the detection interval.}
  interval: {type: int, default: 60, description: Detection interval in seconds.}
  action: {type: int, choices: [20, 21, 22, 23, 26, 27], default: 22, description: WAF CC action code.}
  priority: {type: int, default: 50, description: Rule evaluation priority.}
  valid_time: {type: int, default: 600, description: Action duration in seconds.}
  url: {type: str, default: '', description: URL expression used by the simple match mode.}
  match_function: {type: int, choices: [0, 1, 2, 3, 6, 7], default: 0, description: URL comparison function.}
  advanced: {type: bool, default: false, description: Whether Session-based advanced detection is enabled.}
  options: {type: list, elements: dict, default: [], description: Advanced SDK-compatible CC match options encoded by the module as canonical JSON.}
  session_ids: {type: list, elements: int, default: [], description: Session definition IDs associated with this rule.}
  limit_method: {type: str, default: only_limit, description: Rate-limiting method.}
  logical_operator: {type: str, choices: [and, or], default: and, description: Relationship between advanced conditions.}
  action_ratio: {type: int, default: 100, description: Percentage of matched traffic receiving the action.}
  retries: {description: Number of retries for transient failures., type: int, default: 5}
  waiter_delay: {description: Seconds between polling attempts., type: int, default: 5}
  waiter_timeout: {description: Overall polling timeout in seconds., type: int, default: 120}
  user_agent: {description: User-Agent suffix., type: str, default: ansible-collection.susunola.tencentcloud}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''
EXAMPLES = r'''
- susunola.tencentcloud.waf_cc_rule:
    domain: api.example.com
    name: protect-login
    threshold: 100
    interval: 60
    action: 22
    url: /login
    match_function: 0
'''
RETURN = r'''rule: {description: WAF CC rule metadata., type: dict, returned: always}'''
import json
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


def _load():
    from tencentcloud.waf.v20180125 import models, waf_client
    return models, waf_client
def canonical_options(value):
    if not value: return "[]"
    if isinstance(value, str): value = json.loads(value)
    return json.dumps(value, sort_keys=True, separators=(",", ":"))
def describe_request(models, p, offset=0):
    request = models.DescribeCCRuleListRequest(); request.Domain, request.Offset, request.Limit, request.By, request.Order = p["domain"], offset, 100, "ts_version", "asc"; return request
def upsert_request(models, p, rule_id=0):
    request = models.UpsertCCRuleRequest()
    request.Domain, request.Name, request.Status = p["domain"], p["name"], 1 if p["enabled"] else 0
    request.Advance, request.Limit, request.Interval, request.ActionType = "1" if p["advanced"] else "0", str(p["threshold"]), str(p["interval"]), str(p["action"])
    request.Priority, request.ValidTime, request.Url, request.MatchFunc = p["priority"], p["valid_time"], p["url"], p["match_function"]
    request.OptionsArr, request.Edition, request.Type, request.RuleId = canonical_options(p["options"]), p["edition"], 0, rule_id
    request.SessionApplied, request.Length, request.LimitMethod = sorted(p["session_ids"]), len(p["url"]), p["limit_method"]
    request.LogicalOp, request.ActionRatio, request.Source = p["logical_operator"], p["action_ratio"], ""
    request.JobType, request.ExpireTime, request.ValidStatus = "forever", 0, 1
    return request
def delete_request(models, p, rule_id):
    request = models.DeleteCCRuleRequest(); request.Domain, request.Name, request.Edition, request.RuleId = p["domain"], p["name"], p["edition"], rule_id; return request


def comparable(value):
    return {"Name": value.get("Name"), "Status": int(value.get("Status") or 0), "Advance": str(value.get("Advance") or "0"), "Limit": str(value.get("Limit") or "0"), "Interval": str(value.get("Interval") or "0"), "ActionType": str(value.get("ActionType") or ""), "Priority": int(value.get("Priority") or 0), "ValidTime": int(value.get("ValidTime") or 0), "Url": value.get("Url") or "", "MatchFunc": int(value.get("MatchFunc") or 0), "Options": canonical_options(value.get("Options") or value.get("OptionsArr")), "SessionApplied": sorted(value.get("SessionApplied") or []), "LimitMethod": value.get("LimitMethod") or "only_limit", "LogicalOp": value.get("LogicalOp") or "and", "ActionRatio": int(value.get("ActionRatio") or 100)}
def desired(p): return {"Name": p["name"], "Status": 1 if p["enabled"] else 0, "Advance": "1" if p["advanced"] else "0", "Limit": str(p["threshold"]), "Interval": str(p["interval"]), "ActionType": str(p["action"]), "Priority": p["priority"], "ValidTime": p["valid_time"], "Url": p["url"], "MatchFunc": p["match_function"], "Options": canonical_options(p["options"]), "SessionApplied": sorted(p["session_ids"]), "LimitMethod": p["limit_method"], "LogicalOp": p["logical_operator"], "ActionRatio": p["action_ratio"]}
def find(module, client, models, p):
    offset = 0; matches = []
    while True:
        response = module.sdk_call(client.DescribeCCRuleList, describe_request(models, p, offset)); data = response.Data; values = list(data.Res or []) if data else []
        for item in values:
            value = item._serialize(allow_none=True)
            if (p.get("rule_id") is not None and int(value.get("RuleId") or 0) == p["rule_id"]) or (p.get("rule_id") is None and value.get("Name") == p.get("name")): matches.append(value)
        offset += len(values); total = int(data.TotalCount or 0) if data else 0
        if offset >= total or not values: break
    if len(matches) > 1: module.fail_json(msg="Multiple WAF CC rules matched; specify rule_id")
    return matches[0] if matches else None


def run_module():
    module = TencentCloudModule(argument_spec={"state": {"choices": ["present", "absent"], "default": "present"}, "domain": {"required": True}, "rule_id": {"type": "int"}, "name": {}, "edition": {"choices": ["sparta-waf", "clb-waf"], "default": "sparta-waf"}, "enabled": {"type": "bool", "default": True}, "threshold": {"type": "int", "default": 60}, "interval": {"type": "int", "default": 60}, "action": {"type": "int", "choices": [20, 21, 22, 23, 26, 27], "default": 22}, "priority": {"type": "int", "default": 50}, "valid_time": {"type": "int", "default": 600}, "url": {"default": ""}, "match_function": {"type": "int", "choices": [0, 1, 2, 3, 6, 7], "default": 0}, "advanced": {"type": "bool", "default": False}, "options": {"type": "list", "elements": "dict", "default": []}, "session_ids": {"type": "list", "elements": "int", "default": []}, "limit_method": {"default": "only_limit"}, "logical_operator": {"choices": ["and", "or"], "default": "and"}, "action_ratio": {"type": "int", "default": 100}}, required_one_of=[("rule_id", "name")], supports_check_mode=True)
    p = module.params
    if p["state"] == "present" and not p["name"]: module.fail_json(msg="name is required when state=present")
    module.require_sdk(); models, cm = _load(); client = module.create_client(cm.WafClient, "waf.tencentcloudapi.com")
    try:
        current = find(module, client, models, p)
        if p["state"] == "absent":
            if not current: module.exit_json(changed=False, rule=None)
            diff = maybe_diff(module, comparable(current), None)
            if not module.check_mode: module.sdk_call(client.DeleteCCRule, delete_request(models, p, int(current["RuleId"])))
            module.exit_json(changed=True, **(diff or {}), rule=current if module.check_mode else None)
        target = desired(p); before = comparable(current) if current else None
        if before == target: module.exit_json(changed=False, rule=current)
        diff = maybe_diff(module, before, target)
        if not module.check_mode:
            response = module.sdk_call(client.UpsertCCRule, upsert_request(models, p, int(current["RuleId"]) if current else 0)); p["rule_id"] = int(response.RuleId); current = find(module, client, models, p)
        module.exit_json(changed=True, **(diff or {}), rule=current)
    except Exception as exc: module.fail_json(**sdk_error_payload(exc))


def main(): run_module()
if __name__ == "__main__": main()
