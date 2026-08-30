#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function
__metaclass__ = type

DOCUMENTATION = r'''
---
module: cfw_vpc_acl_rule
short_description: Manage Tencent Cloud Cloud Firewall inter-VPC ACL rules
version_added: "0.14.0"
description: Creates, updates and removes access-control rules between VPCs.
options:
  state: {type: str, choices: [present, absent], default: present, description: Desired rule state.}
  rule_uuid: {type: int, description: Existing rule UUID; preferred for updates and deletion.}
  description: {type: str, description: "Rule description, also used for lookup when rule_uuid is omitted."}
  edge_id: {type: str, required: true, description: VPC firewall edge or all-VPC scope ID.}
  source: {type: str, description: Source IP address or CIDR.}
  destination: {type: str, description: Destination IP network or domain.}
  destination_type: {type: str, choices: [net, domain, dnsparse], default: net, description: Destination value type.}
  protocol: {type: str, choices: [ANY, TCP, UDP, ICMP, HTTP, HTTPS, HTTP/HTTPS, SMTP, SMTPS, SMTP/SMTPS, FTP, DNS, TLS/SSL], default: ANY, description: Network or application protocol.}
  ports: {type: str, default: "-1/-1", description: Port expression accepted by Cloud Firewall.}
  action: {type: str, choices: [observe, block, accept], default: accept, description: Rule action.}
  enabled: {type: bool, default: true, description: Whether the rule is enabled.}
  order_index: {type: int, description: Rule insertion or execution order; defaults to append on creation.}
  firewall_group_id: {type: str, description: Optional VPC firewall group ID.}
  parameter_template_id: {type: str, description: Optional protocol-port parameter template ID.}
  ip_version: {type: int, choices: [0, 1], default: 0, description: Zero for IPv4 or one for IPv6.}
  retries: {description: Number of retries for transient failures., type: int, default: 5}
  waiter_delay: {description: Seconds between polling attempts., type: int, default: 5}
  waiter_timeout: {description: Overall timeout in seconds for state polling., type: int, default: 120}
  user_agent: {description: User-Agent suffix., type: str, default: ansible-collection.susunola.tencentcloud}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''

EXAMPLES = r'''
- name: Allow HTTPS between two VPCs
  susunola.tencentcloud.cfw_vpc_acl_rule:
    region: ap-guangzhou
    edge_id: vpcfw-edge-xxxxxxxx
    description: allow-vpc-https
    source: 10.0.0.0/16
    destination: 10.20.0.0/16
    protocol: TCP
    ports: "443"
'''

RETURN = r'''rule: {description: Cloud Firewall inter-VPC ACL rule metadata., type: dict, returned: always}'''

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload

ACTIONS = {"observe": "log", "block": "drop", "accept": "accept"}


def _load():
    from tencentcloud.cfw.v20190904 import models, cfw_client
    return models, cfw_client


def describe_request(models, offset=0):
    request = models.DescribeVpcAcRuleRequest(); request.Offset, request.Limit = offset, 100; return request


def _rule(models, p, rule_uuid=None):
    item = models.VpcRuleItem()
    item.SourceContent, item.SourceType = p["source"], "net"
    item.DestContent, item.DestType = p["destination"], p["destination_type"]
    item.Protocol, item.Port, item.RuleAction = p["protocol"], p["ports"], ACTIONS[p["action"]]
    item.Description, item.EdgeId = p["description"], p["edge_id"]
    item.OrderIndex = p["order_index"] if p["order_index"] is not None else -1
    item.Enable, item.IpVersion = "true" if p["enabled"] else "false", p["ip_version"]
    if rule_uuid is not None: item.Uuid = rule_uuid
    if p.get("firewall_group_id") is not None: item.FwGroupId = p["firewall_group_id"]
    if p.get("parameter_template_id") is not None: item.ParamTemplateId = p["parameter_template_id"]
    return item


def create_request(models, p):
    request = models.AddVpcAcRuleRequest(); request.Rules = [_rule(models, p)]; return request


def update_request(models, p, rule_uuid):
    request = models.ModifyVpcAcRuleRequest(); request.Rules = [_rule(models, p, rule_uuid)]; return request


def delete_request(models, p, rule_uuid):
    request = models.RemoveVpcAcRuleRequest(); request.RuleUuids, request.IpVersion = [rule_uuid], p["ip_version"]; return request


def find_rule(module, client, models, p):
    offset = 0; matches = []
    while True:
        response = module.sdk_call(client.DescribeVpcAcRule, describe_request(models, offset)); values = list(response.Data or [])
        for value in values:
            item = value._serialize(allow_none=True)
            if p.get("rule_uuid") is not None and item.get("Uuid") == p["rule_uuid"]: matches.append(item)
            elif p.get("rule_uuid") is None and item.get("EdgeId") == p["edge_id"] and p.get("description") and item.get("Description") == p["description"]: matches.append(item)
        offset += len(values)
        if offset >= int(response.Total or 0) or not values: break
    if len(matches) > 1: module.fail_json(msg="Multiple inter-VPC ACL rules matched; specify rule_uuid")
    return matches[0] if matches else None


def desired(p):
    result = {"SourceContent": p["source"], "SourceType": "net", "DestContent": p["destination"], "DestType": p["destination_type"], "Protocol": p["protocol"], "Port": p["ports"], "RuleAction": ACTIONS[p["action"]], "Description": p["description"], "EdgeId": p["edge_id"], "Enable": "true" if p["enabled"] else "false", "IpVersion": p["ip_version"]}
    if p.get("order_index") is not None: result["OrderIndex"] = p["order_index"]
    if p.get("firewall_group_id") is not None: result["FwGroupId"] = p["firewall_group_id"]
    if p.get("parameter_template_id") is not None: result["ParamTemplateId"] = p["parameter_template_id"]
    return result


def run_module():
    module = TencentCloudModule(argument_spec={
        "state": {"choices": ["present", "absent"], "default": "present"}, "rule_uuid": {"type": "int"}, "description": {}, "edge_id": {"required": True},
        "source": {}, "destination": {}, "destination_type": {"choices": ["net", "domain", "dnsparse"], "default": "net"},
        "protocol": {"choices": ["ANY", "TCP", "UDP", "ICMP", "HTTP", "HTTPS", "HTTP/HTTPS", "SMTP", "SMTPS", "SMTP/SMTPS", "FTP", "DNS", "TLS/SSL"], "default": "ANY"},
        "ports": {"default": "-1/-1"}, "action": {"choices": list(ACTIONS), "default": "accept"}, "enabled": {"type": "bool", "default": True},
        "order_index": {"type": "int"}, "firewall_group_id": {}, "parameter_template_id": {}, "ip_version": {"type": "int", "choices": [0, 1], "default": 0},
    }, required_one_of=[("rule_uuid", "description")], supports_check_mode=True)
    p = module.params
    if p["state"] == "present" and any(p.get(key) is None for key in ("description", "source", "destination")): module.fail_json(msg="description, source and destination are required when state=present")
    module.require_sdk(); models, cm = _load(); client = module.create_client(cm.CfwClient, "cfw.tencentcloudapi.com")
    try:
        current = find_rule(module, client, models, p)
        if p["state"] == "absent":
            if not current: module.exit_json(changed=False, rule=None)
            diff = maybe_diff(module, current, None)
            if not module.check_mode: module.sdk_call(client.RemoveVpcAcRule, delete_request(models, p, current["Uuid"]))
            module.exit_json(changed=True, **(diff or {}), rule=current if module.check_mode else None)
        target = desired(p); before = {key: current.get(key) for key in target} if current else None
        if before and "Enable" in before: before["Enable"] = str(before["Enable"]).lower()
        if before == target: module.exit_json(changed=False, rule=current)
        diff = maybe_diff(module, before, target)
        if not module.check_mode:
            if current:
                update_params = dict(p)
                if update_params["order_index"] is None: update_params["order_index"] = current.get("OrderIndex")
                module.sdk_call(client.ModifyVpcAcRule, update_request(models, update_params, current["Uuid"]))
            else:
                p["rule_uuid"] = module.sdk_call(client.AddVpcAcRule, create_request(models, p)).RuleUuids[0]
            current = find_rule(module, client, models, p)
        module.exit_json(changed=True, **(diff or {}), rule=current)
    except Exception as exc: module.fail_json(**sdk_error_payload(exc))


def main(): run_module()
if __name__ == "__main__": main()
