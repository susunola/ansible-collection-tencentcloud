#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type
DOCUMENTATION = r"""
---
module: waf_custom_rule
short_description: Manage Tencent Cloud WAF custom rules
version_added: "0.14.0"
description: Creates, updates and deletes a domain-level WAF custom rule.
options:
  state: {type: str, choices: [present, absent], default: present, description: Desired state.}
  domain: {type: str, required: true, description: Protected domain.}
  rule_id: {type: int, description: Existing rule ID.}
  name: {type: str, description: Rule name.}
  edition: {type: str, choices: [sparta-waf, clb-waf], default: sparta-waf, description: WAF edition.}
  priority: {type: int, default: 100, description: Evaluation priority from 1 to 100.}
  action: {type: str, choices: ['1', '2', '3', '4', '5'], default: '1', description: WAF action code.}
  strategies: {type: list, elements: dict, default: [], description: SDK-compatible match strategies.}
  logical_operator: {type: str, choices: [and, or], default: and, description: Relationship between strategies.}
  redirect: {type: str, default: '', description: Redirect URL for redirect actions.}
  expire_time: {type: int, default: 0, description: Unix expiration time; zero means permanent.}
  action_ratio: {type: int, default: 100, description: Percentage of matched requests receiving the action.}
  retries: {description: Number of retries for transient failures., type: int, default: 5}
  waiter_delay: {description: Seconds between polling attempts., type: int, default: 5}
  waiter_timeout: {description: Overall polling timeout in seconds., type: int, default: 120}
  user_agent: {description: User-Agent suffix., type: str, default: ansible-collection.susunola.tencentcloud}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.waf_custom_rule:
    domain: api.example.com
    name: block-admin
    action: '1'
    strategies:
      - {Field: URI, CompareFunc: contains, Content: /admin, CaseNotSensitive: 1}
"""
RETURN = r"""rule: {description: WAF custom-rule metadata., type: dict, returned: always}"""
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


def _load():
    from tencentcloud.waf.v20180125 import models, waf_client

    return models, waf_client


def _strategies(models, values):
    result = []
    for value in values:
        item = models.Strategy()
        item._deserialize(value)
        result.append(item)
    return result


def build_list(models, p):
    request = models.DescribeCustomRuleListRequest()
    request.Domain, request.Offset, request.Limit = p["domain"], 0, 100
    return request


def build_create(models, p):
    request = models.AddCustomRuleRequest()
    request.Name, request.SortId, request.Domain = p["name"], str(p["priority"]), p["domain"]
    request.Strategies, request.ActionType, request.Redirect = _strategies(models, p["strategies"]), p["action"], p["redirect"]
    request.ExpireTime, request.Edition, request.LogicalOp, request.ActionRatio = str(p["expire_time"]), p["edition"], p["logical_operator"], p["action_ratio"]
    return request


def build_update(models, p, rule_id):
    request = models.ModifyCustomRuleRequest()
    request.Domain, request.RuleId, request.RuleName = p["domain"], rule_id, p["name"]
    request.RuleAction, request.Strategies, request.Edition, request.Redirect = p["action"], _strategies(models, p["strategies"]), p["edition"], p["redirect"]
    request.SortId, request.ExpireTime, request.LogicalOp, request.ActionRatio = p["priority"], p["expire_time"], p["logical_operator"], p["action_ratio"]
    return request


def build_delete(models, p, rule_id):
    request = models.DeleteCustomRuleRequest()
    request.Domain, request.RuleId, request.Edition = p["domain"], str(rule_id), p["edition"]
    return request


def find(module, client, models, p):
    response = module.sdk_call(client.DescribeCustomRuleList, build_list(models, p))
    matches = []
    for item in list(response.RuleList or []):
        value = item._serialize(allow_none=True)
        if (p.get("rule_id") is not None and int(value.get("RuleId") or 0) == p["rule_id"]) or (
            p.get("rule_id") is None and value.get("Name") == p.get("name")
        ):
            matches.append(value)
    if len(matches) > 1:
        module.fail_json(msg="Multiple WAF custom rules have the requested name", name=p.get("name"))
    return matches[0] if matches else None


def desired(p):
    return {
        "Name": p["name"],
        "SortId": p["priority"],
        "ActionType": p["action"],
        "Strategies": p["strategies"],
        "Redirect": p["redirect"],
        "ExpireTime": p["expire_time"],
        "LogicalOp": p["logical_operator"],
        "ActionRatio": p["action_ratio"],
    }


def comparable(v):
    return {
        "Name": v.get("Name"),
        "SortId": int(v.get("SortId") or 0),
        "ActionType": str(v.get("ActionType")),
        "Strategies": v.get("Strategies") or [],
        "Redirect": v.get("Redirect") or "",
        "ExpireTime": int(v.get("ExpireTime") or 0),
        "LogicalOp": v.get("LogicalOp") or "and",
        "ActionRatio": int(v.get("ActionRatio") or 100),
    }


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "state": {"choices": ["present", "absent"], "default": "present"},
            "domain": {"required": True},
            "rule_id": {"type": "int"},
            "name": {},
            "edition": {"choices": ["sparta-waf", "clb-waf"], "default": "sparta-waf"},
            "priority": {"type": "int", "default": 100},
            "action": {"choices": ["1", "2", "3", "4", "5"], "default": "1"},
            "strategies": {"type": "list", "elements": "dict", "default": []},
            "logical_operator": {"choices": ["and", "or"], "default": "and"},
            "redirect": {"default": ""},
            "expire_time": {"type": "int", "default": 0},
            "action_ratio": {"type": "int", "default": 100},
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
            diff = maybe_diff(module, current, None)
            if not module.check_mode:
                module.sdk_call(client.DeleteCustomRule, build_delete(models, p, int(current["RuleId"])))
            module.exit_json(changed=True, **(diff or {}), rule=current if module.check_mode else None)
        target = desired(p)
        before = comparable(current) if current else None
        if before == target:
            module.exit_json(changed=False, rule=current)
        diff = maybe_diff(module, before, target)
        if not module.check_mode:
            if current:
                module.sdk_call(client.ModifyCustomRule, build_update(models, p, int(current["RuleId"])))
            else:
                p["rule_id"] = int(module.sdk_call(client.AddCustomRule, build_create(models, p)).RuleId)
            current = find(module, client, models, p)
        module.exit_json(changed=True, **(diff or {}), rule=current)
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
