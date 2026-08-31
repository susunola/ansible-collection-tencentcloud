#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type
DOCUMENTATION = r"""
---
module: ckafka_route
short_description: Manage Tencent Cloud CKafka access routes
version_added: "0.14.0"
description: Creates and deletes VPC, public or internal-support CKafka access routes and detects immutable drift.
options:
  state: {type: str, choices: [present, absent], default: present, description: Desired state.}
  instance_id: {type: str, required: true, description: CKafka instance ID.}
  route_id: {type: int, description: "Existing route ID, recommended for deletion."}
  network_type: {type: int, choices: [1, 3, 7], default: 3, description: "Public, VPC or internal-support route type."}
  access_type: {type: int, choices: [0, 1, 3, 4, 5], default: 0, description: Authentication and transport mode.}
  vpc_id: {type: str, description: VPC ID required for VPC routes.}
  subnet_id: {type: str, description: Subnet ID required for VPC routes.}
  public_bandwidth: {type: int, description: Public bandwidth required for public routes.}
  note: {type: str, default: '', description: Route note.}
  security_group_ids: {type: list, elements: str, default: [], description: Ordered associated security groups.}
  ip_whitelist: {type: list, elements: str, default: [], description: Initial public-route IP whitelist.}
  retries: {description: Number of retries for transient failures., type: int, default: 5}
  waiter_delay: {description: Seconds between polling attempts., type: int, default: 5}
  waiter_timeout: {description: Overall polling timeout in seconds., type: int, default: 120}
  user_agent: {description: User-Agent suffix., type: str, default: ansible-collection.susunola.tencentcloud}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.ckafka_route:
    instance_id: ckafka-xxxxxxxx
    network_type: 3
    access_type: 3
    vpc_id: vpc-xxxxxxxx
    subnet_id: subnet-xxxxxxxx
    security_group_ids: [sg-xxxxxxxx]
"""
RETURN = r"""route: {description: CKafka route metadata., type: dict, returned: always}"""

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import require_immutable_unchanged, sdk_error_payload


def _load():
    from tencentcloud.ckafka.v20190819 import ckafka_client, models

    return models, ckafka_client


def describe_request(models, instance_id, route_id=None):
    request = models.DescribeRouteRequest()
    request.InstanceId, request.RouteId = instance_id, route_id
    return request


def create_request(models, p):
    request = models.CreateRouteRequest()
    request.InstanceId, request.VipType, request.AccessType = p["instance_id"], p["network_type"], p["access_type"]
    request.VpcId, request.SubnetId, request.PublicNetwork = p.get("vpc_id"), p.get("subnet_id"), p.get("public_bandwidth")
    request.Note, request.SecurityGroupIds, request.IpWhitelist = p["note"], p["security_group_ids"], p["ip_whitelist"]
    return request


def delete_request(models, instance_id, route_id):
    request = models.DeleteRouteRequest()
    request.InstanceId, request.RouteId = instance_id, route_id
    return request


def find(module, client, models, p):
    response = module.sdk_call(client.DescribeRoute, describe_request(models, p["instance_id"], p.get("route_id")))
    items = list(response.Result.Routers or [])
    for item in items:
        value = item._serialize(allow_none=True)
        if p.get("route_id") and int(value.get("RouteId") or 0) == p["route_id"]:
            return value
        if (
            not p.get("route_id")
            and value.get("VipType") == p["network_type"]
            and value.get("AccessType") == p["access_type"]
            and (value.get("VpcId") or None) == p.get("vpc_id")
            and (value.get("Subnet") or None) == p.get("subnet_id")
        ):
            return value
    return None


def comparable(value):
    return {
        "VipType": value.get("VipType"),
        "AccessType": value.get("AccessType"),
        "VpcId": value.get("VpcId") or None,
        "Subnet": value.get("Subnet") or None,
        "Note": value.get("Note") or "",
    }


def desired(p):
    return {"VipType": p["network_type"], "AccessType": p["access_type"], "VpcId": p.get("vpc_id"), "Subnet": p.get("subnet_id"), "Note": p["note"]}


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "state": {"choices": ["present", "absent"], "default": "present"},
            "instance_id": {"required": True},
            "route_id": {"type": "int"},
            "network_type": {"type": "int", "choices": [1, 3, 7], "default": 3},
            "access_type": {"type": "int", "choices": [0, 1, 3, 4, 5], "default": 0},
            "vpc_id": {},
            "subnet_id": {},
            "public_bandwidth": {"type": "int"},
            "note": {"default": ""},
            "security_group_ids": {"type": "list", "elements": "str", "default": []},
            "ip_whitelist": {"type": "list", "elements": "str", "default": []},
        },
        supports_check_mode=True,
    )
    p = module.params
    needs_identity = p["state"] == "present" or p["route_id"] is None
    if needs_identity and p["network_type"] == 3 and (not p["vpc_id"] or not p["subnet_id"]):
        module.fail_json(msg="vpc_id and subnet_id are required for VPC routes")
    if needs_identity and p["network_type"] == 1 and p["public_bandwidth"] is None:
        module.fail_json(msg="public_bandwidth is required for public routes")
    if p["public_bandwidth"] is not None and p["public_bandwidth"] % 3:
        module.fail_json(msg="public_bandwidth must be a multiple of 3")
    module.require_sdk()
    models, cm = _load()
    client = module.create_client(cm.CkafkaClient, "ckafka.tencentcloudapi.com")
    try:
        current = find(module, client, models, p)
        if p["state"] == "absent":
            if not current:
                module.exit_json(changed=False, route=None)
            diff = maybe_diff(module, current, None)
            if not module.check_mode:
                module.sdk_call(client.DeleteRoute, delete_request(models, p["instance_id"], current["RouteId"]))
            module.exit_json(changed=True, **(diff or {}), route=current if module.check_mode else None)
        target, before = desired(p), comparable(current) if current else None
        if before == target:
            module.exit_json(changed=False, route=current)
        diff = maybe_diff(module, before, target)
        if current:
            require_immutable_unchanged(module, before, target, tuple(target), "CKafka route")
        if not module.check_mode:
            module.sdk_call(client.CreateRoute, create_request(models, p))
            current = find(module, client, models, p)
        module.exit_json(changed=True, **(diff or {}), route=current)
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
