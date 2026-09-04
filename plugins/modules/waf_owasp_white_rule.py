#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type
DOCUMENTATION = r"""
---
module: waf_owasp_white_rule
short_description: Manage Tencent Cloud WAF OWASP allowlist rules
version_added: "0.14.0"
description: Creates, updates and deletes domain-level OWASP rule or rule-type allowlists.
options:
  state: {type: str, choices: [present, absent], default: present, description: Desired state.}
  domain: {type: str, required: true, description: Protected domain.}
  rule_id: {type: int, description: Existing allowlist rule ID.}
  name: {type: str, description: Allowlist rule name.}
  allow_type: {type: int, choices: [0, 1], default: 0, description: Allow specific rule IDs or rule-type IDs.}
  owasp_ids: {type: list, elements: int, default: [], description: OWASP rule or rule-type IDs to allow.}
  strategies: {type: list, elements: dict, default: [], description: SDK-compatible Strategy match conditions.}
  logical_operator: {type: str, choices: [and, or], default: and, description: Relationship between strategies.}
  expire_time: {type: int, default: 0, description: Expiration timestamp or 0 for permanent.}
  enabled: {type: bool, default: true, description: Whether the rule is active.}
  retries: {description: Number of retries for transient failures., type: int, default: 5}
  waiter_delay: {description: Seconds between polling attempts., type: int, default: 5}
  waiter_timeout: {description: Overall polling timeout in seconds., type: int, default: 120}
  user_agent: {description: User-Agent suffix., type: str, default: ansible-collection.susunola.tencentcloud}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.waf_owasp_white_rule:
    domain: api.example.com
    name: allow-health-signatures
    owasp_ids: [100001, 100002]
    strategies:
      - {Field: URI, CompareFunc: prefix, Content: /health, Arg: ''}
"""
RETURN = r"""rule: {description: Effective OWASP allowlist rule., type: dict, returned: always}"""
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


def describe_request(models, p, offset=0):
    request = models.DescribeOwaspWhiteRulesRequest()
    request.Domain, request.Offset, request.Limit = p["domain"], offset, 100
    return request


def _apply(request, models, p):
    request.Name, request.Domain, request.Strategies = p["name"], p["domain"], _strategies(models, p["strategies"])
    request.Ids, request.Type, request.ExpireTime = sorted(p["owasp_ids"]), p["allow_type"], p["expire_time"]
    request.Status, request.LogicalOp = 1 if p["enabled"] else 0, p["logical_operator"]
    return request


def create_request(models, p):
    return _apply(models.CreateOwaspWhiteRuleRequest(), models, p)


def update_request(models, p, rule_id):
    request = _apply(models.ModifyOwaspWhiteRuleRequest(), models, p)
    request.RuleId = rule_id
    return request


def delete_request(models, p, rule_id):
    request = models.DeleteOwaspWhiteRuleRequest()
    request.Domain, request.Ids = p["domain"], [rule_id]
    return request


def _sorted(values):
    return sorted(values or [], key=lambda x: (x.get("Field") or "", x.get("Arg") or "", x.get("CompareFunc") or "", x.get("Content") or ""))


def comparable(v):
    return {
        "Name": v.get("Name"),
        "Ids": sorted(int(x) for x in (v.get("Ids") or [])),
        "Type": int(v.get("Type") or 0),
        "Strategies": _sorted(v.get("Strategies")),
        "LogicalOp": v.get("LogicalOp") or "and",
        "Status": int(v.get("Status") or 0),
    }


def desired(p):
    return {
        "Name": p["name"],
        "Ids": sorted(p["owasp_ids"]),
        "Type": p["allow_type"],
        "Strategies": _sorted(p["strategies"]),
        "LogicalOp": p["logical_operator"],
        "Status": 1 if p["enabled"] else 0,
    }


def find(module, client, models, p):
    offset = 0
    matches = []
    while True:
        response = module.sdk_call(client.DescribeOwaspWhiteRules, describe_request(models, p, offset))
        values = list(response.List or [])
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
        module.fail_json(msg="Multiple WAF OWASP allowlist rules matched; specify rule_id")
    return matches[0] if matches else None


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "state": {"choices": ["present", "absent"], "default": "present"},
            "domain": {"required": True},
            "rule_id": {"type": "int"},
            "name": {},
            "allow_type": {"type": "int", "choices": [0, 1], "default": 0},
            "owasp_ids": {"type": "list", "elements": "int", "default": []},
            "strategies": {"type": "list", "elements": "dict", "default": []},
            "logical_operator": {"choices": ["and", "or"], "default": "and"},
            "expire_time": {"type": "int", "default": 0},
            "enabled": {"type": "bool", "default": True},
        },
        required_one_of=[("rule_id", "name")],
        supports_check_mode=True,
    )
    p = module.params
    if p["state"] == "present" and (not p.get("name") or not p["owasp_ids"]):
        module.fail_json(msg="name and owasp_ids are required when state=present")
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
                module.sdk_call(client.DeleteOwaspWhiteRule, delete_request(models, p, int(current["RuleId"])))
            module.exit_json(changed=True, **(diff or {}), rule=current if module.check_mode else None)
        target = desired(p)
        before = comparable(current) if current else None
        if before == target:
            module.exit_json(changed=False, rule=current)
        diff = maybe_diff(module, before, target)
        if not module.check_mode:
            if current:
                module.sdk_call(client.ModifyOwaspWhiteRule, update_request(models, p, int(current["RuleId"])))
            else:
                p["rule_id"] = int(module.sdk_call(client.CreateOwaspWhiteRule, create_request(models, p)).RuleId)
            current = find(module, client, models, p)
        module.exit_json(changed=True, **(diff or {}), rule=current)
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
