#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
---
module: config_rule
short_description: Manage Tencent Cloud Config compliance rules
version_added: "0.14.0"
description: Creates, updates and deletes managed or custom compliance rules.
options:
  state: {description: Desired state., type: str, choices: [present, absent], default: present}
  rule_id: {description: Existing Config rule ID., type: str}
  name: {description: Config rule name., type: str}
  identifier: {description: Managed rule identifier or custom SCF region and function name., type: str}
  identifier_type: {description: Rule template type., type: str, choices: [SYSTEM, CUSTOMIZE], default: SYSTEM}
  resource_types: {description: Exact resource type scope., type: list, elements: str}
  triggers:
    description: Exact trigger configuration list.
    type: list
    elements: dict
    default: [{message_type: ConfigurationItemChangeNotification}]
    suboptions:
      message_type: {description: Trigger type., type: str, choices: [ScheduledNotification, ConfigurationItemChangeNotification], required: true}
      maximum_execution_frequency: {description: Scheduled evaluation frequency., type: str}
  risk_level: {description: Risk level where 1 is high and 3 is low., type: int, choices: [1, 2, 3], default: 2}
  input_parameters: {description: Rule input parameter values keyed by parameter name., type: dict, default: {}}
  description: {description: Rule description., type: str, default: ''}
  regions: {description: Exact evaluated region scope., type: list, elements: str, default: []}
  tags: {description: Exact evaluated tag scope., type: dict, default: {}}
  excluded_resource_ids: {description: Exact resource exclusion list., type: list, elements: str, default: []}
  waiter_delay: {description: Seconds between polling attempts., type: int, default: 5}
  waiter_timeout: {description: Overall polling timeout in seconds., type: int, default: 120}
  retries: {description: Number of retries for transient failures., type: int, default: 5}
  user_agent: {description: User-Agent suffix., type: str, default: ansible-collection.susunola.tencentcloud}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''
EXAMPLES = r'''
- susunola.tencentcloud.config_rule:
    name: require-encrypted-disks
    identifier: CBS_DISK_ENCRYPTED
    identifier_type: SYSTEM
    resource_types: [QCS::CBS::Disk]
    risk_level: 1
    regions: [ap-guangzhou, ap-shanghai]
'''
RETURN = r'''
rule: {description: Config compliance rule metadata., type: dict, returned: always}
'''

import time

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff


def _load_config():
    from tencentcloud.config.v20220802 import config_client, models
    return models, config_client


def build_list_request(models, name=None, offset=0):
    request = models.ListConfigRulesRequest()
    request.Offset, request.Limit = offset, 200
    if name:
        request.RuleName = name
    return request


def build_describe_request(models, rule_id):
    request = models.DescribeConfigRuleRequest()
    request.RuleId = rule_id
    return request


def build_triggers(models, values):
    result = []
    for value in values or []:
        item = models.TriggerType()
        item.MessageType = value["message_type"]
        if value.get("maximum_execution_frequency"):
            item.MaximumExecutionFrequency = value["maximum_execution_frequency"]
        result.append(item)
    return result


def build_parameters(models, values):
    result = []
    for key, value in sorted((values or {}).items()):
        item = models.InputParameter()
        item.ParameterKey, item.Type, item.Value = str(key), "Optional", str(value)
        result.append(item)
    return result


def build_tags(models, values):
    result = []
    for key, value in sorted((values or {}).items()):
        item = models.Tag()
        item.TagKey, item.TagValue = str(key), str(value)
        result.append(item)
    return result


def _apply(request, models, params):
    request.RuleName, request.RiskLevel = params["name"], params["risk_level"]
    request.TriggerType = build_triggers(models, params["triggers"])
    request.InputParameter = build_parameters(models, params["input_parameters"])
    request.Description = params["description"]
    request.RegionsScope = sorted(set(params["regions"]))
    request.TagsScope = build_tags(models, params["tags"])
    request.ExcludeResourceIdsScope = sorted(set(params["excluded_resource_ids"]))
    return request


def build_create_request(models, params):
    request = _apply(models.AddConfigRuleRequest(), models, params)
    request.Identifier, request.IdentifierType = params["identifier"], params["identifier_type"]
    request.ResourceType = sorted(set(params["resource_types"]))
    return request


def build_update_request(models, rule_id, params):
    request = _apply(models.UpdateConfigRuleRequest(), models, params)
    request.RuleId = rule_id
    return request


def build_delete_request(models, rule_id):
    request = models.DeleteConfigRuleRequest()
    request.RuleId = rule_id
    return request


def find_rule(module, client, models, rule_id=None, name=None):
    if rule_id:
        response = module.sdk_call(client.DescribeConfigRule, build_describe_request(models, rule_id))
        return response.ConfigRule._serialize(allow_none=True) if response.ConfigRule else None
    offset, matches = 0, []
    while True:
        response = module.sdk_call(client.ListConfigRules, build_list_request(models, name, offset))
        items = list(response.Items or [])
        matches.extend(item for item in items if item.RuleName == name)
        offset += len(items)
        if not items or offset >= int(response.Total or 0):
            break
    if len(matches) > 1:
        module.fail_json(msg="Multiple Config rules have the requested name", name=name)
    if not matches:
        return None
    response = module.sdk_call(client.DescribeConfigRule, build_describe_request(models, matches[0].ConfigRuleId))
    return response.ConfigRule._serialize(allow_none=True) if response.ConfigRule else None


def _canon_triggers(values):
    return sorted(({"MessageType": x.get("MessageType"), "MaximumExecutionFrequency": x.get("MaximumExecutionFrequency")} for x in (values or [])), key=lambda x: (x["MessageType"] or "", x["MaximumExecutionFrequency"] or ""))


def _desired(params):
    triggers = [{"MessageType": x["message_type"], "MaximumExecutionFrequency": x.get("maximum_execution_frequency")} for x in params["triggers"]]
    inputs = [{"ParameterKey": str(k), "Type": "Optional", "Value": str(v)} for k, v in sorted(params["input_parameters"].items())]
    tags = [{"TagKey": str(k), "TagValue": str(v)} for k, v in sorted(params["tags"].items())]
    return {"Identifier": params["identifier"], "IdentifierType": params["identifier_type"], "RuleName": params["name"], "ResourceType": sorted(set(params["resource_types"])), "TriggerType": _canon_triggers(triggers), "RiskLevel": params["risk_level"], "InputParameter": inputs, "Description": params["description"], "RegionsScope": sorted(set(params["regions"])), "TagsScope": tags, "ExcludeResourceIdsScope": sorted(set(params["excluded_resource_ids"]))}


def _matches(current, desired):
    for key, value in desired.items():
        actual = current.get(key)
        if key == "TriggerType":
            actual = _canon_triggers(actual)
        elif key in ("ResourceType", "RegionsScope", "ExcludeResourceIdsScope"):
            actual = sorted(set(actual or []))
        elif key == "InputParameter":
            actual = sorted(({k: x.get(k) for k in ("ParameterKey", "Type", "Value")} for x in (actual or [])), key=lambda x: x["ParameterKey"] or "")
        elif key == "TagsScope":
            actual = sorted(({k: x.get(k) for k in ("TagKey", "TagValue")} for x in (actual or [])), key=lambda x: x["TagKey"] or "")
        if actual != value:
            return False
    return True


def wait_for_rule(module, client, models, rule_id, desired=None, absent=False):
    deadline = time.time() + module.params["waiter_timeout"]
    while True:
        current = find_rule(module, client, models, rule_id, None)
        if absent and current is None:
            return None
        if not absent and current and _matches(current, desired):
            return current
        if time.time() >= deadline:
            module.fail_json(msg="Timed out waiting for Config rule convergence", rule=current)
        time.sleep(module.params["waiter_delay"])


def run_module():
    module = TencentCloudModule(argument_spec={"state": {"type": "str", "choices": ["present", "absent"], "default": "present"}, "rule_id": {"type": "str"}, "name": {"type": "str"}, "identifier": {"type": "str"}, "identifier_type": {"type": "str", "choices": ["SYSTEM", "CUSTOMIZE"], "default": "SYSTEM"}, "resource_types": {"type": "list", "elements": "str"}, "triggers": {"type": "list", "elements": "dict", "default": [{"message_type": "ConfigurationItemChangeNotification"}], "options": {"message_type": {"type": "str", "choices": ["ScheduledNotification", "ConfigurationItemChangeNotification"], "required": True}, "maximum_execution_frequency": {"type": "str"}}}, "risk_level": {"type": "int", "choices": [1, 2, 3], "default": 2}, "input_parameters": {"type": "dict", "default": {}}, "description": {"type": "str", "default": ""}, "regions": {"type": "list", "elements": "str", "default": []}, "tags": {"type": "dict", "default": {}}, "excluded_resource_ids": {"type": "list", "elements": "str", "default": []}}, required_one_of=[("rule_id", "name")], required_if=[("state", "present", ("name", "identifier", "resource_types"))], supports_check_mode=True)
    p = module.params
    module.require_sdk()
    models, client_module = _load_config()
    client = module.create_client(client_module.ConfigClient, "config.tencentcloudapi.com")
    try:
        current = find_rule(module, client, models, p["rule_id"], p["name"])
        if p["state"] == "absent":
            if current is None:
                module.exit_json(changed=False, rule=None, msg="Config rule is absent")
            diff = maybe_diff(module, current, None)
            if module.check_mode:
                module.exit_json(changed=True, **(diff or {}), rule=current, msg="Would delete Config rule")
            module.sdk_call(client.DeleteConfigRule, build_delete_request(models, current["ConfigRuleId"]))
            wait_for_rule(module, client, models, current["ConfigRuleId"], absent=True)
            module.exit_json(changed=True, **(diff or {}), rule=None, msg="Config rule deleted")
        desired = _desired(p)
        if current is None:
            diff = maybe_diff(module, None, desired)
            if module.check_mode:
                module.exit_json(changed=True, **(diff or {}), rule=None, msg="Would create Config rule")
            response = module.sdk_call(client.AddConfigRule, build_create_request(models, p))
            current = wait_for_rule(module, client, models, response.RuleId, desired)
            module.exit_json(changed=True, **(diff or {}), rule=current, msg="Config rule created")
        for field in ("Identifier", "IdentifierType", "ResourceType"):
            if not _matches({field: current.get(field)}, {field: desired[field]}):
                module.fail_json(msg="Config rule template and resource types cannot be changed; recreate the rule", field=field)
        if _matches(current, desired):
            module.exit_json(changed=False, rule=current, msg="Config rule is up to date")
        diff = maybe_diff(module, current, desired)
        if module.check_mode:
            module.exit_json(changed=True, **(diff or {}), rule=current, msg="Would update Config rule")
        module.sdk_call(client.UpdateConfigRule, build_update_request(models, current["ConfigRuleId"], p))
        current = wait_for_rule(module, client, models, current["ConfigRuleId"], desired)
        module.exit_json(changed=True, **(diff or {}), rule=current, msg="Config rule updated")
    except Exception as exc:
        module.fail_json(msg="Tencent Cloud API request failed", error=str(exc), error_code=getattr(exc, "get_code", lambda: None)(), request_id=getattr(exc, "get_request_id", lambda: None)())


def main():
    run_module()


if __name__ == "__main__":
    main()
