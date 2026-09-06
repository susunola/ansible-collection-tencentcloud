#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type
DOCUMENTATION = r"""
---
module: waf_custom_white_rule
short_description: Manage Tencent Cloud WAF precision allowlist rules
version_added: "0.14.0"
description: Creates, updates, enables and deletes domain-level precision allowlist rules.
options:
  state: {type: str, choices: [present, absent], default: present, description: Desired state.}
  domain: {type: str, required: true, description: Protected domain.}
  rule_id: {type: int, description: Existing rule ID; preferred for rename and deletion.}
  name: {type: str, description: Rule name.}
  priority: {type: int, default: 100, description: Rule priority.}
  bypass_modules: {type: str, default: '', description: Comma-separated WAF modules bypassed by the rule.}
  strategies: {type: list, elements: dict, default: [], description: SDK-compatible Strategy match conditions.}
  logical_operator: {type: str, choices: [and, or], default: and, description: Relationship between strategies.}
  expire_time: {type: int, default: 0, description: Expiration timestamp or 0 for no expiration.}
  enabled: {type: bool, default: true, description: Whether the rule is active.}
  retries: {description: Number of retries for transient failures., type: int, default: 5}
  waiter_delay: {description: Seconds between polling attempts., type: int, default: 5}
  waiter_timeout: {description: Overall polling timeout in seconds., type: int, default: 120}
  user_agent: {description: User-Agent suffix., type: str, default: ansible-collection.susunola.tencentcloud}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.waf_custom_white_rule:
    domain: api.example.com
    name: allow-health-check
    bypass_modules: owasp,acl
    strategies:
      - {Field: URI, CompareFunc: prefix, Content: /health, Arg: ''}
"""
RETURN = r"""rule: {description: Effective precision allowlist rule., type: dict, returned: always}"""
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
    request = models.DescribeCustomWhiteRuleRequest()
    request.Domain, request.Offset, request.Limit = p["domain"], offset, 100
    return request


def _apply(request, models, p):
    request.Domain, request.Strategies, request.Bypass = p["domain"], _strategies(models, p["strategies"]), p["bypass_modules"]
    request.SortId, request.ExpireTime, request.LogicalOp = p["priority"], p["expire_time"], p["logical_operator"]
    return request


def create_request(models, p):
    request = _apply(models.AddCustomWhiteRuleRequest(), models, p)
    request.Name, request.SortId, request.ExpireTime = p["name"], str(p["priority"]), str(p["expire_time"])
    return request


def update_request(models, p, rule_id):
    request = _apply(models.ModifyCustomWhiteRuleRequest(), models, p)
    request.RuleId, request.RuleName = rule_id, p["name"]
    return request


def status_request(models, p, rule_id):
    request = models.ModifyCustomWhiteRuleStatusRequest()
    request.Domain, request.RuleId, request.Status = p["domain"], rule_id, 1 if p["enabled"] else 0
    return request


def delete_request(models, p, rule_id):
    request = models.DeleteCustomWhiteRuleRequest()
    request.Domain, request.RuleId = p["domain"], rule_id
    return request


def _sorted(values):
    return sorted(values or [], key=lambda x: (x.get("Field") or "", x.get("Arg") or "", x.get("CompareFunc") or "", x.get("Content") or ""))


def comparable(value):
    return {
        "Name": value.get("Name"),
        "SortId": int(value.get("SortId") or 0),
        "Bypass": value.get("Bypass") or "",
        "Strategies": _sorted(value.get("Strategies")),
        "LogicalOp": value.get("LogicalOp") or "and",
        "ExpireTime": int(value.get("ExpireTime") or 0),
        "Status": int(value.get("Status") or 0),
    }


def desired(p):
    return {
        "Name": p["name"],
        "SortId": p["priority"],
        "Bypass": p["bypass_modules"],
        "Strategies": _sorted(p["strategies"]),
        "LogicalOp": p["logical_operator"],
        "ExpireTime": p["expire_time"],
        "Status": 1 if p["enabled"] else 0,
    }


def find(module, client, models, p):
    offset = 0
    matches = []
    while True:
        response = module.sdk_call(client.DescribeCustomWhiteRule, describe_request(models, p, offset))
        values = list(response.RuleList or [])
        for item in values:
            value = item._serialize(allow_none=True)
            if (p.get("rule_id") is not None and int(value.get("RuleId") or 0) == p["rule_id"]) or (
                p.get("rule_id") is None and value.get("Name") == p.get("name")
            ):
                matches.append(value)
        offset += len(values)
        if offset >= int(response.TotalCount or 0) or not values:
            break
    if len(matches) > 1:
        module.fail_json(msg="Multiple WAF precision allowlist rules matched; specify rule_id")
    return matches[0] if matches else None


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "state": {"choices": ["present", "absent"], "default": "present"},
            "domain": {"required": True},
            "rule_id": {"type": "int"},
            "name": {},
            "priority": {"type": "int", "default": 100},
            "bypass_modules": {"default": "", "no_log": False},
            "strategies": {"type": "list", "elements": "dict", "default": []},
            "logical_operator": {"choices": ["and", "or"], "default": "and"},
            "expire_time": {"type": "int", "default": 0},
            "enabled": {"type": "bool", "default": True},
        },
        required_one_of=[("rule_id", "name")],
        supports_check_mode=True,
    )
    p = module.params
    if p["state"] == "present" and not p.get("name"):
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
                module.sdk_call(client.DeleteCustomWhiteRule, delete_request(models, p, int(current["RuleId"])))
            module.exit_json(changed=True, **(diff or {}), rule=current if module.check_mode else None)
        target = desired(p)
        before = comparable(current) if current else None
        if before == target:
            module.exit_json(changed=False, rule=current)
        diff = maybe_diff(module, before, target)
        if not module.check_mode:
            if current:
                rule_id = int(current["RuleId"])
                module.sdk_call(client.ModifyCustomWhiteRule, update_request(models, p, rule_id))
            else:
                rule_id = int(module.sdk_call(client.AddCustomWhiteRule, create_request(models, p)).RuleId)
                p["rule_id"] = rule_id
            module.sdk_call(client.ModifyCustomWhiteRuleStatus, status_request(models, p, rule_id))
            current = find(module, client, models, p)
        module.exit_json(changed=True, **(diff or {}), rule=current)
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
