#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type
DOCUMENTATION = r"""
---
module: eb_rule
short_description: Manage Tencent Cloud EventBridge rules
version_added: "0.14.0"
description: Creates, updates and deletes EventBridge event-routing rules.
options:
  state: {type: str, choices: [present, absent], default: present, description: Desired state.}
  event_bus_id: {type: str, required: true, description: Event bus ID.}
  rule_id: {type: str, description: Existing rule ID.}
  name: {type: str, description: Rule name.}
  event_pattern: {type: str, description: Event pattern JSON string.}
  enabled: {type: bool, default: true, description: Enable the rule.}
  description: {type: str, default: '', description: Rule description.}
  retries: {type: int, default: 5, description: Number of retries for transient failures.}
  waiter_delay: {type: int, default: 5, description: Seconds between polling attempts.}
  waiter_timeout: {type: int, default: 120, description: Overall polling timeout in seconds.}
  user_agent: {type: str, default: ansible-collection.susunola.tencentcloud, description: User-Agent suffix.}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.eb_rule:
    event_bus_id: eb-l8q2xxxx
    name: order-created
    event_pattern: '{"source":["orders"]}'
"""
RETURN = r"""rule: {description: Effective EventBridge rule metadata., type: dict, returned: always}"""
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


def _load():
    from tencentcloud.eb.v20210416 import models, eb_client

    return models, eb_client


def list_request(models, p):
    r = models.ListRulesRequest()
    r.EventBusId, r.Offset, r.Limit = p["event_bus_id"], 0, 100
    return r


def get_request(models, p, rule_id):
    r = models.GetRuleRequest()
    r.EventBusId, r.RuleId = p["event_bus_id"], rule_id
    return r


def create_request(models, p):
    r = models.CreateRuleRequest()
    r.EventBusId, r.RuleName, r.EventPattern = p["event_bus_id"], p["name"], p["event_pattern"]
    r.Enable, r.Description = p["enabled"], p["description"]
    return r


def update_request(models, p, rule_id):
    r = models.UpdateRuleRequest()
    r.EventBusId, r.RuleId, r.RuleName = p["event_bus_id"], rule_id, p.get("name")
    r.EventPattern, r.Enable, r.Description = p.get("event_pattern"), p["enabled"], p["description"]
    return r


def delete_request(models, p, rule_id):
    r = models.DeleteRuleRequest()
    r.EventBusId, r.RuleId = p["event_bus_id"], rule_id
    return r


def find(module, client, models, p):
    response = module.sdk_call(client.ListRules, list_request(models, p))
    matches = []
    for item in response.Rules or []:
        value = item._serialize(allow_none=True)
        if (p.get("rule_id") and value.get("RuleId") == p["rule_id"]) or (not p.get("rule_id") and value.get("RuleName") == p.get("name")):
            matches.append(value)
    if len(matches) > 1:
        module.fail_json(msg="Multiple rules matched; specify rule_id")
    if not matches:
        return None
    value = module.sdk_call(client.GetRule, get_request(models, p, matches[0]["RuleId"]))._serialize(allow_none=True)
    value.pop("RequestId", None)
    return value


def run_module():
    spec = {
        "state": {"choices": ["present", "absent"], "default": "present"},
        "event_bus_id": {"required": True},
        "rule_id": {},
        "name": {},
        "event_pattern": {},
        "enabled": {"type": "bool", "default": True},
        "description": {"default": ""},
    }
    module = TencentCloudModule(argument_spec=spec, required_one_of=[("rule_id", "name")], supports_check_mode=True)
    p = module.params
    module.require_sdk()
    models, cm = _load()
    client = module.create_client(cm.EbClient, "eb.tencentcloudapi.com")
    try:
        current = find(module, client, models, p)
        if p["state"] == "absent":
            if not current:
                module.exit_json(changed=False, rule=None)
            diff = maybe_diff(module, current, None)
            if not module.check_mode:
                module.sdk_call(client.DeleteRule, delete_request(models, p, current["RuleId"]))
            module.exit_json(changed=True, **(diff or {}), rule=None)
        if not current:
            missing = [k for k in ("name", "event_pattern") if not p.get(k)]
            if missing:
                module.fail_json(msg="creation parameters are required for a new EventBridge rule", missing=missing)
            target = {"RuleName": p["name"], "EventPattern": p["event_pattern"], "Enable": p["enabled"], "Description": p["description"]}
            diff = maybe_diff(module, None, target)
            if not module.check_mode:
                p["rule_id"] = module.sdk_call(client.CreateRule, create_request(models, p)).RuleId
                current = find(module, client, models, p)
            module.exit_json(changed=True, **(diff or {}), rule=current if not module.check_mode else target)
        before = {
            "RuleName": current.get("RuleName"),
            "EventPattern": current.get("EventPattern"),
            "Enable": current.get("Enable"),
            "Description": current.get("Description") or "",
        }
        target = {
            "RuleName": p.get("name") or before["RuleName"],
            "EventPattern": p.get("event_pattern") or before["EventPattern"],
            "Enable": p["enabled"],
            "Description": p["description"],
        }
        if before == target:
            module.exit_json(changed=False, rule=current)
        diff = maybe_diff(module, before, target)
        if not module.check_mode:
            module.sdk_call(client.UpdateRule, update_request(models, p, current["RuleId"]))
            p["rule_id"] = current["RuleId"]
            current = find(module, client, models, p)
        module.exit_json(changed=True, **(diff or {}), rule=current)
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
