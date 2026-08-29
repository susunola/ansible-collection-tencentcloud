#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
---
module: network_acl
short_description: Manage Tencent Cloud VPC network ACLs
version_added: "0.14.0"
description:
  - Manages network ACL lifecycle, exact ingress and egress rule sets, and exact subnet associations.
options:
  state: {description: Desired state., type: str, choices: [present, absent], default: present}
  network_acl_id: {description: Existing ACL ID., type: str}
  name: {description: ACL name., type: str}
  vpc_id: {description: Parent VPC ID., type: str}
  acl_type: {description: ACL type applied at creation., type: str}
  ingress:
    description: Exact ingress rule set.
    type: list
    elements: dict
    suboptions:
      protocol: {description: Network protocol., type: str, choices: [TCP, UDP, ICMP, ALL], default: ALL}
      port: {description: Port or range such as C(443) or C(8000-9000)., type: str}
      cidr: {description: IPv4 CIDR., type: str}
      ipv6_cidr: {description: IPv6 CIDR., type: str}
      action: {description: Rule action., type: str, choices: [ACCEPT, DROP], required: true}
      description: {description: Rule description., type: str, default: ''}
      priority: {description: Rule priority starting at one., type: int, required: true}
  egress:
    description: Exact egress rule set.
    type: list
    elements: dict
    suboptions:
      protocol: {description: Network protocol., type: str, choices: [TCP, UDP, ICMP, ALL], default: ALL}
      port: {description: Port or range such as C(443) or C(8000-9000)., type: str}
      cidr: {description: IPv4 CIDR., type: str}
      ipv6_cidr: {description: IPv6 CIDR., type: str}
      action: {description: Rule action., type: str, choices: [ACCEPT, DROP], required: true}
      description: {description: Rule description., type: str, default: ''}
      priority: {description: Rule priority starting at one., type: int, required: true}
  subnet_ids: {description: Exact set of associated subnet IDs., type: list, elements: str}
  tags: {description: Tags applied at creation., type: dict, default: {}}
  retries: {description: Number of retries for transient failures., type: int, default: 5}
  waiter_delay: {description: Seconds between polling attempts., type: int, default: 5}
  waiter_timeout: {description: Overall polling timeout in seconds., type: int, default: 120}
  user_agent: {description: User-Agent suffix., type: str, default: ansible-collection.susunola.tencentcloud}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''

EXAMPLES = r'''
- susunola.tencentcloud.network_acl:
    name: app-acl
    vpc_id: vpc-xxxxxxxx
    subnet_ids: [subnet-xxxxxxxx]
    ingress:
      - {protocol: TCP, port: '443', cidr: 10.0.0.0/8, action: ACCEPT, priority: 1}
    egress:
      - {protocol: ALL, cidr: 0.0.0.0/0, action: ACCEPT, priority: 1}
'''

RETURN = r'''
network_acl: {description: Network ACL metadata., type: dict, returned: always}
'''

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff


def _load_vpc():
    from tencentcloud.vpc.v20170312 import models, vpc_client

    return models, vpc_client


def build_describe_request(models, acl_id=None, name=None, vpc_id=None, offset=0):
    request = models.DescribeNetworkAclsRequest()
    request.Offset, request.Limit = offset, 100
    if acl_id:
        request.NetworkAclIds = [acl_id]
    else:
        filters = []
        for key, value in (("network-acl-name", name), ("vpc-id", vpc_id)):
            if value:
                item = models.Filter()
                item.Name, item.Values = key, [value]
                filters.append(item)
        if filters:
            request.Filters = filters
    return request


def build_entries(models, values):
    result = []
    for value in values or []:
        item = models.NetworkAclEntry()
        item.Protocol, item.Action, item.Priority = value["protocol"], value["action"], value["priority"]
        item.Description = value.get("description", "")
        for api, key in (("Port", "port"), ("CidrBlock", "cidr"), ("Ipv6CidrBlock", "ipv6_cidr")):
            if value.get(key):
                setattr(item, api, value[key])
        result.append(item)
    return result


def build_create_request(models, params):
    request = models.CreateNetworkAclRequest()
    request.VpcId, request.NetworkAclName = params["vpc_id"], params["name"]
    if params.get("acl_type"):
        request.NetworkAclType = params["acl_type"]
    if params.get("tags"):
        request.Tags = []
        for key, value in sorted(params["tags"].items()):
            tag = models.Tag()
            tag.Key, tag.Value = str(key), str(value)
            request.Tags.append(tag)
    return request


def build_entries_request(models, acl_id, ingress, egress):
    request = models.ModifyNetworkAclEntriesRequest()
    request.NetworkAclId = acl_id
    entries = models.NetworkAclEntrySet()
    entries.Ingress, entries.Egress = build_entries(models, ingress), build_entries(models, egress)
    request.NetworkAclEntrySet = entries
    return request


def build_subnets_request(models, request_class, acl_id, subnet_ids):
    request = request_class()
    request.NetworkAclId, request.SubnetIds = acl_id, subnet_ids
    return request


def _dict(value):
    return value._serialize(allow_none=True)


def find_acl(module, client, models, acl_id, name, vpc_id):
    offset, matches = 0, []
    while True:
        response = module.sdk_call(client.DescribeNetworkAcls, build_describe_request(models, acl_id, name, vpc_id, offset))
        items = list(getattr(response, "NetworkAclSet", None) or [])
        matches.extend(_dict(item) for item in items)
        offset += len(items)
        if acl_id or not items or offset >= int(getattr(response, "TotalCount", 0) or 0):
            break
    if len(matches) > 1:
        module.fail_json(msg="Multiple network ACLs match; specify network_acl_id")
    return matches[0] if matches else None


def _rules(values):
    result = []
    for value in values or []:
        result.append(
            {
                "protocol": value.get("Protocol") or value.get("protocol", "ALL"),
                "port": value.get("Port") or value.get("port"),
                "cidr": value.get("CidrBlock") or value.get("cidr"),
                "ipv6_cidr": value.get("Ipv6CidrBlock") or value.get("ipv6_cidr"),
                "action": value.get("Action") or value.get("action"),
                "description": value.get("Description") or value.get("description", ""),
                "priority": value.get("Priority") or value.get("priority"),
            }
        )
    return sorted(result, key=lambda x: x["priority"])


def _subnets(values):
    return sorted(x if isinstance(x, str) else x.get("SubnetId") for x in (values or []))


def run_module():
    rule = {
        "type": "dict",
        "options": {
            "protocol": {"type": "str", "choices": ["TCP", "UDP", "ICMP", "ALL"], "default": "ALL"},
            "port": {"type": "str"},
            "cidr": {"type": "str"},
            "ipv6_cidr": {"type": "str"},
            "action": {"type": "str", "choices": ["ACCEPT", "DROP"], "required": True},
            "description": {"type": "str", "default": ""},
            "priority": {"type": "int", "required": True},
        },
    }
    module = TencentCloudModule(
        argument_spec={
            "state": {"type": "str", "choices": ["present", "absent"], "default": "present"},
            "network_acl_id": {"type": "str"},
            "name": {"type": "str"},
            "vpc_id": {"type": "str"},
            "acl_type": {"type": "str"},
            "ingress": dict(rule, type="list", elements="dict"),
            "egress": dict(rule, type="list", elements="dict"),
            "subnet_ids": {"type": "list", "elements": "str"},
            "tags": {"type": "dict", "default": {}},
        },
        required_one_of=[("network_acl_id", "name")],
        supports_check_mode=True,
    )
    p = module.params
    module.require_sdk()
    models, client_module = _load_vpc()
    client = module.create_client(client_module.VpcClient, "vpc.tencentcloudapi.com")
    try:
        current = find_acl(module, client, models, p["network_acl_id"], p["name"], p["vpc_id"])
        if p["state"] == "absent":
            if current is None:
                module.exit_json(changed=False, network_acl=None, msg="Network ACL is absent")
            diff = maybe_diff(module, current, None)
            if module.check_mode:
                module.exit_json(changed=True, **(diff or {}), network_acl=current, msg="Would delete network ACL")
            request = models.DeleteNetworkAclRequest()
            request.NetworkAclId = current["NetworkAclId"]
            module.sdk_call(client.DeleteNetworkAcl, request)
            module.exit_json(changed=True, **(diff or {}), network_acl=None, msg="Network ACL deleted")
        if current is None and (not p["name"] or not p["vpc_id"]):
            module.fail_json(msg="name and vpc_id are required when creating a network ACL")
        desired_rules = {"IngressEntries": _rules(p["ingress"] or []), "EgressEntries": _rules(p["egress"] or [])}
        desired_subnets = _subnets(p["subnet_ids"] or [])
        desired = {"NetworkAclName": p["name"], **desired_rules, "SubnetIds": desired_subnets}
        was_created = current is None
        if was_created:
            diff = maybe_diff(module, None, desired)
            if module.check_mode:
                module.exit_json(changed=True, **(diff or {}), network_acl=None, msg="Would create network ACL")
            response = module.sdk_call(client.CreateNetworkAcl, build_create_request(models, p))
            current = find_acl(module, client, models, response.NetworkAcl.NetworkAclId, None, None)
        acl_id = current["NetworkAclId"]
        current_rules = {"IngressEntries": _rules(current.get("IngressEntries")), "EgressEntries": _rules(current.get("EgressEntries"))}
        current_subnets = _subnets(current.get("SubnetSet"))
        name_drift = current.get("NetworkAclName") != p["name"]
        rules_drift = current_rules != desired_rules
        subnet_drift = current_subnets != desired_subnets
        if not was_created and not name_drift and not rules_drift and not subnet_drift:
            module.exit_json(changed=False, network_acl=current, msg="Network ACL is up to date")
        diff = maybe_diff(module, current, desired)
        if module.check_mode:
            module.exit_json(changed=True, **(diff or {}), network_acl=current, msg="Would reconcile network ACL")
        if name_drift:
            request = models.ModifyNetworkAclAttributeRequest()
            request.NetworkAclId, request.NetworkAclName = acl_id, p["name"]
            module.sdk_call(client.ModifyNetworkAclAttribute, request)
        if rules_drift:
            module.sdk_call(client.ModifyNetworkAclEntries, build_entries_request(models, acl_id, p["ingress"] or [], p["egress"] or []))
        remove, add = sorted(set(current_subnets) - set(desired_subnets)), sorted(set(desired_subnets) - set(current_subnets))
        if remove:
            module.sdk_call(client.DisassociateNetworkAclSubnets, build_subnets_request(models, models.DisassociateNetworkAclSubnetsRequest, acl_id, remove))
        if add:
            module.sdk_call(client.AssociateNetworkAclSubnets, build_subnets_request(models, models.AssociateNetworkAclSubnetsRequest, acl_id, add))
        updated = find_acl(module, client, models, acl_id, None, None)
        module.exit_json(changed=True, **(diff or {}), network_acl=updated, msg="Network ACL reconciled")
    except Exception as exc:
        module.fail_json(
            msg="Tencent Cloud API request failed",
            error=str(exc),
            error_code=getattr(exc, "get_code", lambda: None)(),
            request_id=getattr(exc, "get_request_id", lambda: None)(),
        )


def main():
    run_module()


if __name__ == "__main__":
    main()
