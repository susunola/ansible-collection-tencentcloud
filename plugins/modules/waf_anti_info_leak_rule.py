#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type
DOCUMENTATION = r"""
---
module: waf_anti_info_leak_rule
short_description: Manage Tencent Cloud WAF sensitive-information leakage rules
version_added: "0.14.0"
description: Creates, updates and deletes response-data leakage protection rules for a protected domain.
options:
  state: {type: str, choices: [present, absent], default: present, description: Desired state.}
  domain: {type: str, required: true, description: Protected domain.}
  rule_id: {type: int, description: Existing rule ID; preferred for rename and deletion.}
  name: {type: str, description: Rule name.}
  action: {type: int, choices: [0, 1, 2, 3, 4], default: 0, description: "Action code for alert, replacement, partial display or blocking."}
  strategies: {type: list, elements: dict, default: [], description: SDK-compatible response match strategies.}
  uri: {type: str, default: '/', description: URL match expression; immutable after creation.}
  enabled: {type: bool, default: true, description: Whether the rule is enabled.}
  force_replace: {type: bool, default: false, description: Delete and recreate when immutable URI changes.}
  retries: {description: Number of retries for transient failures., type: int, default: 5}
  waiter_delay: {description: Seconds between polling attempts., type: int, default: 5}
  waiter_timeout: {description: Overall polling timeout in seconds., type: int, default: 120}
  user_agent: {description: User-Agent suffix., type: str, default: ansible-collection.susunola.tencentcloud}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.waf_anti_info_leak_rule:
    domain: api.example.com
    name: mask-phone-numbers
    action: 1
    uri: /customers
    strategies:
      - {Field: information, CompareFunc: contains, Content: phone}
"""
RETURN = r"""rule: {description: WAF leakage-protection rule metadata., type: dict, returned: always}"""
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


def _load():
    from tencentcloud.waf.v20180125 import models, waf_client

    return models, waf_client


def _strategies(models, values):
    result = []
    for value in values:
        item = models.StrategyForAntiInfoLeak()
        item._deserialize(value)
        result.append(item)
    return result


def describe_request(models, p, offset=0):
    request = models.DescribeAntiInfoLeakageRulesRequest()
    request.Domain, request.Offset, request.Limit = p["domain"], offset, 100
    return request


def create_request(models, p):
    request = models.AddAntiInfoLeakRulesRequest()
    request.Domain, request.Name, request.ActionType, request.Strategies, request.Uri = (
        p["domain"],
        p["name"],
        p["action"],
        _strategies(models, p["strategies"]),
        p["uri"],
    )
    return request


def update_request(models, p, rule_id):
    request = models.ModifyAntiInfoLeakRulesRequest()
    request.RuleId, request.Name, request.Domain, request.ActionType, request.Strategies = (
        rule_id,
        p["name"],
        p["domain"],
        p["action"],
        _strategies(models, p["strategies"]),
    )
    return request


def status_request(models, p, rule_id):
    request = models.ModifyAntiInfoLeakRuleStatusRequest()
    request.Domain, request.RuleId, request.Status = p["domain"], rule_id, 1 if p["enabled"] else 0
    return request


def delete_request(models, p, rule_id):
    request = models.DeleteAntiInfoLeakRuleRequest()
    request.Domain, request.RuleId = p["domain"], rule_id
    return request


def find(module, client, models, p):
    offset = 0
    matches = []
    while True:
        response = module.sdk_call(client.DescribeAntiInfoLeakageRules, describe_request(models, p, offset))
        values = list(response.RuleList or [])
        for item in values:
            value = item._serialize(allow_none=True)
            if (p.get("rule_id") is not None and int(value.get("RuleId") or 0) == p["rule_id"]) or (
                p.get("rule_id") is None and value.get("Name") == p.get("name")
            ):
                matches.append(value)
        offset += len(values)
        if offset >= int(response.Total or 0) or not values:
            break
    if len(matches) > 1:
        module.fail_json(msg="Multiple WAF anti-information-leak rules matched; specify rule_id")
    return matches[0] if matches else None


def desired(p):
    return {"Name": p["name"], "Action": str(p["action"]), "Strategies": p["strategies"], "Uri": p["uri"], "Status": 1 if p["enabled"] else 0}


def comparable(value):
    return {
        "Name": value.get("Name"),
        "Action": str(value.get("Action")),
        "Strategies": value.get("Strategies") or [],
        "Uri": value.get("Uri") or "/",
        "Status": int(value.get("Status") or 0),
    }


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "state": {"choices": ["present", "absent"], "default": "present"},
            "domain": {"required": True},
            "rule_id": {"type": "int"},
            "name": {},
            "action": {"type": "int", "choices": [0, 1, 2, 3, 4], "default": 0},
            "strategies": {"type": "list", "elements": "dict", "default": []},
            "uri": {"default": "/"},
            "enabled": {"type": "bool", "default": True},
            "force_replace": {"type": "bool", "default": False},
        },
        required_one_of=[("rule_id", "name")],
        supports_check_mode=True,
    )
    p = module.params
    if p["state"] == "present" and not p["name"]:
        module.fail_json(msg="name is required when state=present")
    module.require_sdk()
    models, cm = _load()
    client = module.create_client(cm.WafClient, "waf.tencentcloudapi.com")
    try:
        current = find(module, client, models, p)
        if p["state"] == "absent":
            if not current:
                module.exit_json(changed=False, rule=None)
            diff = maybe_diff(module, comparable(current), None)
            if not module.check_mode:
                module.sdk_call(client.DeleteAntiInfoLeakRule, delete_request(models, p, int(current["RuleId"])))
            module.exit_json(changed=True, **(diff or {}), rule=current if module.check_mode else None)
        target = desired(p)
        before = comparable(current) if current else None
        replace = bool(current and before["Uri"] != target["Uri"])
        if replace and not p["force_replace"]:
            module.fail_json(msg="uri is immutable; set force_replace=true to recreate the rule", current_uri=before["Uri"], desired_uri=target["Uri"])
        if before == target:
            module.exit_json(changed=False, rule=current)
        diff = maybe_diff(module, before, target)
        if not module.check_mode:
            if replace:
                module.sdk_call(client.DeleteAntiInfoLeakRule, delete_request(models, p, int(current["RuleId"])))
                current = None
            if current:
                rule_id = int(current["RuleId"])
                module.sdk_call(client.ModifyAntiInfoLeakRules, update_request(models, p, rule_id))
            else:
                rule_id = int(module.sdk_call(client.AddAntiInfoLeakRules, create_request(models, p)).RuleId)
                p["rule_id"] = rule_id
            module.sdk_call(client.ModifyAntiInfoLeakRuleStatus, status_request(models, p, rule_id))
            current = find(module, client, models, p)
        module.exit_json(changed=True, **(diff or {}), rule=current)
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
