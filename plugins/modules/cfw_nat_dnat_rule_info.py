#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
---
module: cfw_nat_dnat_rule_info
short_description: Gather Tencent Cloud Cloud Firewall NAT DNAT rules
version_added: "1.4.0"
description:
  - Returns NAT firewall destination-NAT forwarding rules from Cloud Firewall.
options:
  firewall_instance_id:
    description: Optional Cloud Firewall NAT instance ID used to narrow returned rules.
    type: str
  protocol:
    description: Optional forwarding protocol used to identify a rule.
    type: str
    choices: [TCP, UDP]
  public_ip:
    description: Optional public elastic IP used to identify a rule.
    type: str
  public_port:
    description: Optional public port used to identify a rule.
    type: int
  page_size:
    description: Number of rules requested per API call.
    type: int
    default: 100
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''

EXAMPLES = r'''
- name: List Cloud Firewall NAT DNAT rules
  susunola.tencentcloud.cfw_nat_dnat_rule_info:
    region: ap-guangzhou

- name: Find a Cloud Firewall NAT DNAT rule by public endpoint
  susunola.tencentcloud.cfw_nat_dnat_rule_info:
    region: ap-guangzhou
    firewall_instance_id: cfwnat-xxxxxxxx
    protocol: TCP
    public_ip: 203.0.113.10
    public_port: 443
'''

RETURN = r'''
rules:
  description: Matching NAT DNAT rules.
  returned: always
  type: list
  elements: dict
rule:
  description: First matching rule when identifying filters are supplied.
  returned: always
  type: dict
total_count:
  description: Number of rules reported by the API.
  returned: always
  type: int
request_id:
  description: Request ID of the last API call, for cross-referencing cloud audit logs.
  returned: always
  type: str
'''

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.paging import Paginator
from ansible_collections.susunola.tencentcloud.plugins.module_utils.tencentcloud import (
    create_client_profile,
    create_credential,
    sdk_call,
    serialize_sdk_object,
    tencentcloud_argument_spec,
)


def build_request(models, offset, limit):
    request = models.DescribeNatFwDnatRuleRequest()
    request.Offset = offset
    request.Limit = limit
    return request


def _matches(item, firewall_instance_id, protocol, public_ip, public_port):
    if firewall_instance_id and item.get("FwInsId") != firewall_instance_id:
        return False
    if protocol and item.get("IpProtocol") != protocol:
        return False
    if public_ip and item.get("PublicIpAddress") != public_ip:
        return False
    if public_port is not None and item.get("PublicPort") != public_port:
        return False
    return True


def run_module():
    argument_spec = tencentcloud_argument_spec()
    argument_spec.update({
        "firewall_instance_id": {"type": "str"},
        "protocol": {"type": "str", "choices": ["TCP", "UDP"]},
        "public_ip": {"type": "str"},
        "public_port": {"type": "int"},
        "page_size": {"type": "int", "default": 100},
    })
    module = AnsibleModule(argument_spec=argument_spec, supports_check_mode=True)
    try:
        from tencentcloud.cfw.v20190904 import cfw_client, models
    except ImportError:
        module.fail_json(msg="The tencentcloud-sdk-python-cfw package is required.")

    client = cfw_client.CfwClient(create_credential(module), module.params["region"], create_client_profile(module, "cfw.tencentcloudapi.com"))
    paginator = Paginator(
        module.params["page_size"],
        lambda offset, limit: build_request(models, offset, limit),
        lambda request: sdk_call(module, client.DescribeNatFwDnatRule, request),
        lambda response: getattr(response, "Data", None),
        lambda response: getattr(response, "Total", None),
    )
    item_set, total_count = paginator.fetch_all()
    rules = [
        item for item in (serialize_sdk_object(value) for value in item_set)
        if _matches(item, module.params["firewall_instance_id"], module.params["protocol"], module.params["public_ip"], module.params["public_port"])
    ]
    has_identifier = any(module.params.get(key) is not None for key in ("firewall_instance_id", "protocol", "public_ip", "public_port"))
    module.exit_json(
        changed=False,
        rules=rules,
        rule=rules[0] if has_identifier and rules else None,
        total_count=total_count,
        request_id=paginator.request_id,
    )


def main():
    run_module()


if __name__ == "__main__":
    main()
