#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r"""
---
module: cfw_nat_dnat_rule
short_description: Manage Tencent Cloud Cloud Firewall NAT DNAT rules
version_added: "0.14.0"
description: Creates, updates and deletes NAT firewall destination-NAT forwarding rules.
options:
  state: {type: str, choices: [present, absent], default: present, description: Desired rule state.}
  firewall_instance_id: {type: str, required: true, description: Cloud Firewall NAT instance ID.}
  mode: {type: int, choices: [0, 1], default: 0, description: Zero for CFW-created mode or one for access mode.}
  protocol: {type: str, choices: [TCP, UDP], required: true, description: Forwarding protocol.}
  public_ip: {type: str, required: true, description: Public elastic IP used to identify the rule.}
  public_port: {type: int, required: true, description: Public port used to identify the rule.}
  private_ip: {type: str, description: Private destination IP; required when state is present.}
  private_port: {type: int, description: Private destination port; required when state is present.}
  description: {type: str, default: '', description: Rule description.}
  retries: {description: Number of retries for transient failures., type: int, default: 5}
  waiter_delay: {description: Seconds between polling attempts., type: int, default: 5}
  waiter_timeout: {description: Overall timeout in seconds for state polling., type: int, default: 120}
  user_agent: {description: User-Agent suffix., type: str, default: ansible-collection.susunola.tencentcloud}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""

EXAMPLES = r"""
- name: Forward public HTTPS through a NAT firewall
  susunola.tencentcloud.cfw_nat_dnat_rule:
    region: ap-guangzhou
    firewall_instance_id: cfwnat-xxxxxxxx
    protocol: TCP
    public_ip: 203.0.113.10
    public_port: 443
    private_ip: 10.0.1.10
    private_port: 8443
    description: application HTTPS
"""

RETURN = r"""rule: {description: Cloud Firewall NAT DNAT rule metadata., type: dict, returned: always}"""

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


def _load():
    from tencentcloud.cfw.v20190904 import models, cfw_client

    return models, cfw_client


def describe_request(models, offset=0):
    request = models.DescribeNatFwDnatRuleRequest()
    request.Offset, request.Limit = offset, 100
    return request


def dnat_rule(models, p):
    item = models.CfwNatDnatRule()
    item.IpProtocol, item.PublicIpAddress, item.PublicPort = p["protocol"], p["public_ip"], p["public_port"]
    item.PrivateIpAddress, item.PrivatePort, item.Description = p["private_ip"], p["private_port"], p["description"]
    return item


def create_request(models, p):
    request = models.CreateNatFwDnatRuleRequest()
    request.Mode, request.CfwInstance, request.DnatRules = p["mode"], p["firewall_instance_id"], [dnat_rule(models, p)]
    return request


def update_request(models, p, current):
    request = models.SetNatFwDnatRuleRequest()
    request.Mode, request.OperationType, request.CfwInstance = p["mode"], "modify", p["firewall_instance_id"]
    original = models.CfwNatDnatRule()
    original._deserialize({key: current.get(key) for key in ("IpProtocol", "PublicIpAddress", "PublicPort", "PrivateIpAddress", "PrivatePort", "Description")})
    request.OriginDnat, request.NewDnat = original, dnat_rule(models, p)
    return request


def delete_request(models, p, current):
    request = models.DeleteNatFwDnatRuleRequest()
    request.Mode, request.CfwInstance = p["mode"], p["firewall_instance_id"]
    item = models.CfwNatDnatRule()
    item._deserialize({key: current.get(key) for key in ("IpProtocol", "PublicIpAddress", "PublicPort", "PrivateIpAddress", "PrivatePort", "Description")})
    request.DnatRules = [item]
    return request


def find_rule(module, client, models, p):
    offset = 0
    matches = []
    while True:
        response = module.sdk_call(client.DescribeNatFwDnatRule, describe_request(models, offset))
        values = list(response.Data or [])
        for value in values:
            item = value._serialize(allow_none=True)
            if (
                item.get("FwInsId") == p["firewall_instance_id"]
                and item.get("IpProtocol") == p["protocol"]
                and item.get("PublicIpAddress") == p["public_ip"]
                and item.get("PublicPort") == p["public_port"]
            ):
                matches.append(item)
        offset += len(values)
        if offset >= int(response.Total or 0) or not values:
            break
    if len(matches) > 1:
        module.fail_json(msg="Multiple NAT DNAT rules matched the public endpoint")
    return matches[0] if matches else None


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "state": {"choices": ["present", "absent"], "default": "present"},
            "firewall_instance_id": {"required": True},
            "mode": {"type": "int", "choices": [0, 1], "default": 0},
            "protocol": {"choices": ["TCP", "UDP"], "required": True},
            "public_ip": {"required": True},
            "public_port": {"type": "int", "required": True},
            "private_ip": {},
            "private_port": {"type": "int"},
            "description": {"default": ""},
        },
        supports_check_mode=True,
    )
    p = module.params
    if p["state"] == "present" and (not p.get("private_ip") or p.get("private_port") is None):
        module.fail_json(msg="private_ip and private_port are required when state=present")
    module.require_sdk()
    models, cm = _load()
    client = module.create_client(cm.CfwClient, "cfw.tencentcloudapi.com")
    try:
        current = find_rule(module, client, models, p)
        if p["state"] == "absent":
            if not current:
                module.exit_json(changed=False, rule=None)
            diff = maybe_diff(module, current, None)
            if not module.check_mode:
                module.sdk_call(client.DeleteNatFwDnatRule, delete_request(models, p, current))
            module.exit_json(changed=True, **(diff or {}), rule=current if module.check_mode else None)
        desired = {
            "IpProtocol": p["protocol"],
            "PublicIpAddress": p["public_ip"],
            "PublicPort": p["public_port"],
            "PrivateIpAddress": p["private_ip"],
            "PrivatePort": p["private_port"],
            "Description": p["description"],
        }
        before = {key: current.get(key) for key in desired} if current else None
        if before == desired:
            module.exit_json(changed=False, rule=current)
        diff = maybe_diff(module, before, desired)
        if not module.check_mode:
            if current:
                module.sdk_call(client.SetNatFwDnatRule, update_request(models, p, current))
            else:
                module.sdk_call(client.CreateNatFwDnatRule, create_request(models, p))
            current = find_rule(module, client, models, p)
        module.exit_json(changed=True, **(diff or {}), rule=current)
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
