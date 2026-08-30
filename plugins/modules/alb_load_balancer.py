#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function
__metaclass__ = type
DOCUMENTATION = r'''
---
module: alb_load_balancer
short_description: Manage Tencent Cloud Application Load Balancers
version_added: "0.14.0"
description: Creates, updates and deletes ALB instances, including address-type conversion and deletion protection.
options:
  state: {type: str, choices: [present, absent], default: present, description: Desired state.}
  load_balancer_id: {type: str, description: Existing ALB ID.}
  name: {type: str, description: ALB name.}
  address_type: {type: str, choices: [Internet, Intranet], description: Public or private address type.}
  vpc_id: {type: str, description: VPC ID; immutable after creation.}
  zone_mappings: {type: list, elements: dict, description: SDK ZoneMappingsItem payloads used for creation or address conversion.}
  ip_version: {type: str, choices: [IPv4, IPv6], default: IPv4, description: Address IP version; immutable after creation.}
  charge_type: {type: str, default: POSTPAID_BY_HOUR, description: Billing charge type used during creation.}
  bandwidth_package_id: {type: str, description: Optional bandwidth package ID.}
  internet_address_type: {type: str, choices: [EIP, AntiDDoSEIP, AnycastEIP, HighQualityEIP, ResidentialEIP], default: EIP, description: Creation-time EIP type.}
  deletion_protection: {type: bool, description: Enable deletion protection.}
  deletion_protection_reason: {type: str, default: Managed by Ansible, description: Protection reason.}
  tags: {type: dict, description: Creation-time tags.}
  client_token: {type: str, description: Optional idempotency token.}
  retries: {type: int, default: 5, description: Number of retries for transient failures.}
  waiter_delay: {type: int, default: 5, description: Seconds between polling attempts.}
  waiter_timeout: {type: int, default: 120, description: Overall polling timeout in seconds.}
  user_agent: {type: str, default: ansible-collection.susunola.tencentcloud, description: User-Agent suffix.}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''
EXAMPLES = r'''
- susunola.tencentcloud.alb_load_balancer:
    name: public-app
    address_type: Internet
    vpc_id: vpc-xxxxxxxx
    zone_mappings:
      - {ZoneId: ap-guangzhou-3, SubnetId: subnet-xxxxxxxx}
      - {ZoneId: ap-guangzhou-4, SubnetId: subnet-yyyyyyyy}
    deletion_protection: true
'''
RETURN = r'''load_balancer: {description: Effective ALB metadata., type: dict, returned: always}'''
import json
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import require_immutable_unchanged, sdk_error_payload


def _load():
    from tencentcloud.alb.v20251030 import models, alb_client
    return models, alb_client
def _model(cls, value):
    if value is None: return None
    x = cls(); x.from_json_string(json.dumps(value)); return x
def list_request(models):
    r = models.DescribeLoadBalancersRequest(); r.MaxResults = 100; return r
def describe_request(models, load_balancer_id):
    r = models.DescribeLoadBalancerDetailRequest(); r.LoadBalancerId = load_balancer_id; return r
def _tags(models, values):
    result = []
    for key, value in sorted((values or {}).items()): x = models.TagInfo(); x.TagKey, x.TagValue = key, value; result.append(x)
    return result
def create_request(models, p):
    r = models.CreateLoadBalancerRequest(); r.AddressType, r.VpcId, r.AddressIpVersion, r.LoadBalancerName = p["address_type"], p["vpc_id"], p["ip_version"], p["name"]; r.ZoneMappings = [_model(models.ZoneMappingsItem, x) for x in p["zone_mappings"]]; r.InternetAddressType, r.ClientToken = p["internet_address_type"], p.get("client_token"); billing = models.LoadBalancerBillingConfig(); billing.ChargeType, billing.BandwidthPackageId = p["charge_type"], p.get("bandwidth_package_id"); r.LoadBalancerBillingConfig = billing; protection = models.DeletionProtectionConfig(); protection.DeletionProtectionEnabled, protection.Reason = bool(p.get("deletion_protection")), p["deletion_protection_reason"]; r.DeleteProtection, r.Tags = protection, _tags(models, p.get("tags")); return r
def update_request(models, p, load_balancer_id, name, protection):
    r = models.ModifyLoadBalancerAttributesRequest(); r.LoadBalancerId, r.LoadBalancerName, r.DeletionProtection, r.ClientToken = load_balancer_id, name, protection, p.get("client_token"); return r
def address_request(models, p, load_balancer_id, address_type):
    r = models.ModifyLoadBalancerAddressTypeRequest(); r.LoadBalancerId, r.AddressType, r.BandwidthPackageId = load_balancer_id, address_type, p.get("bandwidth_package_id"); r.ZoneMappings = [_model(models.ZoneMappingsItem, x) for x in p.get("zone_mappings") or []]; return r
def delete_request(models, p, load_balancer_id):
    r = models.DeleteLoadBalancersRequest(); r.LoadBalancerIds, r.ClientToken = [load_balancer_id], p.get("client_token"); return r
def find(module, client, models, p):
    response = module.sdk_call(client.DescribeLoadBalancers, list_request(models)); matches = []
    for item in response.LoadBalancers or []:
        value = item._serialize(allow_none=True)
        if (p.get("load_balancer_id") and value.get("LoadBalancerId") == p["load_balancer_id"]) or (not p.get("load_balancer_id") and value.get("LoadBalancerName") == p.get("name")): matches.append(value)
    if len(matches) > 1: module.fail_json(msg="Multiple ALBs matched; specify load_balancer_id")
    if not matches: return None
    value = module.sdk_call(client.DescribeLoadBalancerDetail, describe_request(models, matches[0]["LoadBalancerId"])).LoadBalancerDetail._serialize(allow_none=True); return value
def _protected(value): return bool((value.get("DeletionProtection") or {}).get("DeletionProtectionEnabled"))
def run_module():
    spec = {"state": {"choices": ["present", "absent"], "default": "present"}, "load_balancer_id": {}, "name": {}, "address_type": {"choices": ["Internet", "Intranet"]}, "vpc_id": {}, "zone_mappings": {"type": "list", "elements": "dict"}, "ip_version": {"choices": ["IPv4", "IPv6"], "default": "IPv4"}, "charge_type": {"default": "POSTPAID_BY_HOUR"}, "bandwidth_package_id": {}, "internet_address_type": {"choices": ["EIP", "AntiDDoSEIP", "AnycastEIP", "HighQualityEIP", "ResidentialEIP"], "default": "EIP"}, "deletion_protection": {"type": "bool"}, "deletion_protection_reason": {"default": "Managed by Ansible"}, "tags": {"type": "dict"}, "client_token": {"no_log": False}}
    module = TencentCloudModule(argument_spec=spec, required_one_of=[("load_balancer_id", "name")], supports_check_mode=True); p = module.params; module.require_sdk(); models, cm = _load(); client = module.create_client(cm.AlbClient, "alb.tencentcloudapi.com")
    try:
        current = find(module, client, models, p)
        if p["state"] == "absent":
            if not current: module.exit_json(changed=False, load_balancer=None)
            if _protected(current) and p.get("deletion_protection") is not False: module.fail_json(msg="set deletion_protection=false to authorize disabling protection before deletion")
            diff = maybe_diff(module, current, None)
            if not module.check_mode:
                if _protected(current): module.sdk_call(client.ModifyLoadBalancerAttributes, update_request(models, p, current["LoadBalancerId"], current["LoadBalancerName"], False))
                module.sdk_call(client.DeleteLoadBalancers, delete_request(models, p, current["LoadBalancerId"]))
            module.exit_json(changed=True, **(diff or {}), load_balancer=None)
        if not current:
            missing = [k for k in ("name", "address_type", "vpc_id", "zone_mappings") if not p.get(k)]
            if missing: module.fail_json(msg="creation parameters are required for a new ALB", missing=missing)
            target = {"LoadBalancerName": p["name"], "AddressType": p["address_type"], "VpcId": p["vpc_id"], "AddressIpVersion": p["ip_version"], "DeletionProtection": bool(p.get("deletion_protection"))}; diff = maybe_diff(module, None, target)
            if not module.check_mode: p["load_balancer_id"] = module.sdk_call(client.CreateLoadBalancer, create_request(models, p)).LoadBalancerId; current = find(module, client, models, p)
            module.exit_json(changed=True, **(diff or {}), load_balancer=current if not module.check_mode else target)
        before = {"LoadBalancerName": current.get("LoadBalancerName"), "AddressType": current.get("AddressType"), "VpcId": current.get("VpcId"), "AddressIpVersion": current.get("AddressIpVersion"), "DeletionProtection": _protected(current)}; target = {"LoadBalancerName": p.get("name") or before["LoadBalancerName"], "AddressType": p.get("address_type") or before["AddressType"], "VpcId": p.get("vpc_id") or before["VpcId"], "AddressIpVersion": p.get("ip_version") or before["AddressIpVersion"], "DeletionProtection": p.get("deletion_protection") if p.get("deletion_protection") is not None else before["DeletionProtection"]}; require_immutable_unchanged(module, before, target, ("VpcId", "AddressIpVersion"), "ALB")
        if before == target: module.exit_json(changed=False, load_balancer=current)
        diff = maybe_diff(module, before, target)
        if not module.check_mode:
            if before["AddressType"] != target["AddressType"]: module.sdk_call(client.ModifyLoadBalancerAddressType, address_request(models, p, current["LoadBalancerId"], target["AddressType"]))
            if before["LoadBalancerName"] != target["LoadBalancerName"] or before["DeletionProtection"] != target["DeletionProtection"]: module.sdk_call(client.ModifyLoadBalancerAttributes, update_request(models, p, current["LoadBalancerId"], target["LoadBalancerName"], target["DeletionProtection"]))
            p["load_balancer_id"] = current["LoadBalancerId"]; current = find(module, client, models, p)
        module.exit_json(changed=True, **(diff or {}), load_balancer=current)
    except Exception as exc: module.fail_json(**sdk_error_payload(exc))
def main(): run_module()
if __name__ == "__main__": main()
