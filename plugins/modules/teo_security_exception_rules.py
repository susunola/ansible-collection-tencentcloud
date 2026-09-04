#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r"""
---
module: teo_security_exception_rules
short_description: Manage Tencent Cloud EdgeOne web security exception rules
version_added: "0.14.0"
description: Exactly reconciles web security exception rules without modifying other EdgeOne security policy modules.
options:
  zone_id: {type: str, required: true, description: EdgeOne zone ID.}
  scope: {type: str, choices: [zone, template, host], default: zone, description: Security policy scope.}
  template_id: {type: str, description: Web security template ID required for template scope.}
  host: {type: str, description: Acceleration domain required for host scope.}
  rules:
    type: list
    elements: dict
    required: true
    description: Exact exception-rule set; an empty list removes every exception rule in this scope.
    suboptions:
      rule_id: {type: str, description: Existing rule ID; otherwise an existing rule is matched by unique name.}
      name: {type: str, required: true, description: Exception rule name.}
      condition: {type: str, required: true, description: EdgeOne security expression selecting requests.}
      enabled: {type: bool, default: true, description: Whether the exception is enabled.}
      skip_scope: {type: str, choices: [WebSecurityModules, ManagedRules], required: true, description: Kind of protection bypassed.}
      skip_option:
        type: str
        choices: [SkipOnAllRequestFields, SkipOnSpecifiedRequestFields]
        default: SkipOnAllRequestFields
        description: Request-field bypass mode for managed rules.
      web_security_modules:
        type: list
        elements: str
        default: []
        choices: [websec-mod-managed-rules, websec-mod-rate-limiting, websec-mod-custom-rules, websec-mod-adaptive-control, websec-mod-bot]
        description: Modules bypassed when skip_scope is WebSecurityModules.
      managed_rule_ids: {type: list, elements: str, default: [], description: Exact managed rule IDs bypassed.}
      managed_rule_group_ids: {type: list, elements: str, default: [], description: Exact managed rule-group IDs bypassed.}
      request_fields:
        type: list
        elements: dict
        default: []
        description: Request fields excluded from managed-rule inspection.
        suboptions:
          field_scope: {type: str, choices: [body.json, cookie, header, uri.query, uri, body], required: true, description: Request field category.}
          condition: {type: str, default: '', description: Field-selection expression.}
          target_field: {type: str, required: true, description: "Key, value, path, query, fullpath, fullbody, or multipart target."}
  retries: {description: Number of retries for transient failures., type: int, default: 5}
  waiter_delay: {description: Seconds between polling attempts., type: int, default: 5}
  waiter_timeout: {description: Overall timeout in seconds for state polling., type: int, default: 120}
  user_agent: {description: User-Agent suffix., type: str, default: ansible-collection.susunola.tencentcloud}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""

EXAMPLES = r"""
- name: Exclude an upload field from managed WAF inspection
  susunola.tencentcloud.teo_security_exception_rules:
    region: ap-guangzhou
    zone_id: zone-xxxxxxxx
    scope: template
    template_id: temp-xxxxxxxx
    rules:
      - name: trusted_upload_payload
        condition: "$http.request.uri.path eq '/upload'"
        skip_scope: ManagedRules
        skip_option: SkipOnSpecifiedRequestFields
        managed_rule_group_ids: [OWASP]
        request_fields:
          - field_scope: body
            target_field: multipart
"""

RETURN = r"""rules: {description: Current normalized security exception rules., type: list, returned: always}"""

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


def _load():
    from tencentcloud.teo.v20220901 import models, teo_client

    return models, teo_client


def _scope(request, p):
    request.ZoneId = p["zone_id"]
    request.Entity = {"zone": "ZoneDefaultPolicy", "template": "Template", "host": "Host"}[p["scope"]]
    if p["scope"] == "template":
        request.TemplateId = p["template_id"]
    if p["scope"] == "host":
        request.Host = p["host"]
    return request


def describe_request(models, p):
    return _scope(models.DescribeSecurityPolicyRequest(), p)


def _normalize(values, sdk=False):
    result = []
    for value in values or []:
        fields = []
        for field in (value.get("RequestFieldsForException") if sdk else value["request_fields"]) or []:
            fields.append(
                {
                    "field_scope": field.get("Scope") if sdk else field["field_scope"],
                    "condition": (field.get("Condition") if sdk else field["condition"]) or "",
                    "target_field": field.get("TargetField") if sdk else field["target_field"],
                }
            )
        result.append(
            {
                "name": value.get("Name") if sdk else value["name"],
                "condition": value.get("Condition") if sdk else value["condition"],
                "enabled": (value.get("Enabled") == "on") if sdk else value["enabled"],
                "skip_scope": value.get("SkipScope") if sdk else value["skip_scope"],
                "skip_option": (value.get("SkipOption") or "SkipOnAllRequestFields") if sdk else value["skip_option"],
                "web_security_modules": sorted((value.get("WebSecurityModulesForException") if sdk else value["web_security_modules"]) or []),
                "managed_rule_ids": sorted((value.get("ManagedRulesForException") if sdk else value["managed_rule_ids"]) or []),
                "managed_rule_group_ids": sorted((value.get("ManagedRuleGroupsForException") if sdk else value["managed_rule_group_ids"]) or []),
                "request_fields": sorted(fields, key=lambda item: (item["field_scope"], item["target_field"], item["condition"])),
            }
        )
    return sorted(result, key=lambda item: item["name"])


def update_request(models, p, current=None):
    by_id = {item.get("Id"): item for item in current or [] if item.get("Id")}
    by_name = {}
    for item in current or []:
        by_name.setdefault(item.get("Name"), []).append(item)
    output = []
    for value in p["rules"]:
        item = models.ExceptionRule()
        item.Name, item.Condition, item.Enabled = value["name"], value["condition"], "on" if value["enabled"] else "off"
        item.SkipScope, item.SkipOption = value["skip_scope"], value["skip_option"]
        item.WebSecurityModulesForException, item.ManagedRulesForException = value["web_security_modules"], value["managed_rule_ids"]
        item.ManagedRuleGroupsForException = value["managed_rule_group_ids"]
        item.RequestFieldsForException = []
        for field in value["request_fields"]:
            request_field = models.RequestFieldsForException()
            request_field.Scope, request_field.Condition, request_field.TargetField = field["field_scope"], field["condition"], field["target_field"]
            item.RequestFieldsForException.append(request_field)
        match = by_id.get(value.get("rule_id"))
        candidates = by_name.get(value["name"], [])
        if match:
            item.Id = match.get("Id")
        elif len(candidates) == 1:
            item.Id = candidates[0].get("Id")
        output.append(item)
    rules = models.ExceptionRules()
    rules.Rules = output
    policy = models.SecurityPolicy()
    policy.ExceptionRules = rules
    request = _scope(models.ModifySecurityPolicyRequest(), p)
    request.SecurityPolicy = policy
    return request


def get_rules(module, client, models, p):
    response = module.sdk_call(client.DescribeSecurityPolicy, describe_request(models, p))
    policy = response.SecurityPolicy
    if not policy or not policy.ExceptionRules:
        return [], []
    raw = [item._serialize(allow_none=True) for item in policy.ExceptionRules.Rules or []]
    return raw, _normalize(raw, True)


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "zone_id": {"required": True},
            "scope": {"choices": ["zone", "template", "host"], "default": "zone"},
            "template_id": {},
            "host": {},
            "rules": {
                "type": "list",
                "elements": "dict",
                "required": True,
                "options": {
                    "rule_id": {},
                    "name": {"required": True},
                    "condition": {"required": True},
                    "enabled": {"type": "bool", "default": True},
                    "skip_scope": {"choices": ["WebSecurityModules", "ManagedRules"], "required": True},
                    "skip_option": {"choices": ["SkipOnAllRequestFields", "SkipOnSpecifiedRequestFields"], "default": "SkipOnAllRequestFields"},
                    "web_security_modules": {
                        "type": "list",
                        "elements": "str",
                        "default": [],
                        "choices": [
                            "websec-mod-managed-rules",
                            "websec-mod-rate-limiting",
                            "websec-mod-custom-rules",
                            "websec-mod-adaptive-control",
                            "websec-mod-bot",
                        ],
                    },
                    "managed_rule_ids": {"type": "list", "elements": "str", "default": []},
                    "managed_rule_group_ids": {"type": "list", "elements": "str", "default": []},
                    "request_fields": {
                        "type": "list",
                        "elements": "dict",
                        "default": [],
                        "options": {
                            "field_scope": {"choices": ["body.json", "cookie", "header", "uri.query", "uri", "body"], "required": True},
                            "condition": {"default": ""},
                            "target_field": {"required": True},
                        },
                    },
                },
            },
        },
        supports_check_mode=True,
    )
    p = module.params
    if p["scope"] == "template" and not p.get("template_id"):
        module.fail_json(msg="template_id is required for template scope")
    if p["scope"] == "host" and not p.get("host"):
        module.fail_json(msg="host is required for host scope")
    names = [item["name"] for item in p["rules"]]
    if len(names) != len(set(names)):
        module.fail_json(msg="exception rule names must be unique")
    for rule in p["rules"]:
        if rule["skip_scope"] == "WebSecurityModules" and not rule["web_security_modules"]:
            module.fail_json(msg="WebSecurityModules exceptions require web_security_modules")
        if rule["skip_scope"] == "ManagedRules" and bool(rule["managed_rule_ids"]) == bool(rule["managed_rule_group_ids"]):
            module.fail_json(msg="ManagedRules exceptions require exactly one of managed_rule_ids or managed_rule_group_ids")
        if rule["skip_option"] == "SkipOnSpecifiedRequestFields" and not rule["request_fields"]:
            module.fail_json(msg="SkipOnSpecifiedRequestFields requires request_fields")
    module.require_sdk()
    models, cm = _load()
    client = module.create_client(cm.TeoClient, "teo.tencentcloudapi.com")
    try:
        raw, before = get_rules(module, client, models, p)
        target = _normalize(p["rules"])
        if before == target:
            module.exit_json(changed=False, rules=before)
        diff = maybe_diff(module, before, target)
        if not module.check_mode:
            module.sdk_call(client.ModifySecurityPolicy, update_request(models, p, raw))
            raw, before = get_rules(module, client, models, p)
        module.exit_json(changed=True, **(diff or {}), rules=before if not module.check_mode else target)
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
