#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type
DOCUMENTATION = r"""
---
module: dc_direct_connect_tunnel
short_description: Manage Tencent Cloud Direct Connect tunnels
version_added: "0.14.0"
description: Creates, updates and deletes Direct Connect tunnels with BGP or static routing configuration.
options:
  state: {type: str, choices: [present, absent], default: present, description: Desired state.}
  tunnel_id: {type: str, description: Existing tunnel ID.}
  name: {type: str, description: Tunnel name.}
  direct_connect_id: {type: str, description: Physical connection ID required for creation and immutable afterwards.}
  owner_account: {type: str, description: Creation-time owner account.}
  network_type: {type: str, description: Network type required for creation and immutable afterwards.}
  network_region: {type: str, description: Network region required for creation and immutable afterwards.}
  vpc_id: {type: str, description: VPC ID required for VPC tunnels and immutable afterwards.}
  direct_connect_gateway_id: {type: str, description: Direct Connect gateway ID required for creation and immutable afterwards.}
  bandwidth: {type: int, description: Tunnel bandwidth in Mbps.}
  route_type: {type: str, choices: [BGP, STATIC], description: Route type required for creation and immutable afterwards.}
  bgp_peer: {type: dict, description: SDK BgpPeer payload including ASN and optional authentication key.}
  route_filter_prefixes: {type: list, elements: str, description: Customer route CIDRs.}
  vlan: {type: int, description: Tunnel VLAN.}
  tencent_address: {type: str, description: Tencent-side IPv4 address.}
  customer_address: {type: str, description: Customer-side IPv4 address.}
  tencent_backup_address: {type: str, description: Tencent-side backup IPv4 address.}
  bfd_enabled: {type: int, choices: [0, 1], description: Enable BFD.}
  nqa_enabled: {type: int, choices: [0, 1], description: Enable NQA.}
  tags: {type: dict, description: Creation-time tags.}
  retries: {type: int, default: 5, description: Number of retries for transient failures.}
  waiter_delay: {type: int, default: 5, description: Seconds between polling attempts.}
  waiter_timeout: {type: int, default: 120, description: Overall polling timeout in seconds.}
  user_agent: {type: str, default: ansible-collection.susunola.tencentcloud, description: User-Agent suffix.}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.dc_direct_connect_tunnel:
    name: production-vpc
    direct_connect_id: dc-xxxxxxxx
    network_type: VPC
    network_region: ap-guangzhou
    vpc_id: vpc-xxxxxxxx
    direct_connect_gateway_id: dcg-xxxxxxxx
    bandwidth: 500
    route_type: BGP
    vlan: 100
    tencent_address: 192.0.2.1/30
    customer_address: 192.0.2.2/30
    bgp_peer: {Asn: 65001}
"""
RETURN = r"""tunnel: {description: Effective Direct Connect tunnel metadata., type: dict, returned: always}"""
import json
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import require_immutable_unchanged, sdk_error_payload


def _load():
    from tencentcloud.dc.v20180410 import models, dc_client

    return models, dc_client


def _model(cls, value):
    if value is None:
        return None
    x = cls()
    x.from_json_string(json.dumps(value))
    return x


def describe_request(models, p):
    r = models.DescribeDirectConnectTunnelsRequest()
    r.Offset, r.Limit = 0, 100
    if p.get("tunnel_id"):
        r.DirectConnectTunnelIds = [p["tunnel_id"]]
    return r


def _routes(models, values):
    result = []
    for value in values or []:
        x = models.RouteFilterPrefix()
        x.Cidr = value
        result.append(x)
    return result


def _tags(models, values):
    result = []
    for key, value in sorted((values or {}).items()):
        x = models.Tag()
        x.Key, x.Value = key, value
        result.append(x)
    return result


def _fill(r, models, p):
    r.DirectConnectTunnelName, r.Bandwidth = p["name"], p.get("bandwidth")
    r.BgpPeer, r.RouteFilterPrefixes = _model(models.BgpPeer, p.get("bgp_peer")), _routes(models, p.get("route_filter_prefixes"))
    r.TencentAddress, r.CustomerAddress, r.TencentBackupAddress = p.get("tencent_address"), p.get("customer_address"), p.get("tencent_backup_address")
    return r


def create_request(models, p):
    r = _fill(models.CreateDirectConnectTunnelRequest(), models, p)
    r.DirectConnectId, r.DirectConnectOwnerAccount = p["direct_connect_id"], p.get("owner_account")
    r.NetworkType, r.NetworkRegion, r.VpcId, r.DirectConnectGatewayId = p["network_type"], p["network_region"], p.get("vpc_id"), p["direct_connect_gateway_id"]
    r.RouteType, r.Vlan = p["route_type"], p.get("vlan")
    r.BfdEnable, r.NqaEnable, r.Tags = p.get("bfd_enabled"), p.get("nqa_enabled"), _tags(models, p.get("tags"))
    return r


def update_request(models, p, tunnel_id):
    r = _fill(models.ModifyDirectConnectTunnelAttributeRequest(), models, p)
    r.DirectConnectTunnelId = tunnel_id
    return r


def delete_request(models, tunnel_id):
    r = models.DeleteDirectConnectTunnelRequest()
    r.DirectConnectTunnelId = tunnel_id
    return r


def find(module, client, models, p):
    response = module.sdk_call(client.DescribeDirectConnectTunnels, describe_request(models, p))
    matches = []
    for item in response.DirectConnectTunnelSet or []:
        value = item._serialize(allow_none=True)
        if isinstance(value.get("BgpPeer"), dict):
            value["BgpPeer"].pop("AuthKey", None)
        if (p.get("tunnel_id") and value.get("DirectConnectTunnelId") == p["tunnel_id"]) or (
            not p.get("tunnel_id")
            and value.get("DirectConnectTunnelName") == p.get("name")
            and (not p.get("direct_connect_id") or value.get("DirectConnectId") == p["direct_connect_id"])
        ):
            matches.append(value)
    if len(matches) > 1:
        module.fail_json(msg="Multiple Direct Connect tunnels matched; specify tunnel_id")
    return matches[0] if matches else None


def _route_values(v):
    return sorted(x.get("Cidr") for x in v.get("RouteFilterPrefixes") or [])


def _safe_bgp(value):
    result = dict(value or {})
    result.pop("AuthKey", None)
    return result or None


def comparable(v):
    return {
        "DirectConnectTunnelName": v.get("DirectConnectTunnelName"),
        "DirectConnectId": v.get("DirectConnectId"),
        "NetworkType": v.get("NetworkType"),
        "NetworkRegion": v.get("NetworkRegion"),
        "VpcId": v.get("VpcId"),
        "DirectConnectGatewayId": v.get("DirectConnectGatewayId"),
        "Bandwidth": v.get("Bandwidth"),
        "RouteType": v.get("RouteType"),
        "BgpPeer": _safe_bgp(v.get("BgpPeer")),
        "RouteFilterPrefixes": _route_values(v),
        "Vlan": v.get("Vlan"),
        "TencentAddress": v.get("TencentAddress"),
        "CustomerAddress": v.get("CustomerAddress"),
        "TencentBackupAddress": v.get("TencentBackupAddress"),
        "BfdEnable": v.get("BfdEnable"),
    }


def desired(p, current=None):
    old = comparable(current) if current else {}
    mapping = {
        "DirectConnectTunnelName": "name",
        "DirectConnectId": "direct_connect_id",
        "NetworkType": "network_type",
        "NetworkRegion": "network_region",
        "VpcId": "vpc_id",
        "DirectConnectGatewayId": "direct_connect_gateway_id",
        "Bandwidth": "bandwidth",
        "RouteType": "route_type",
        "BgpPeer": "bgp_peer",
        "RouteFilterPrefixes": "route_filter_prefixes",
        "Vlan": "vlan",
        "TencentAddress": "tencent_address",
        "CustomerAddress": "customer_address",
        "TencentBackupAddress": "tencent_backup_address",
        "BfdEnable": "bfd_enabled",
    }
    result = {api: p.get(param) if p.get(param) is not None else old.get(api) for api, param in mapping.items()}
    result["BgpPeer"] = _safe_bgp(result.get("BgpPeer"))
    result["RouteFilterPrefixes"] = sorted(result.get("RouteFilterPrefixes") or [])
    return result


def run_module():
    spec = {
        "state": {"choices": ["present", "absent"], "default": "present"},
        "tunnel_id": {},
        "name": {},
        "direct_connect_id": {},
        "owner_account": {},
        "network_type": {},
        "network_region": {},
        "vpc_id": {},
        "direct_connect_gateway_id": {},
        "bandwidth": {"type": "int"},
        "route_type": {"choices": ["BGP", "STATIC"]},
        "bgp_peer": {"type": "dict", "no_log": True},
        "route_filter_prefixes": {"type": "list", "elements": "str"},
        "vlan": {"type": "int"},
        "tencent_address": {},
        "customer_address": {},
        "tencent_backup_address": {},
        "bfd_enabled": {"type": "int", "choices": [0, 1]},
        "nqa_enabled": {"type": "int", "choices": [0, 1]},
        "tags": {"type": "dict"},
    }
    module = TencentCloudModule(argument_spec=spec, required_one_of=[("tunnel_id", "name")], supports_check_mode=True)
    p = module.params
    module.require_sdk()
    models, cm = _load()
    client = module.create_client(cm.DcClient, "dc.tencentcloudapi.com")
    try:
        current = find(module, client, models, p)
        if p["state"] == "absent":
            if not current:
                module.exit_json(changed=False, tunnel=None)
            diff = maybe_diff(module, current, None)
            if not module.check_mode:
                module.sdk_call(client.DeleteDirectConnectTunnel, delete_request(models, current["DirectConnectTunnelId"]))
            module.exit_json(changed=True, **(diff or {}), tunnel=None)
        if not current:
            missing = [
                k
                for k in ("name", "direct_connect_id", "network_type", "network_region", "direct_connect_gateway_id", "bandwidth", "route_type")
                if p.get(k) is None
            ]
            if missing:
                module.fail_json(msg="creation parameters are required for a Direct Connect tunnel", missing=missing)
        before, target = comparable(current) if current else None, desired(p, current)
        if before == target:
            module.exit_json(changed=False, tunnel=current)
        if current:
            require_immutable_unchanged(
                module,
                before,
                target,
                ("DirectConnectId", "NetworkType", "NetworkRegion", "VpcId", "DirectConnectGatewayId", "RouteType", "Vlan"),
                "Direct Connect tunnel",
            )
        diff = maybe_diff(module, before, target)
        if not module.check_mode:
            effective = dict(p)
            reverse = {
                "DirectConnectTunnelName": "name",
                "Bandwidth": "bandwidth",
                "BgpPeer": "bgp_peer",
                "RouteFilterPrefixes": "route_filter_prefixes",
                "TencentAddress": "tencent_address",
                "CustomerAddress": "customer_address",
                "TencentBackupAddress": "tencent_backup_address",
            }
            for api, param in reverse.items():
                effective[param] = p.get(param) if param == "bgp_peer" and p.get(param) is not None else target[api]
            response = module.sdk_call(
                client.ModifyDirectConnectTunnelAttribute if current else client.CreateDirectConnectTunnel,
                update_request(models, effective, current["DirectConnectTunnelId"]) if current else create_request(models, effective),
            )
            p["tunnel_id"] = current["DirectConnectTunnelId"] if current else response.DirectConnectTunnelIdSet[0]
            current = find(module, client, models, p)
        module.exit_json(changed=True, **(diff or {}), tunnel=current if not module.check_mode else target)
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
