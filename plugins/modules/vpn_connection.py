#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
---
module: vpn_connection
short_description: Manage Tencent Cloud IPsec VPN connections
version_added: "0.14.0"
description:
  - Manages an IPsec connection between a VPN gateway and customer gateway.
  - Reconciles tunnel name, customer gateway, SPD routes, negotiation mode and DPD settings.
options:
  state: {description: Desired state., type: str, choices: [present, absent], default: present}
  vpn_connection_id: {description: Existing VPN connection ID., type: str}
  name: {description: VPN connection name., type: str}
  vpn_gateway_id: {description: Parent VPN gateway ID., type: str}
  customer_gateway_id: {description: Remote customer gateway ID., type: str}
  vpc_id: {description: VPC ID used when creating the connection., type: str}
  pre_shared_key: {description: IPsec pre-shared key; used on create or explicit rotation., type: str}
  rotate_pre_shared_key: {description: Explicitly replace the pre-shared key during this run., type: bool, default: false}
  security_policy_databases:
    description: Exact local and remote CIDR pairs for policy-based routing.
    type: list
    elements: dict
    suboptions:
      local_cidr: {description: Local VPC CIDR., type: str, required: true}
      remote_cidr: {description: Remote network CIDR., type: str, required: true}
  route_type: {description: Connection route type applied at creation., type: str, choices: [StaticRoute, BgpRoute, Policy], default: Policy}
  negotiation_type: {description: IKE negotiation type., type: str, choices: [active, passive, flowTrigger]}
  dpd_enabled: {description: Enable dead peer detection., type: bool}
  dpd_timeout: {description: Dead peer detection timeout in seconds., type: int}
  dpd_action: {description: Action after DPD timeout., type: str, choices: [clear, restart]}
  tags: {description: Tags applied at creation., type: dict, default: {}}
  retries: {description: Number of retries for transient failures., type: int, default: 5}
  waiter_delay: {description: Seconds between polling attempts., type: int, default: 5}
  waiter_timeout: {description: Overall polling timeout in seconds., type: int, default: 120}
  user_agent: {description: User-Agent suffix., type: str, default: ansible-collection.susunola.tencentcloud}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''

EXAMPLES = r'''
- susunola.tencentcloud.vpn_connection:
    name: office-tunnel
    vpn_gateway_id: vpngw-xxxxxxxx
    customer_gateway_id: cgw-xxxxxxxx
    vpc_id: vpc-xxxxxxxx
    pre_shared_key: '{{ vault_vpn_psk }}'
    security_policy_databases:
      - local_cidr: 10.0.0.0/16
        remote_cidr: 192.168.0.0/16
'''

RETURN = r'''
vpn_connection: {description: VPN connection metadata., type: dict, returned: always}
'''

import time

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff


def _load_vpc():
    from tencentcloud.vpc.v20170312 import models, vpc_client
    return models, vpc_client


def _policies(values):
    return sorted(
        ({"LocalCidrBlock": x.get("LocalCidrBlock") or x.get("local_cidr"),
          "RemoteCidrBlock": x.get("RemoteCidrBlock") or [x.get("remote_cidr")]} for x in (values or [])),
        key=lambda x: (x["LocalCidrBlock"], tuple(x["RemoteCidrBlock"])),
    )


def build_policies(models, values):
    result = []
    for value in values or []:
        item = models.SecurityPolicyDatabase()
        item.LocalCidrBlock, item.RemoteCidrBlock = value["local_cidr"], [value["remote_cidr"]]
        result.append(item)
    return result


def build_describe_request(models, connection_id=None, name=None, gateway_id=None, offset=0):
    request = models.DescribeVpnConnectionsRequest()
    request.Offset, request.Limit = offset, 100
    if connection_id:
        request.VpnConnectionIds = [connection_id]
    else:
        filters = []
        for key, value in (("vpn-connection-name", name), ("vpn-gateway-id", gateway_id)):
            if value:
                item = models.Filter()
                item.Name, item.Values = key, [value]
                filters.append(item)
        if filters:
            request.Filters = filters
    return request


def _apply_mutable(request, models, params, include_psk=False):
    request.VpnConnectionName = params["name"]
    request.CustomerGatewayId = params["customer_gateway_id"]
    if params.get("security_policy_databases") is not None:
        request.SecurityPolicyDatabases = build_policies(models, params["security_policy_databases"])
    if params.get("negotiation_type") is not None:
        request.NegotiationType = params["negotiation_type"]
    if params.get("dpd_enabled") is not None:
        request.DpdEnable = 1 if params["dpd_enabled"] else 0
    if params.get("dpd_timeout") is not None:
        request.DpdTimeout = str(params["dpd_timeout"])
    if params.get("dpd_action") is not None:
        request.DpdAction = params["dpd_action"]
    if include_psk:
        request.PreShareKey = params["pre_shared_key"]
    return request


def build_create_request(models, params):
    request = _apply_mutable(models.CreateVpnConnectionRequest(), models, params, True)
    request.VpnGatewayId, request.VpcId = params["vpn_gateway_id"], params["vpc_id"]
    request.RouteType = params["route_type"]
    if params.get("tags"):
        request.Tags = []
        for key, value in sorted(params["tags"].items()):
            tag = models.Tag()
            tag.Key, tag.Value = str(key), str(value)
            request.Tags.append(tag)
    return request


def build_update_request(models, connection_id, params):
    request = _apply_mutable(
        models.ModifyVpnConnectionAttributeRequest(), models, params,
        params.get("rotate_pre_shared_key", False),
    )
    request.VpnConnectionId = connection_id
    return request


def build_delete_request(models, gateway_id, connection_id):
    request = models.DeleteVpnConnectionRequest()
    request.VpnGatewayId, request.VpnConnectionId = gateway_id, connection_id
    return request


def find_connection(module, client, models, connection_id, name, gateway_id):
    offset, matches = 0, []
    while True:
        response = module.sdk_call(client.DescribeVpnConnections, build_describe_request(models, connection_id, name, gateway_id, offset))
        items = list(getattr(response, "VpnConnectionSet", None) or [])
        matches.extend(item._serialize(allow_none=True) for item in items)
        offset += len(items)
        if connection_id or not items or offset >= int(getattr(response, "TotalCount", 0) or 0):
            break
    if len(matches) > 1:
        module.fail_json(msg="Multiple VPN connections match; specify vpn_connection_id")
    return matches[0] if matches else None


def _desired(params):
    result = {"VpnConnectionName": params["name"], "CustomerGatewayId": params["customer_gateway_id"]}
    optional = {"NegotiationType": "negotiation_type", "DpdEnable": "dpd_enabled", "DpdTimeout": "dpd_timeout", "DpdAction": "dpd_action"}
    for api, key in optional.items():
        if params.get(key) is not None:
            if key == "dpd_timeout":
                result[api] = str(params[key])
            elif key == "dpd_enabled":
                result[api] = 1 if params[key] else 0
            else:
                result[api] = params[key]
    if params.get("security_policy_databases") is not None:
        result["SecurityPolicyDatabaseSet"] = _policies(params["security_policy_databases"])
    return result


def _matches(current, desired):
    for key, value in desired.items():
        actual = _policies(current.get(key)) if key == "SecurityPolicyDatabaseSet" else current.get(key)
        if actual != value:
            return False
    return True


def wait_for_connection(module, client, models, connection_id, desired=None, absent=False):
    deadline = time.time() + module.params["waiter_timeout"]
    while True:
        current = find_connection(module, client, models, connection_id, None, None)
        if absent and current is None:
            return None
        if not absent and current and _matches(current, desired):
            return current
        if time.time() >= deadline:
            module.fail_json(msg="Timed out waiting for VPN connection convergence", vpn_connection=current)
        time.sleep(module.params["waiter_delay"])


def run_module():
    module = TencentCloudModule(argument_spec={
        "state": {"type": "str", "choices": ["present", "absent"], "default": "present"},
        "vpn_connection_id": {"type": "str"}, "name": {"type": "str"},
        "vpn_gateway_id": {"type": "str"}, "customer_gateway_id": {"type": "str"}, "vpc_id": {"type": "str"},
        "pre_shared_key": {"type": "str", "no_log": True}, "rotate_pre_shared_key": {"type": "bool", "default": False},
        "security_policy_databases": {"type": "list", "elements": "dict", "options": {"local_cidr": {"type": "str", "required": True}, "remote_cidr": {"type": "str", "required": True}}},
        "route_type": {"type": "str", "choices": ["StaticRoute", "BgpRoute", "Policy"], "default": "Policy"},
        "negotiation_type": {"type": "str", "choices": ["active", "passive", "flowTrigger"]},
        "dpd_enabled": {"type": "bool"}, "dpd_timeout": {"type": "int"},
        "dpd_action": {"type": "str", "choices": ["clear", "restart"]}, "tags": {"type": "dict", "default": {}},
    }, required_one_of=[("vpn_connection_id", "name")], supports_check_mode=True)
    p = module.params
    if p["rotate_pre_shared_key"] and not p["pre_shared_key"]:
        module.fail_json(msg="pre_shared_key is required when rotate_pre_shared_key=true")
    module.require_sdk()
    models, client_module = _load_vpc()
    client = module.create_client(client_module.VpcClient, "vpc.tencentcloudapi.com")
    try:
        current = find_connection(module, client, models, p["vpn_connection_id"], p["name"], p["vpn_gateway_id"])
        if p["state"] == "absent":
            if current is None:
                module.exit_json(changed=False, vpn_connection=None, msg="VPN connection is absent")
            diff = maybe_diff(module, current, None)
            if module.check_mode:
                module.exit_json(changed=True, **(diff or {}), vpn_connection=current, msg="Would delete VPN connection")
            gateway_id = p["vpn_gateway_id"] or current["VpnGatewayId"]
            module.sdk_call(client.DeleteVpnConnection, build_delete_request(models, gateway_id, current["VpnConnectionId"]))
            wait_for_connection(module, client, models, current["VpnConnectionId"], absent=True)
            module.exit_json(changed=True, **(diff or {}), vpn_connection=None, msg="VPN connection deleted")
        if current is None:
            missing = [x for x in ("name", "vpn_gateway_id", "customer_gateway_id", "vpc_id", "pre_shared_key") if not p[x]]
            if missing:
                module.fail_json(msg="Required when creating: %s" % ", ".join(missing))
            desired = _desired(p)
            diff = maybe_diff(module, None, desired)
            if module.check_mode:
                module.exit_json(changed=True, **(diff or {}), vpn_connection=None, msg="Would create VPN connection")
            response = module.sdk_call(client.CreateVpnConnection, build_create_request(models, p))
            current = wait_for_connection(module, client, models, response.VpnConnection.VpnConnectionId, desired)
            module.exit_json(changed=True, **(diff or {}), vpn_connection=current, msg="VPN connection created")
        desired = _desired(p)
        changed = not _matches(current, desired) or p["rotate_pre_shared_key"]
        if not changed:
            module.exit_json(changed=False, vpn_connection=current, msg="VPN connection is up to date")
        diff = maybe_diff(module, current, desired)
        if module.check_mode:
            module.exit_json(changed=True, **(diff or {}), vpn_connection=current, msg="Would update VPN connection")
        module.sdk_call(client.ModifyVpnConnectionAttribute, build_update_request(models, current["VpnConnectionId"], p))
        current = wait_for_connection(module, client, models, current["VpnConnectionId"], desired)
        module.exit_json(changed=True, **(diff or {}), vpn_connection=current, msg="VPN connection updated")
    except Exception as exc:
        module.fail_json(msg="Tencent Cloud API request failed", error=str(exc), error_code=getattr(exc, "get_code", lambda: None)(), request_id=getattr(exc, "get_request_id", lambda: None)())


def main():
    run_module()


if __name__ == "__main__":
    main()
