#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r"""
---
module: tsf_lane_rule
short_description: Manage a Tencent Cloud TSF traffic lane rule
version_added: "0.15.0"
description: Creates, updates, enables, disables and deletes a fully observable TSF traffic lane rule.
options:
  state: {type: str, choices: [present, absent], default: present, description: Desired resource state.}
  rule_id: {type: str, description: Existing rule ID; exact lane-scoped name is used when omitted.}
  name: {type: str, required: true, description: Rule name.}
  lane_id: {type: str, required: true, description: Owning traffic lane ID.}
  remark: {type: str, description: Rule remark.}
  enabled: {type: bool, default: true, description: Whether the rule is enabled.}
  tag_relationship: {type: str, choices: [RELEATION_AND, RELEATION_OR], default: RELEATION_AND, description: Relationship between tags, using TSF API values.}
  tags:
    type: list
    elements: dict
    description: Exact request tag conditions; required when creating.
    suboptions:
      name: {type: str, required: true, description: Request tag name.}
      operator: {type: str, required: true, description: TSF tag matching operator.}
      value: {type: str, required: true, description: Match value.}
extends_documentation_fragment:
  - susunola.tencentcloud.credentials
  - susunola.tencentcloud.region
  - susunola.tencentcloud.connection
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.tsf_lane_rule:
    name: checkout-canary-header
    lane_id: lane-xxxxxxxx
    tags:
      - {name: x-canary, operator: EQUAL, value: 'true'}
"""
RETURN = r"""lane_rule: {description: Effective TSF lane rule metadata., type: dict, returned: always}"""

import json
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


def _load():
    from tencentcloud.tsf.v20180326 import models, tsf_client

    return models, tsf_client


def normalize_tags(values):
    result = [{key: value.get(key) for key in ("TagName", "TagOperator", "TagValue")} for value in (values or [])]
    return sorted(result, key=lambda item: (item["TagName"], item["TagOperator"], item["TagValue"]))


def desired(params):
    target = {"RuleName": params["name"], "LaneId": params["lane_id"], "Enable": params["enabled"], "RuleTagRelationship": params["tag_relationship"]}
    if params.get("remark") is not None:
        target["Remark"] = params["remark"]
    if params.get("tags") is not None:
        target["RuleTagList"] = normalize_tags(
            [{"TagName": item["name"], "TagOperator": item["operator"], "TagValue": item["value"]} for item in params["tags"]]
        )
    return target


def comparable(current, target):
    result = {key: current.get(key) for key in target}
    if "RuleTagList" in result:
        result["RuleTagList"] = normalize_tags(result["RuleTagList"])
    return result


def find(module, client, models, params):
    request = models.DescribeLaneRulesRequest()
    request.Offset, request.Limit = 0, 500
    if params.get("rule_id"):
        request.RuleId = params["rule_id"]
    else:
        request.SearchWord = params["name"]
    result = module.sdk_call(client.DescribeLaneRules, request).Result
    values = (result.Content if result else None) or []
    matches = (
        [item for item in values if item.RuleId == params.get("rule_id")]
        if params.get("rule_id")
        else [item for item in values if item.RuleName == params["name"] and item.LaneId == params["lane_id"]]
    )
    if len(matches) > 1:
        module.fail_json(msg="Multiple TSF lane rules matched", name=params["name"], lane_id=params["lane_id"])
    return matches[0]._serialize(allow_none=True) if matches else None


def tag_models(models, tags):
    result = []
    for tag in tags or []:
        payload = {
            "TagName": tag.get("name", tag.get("TagName")),
            "TagOperator": tag.get("operator", tag.get("TagOperator")),
            "TagValue": tag.get("value", tag.get("TagValue")),
        }
        item = models.LaneRuleTag()
        item.from_json_string(json.dumps(payload))
        result.append(item)
    return result


def set_result(module, response, action):
    if response.Result is False:
        module.fail_json(msg="Tencent Cloud rejected the TSF lane rule %s" % action, request_id=response.RequestId)


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "state": {"choices": ["present", "absent"], "default": "present"},
            "rule_id": {},
            "name": {"required": True},
            "lane_id": {"required": True},
            "remark": {},
            "enabled": {"type": "bool", "default": True},
            "tag_relationship": {"choices": ["RELEATION_AND", "RELEATION_OR"], "default": "RELEATION_AND"},
            "tags": {"type": "list", "elements": "dict", "options": {"name": {"required": True}, "operator": {"required": True}, "value": {"required": True}}},
        },
        supports_check_mode=True,
    )
    params = module.params
    module.require_sdk()
    models, client_module = _load()
    client = module.create_client(client_module.TsfClient, "tsf.tencentcloudapi.com")
    try:
        current = find(module, client, models, params)
        if params["state"] == "absent":
            if not current:
                module.exit_json(changed=False, lane_rule=None)
            diff = maybe_diff(module, current, None)
            if not module.check_mode:
                request = models.DeleteLaneRuleRequest()
                request.RuleId = current["RuleId"]
                set_result(module, module.sdk_call(client.DeleteLaneRule, request), "deletion")
            module.exit_json(changed=True, **(diff or {}), lane_rule=None)
        target = desired(params)
        if not current and params.get("tags") is None:
            module.fail_json(msg="tags is required when creating a TSF lane rule")
        if current and comparable(current, target) == target:
            module.exit_json(changed=False, lane_rule=current)
        diff = maybe_diff(module, comparable(current, target) if current else None, target)
        if not module.check_mode:
            if current:
                request = models.ModifyLaneRuleRequest()
                request.RuleId = current["RuleId"]
                request.RuleName, request.Remark, request.LaneId = target["RuleName"], target.get("Remark"), target["LaneId"]
                request.RuleTagRelationship = target["RuleTagRelationship"]
                request.RuleTagList = tag_models(models, params["tags"] if params.get("tags") is not None else current.get("RuleTagList"))
                request.Enable = target["Enable"]
                set_result(module, module.sdk_call(client.ModifyLaneRule, request), "update")
                params["rule_id"] = current["RuleId"]
            else:
                request = models.CreateLaneRuleRequest()
                request.RuleName, request.Remark, request.LaneId = target["RuleName"], target.get("Remark"), target["LaneId"]
                request.RuleTagRelationship, request.RuleTagList = target["RuleTagRelationship"], tag_models(models, params["tags"])
                params["rule_id"] = module.sdk_call(client.CreateLaneRule, request).Result
                action = "EnableLaneRule" if target["Enable"] else "DisableLaneRule"
                request = getattr(models, action + "Request")()
                request.RuleId = params["rule_id"]
                set_result(module, module.sdk_call(getattr(client, action), request), "enable" if target["Enable"] else "disable")
            current = find(module, client, models, params)
        module.exit_json(changed=True, **(diff or {}), lane_rule=current if not module.check_mode else target)
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
