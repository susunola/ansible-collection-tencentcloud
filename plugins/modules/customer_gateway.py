#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
---
module: customer_gateway
short_description: Manage Tencent Cloud VPN customer gateways
version_added: "0.14.0"
description:
  - Creates, updates and deletes the remote peer definition used by IPsec VPN connections.
  - Supports idempotency, check mode, diff output and bounded convergence polling.
options:
  state: {description: Desired state., type: str, choices: [present, absent], default: present}
  customer_gateway_id: {description: Existing customer gateway ID., type: str}
  name: {description: Customer gateway name., type: str}
  ip_address: {description: Public IPv4 address of the remote VPN device., type: str}
  bgp_asn: {description: BGP autonomous system number., type: int}
  tags: {description: Tags applied when creating the gateway., type: dict, default: {}}
  retries: {description: Number of retries for transient SDK failures., type: int, default: 5}
  waiter_delay: {description: Seconds between polling attempts., type: int, default: 5}
  waiter_timeout: {description: Overall polling timeout in seconds., type: int, default: 120}
  user_agent: {description: User-Agent suffix for API requests., type: str, default: ansible-collection.susunola.tencentcloud}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''

EXAMPLES = r'''
- name: Define an office VPN peer
  susunola.tencentcloud.customer_gateway:
    name: office-peer
    ip_address: 203.0.113.10
    bgp_asn: 65001

- name: Remove the peer
  susunola.tencentcloud.customer_gateway:
    customer_gateway_id: cgw-xxxxxxxx
    state: absent
'''

RETURN = r'''
customer_gateway:
  description: Customer gateway metadata.
  type: dict
  returned: always
'''

import time

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff


def _load_vpc():
    from tencentcloud.vpc.v20170312 import models, vpc_client
    return models, vpc_client


def build_describe_request(models, customer_gateway_id=None, name=None, offset=0):
    request = models.DescribeCustomerGatewaysRequest()
    request.Offset, request.Limit = offset, 100
    if customer_gateway_id:
        request.CustomerGatewayIds = [customer_gateway_id]
    elif name:
        item = models.Filter()
        item.Name, item.Values = "customer-gateway-name", [name]
        request.Filters = [item]
    return request


def build_create_request(models, params):
    request = models.CreateCustomerGatewayRequest()
    request.CustomerGatewayName = params["name"]
    request.IpAddress = params["ip_address"]
    if params.get("bgp_asn") is not None:
        request.BgpAsn = params["bgp_asn"]
    if params.get("tags"):
        request.Tags = []
        for key, value in sorted(params["tags"].items()):
            tag = models.Tag()
            tag.Key, tag.Value = str(key), str(value)
            request.Tags.append(tag)
    return request


def build_update_request(models, gateway_id, name, bgp_asn):
    request = models.ModifyCustomerGatewayAttributeRequest()
    request.CustomerGatewayId = gateway_id
    request.CustomerGatewayName = name
    if bgp_asn is not None:
        request.BgpAsn = bgp_asn
    return request


def build_delete_request(models, gateway_id):
    request = models.DeleteCustomerGatewayRequest()
    request.CustomerGatewayId = gateway_id
    return request


def _serialize(value):
    return value._serialize(allow_none=True)


def find_gateway(module, client, models, gateway_id, name):
    offset, matches = 0, []
    while True:
        response = module.sdk_call(
            client.DescribeCustomerGateways,
            build_describe_request(models, gateway_id, name, offset),
        )
        items = list(getattr(response, "CustomerGatewaySet", None) or [])
        matches.extend(_serialize(item) for item in items)
        offset += len(items)
        if gateway_id or not items or offset >= int(getattr(response, "TotalCount", 0) or 0):
            break
    if len(matches) > 1:
        module.fail_json(msg="Multiple customer gateways have the requested name", name=name)
    return matches[0] if matches else None


def wait_for_gateway(module, client, models, gateway_id, desired=None, absent=False):
    deadline = time.time() + module.params["waiter_timeout"]
    while True:
        current = find_gateway(module, client, models, gateway_id, None)
        if absent and current is None:
            return None
        if not absent and current and all(current.get(k) == v for k, v in desired.items()):
            return current
        if time.time() >= deadline:
            module.fail_json(
                msg="Timed out waiting for customer gateway convergence",
                customer_gateway=current,
                expected="absent" if absent else desired,
            )
        time.sleep(module.params["waiter_delay"])


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "state": {"type": "str", "choices": ["present", "absent"], "default": "present"},
            "customer_gateway_id": {"type": "str"},
            "name": {"type": "str"},
            "ip_address": {"type": "str"},
            "bgp_asn": {"type": "int"},
            "tags": {"type": "dict", "default": {}},
        },
        required_one_of=[("customer_gateway_id", "name")],
        required_if=[("state", "present", ["name"])],
        supports_check_mode=True,
    )
    p = module.params
    module.require_sdk()
    models, client_module = _load_vpc()
    client = module.create_client(client_module.VpcClient, "vpc.tencentcloudapi.com")
    try:
        current = find_gateway(module, client, models, p["customer_gateway_id"], p["name"])
        if p["state"] == "absent":
            if current is None:
                module.exit_json(changed=False, customer_gateway=None, msg="Customer gateway is absent")
            diff = maybe_diff(module, current, None)
            if module.check_mode:
                module.exit_json(changed=True, **(diff or {}), customer_gateway=current, msg="Would delete customer gateway")
            module.sdk_call(
                client.DeleteCustomerGateway,
                build_delete_request(models, current["CustomerGatewayId"]),
            )
            wait_for_gateway(module, client, models, current["CustomerGatewayId"], absent=True)
            module.exit_json(changed=True, **(diff or {}), customer_gateway=None, msg="Customer gateway deleted")

        if current is None:
            if not p["ip_address"]:
                module.fail_json(msg="ip_address is required when creating a customer gateway")
            desired = {"CustomerGatewayName": p["name"], "IpAddress": p["ip_address"]}
            if p["bgp_asn"] is not None:
                desired["BgpAsn"] = p["bgp_asn"]
            diff = maybe_diff(module, None, desired)
            if module.check_mode:
                module.exit_json(changed=True, **(diff or {}), customer_gateway=None, msg="Would create customer gateway")
            response = module.sdk_call(client.CreateCustomerGateway, build_create_request(models, p))
            current = wait_for_gateway(module, client, models, response.CustomerGateway.CustomerGatewayId, desired)
            module.exit_json(changed=True, **(diff or {}), customer_gateway=current, msg="Customer gateway created")

        if p["ip_address"] and current.get("IpAddress") != p["ip_address"]:
            module.fail_json(
                msg="ip_address is immutable; replace the customer gateway to change it",
                customer_gateway=current,
            )
        desired = {"CustomerGatewayName": p["name"]}
        if p["bgp_asn"] is not None:
            desired["BgpAsn"] = p["bgp_asn"]
        changed = any(current.get(key) != value for key, value in desired.items())
        if not changed:
            module.exit_json(changed=False, customer_gateway=current, msg="Customer gateway is up to date")
        diff = maybe_diff(module, current, desired)
        if module.check_mode:
            module.exit_json(changed=True, **(diff or {}), customer_gateway=current, msg="Would update customer gateway")
        request = build_update_request(models, current["CustomerGatewayId"], p["name"], p["bgp_asn"])
        module.sdk_call(client.ModifyCustomerGatewayAttribute, request)
        current = wait_for_gateway(module, client, models, current["CustomerGatewayId"], desired)
        module.exit_json(changed=True, **(diff or {}), customer_gateway=current, msg="Customer gateway updated")
    except Exception as exc:
        module.fail_json(
            msg="Tencent Cloud API request failed", error=str(exc),
            error_code=getattr(exc, "get_code", lambda: None)(),
            request_id=getattr(exc, "get_request_id", lambda: None)(),
        )


def main():
    run_module()


if __name__ == "__main__":
    main()
