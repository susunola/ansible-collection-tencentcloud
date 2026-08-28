#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
---
module: nat_gateway_rule
short_description: Manage Tencent Cloud NAT gateway DNAT and SNAT rules
version_added: "0.14.0"
description:
  - Reconcile the DNAT (destination IP-port translation) and SNAT (source IP
    translation) rule sets of a single NAT gateway through the
    C(vpc.v20170312) API.
  - The module compares the desired rules with the rules currently configured
    on the gateway, creates the missing delta and, when O(purge=true),
    deletes the surplus.
  - A DNAT rule is identified by protocol, public IP, public port, private IP
    and private port; a SNAT rule by resource type, resource ID and private
    IP. Changing any other attribute (public IPs or description) of an
    existing rule replaces it (delete and re-create), matching the
    C(security_group_rule) behaviour.
  - This module is idempotent. Running it twice leaves the rule sets
    unchanged and the second run reports C(changed=false).
  - Supports check mode; no API write happens in check mode, only reads.
options:
  nat_gateway_id:
    description:
      - ID of the NAT gateway whose translation rules are managed, e.g.
        C(nat-xxxxxxxx).
      - The gateway must exist; the module fails when it does not.
    type: str
    required: true
  dnat_rules:
    description:
      - Desired DNAT rules for the gateway. A rule maps a public IP and port
        to a private IP and port for one protocol.
    type: list
    elements: dict
    default: []
    suboptions:
      ip_protocol:
        description:
          - Network protocol of the rule. One of C(TCP) or C(UDP); values
            are normalized to upper case before comparison.
        type: str
        required: true
      public_ip_address:
        description:
          - Public (elastic) IP the rule listens on, e.g. C(114.182.81.73).
        type: str
        required: true
      public_port:
        description:
          - Public port of the rule, written to
            V(DestinationIpPortTranslationNatRule.PublicPort).
        type: int
        required: true
      private_ip_address:
        description:
          - Private IP the rule forwards to, e.g. C(192.168.4.43).
        type: str
        required: true
      private_port:
        description:
          - Private port the rule forwards to, written to
            V(DestinationIpPortTranslationNatRule.PrivatePort).
        type: int
        required: true
      description:
        description: Description of the rule.
        type: str
        default: ""
  snat_rules:
    description:
      - Desired SNAT rules for the gateway. A rule maps a private resource
        (CVM instance or subnet) to one or more public IPs.
    type: list
    elements: dict
    default: []
    suboptions:
      resource_type:
        description:
          - Type of the resource the rule covers. One of C(CVM), C(SUBNET)
            or C(NETWORKINTERFACE); values are normalized to upper case
            before comparison.
        type: str
        default: CVM
      resource_id:
        description:
          - ID of the resource the rule covers, e.g. C(cvm-xxxxxxxx) or
            C(subnet-xxxxxxxx), written to
            V(SourceIpTranslationNatRule.ResourceId).
        type: str
        required: true
      private_ip_address:
        description:
          - Private IP the rule applies to, e.g. C(10.0.0.5).
        type: str
        required: true
      public_ip_addresses:
        description:
          - Public IPs the private IP is translated to, written to
            V(SourceIpTranslationNatRule.PublicIpAddresses).
          - The order is not significant; the module sorts the list before
            comparison.
        type: list
        elements: str
        required: true
      description:
        description: Description of the rule.
        type: str
        default: ""
  purge:
    description:
      - When C(true), existing rules not listed in O(dnat_rules) or
        O(snat_rules) are deleted.
      - When C(false), rules from O(dnat_rules) and O(snat_rules) are
        created when missing, but no rule is ever deleted.
    type: bool
    default: true
  retries:
    description: Number of retries for transient SDK failures.
    type: int
    default: 5
  waiter_timeout:
    description:
      - Maximum time in seconds to wait for an asynchronous resource to reach
        the desired state.
    type: int
    default: 120
  waiter_delay:
    description: Interval in seconds between state polls while waiting.
    type: int
    default: 5
  user_agent:
    description:
      - Value appended to the SDK User-Agent header so API usage can be
        attributed to this collection.
    type: str
    default: ansible-collection.susunola.tencentcloud
notes:
  - Requires the C(tencentcloud-sdk-python-vpc) package on the controller.
  - DNAT deletion addresses rules by the full rule object
    (V(DeleteNatGatewayDestinationIpPortTranslationNatRuleRequest)), as
    required by the API; SNAT deletion uses the C(NatGatewaySnatId) output
    field (V(DeleteNatGatewaySourceIpTranslationNatRuleRequest)).
  - Recreating an SNAT rule changes its public IPs; per the official
    documentation this may interrupt in-flight connections, so keep
    O(snat_rules) stable unless a change is intended.
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''

EXAMPLES = r'''
- name: Configure one DNAT and one SNAT rule, removing any surplus
  susunola.tencentcloud.nat_gateway_rule:
    region: ap-guangzhou
    nat_gateway_id: nat-xxxxxxxx
    dnat_rules:
      - ip_protocol: TCP
        public_ip_address: 114.182.81.73
        public_port: 8989
        private_ip_address: 10.80.80.41
        private_port: 8989
        description: web-forward
    snat_rules:
      - resource_type: CVM
        resource_id: cvm-xxxxxxxx
        private_ip_address: 10.80.80.41
        public_ip_addresses:
          - 180.12.59.43
        description: prod-eip

- name: Add a second DNAT rule without touching existing rules
  susunola.tencentcloud.nat_gateway_rule:
    region: ap-guangzhou
    nat_gateway_id: nat-xxxxxxxx
    purge: false
    dnat_rules:
      - ip_protocol: UDP
        public_ip_address: 114.182.81.73
        public_port: 5353
        private_ip_address: 10.80.80.42
        private_port: 5353

- name: Remove every translation rule from the gateway
  susunola.tencentcloud.nat_gateway_rule:
    region: ap-guangzhou
    nat_gateway_id: nat-xxxxxxxx
    dnat_rules: []
    snat_rules: []
'''

RETURN = r'''
dnat_rules:
  description: The DNAT rules as reported by
    V(DescribeNatGatewayDestinationIpPortTranslationNatRules) after the
    operation.
  returned: success
  type: list
  elements: dict
  sample:
    - IpProtocol: TCP
      PublicIpAddress: 114.182.81.73
      PublicPort: 8989
      PrivateIpAddress: 10.80.80.41
      PrivatePort: 8989
      Description: web-forward
snat_rules:
  description: The SNAT rules as reported by
    V(DescribeNatGatewaySourceIpTranslationNatRules) after the operation.
  returned: success
  type: list
  elements: dict
  sample:
    - NatGatewaySnatId: snat-xxxxxxxx
      ResourceType: CVM
      ResourceId: cvm-xxxxxxxx
      PrivateIpAddress: 10.80.80.41
      PublicIpAddresses:
        - 180.12.59.43
      Description: prod-eip
'''

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff


def _load_vpc():
    from tencentcloud.vpc.v20170312 import models, vpc_client
    return models, vpc_client


def _first(collection):
    return collection[0] if collection else None


def find_gateway(module, client, models, nat_gateway_id):
    """Return the NAT gateway dict or None."""
    request = models.DescribeNatGatewaysRequest()
    request.NatGatewayIds = [nat_gateway_id]
    response = module.sdk_call(client.DescribeNatGateways, request)
    gateway = _first(response.NatGatewaySet or [])
    if gateway is None:
        return None
    return gateway._serialize(allow_none=True)


def build_dnat_describe_request(models, nat_gateway_id):
    request = models.DescribeNatGatewayDestinationIpPortTranslationNatRulesRequest()
    request.NatGatewayIds = [nat_gateway_id]
    request.Offset = 0
    request.Limit = 100
    return request


def build_snat_describe_request(models, nat_gateway_id):
    request = models.DescribeNatGatewaySourceIpTranslationNatRulesRequest()
    request.NatGatewayId = nat_gateway_id
    request.Offset = 0
    request.Limit = 100
    return request


def list_dnat_rules(module, client, models, nat_gateway_id):
    """Return all DNAT rules of the gateway as serialized dicts."""
    request = build_dnat_describe_request(models, nat_gateway_id)
    response = module.sdk_call(client.DescribeNatGatewayDestinationIpPortTranslationNatRules, request)
    rules = []
    for rule in response.NatGatewayDestinationIpPortTranslationNatRuleSet or []:
        current = rule._serialize(allow_none=True)
        rules.append({
            "IpProtocol": current.get("IpProtocol"),
            "PublicIpAddress": current.get("PublicIpAddress"),
            "PublicPort": current.get("PublicPort"),
            "PrivateIpAddress": current.get("PrivateIpAddress"),
            "PrivatePort": current.get("PrivatePort"),
            "Description": current.get("Description") or "",
        })
    return rules


def list_snat_rules(module, client, models, nat_gateway_id):
    """Return all SNAT rules of the gateway as serialized dicts.

    Output-only fields (NatGatewayId, VpcId, CreatedTime) are dropped; the
    NatGatewaySnatId is kept because deletions address rules by it.
    """
    request = build_snat_describe_request(models, nat_gateway_id)
    response = module.sdk_call(client.DescribeNatGatewaySourceIpTranslationNatRules, request)
    rules = []
    for rule in response.SourceIpTranslationNatRuleSet or []:
        current = rule._serialize(allow_none=True)
        rules.append({
            "NatGatewaySnatId": current.get("NatGatewaySnatId"),
            "ResourceType": (current.get("ResourceType") or "").upper(),
            "ResourceId": current.get("ResourceId"),
            "PrivateIpAddress": current.get("PrivateIpAddress"),
            "PublicIpAddresses": sorted(current.get("PublicIpAddresses") or []),
            "Description": current.get("Description") or "",
        })
    return rules


def build_dnat_rule(models, rule):
    """Build the SDK DNAT rule object from a comparison-shape rule dict."""
    sdk_rule = models.DestinationIpPortTranslationNatRule()
    sdk_rule.IpProtocol = rule["IpProtocol"]
    sdk_rule.PublicIpAddress = rule["PublicIpAddress"]
    sdk_rule.PublicPort = rule["PublicPort"]
    sdk_rule.PrivateIpAddress = rule["PrivateIpAddress"]
    sdk_rule.PrivatePort = rule["PrivatePort"]
    sdk_rule.Description = rule["Description"]
    return sdk_rule


def build_snat_rule(models, rule):
    """Build the SDK SNAT rule object from a comparison-shape rule dict."""
    sdk_rule = models.SourceIpTranslationNatRule()
    sdk_rule.ResourceType = rule["ResourceType"]
    sdk_rule.ResourceId = rule["ResourceId"]
    sdk_rule.PrivateIpAddress = rule["PrivateIpAddress"]
    sdk_rule.PublicIpAddresses = rule["PublicIpAddresses"]
    sdk_rule.Description = rule["Description"]
    return sdk_rule


def normalize_dnat(rule):
    """Normalize a user DNAT rule to its comparison shape."""
    return {
        "IpProtocol": rule["ip_protocol"].upper(),
        "PublicIpAddress": rule["public_ip_address"],
        "PublicPort": rule["public_port"],
        "PrivateIpAddress": rule["private_ip_address"],
        "PrivatePort": rule["private_port"],
        "Description": rule.get("description") or "",
    }


def normalize_snat(rule):
    """Normalize a user SNAT rule to its comparison shape.

    The output-only ``NatGatewaySnatId`` is intentionally absent; current
    rules carry it (deletion addresses rules by it) but desired rules never
    do, so comparing raw dicts would never match.
    """
    return {
        "ResourceType": rule["resource_type"].upper(),
        "ResourceId": rule["resource_id"],
        "PrivateIpAddress": rule["private_ip_address"],
        "PublicIpAddresses": sorted(rule["public_ip_addresses"]),
        "Description": rule.get("description") or "",
    }


def _snat_compare(rule):
    """Project a SNAT rule to the attributes that describe the desired state.

    Excludes the output-only ``NatGatewaySnatId`` so current and desired
    rules compare on the attributes the user controls.
    """
    return {
        "ResourceType": rule["ResourceType"],
        "ResourceId": rule["ResourceId"],
        "PrivateIpAddress": rule["PrivateIpAddress"],
        "PublicIpAddresses": rule["PublicIpAddresses"],
        "Description": rule["Description"],
    }


def _dnat_key(rule):
    return (
        rule["IpProtocol"], rule["PublicIpAddress"], rule["PublicPort"],
        rule["PrivateIpAddress"], rule["PrivatePort"],
    )


def _snat_key(rule):
    return (rule["ResourceType"], rule["ResourceId"], rule["PrivateIpAddress"])


def reconcile(current, desired, key_fn, compare_fn):
    """Split desired against current into create, replace and delete sets.

    :param current: list of current rules (comparison shape plus any
        output-only fields the management path needs, e.g. SnatId).
    :param desired: list of desired rules in comparison shape.
    :param key_fn: identity function (key of a rule dict).
    :param compare_fn: projection of a rule to the attributes that define
        equality; output-only fields are excluded so current and desired
        rules compare on what the user controls.
    :returns: tuple of (to_create, to_replace, to_delete). ``to_replace`` is
        a list of (current_rule, desired_rule) pairs where the identity
        matches but the attributes differ; ``to_delete`` holds the surplus
        rules the caller only acts on when purge is enabled.
    """
    current_by_key = {key_fn(rule): rule for rule in current}
    to_create = []
    to_replace = []
    desired_keys = set()
    for rule in desired:
        key = key_fn(rule)
        desired_keys.add(key)
        existing = current_by_key.get(key)
        if existing is None:
            to_create.append(rule)
        elif compare_fn(existing) != compare_fn(rule):
            to_replace.append((existing, rule))
    to_delete = [rule for rule in current if key_fn(rule) not in desired_keys]
    return to_create, to_replace, to_delete


def _create_dnat(module, client, models, nat_gateway_id, rules):
    if not rules:
        return
    request = models.CreateNatGatewayDestinationIpPortTranslationNatRuleRequest()
    request.NatGatewayId = nat_gateway_id
    request.DestinationIpPortTranslationNatRules = [
        build_dnat_rule(models, rule) for rule in rules
    ]
    module.sdk_call(client.CreateNatGatewayDestinationIpPortTranslationNatRule, request)


def _delete_dnat(module, client, models, nat_gateway_id, rules):
    if not rules:
        return
    request = models.DeleteNatGatewayDestinationIpPortTranslationNatRuleRequest()
    request.NatGatewayId = nat_gateway_id
    request.DestinationIpPortTranslationNatRules = [
        build_dnat_rule(models, rule) for rule in rules
    ]
    module.sdk_call(client.DeleteNatGatewayDestinationIpPortTranslationNatRule, request)


def _create_snat(module, client, models, nat_gateway_id, rules):
    if not rules:
        return
    request = models.CreateNatGatewaySourceIpTranslationNatRuleRequest()
    request.NatGatewayId = nat_gateway_id
    request.SourceIpTranslationNatRules = [
        build_snat_rule(models, rule) for rule in rules
    ]
    module.sdk_call(client.CreateNatGatewaySourceIpTranslationNatRule, request)


def _delete_snat(module, client, models, nat_gateway_id, snat_ids):
    if not snat_ids:
        return
    request = models.DeleteNatGatewaySourceIpTranslationNatRuleRequest()
    request.NatGatewayId = nat_gateway_id
    request.NatGatewaySnatIds = snat_ids
    module.sdk_call(client.DeleteNatGatewaySourceIpTranslationNatRule, request)


def _split_replacements(replacements):
    """Split (current, desired) replacement pairs into delete and create lists.

    Deletion needs the current (remote) rule shape; creation needs the
    desired (user) rule shape, so the two halves are returned separately.
    """
    to_delete = [current for current, _desired in replacements]
    to_create = [desired for _current, desired in replacements]
    return to_delete, to_create


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "nat_gateway_id": {"type": "str", "required": True},
            "dnat_rules": {
                "type": "list",
                "elements": "dict",
                "default": [],
                "options": {
                    "ip_protocol": {"type": "str", "required": True},
                    "public_ip_address": {"type": "str", "required": True},
                    "public_port": {"type": "int", "required": True},
                    "private_ip_address": {"type": "str", "required": True},
                    "private_port": {"type": "int", "required": True},
                    "description": {"type": "str", "default": ""},
                },
            },
            "snat_rules": {
                "type": "list",
                "elements": "dict",
                "default": [],
                "options": {
                    "resource_type": {"type": "str", "default": "CVM"},
                    "resource_id": {"type": "str", "required": True},
                    "private_ip_address": {"type": "str", "required": True},
                    "public_ip_addresses": {"type": "list", "elements": "str", "required": True},
                    "description": {"type": "str", "default": ""},
                },
            },
            "purge": {"type": "bool", "default": True},
        },
        supports_check_mode=True,
    )
    module.require_sdk()

    nat_gateway_id = module.params["nat_gateway_id"]
    purge = module.params["purge"]
    desired_dnat = [normalize_dnat(rule) for rule in module.params["dnat_rules"]]
    desired_snat = [normalize_snat(rule) for rule in module.params["snat_rules"]]

    models, vpc_client = _load_vpc()
    client = module.create_client(vpc_client.VpcClient, "vpc.tencentcloudapi.com")

    try:
        gateway = find_gateway(module, client, models, nat_gateway_id)
    except Exception as exc:
        module.fail_json(
            msg="Tencent Cloud API request failed",
            error=str(exc),
            error_code=getattr(exc, "get_code", lambda: None)(),
            request_id=getattr(exc, "get_request_id", lambda: None)(),
        )
    if gateway is None:
        module.fail_json(msg="NAT gateway %s not found" % nat_gateway_id, nat_gateway_id=nat_gateway_id)

    current_dnat = list_dnat_rules(module, client, models, nat_gateway_id)
    current_snat = list_snat_rules(module, client, models, nat_gateway_id)

    dnat_create, dnat_replace, dnat_delete = reconcile(
        current_dnat, desired_dnat, _dnat_key, lambda rule: rule)
    snat_create, snat_replace, snat_delete = reconcile(
        current_snat, desired_snat, _snat_key, _snat_compare)

    dnat_delete = dnat_delete if purge else []
    snat_delete = snat_delete if purge else []

    dnat_del, dnat_new = _split_replacements(dnat_replace)
    snat_del, snat_new = _split_replacements(snat_replace)

    dnat_to_delete = dnat_delete + dnat_del
    dnat_to_create = dnat_create + dnat_new
    snat_to_delete_ids = sorted({
        rule["NatGatewaySnatId"] for rule in snat_delete + snat_del
        if rule["NatGatewaySnatId"]
    })
    snat_to_create = snat_create + snat_new

    changed = bool(dnat_to_create or dnat_to_delete or snat_to_create or snat_to_delete_ids)
    if not changed:
        module.exit_json(changed=False, dnat_rules=current_dnat, snat_rules=current_snat,
                         msg="NAT gateway rules are up to date")

    diff = maybe_diff(module, {
        "dnat_rules": current_dnat,
        "snat_rules": current_snat,
    }, {
        "dnat_rules": desired_dnat,
        "snat_rules": desired_snat,
    })
    if module.check_mode:
        module.exit_json(changed=True, **(diff or {}),
                         msg="Would reconcile %d DNAT and %d SNAT rules" % (
                             len(dnat_to_create) + len(dnat_to_delete),
                             len(snat_to_create) + len(snat_to_delete_ids)))

    # Deletes first so replaced rules never collide with creates on the
    # same identity.
    _delete_dnat(module, client, models, nat_gateway_id, dnat_to_delete)
    _delete_snat(module, client, models, nat_gateway_id, snat_to_delete_ids)
    _create_dnat(module, client, models, nat_gateway_id, dnat_to_create)
    _create_snat(module, client, models, nat_gateway_id, snat_to_create)

    updated_dnat = list_dnat_rules(module, client, models, nat_gateway_id)
    updated_snat = list_snat_rules(module, client, models, nat_gateway_id)
    module.exit_json(changed=True, **(diff or {}),
                     dnat_rules=updated_dnat, snat_rules=updated_snat,
                     msg="NAT gateway rules reconciled")


def main():
    run_module()


if __name__ == "__main__":
    main()
