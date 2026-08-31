#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type
DOCUMENTATION = r"""
---
module: gwlb_load_balancer
short_description: Manage Tencent Cloud Gateway Load Balancers
version_added: "0.14.0"
description: Creates, updates and deletes Gateway Load Balancer instances with deletion protection.
options:
  state: {type: str, choices: [present, absent], default: present, description: Desired state.}
  load_balancer_id: {type: str, description: Existing GWLB ID.}
  name: {type: str, description: GWLB name.}
  vpc_id: {type: str, description: VPC ID required for creation and immutable afterwards.}
  subnet_id: {type: str, description: Subnet ID required for creation and immutable afterwards.}
  charge_type: {type: str, default: POSTPAID_BY_HOUR, description: Creation-time billing type.}
  deletion_protection: {type: bool, description: Enable deletion protection.}
  tags: {type: dict, description: Creation-time tags.}
  retries: {type: int, default: 5, description: Number of retries for transient failures.}
  waiter_delay: {type: int, default: 5, description: Seconds between polling attempts.}
  waiter_timeout: {type: int, default: 120, description: Overall polling timeout in seconds.}
  user_agent: {type: str, default: ansible-collection.susunola.tencentcloud, description: User-Agent suffix.}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.gwlb_load_balancer:
    name: security-appliance
    vpc_id: vpc-xxxxxxxx
    subnet_id: subnet-xxxxxxxx
    deletion_protection: true
"""
RETURN = r"""load_balancer: {description: Effective GWLB metadata., type: dict, returned: always}"""
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import require_immutable_unchanged, sdk_error_payload


def _load():
    from tencentcloud.gwlb.v20240906 import models, gwlb_client

    return models, gwlb_client


def describe_request(models, p):
    r = models.DescribeGatewayLoadBalancersRequest()
    r.Offset, r.Limit = 0, 100
    if p.get("load_balancer_id"):
        r.LoadBalancerIds = [p["load_balancer_id"]]
    return r


def _tags(models, values):
    result = []
    for key, value in sorted((values or {}).items()):
        x = models.TagInfo()
        x.TagKey, x.TagValue = key, value
        result.append(x)
    return result


def create_request(models, p):
    r = models.CreateGatewayLoadBalancerRequest()
    r.VpcId, r.SubnetId, r.LoadBalancerName, r.Number, r.LBChargeType = p["vpc_id"], p["subnet_id"], p["name"], 1, p["charge_type"]
    r.Tags = _tags(models, p.get("tags"))
    return r


def update_request(models, load_balancer_id, name, protection):
    r = models.ModifyGatewayLoadBalancerAttributeRequest()
    r.LoadBalancerId, r.LoadBalancerName, r.DeleteProtect = load_balancer_id, name, protection
    return r


def delete_request(models, load_balancer_id):
    r = models.DeleteGatewayLoadBalancerRequest()
    r.LoadBalancerIds = [load_balancer_id]
    return r


def find(module, client, models, p):
    response = module.sdk_call(client.DescribeGatewayLoadBalancers, describe_request(models, p))
    matches = []
    for item in response.LoadBalancerSet or []:
        value = item._serialize(allow_none=True)
        if (p.get("load_balancer_id") and value.get("LoadBalancerId") == p["load_balancer_id"]) or (
            not p.get("load_balancer_id") and value.get("LoadBalancerName") == p.get("name")
        ):
            matches.append(value)
    if len(matches) > 1:
        module.fail_json(msg="Multiple GWLB instances matched; specify load_balancer_id")
    return matches[0] if matches else None


def comparable(v):
    return {
        "LoadBalancerName": v.get("LoadBalancerName"),
        "VpcId": v.get("VpcId"),
        "SubnetId": v.get("SubnetId"),
        "DeleteProtect": bool(v.get("DeleteProtect")),
    }


def run_module():
    spec = {
        "state": {"choices": ["present", "absent"], "default": "present"},
        "load_balancer_id": {},
        "name": {},
        "vpc_id": {},
        "subnet_id": {},
        "charge_type": {"default": "POSTPAID_BY_HOUR"},
        "deletion_protection": {"type": "bool"},
        "tags": {"type": "dict"},
    }
    module = TencentCloudModule(argument_spec=spec, required_one_of=[("load_balancer_id", "name")], supports_check_mode=True)
    p = module.params
    module.require_sdk()
    models, cm = _load()
    client = module.create_client(cm.GwlbClient, "gwlb.tencentcloudapi.com")
    try:
        current = find(module, client, models, p)
        if p["state"] == "absent":
            if not current:
                module.exit_json(changed=False, load_balancer=None)
            if current.get("DeleteProtect") and p.get("deletion_protection") is not False:
                module.fail_json(msg="set deletion_protection=false to authorize disabling protection before deletion")
            diff = maybe_diff(module, current, None)
            if not module.check_mode:
                if current.get("DeleteProtect"):
                    module.sdk_call(
                        client.ModifyGatewayLoadBalancerAttribute, update_request(models, current["LoadBalancerId"], current["LoadBalancerName"], False)
                    )
                module.sdk_call(client.DeleteGatewayLoadBalancer, delete_request(models, current["LoadBalancerId"]))
            module.exit_json(changed=True, **(diff or {}), load_balancer=None)
        if not current:
            missing = [k for k in ("name", "vpc_id", "subnet_id") if not p.get(k)]
            if missing:
                module.fail_json(msg="creation parameters are required for a new GWLB", missing=missing)
            target = {"LoadBalancerName": p["name"], "VpcId": p["vpc_id"], "SubnetId": p["subnet_id"], "DeleteProtect": bool(p.get("deletion_protection"))}
            diff = maybe_diff(module, None, target)
            if not module.check_mode:
                p["load_balancer_id"] = module.sdk_call(client.CreateGatewayLoadBalancer, create_request(models, p)).LoadBalancerIds[0]
                current = find(module, client, models, p)
            module.exit_json(changed=True, **(diff or {}), load_balancer=current if not module.check_mode else target)
        before = comparable(current)
        target = {
            "LoadBalancerName": p.get("name") or before["LoadBalancerName"],
            "VpcId": p.get("vpc_id") or before["VpcId"],
            "SubnetId": p.get("subnet_id") or before["SubnetId"],
            "DeleteProtect": p.get("deletion_protection") if p.get("deletion_protection") is not None else before["DeleteProtect"],
        }
        require_immutable_unchanged(module, before, target, ("VpcId", "SubnetId"), "GWLB")
        if before == target:
            module.exit_json(changed=False, load_balancer=current)
        diff = maybe_diff(module, before, target)
        if not module.check_mode:
            module.sdk_call(
                client.ModifyGatewayLoadBalancerAttribute,
                update_request(models, current["LoadBalancerId"], target["LoadBalancerName"], target["DeleteProtect"]),
            )
            p["load_balancer_id"] = current["LoadBalancerId"]
            current = find(module, client, models, p)
        module.exit_json(changed=True, **(diff or {}), load_balancer=current)
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
