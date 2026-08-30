#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function
__metaclass__ = type
DOCUMENTATION = r'''
---
module: waf_attack_white_rule
short_description: Manage Tencent Cloud WAF attack-signature allow rules
version_added: "0.14.0"
description: Creates, updates and deletes domain-level WAF attack-signature allow rules.
options:
  state: {type: str, choices: [present, absent], default: present, description: Desired state.}
  domain: {type: str, required: true, description: Protected domain.}
  rule_id: {type: int, description: Existing allow-rule ID; preferred for rename and deletion.}
  name: {type: str, description: Rule name.}
  enabled: {type: bool, default: true, description: Whether the allow rule is enabled.}
  mode: {type: int, choices: [0, 1], default: 0, description: Match individual signature IDs or signature type IDs.}
  signature_ids: {type: list, elements: str, default: [], description: Exact set of attack signature IDs used in mode 0.}
  type_ids: {type: list, elements: str, default: [], description: Exact set of signature category IDs used in mode 1.}
  rules: {type: list, elements: dict, default: [], description: SDK-compatible request matching conditions.}
  retries: {description: Number of retries for transient failures., type: int, default: 5}
  waiter_delay: {description: Seconds between polling attempts., type: int, default: 5}
  waiter_timeout: {description: Overall polling timeout in seconds., type: int, default: 120}
  user_agent: {description: User-Agent suffix., type: str, default: ansible-collection.susunola.tencentcloud}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''
EXAMPLES = r'''
- susunola.tencentcloud.waf_attack_white_rule:
    domain: api.example.com
    name: allow-health-check-signatures
    signature_ids: ['100001', '100002']
    rules:
      - {MatchField: URI, MatchMethod: prefix, MatchContent: /health, MatchParams: ''}
'''
RETURN = r'''rule: {description: WAF attack-signature allow-rule metadata., type: dict, returned: always}'''
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


def _load():
    from tencentcloud.waf.v20180125 import models, waf_client
    return models, waf_client
def _rules(models, values):
    result = []
    for value in values: item = models.UserWhiteRuleItem(); item._deserialize(value); result.append(item)
    return result
def describe_request(models, p, offset=0):
    request = models.DescribeAttackWhiteRuleRequest(); request.Domain, request.Offset, request.Limit = p["domain"], offset, 100; return request
def _apply(request, models, p, rule_id=None):
    request.Domain, request.Status, request.Rules = p["domain"], 1 if p["enabled"] else 0, _rules(models, p["rules"])
    request.SignatureIds, request.TypeIds, request.Mode, request.Name = sorted(p["signature_ids"]), sorted(p["type_ids"]), p["mode"], p["name"]
    if rule_id is not None: request.RuleId = rule_id
    return request
def create_request(models, p): return _apply(models.AddAttackWhiteRuleRequest(), models, p)
def update_request(models, p, rule_id): return _apply(models.ModifyAttackWhiteRuleRequest(), models, p, rule_id)
def delete_request(models, p, rule_id):
    request = models.DeleteAttackWhiteRuleRequest(); request.Domain, request.Ids = p["domain"], [rule_id]; return request


def _sorted_rules(values):
    return sorted(values or [], key=lambda item: (item.get("MatchField") or "", item.get("MatchParams") or "", item.get("MatchMethod") or "", item.get("MatchContent") or ""))
def comparable(value):
    return {"Name": value.get("Name"), "Status": int(value.get("Status") or 0), "Mode": int(value.get("Mode") or 0), "SignatureIds": sorted(value.get("SignatureIds") or ([value["SignatureId"]] if value.get("SignatureId") else [])), "TypeIds": sorted(value.get("TypeIds") or ([value["TypeId"]] if value.get("TypeId") else [])), "Rules": _sorted_rules(value.get("MatchInfo") or [])}
def desired(p): return {"Name": p["name"], "Status": 1 if p["enabled"] else 0, "Mode": p["mode"], "SignatureIds": sorted(p["signature_ids"]), "TypeIds": sorted(p["type_ids"]), "Rules": _sorted_rules(p["rules"])}
def find(module, client, models, p):
    offset = 0; matches = []
    while True:
        response = module.sdk_call(client.DescribeAttackWhiteRule, describe_request(models, p, offset)); values = list(response.List or [])
        for item in values:
            value = item._serialize(allow_none=True)
            if (p.get("rule_id") is not None and int(value.get("WhiteRuleId") or 0) == p["rule_id"]) or (p.get("rule_id") is None and value.get("Name") == p.get("name")): matches.append(value)
        offset += len(values)
        if offset >= int(response.Total or 0) or not values: break
    if len(matches) > 1: module.fail_json(msg="Multiple WAF attack allow rules matched; specify rule_id")
    return matches[0] if matches else None


def run_module():
    module = TencentCloudModule(argument_spec={"state": {"choices": ["present", "absent"], "default": "present"}, "domain": {"required": True}, "rule_id": {"type": "int"}, "name": {}, "enabled": {"type": "bool", "default": True}, "mode": {"type": "int", "choices": [0, 1], "default": 0}, "signature_ids": {"type": "list", "elements": "str", "default": []}, "type_ids": {"type": "list", "elements": "str", "default": []}, "rules": {"type": "list", "elements": "dict", "default": []}}, required_one_of=[("rule_id", "name")], supports_check_mode=True)
    p = module.params
    if p["state"] == "present" and not p["name"]: module.fail_json(msg="name is required when state=present")
    if p["state"] == "present" and p["mode"] == 0 and not p["signature_ids"]: module.fail_json(msg="signature_ids is required when mode=0")
    if p["state"] == "present" and p["mode"] == 1 and not p["type_ids"]: module.fail_json(msg="type_ids is required when mode=1")
    module.require_sdk(); models, cm = _load(); client = module.create_client(cm.WafClient, "waf.tencentcloudapi.com")
    try:
        current = find(module, client, models, p)
        if p["state"] == "absent":
            if not current: module.exit_json(changed=False, rule=None)
            diff = maybe_diff(module, comparable(current), None)
            if not module.check_mode:
                response = module.sdk_call(client.DeleteAttackWhiteRule, delete_request(models, p, int(current["WhiteRuleId"])))
                if response.FailIds: module.fail_json(msg="Tencent Cloud WAF did not delete the attack allow rule", failed_rule_ids=response.FailIds)
            module.exit_json(changed=True, **(diff or {}), rule=current if module.check_mode else None)
        target = desired(p); before = comparable(current) if current else None
        if before == target: module.exit_json(changed=False, rule=current)
        diff = maybe_diff(module, before, target)
        if not module.check_mode:
            if current: module.sdk_call(client.ModifyAttackWhiteRule, update_request(models, p, int(current["WhiteRuleId"])))
            else: p["rule_id"] = int(module.sdk_call(client.AddAttackWhiteRule, create_request(models, p)).RuleId)
            current = find(module, client, models, p)
        module.exit_json(changed=True, **(diff or {}), rule=current)
    except Exception as exc: module.fail_json(**sdk_error_payload(exc))


def main(): run_module()
if __name__ == "__main__": main()
