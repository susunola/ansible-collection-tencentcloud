#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function
__metaclass__ = type

DOCUMENTATION = r'''
---
module: cfw_nat_acl_rule
short_description: Manage Tencent Cloud Cloud Firewall NAT access-control rules
version_added: "0.14.0"
description: Creates, updates and removes NAT firewall access-control rules.
options:
  state: {type: str, choices: [present, absent], default: present, description: Desired rule state.}
  rule_uuid: {type: int, description: Existing rule UUID; preferred for updates and deletion.}
  description: {type: str, description: "Rule description, also used as the unique lookup key when rule_uuid is omitted."}
  source: {type: str, description: "Source address, domain or address-template UUID."}
  source_type: {type: str, choices: [ip, domain, ip_template, domain_template], default: ip, description: Source value type.}
  destination: {type: str, description: "Destination address, domain or address-template UUID."}
  destination_type: {type: str, choices: [ip, domain, ip_template, domain_template], default: ip, description: Destination value type.}
  protocol: {type: str, choices: [ANY, TCP, UDP, ICMP, HTTP, HTTPS, HTTP/HTTPS, SMTP, SMTPS, SMTP/SMTPS, FTP, DNS], default: ANY, description: Network or application protocol.}
  ports: {type: str, default: "-1/-1", description: Port expression accepted by Cloud Firewall.}
  action: {type: str, choices: [observe, block, accept], default: accept, description: Rule action.}
  direction: {type: str, choices: [outbound, inbound], default: outbound, description: Traffic direction.}
  enabled: {type: bool, default: true, description: Whether the rule is enabled.}
  order_index: {type: int, description: Rule insertion or execution order; defaults to append on creation.}
  scope: {type: str, description: Optional NAT firewall instance scope.}
  parameter_template_id: {type: str, description: Optional protocol-port parameter template ID.}
  retries: {description: Number of retries for transient failures., type: int, default: 5}
  waiter_delay: {description: Seconds between polling attempts., type: int, default: 5}
  waiter_timeout: {description: Overall timeout in seconds for state polling., type: int, default: 120}
  user_agent: {description: User-Agent suffix., type: str, default: ansible-collection.susunola.tencentcloud}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''

EXAMPLES = r'''
- name: Allow a private network through the NAT firewall
  susunola.tencentcloud.cfw_nat_acl_rule:
    region: ap-guangzhou
    description: allow-app-egress
    source: 10.0.0.0/8
    destination: 203.0.113.0/24
    protocol: TCP
    ports: "443"
    action: accept
'''

RETURN = r'''rule: {description: Cloud Firewall NAT ACL rule metadata., type: dict, returned: always}'''

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload

VALUE_TYPES = ("ip", "domain", "ip_template", "domain_template")
ACTIONS = {"observe": "log", "block": "drop", "accept": "accept"}
DIRECTIONS = {"outbound": 0, "inbound": 1}


def _load():
    from tencentcloud.cfw.v20190904 import models, cfw_client
    return models, cfw_client


def describe_request(models, offset=0):
    request = models.DescribeNatAcRuleRequest(); request.Offset, request.Limit = offset, 100; return request


def _api_value_type(kind, value):
    if kind in ("ip_template", "domain_template"): return "template"
    if kind == "domain": return "domain"
    return "net" if "/" in value else "ip"


def _rule(models, p, rule_uuid=None):
    item = models.CreateNatRuleItem()
    item.SourceContent, item.SourceType = p["source"], _api_value_type(p["source_type"], p["source"])
    item.TargetContent, item.TargetType = p["destination"], _api_value_type(p["destination_type"], p["destination"])
    item.Protocol, item.Port, item.RuleAction = p["protocol"], p["ports"], ACTIONS[p["action"]]
    item.Direction, item.OrderIndex = DIRECTIONS[p["direction"]], p["order_index"] if p["order_index"] is not None else -1
    item.Enable, item.Description = "true" if p["enabled"] else "false", p["description"]
    if rule_uuid is not None: item.Uuid = rule_uuid
    if p.get("scope") is not None: item.Scope = p["scope"]
    if p.get("parameter_template_id") is not None: item.ParamTemplateId = p["parameter_template_id"]
    return item


def create_request(models, p):
    request = models.AddNatAcRuleRequest(); request.Rules = [_rule(models, p)]; return request


def update_request(models, p, rule_uuid):
    request = models.ModifyNatAcRuleRequest(); request.Rules = [_rule(models, p, rule_uuid)]; return request


def delete_request(models, p, rule_uuid):
    request = models.RemoveNatAcRuleRequest(); request.RuleUuid, request.Direction = [rule_uuid], DIRECTIONS[p["direction"]]; return request


def find_rule(module, client, models, p):
    offset = 0; matches = []
    while True:
        response = module.sdk_call(client.DescribeNatAcRule, describe_request(models, offset)); values = list(response.Data or [])
        for value in values:
            item = value._serialize(allow_none=True)
            if p.get("rule_uuid") is not None and item.get("Uuid") == p["rule_uuid"]: matches.append(item)
            elif p.get("rule_uuid") is None and p.get("description") and item.get("Description") == p["description"]: matches.append(item)
        offset += len(values)
        if offset >= int(response.Total or 0) or not values: break
    if len(matches) > 1: module.fail_json(msg="Multiple NAT ACL rules matched; specify rule_uuid")
    return matches[0] if matches else None


def desired(p):
    result = {"SourceContent": p["source"], "SourceType": _api_value_type(p["source_type"], p["source"]), "TargetContent": p["destination"], "TargetType": _api_value_type(p["destination_type"], p["destination"]), "Protocol": p["protocol"], "Port": p["ports"], "RuleAction": ACTIONS[p["action"]], "Direction": DIRECTIONS[p["direction"]], "Enable": "true" if p["enabled"] else "false", "Description": p["description"]}
    if p.get("order_index") is not None: result["OrderIndex"] = p["order_index"]
    if p.get("scope") is not None: result["Scope"] = p["scope"]
    if p.get("parameter_template_id") is not None: result["ParamTemplateId"] = p["parameter_template_id"]
    return result


def run_module():
    module = TencentCloudModule(argument_spec={
        "state": {"choices": ["present", "absent"], "default": "present"}, "rule_uuid": {"type": "int"}, "description": {}, "source": {},
        "source_type": {"choices": list(VALUE_TYPES), "default": "ip"}, "destination": {}, "destination_type": {"choices": list(VALUE_TYPES), "default": "ip"},
        "protocol": {"choices": ["ANY", "TCP", "UDP", "ICMP", "HTTP", "HTTPS", "HTTP/HTTPS", "SMTP", "SMTPS", "SMTP/SMTPS", "FTP", "DNS"], "default": "ANY"},
        "ports": {"default": "-1/-1"}, "action": {"choices": list(ACTIONS), "default": "accept"}, "direction": {"choices": list(DIRECTIONS), "default": "outbound"},
        "enabled": {"type": "bool", "default": True}, "order_index": {"type": "int"}, "scope": {}, "parameter_template_id": {},
    }, required_one_of=[("rule_uuid", "description")], supports_check_mode=True)
    p = module.params
    if p["state"] == "present" and any(p.get(key) is None for key in ("description", "source", "destination")): module.fail_json(msg="description, source and destination are required when state=present")
    module.require_sdk(); models, cm = _load(); client = module.create_client(cm.CfwClient, "cfw.tencentcloudapi.com")
    try:
        current = find_rule(module, client, models, p)
        if p["state"] == "absent":
            if not current: module.exit_json(changed=False, rule=None)
            diff = maybe_diff(module, current, None)
            if not module.check_mode: module.sdk_call(client.RemoveNatAcRule, delete_request(models, p, current["Uuid"]))
            module.exit_json(changed=True, **(diff or {}), rule=current if module.check_mode else None)
        target = desired(p); before = {key: current.get(key) for key in target} if current else None
        if before and "Enable" in before: before["Enable"] = str(before["Enable"]).lower()
        if before == target: module.exit_json(changed=False, rule=current)
        diff = maybe_diff(module, before, target)
        if not module.check_mode:
            if current:
                update_params = dict(p)
                if update_params["order_index"] is None: update_params["order_index"] = current.get("OrderIndex")
                module.sdk_call(client.ModifyNatAcRule, update_request(models, update_params, current["Uuid"]))
            else:
                p["rule_uuid"] = module.sdk_call(client.AddNatAcRule, create_request(models, p)).RuleUuid[0]
            current = find_rule(module, client, models, p)
        module.exit_json(changed=True, **(diff or {}), rule=current)
    except Exception as exc: module.fail_json(**sdk_error_payload(exc))


def main(): run_module()
if __name__ == "__main__": main()
