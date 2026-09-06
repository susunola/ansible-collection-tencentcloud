#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r"""
---
module: config_compliance_pack
short_description: Manage Tencent Cloud Config compliance packs
version_added: "0.14.0"
description: Creates, updates, enables, disables and deletes Config compliance packs with an exact rule set.
options:
  state: {type: str, choices: [present, absent], default: present, description: Desired pack state.}
  compliance_pack_id: {type: str, description: Existing compliance pack ID; preferred for updates and deletion.}
  name: {type: str, description: "Compliance pack name, also used for lookup."}
  description: {type: str, default: '', description: Compliance pack description.}
  risk_level: {type: int, choices: [1, 2, 3], default: 2, description: Pack risk level.}
  enabled: {type: bool, default: true, description: Whether compliance evaluation is active.}
  rules:
    description: Exact set of Config rules contained in the pack.
    type: list
    elements: dict
    default: []
    suboptions:
      name: {type: str, required: true, description: Rule name.}
      risk_level: {type: int, choices: [1, 2, 3], required: true, description: Rule risk level.}
      identifier: {type: str, required: true, description: Rule identity identifier.}
      config_rule_id: {type: str, required: true, description: Existing Config rule ID.}
      managed_rule_identifier: {type: str, description: Optional preset managed-rule identifier.}
      description: {type: str, default: '', description: Rule description.}
      input_parameters:
        type: list
        elements: dict
        default: []
        description: Exact rule input parameter list.
        suboptions:
          parameter_name: {type: str, required: true, description: Parameter key name.}
          type: {type: str, required: true, description: Parameter value type.}
          value: {type: str, required: true, description: Parameter value.}
  retries: {description: Number of retries for transient failures., type: int, default: 5}
  waiter_delay: {description: Seconds between polling attempts., type: int, default: 5}
  waiter_timeout: {description: Overall timeout in seconds for state polling., type: int, default: 120}
  user_agent: {description: User-Agent suffix., type: str, default: ansible-collection.susunola.tencentcloud}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""

EXAMPLES = r"""
- name: Create a production security baseline
  susunola.tencentcloud.config_compliance_pack:
    region: ap-guangzhou
    name: production-security
    risk_level: 1
    rules:
      - name: public-bucket-denied
        risk_level: 1
        identifier: cos-public-read-prohibited
        managed_rule_identifier: cos-public-read-prohibited
        config_rule_id: cr-xxxxxxxx
"""

RETURN = r"""compliance_pack: {description: Config compliance pack metadata., type: dict, returned: always}"""

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


def _load():
    from tencentcloud.config.v20220802 import models, config_client

    return models, config_client


def list_request(models, p, offset=0):
    request = models.ListCompliancePacksRequest()
    request.Offset, request.Limit = offset, 100
    if p.get("name"):
        request.CompliancePackName = p["name"]
    return request


def describe_request(models, pack_id):
    request = models.DescribeCompliancePackRequest()
    request.CompliancePackId = pack_id
    return request


def _rules(models, values):
    result = []
    for value in values:
        rule = models.CompliancePackRule()
        rule.RuleName, rule.RiskLevel = value["name"], value["risk_level"]
        rule.Identifier, rule.ConfigRuleId, rule.Description = value["identifier"], value["config_rule_id"], value["description"]
        if value.get("managed_rule_identifier"):
            rule.ManagedRuleIdentifier = value["managed_rule_identifier"]
        rule.InputParameter = []
        for param in value["input_parameters"]:
            item = models.InputParameter()
            item.ParameterKey, item.Type, item.Value = param["parameter_name"], param["type"], param["value"]
            rule.InputParameter.append(item)
        result.append(rule)
    return result


def create_request(models, p):
    request = models.AddCompliancePackRequest()
    request.CompliancePackName, request.Description, request.RiskLevel = p["name"], p["description"], p["risk_level"]
    request.ConfigRules = _rules(models, p["rules"])
    return request


def update_request(models, p, pack_id):
    request = models.UpdateCompliancePackRequest()
    request.CompliancePackId, request.CompliancePackName = pack_id, p["name"]
    request.Description, request.RiskLevel, request.ConfigRules = p["description"], p["risk_level"], _rules(models, p["rules"])
    return request


def status_request(models, pack_id, enabled):
    request = models.UpdateCompliancePackStatusRequest()
    request.CompliancePackId, request.Status = pack_id, "ACTIVE" if enabled else "UN_ACTIVE"
    return request


def delete_request(models, pack_id):
    request = models.DeleteCompliancePackRequest()
    request.CompliancePackId = pack_id
    return request


def find_pack(module, client, models, p):
    offset = 0
    matches = []
    while True:
        response = module.sdk_call(client.ListCompliancePacks, list_request(models, p, offset))
        values = list(response.Items or [])
        for value in values:
            item = value._serialize(allow_none=True)
            if p.get("compliance_pack_id") and item.get("CompliancePackId") == p["compliance_pack_id"]:
                matches.append(item)
            elif not p.get("compliance_pack_id") and p.get("name") and item.get("CompliancePackName") == p["name"]:
                matches.append(item)
        offset += len(values)
        if offset >= int(response.Total or 0) or not values:
            break
    if len(matches) > 1:
        module.fail_json(msg="Multiple compliance packs matched; specify compliance_pack_id")
    if not matches:
        return None
    response = module.sdk_call(client.DescribeCompliancePack, describe_request(models, matches[0]["CompliancePackId"]))
    value = response._serialize(allow_none=True)
    value.pop("RequestId", None)
    return value


def _normalized_rules(values):
    result = []
    for value in values or []:
        params = value.get("InputParameter") or value.get("input_parameters") or []
        result.append(
            {
                "RuleName": value.get("RuleName") or value.get("name"),
                "RiskLevel": value.get("RiskLevel") or value.get("risk_level"),
                "Identifier": value.get("Identifier") or value.get("identifier"),
                "ConfigRuleId": value.get("ConfigRuleId") or value.get("config_rule_id"),
                "ManagedRuleIdentifier": value.get("ManagedRuleIdentifier") or value.get("managed_rule_identifier"),
                "Description": value.get("Description") or value.get("description") or "",
                "InputParameter": sorted(
                    (
                        {
                            "ParameterKey": x.get("ParameterKey") or x.get("parameter_name"),
                            "Type": x.get("Type") or x.get("type"),
                            "Value": x.get("Value") or x.get("value"),
                        }
                        for x in params
                    ),
                    key=lambda x: x["ParameterKey"],
                ),
            }
        )
    return sorted(result, key=lambda x: x["ConfigRuleId"])


def run_module():
    rule_options = {
        "name": {"required": True},
        "risk_level": {"type": "int", "choices": [1, 2, 3], "required": True},
        "identifier": {"required": True},
        "config_rule_id": {"required": True},
        "managed_rule_identifier": {},
        "description": {"default": ""},
        "input_parameters": {
            "type": "list",
            "elements": "dict",
            "default": [],
            "options": {"parameter_name": {"required": True}, "type": {"required": True}, "value": {"required": True}},
        },
    }
    module = TencentCloudModule(
        argument_spec={
            "state": {"choices": ["present", "absent"], "default": "present"},
            "compliance_pack_id": {},
            "name": {},
            "description": {"default": ""},
            "risk_level": {"type": "int", "choices": [1, 2, 3], "default": 2},
            "enabled": {"type": "bool", "default": True},
            "rules": {"type": "list", "elements": "dict", "default": [], "options": rule_options},
        },
        required_one_of=[("compliance_pack_id", "name")],
        supports_check_mode=True,
    )
    p = module.params
    if p["state"] == "present" and not p.get("name"):
        module.fail_json(msg="name is required when state=present")
    module.require_sdk()
    models, cm = _load()
    client = module.create_client(cm.ConfigClient, "config.tencentcloudapi.com")
    try:
        current = find_pack(module, client, models, p)
        if p["state"] == "absent":
            if not current:
                module.exit_json(changed=False, compliance_pack=None)
            diff = maybe_diff(module, current, None)
            if not module.check_mode:
                module.sdk_call(client.DeleteCompliancePack, delete_request(models, current["CompliancePackId"]))
            module.exit_json(changed=True, **(diff or {}), compliance_pack=current if module.check_mode else None)
        desired = {
            "CompliancePackName": p["name"],
            "Description": p["description"],
            "RiskLevel": p["risk_level"],
            "ConfigRules": _normalized_rules(p["rules"]),
            "Status": "ACTIVE" if p["enabled"] else "UN_ACTIVE",
        }
        before = (
            None
            if not current
            else {
                "CompliancePackName": current.get("CompliancePackName"),
                "Description": current.get("Description") or "",
                "RiskLevel": current.get("RiskLevel"),
                "ConfigRules": _normalized_rules(current.get("ConfigRules")),
                "Status": current.get("Status"),
            }
        )
        if before == desired:
            module.exit_json(changed=False, compliance_pack=current)
        diff = maybe_diff(module, before, desired)
        if not module.check_mode:
            if not current:
                p["compliance_pack_id"] = module.sdk_call(client.AddCompliancePack, create_request(models, p)).CompliancePackId
                module.sdk_call(client.UpdateCompliancePackStatus, status_request(models, p["compliance_pack_id"], p["enabled"]))
            else:
                content_changed = any(before[key] != desired[key] for key in ("CompliancePackName", "Description", "RiskLevel", "ConfigRules"))
                if content_changed:
                    module.sdk_call(client.UpdateCompliancePack, update_request(models, p, current["CompliancePackId"]))
                if before["Status"] != desired["Status"]:
                    module.sdk_call(client.UpdateCompliancePackStatus, status_request(models, current["CompliancePackId"], p["enabled"]))
            current = find_pack(module, client, models, p)
        module.exit_json(changed=True, **(diff or {}), compliance_pack=current)
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
