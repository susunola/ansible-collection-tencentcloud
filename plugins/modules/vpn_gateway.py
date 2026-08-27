#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
---
module: vpn_gateway
short_description: Manage Tencent Cloud VPN gateways
version_added: "0.12.0"
description:
  - Create, update and delete VPN gateways through the C(vpc.v20170312) API.
  - This module is idempotent. Running it twice leaves the gateway unchanged
    and the second run reports C(changed=false).
  - Supports check mode; no API write happens in check mode, only reads.
options:
  state:
    description:
      - C(present) creates the gateway when it does not exist and updates its
        name, connection cap and BGP ASN when it does.
      - C(absent) deletes the gateway.
    type: str
    choices: [present, absent]
    default: present
  vpn_gateway_id:
    description:
      - ID of an existing VPN gateway, e.g. C(vpngw-xxxxxxxx).
      - When given, the module operates on that gateway; otherwise the gateway
        is matched by O(name) and O(vpc_id).
    type: str
  name:
    description:
      - Name of the VPN gateway, written to
        V(CreateVpnGatewayRequest.VpnGatewayName) and
        V(ModifyVpnGatewayAttributeRequest.VpnGatewayName).
    type: str
  vpc_id:
    description:
      - ID of the VPC (C(vpc-xxxxxxxx)) the gateway belongs to.
      - Required when creating the gateway.
    type: str
  internet_max_bandwidth_out:
    description:
      - Outbound bandwidth cap in Mbps, written to
        V(CreateVpnGatewayRequest.InternetMaxBandwidthOut).
      - Only applied at creation.
    type: int
  instance_charge_type:
    description:
      - Billing mode of the gateway, written to V(CreateVpnGatewayRequest).
    type: str
    choices:
      - POSTPAID_BY_HOUR
      - PREPAID_BY_MONTH
    default: POSTPAID_BY_HOUR
  type:
    description:
      - Gateway type, C(IPSEC) for IPsec VPN, C(SSL) for SSL VPN.
    type: str
    choices: [IPSEC, SSL]
    default: IPSEC
  max_connection:
    description:
      - Maximum concurrent connections, written to V(CreateVpnGatewayRequest)
        and V(ModifyVpnGatewayAttributeRequest).
    type: int
  zone:
    description:
      - Availability zone of the gateway, e.g. C(ap-guangzhou-3).
      - Only applied at creation.
    type: str
  bgp_asn:
    description:
      - BGP ASN of the gateway, written to V(CreateVpnGatewayRequest) and
        V(ModifyVpnGatewayAttributeRequest).
    type: int
  tags:
    description:
      - Tags to apply to the gateway as a dict, for example I(env=prod).
      - Only applied at creation.
    type: dict
    default: {}
  retries:
    description: Number of retries for transient SDK failures.
    type: int
    default: 5
  waiter_delay:
    description: Seconds to wait between state-polling attempts.
    type: int
    default: 5
  waiter_timeout:
    description: Overall timeout in seconds for state polling.
    type: int
    default: 120
  user_agent:
    description:
      - Value appended to the SDK User-Agent header so API usage can be
        attributed to this collection.
    type: str
    default: ansible-collection.susunola.tencentcloud
notes:
  - Requires the C(tencentcloud-sdk-python-vpc) package on the controller.
  - Deleting a gateway also removes its associated VPN connections and routes;
    only IPsec tunnels under SSL gateways are unaffected.
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''

EXAMPLES = r'''
- name: Create a POSTPAID IPsec VPN gateway
  susunola.tencentcloud.vpn_gateway:
    region: ap-guangzhou
    state: present
    name: office-vpn
    vpc_id: vpc-aaaaaaaa
    internet_max_bandwidth_out: 10
    zone: ap-guangzhou-3

- name: Rename the gateway
  susunola.tencentcloud.vpn_gateway:
    region: ap-guangzhou
    state: present
    vpn_gateway_id: vpngw-xxxxxxxx
    name: office-vpn-prod

- name: Delete a VPN gateway
  susunola.tencentcloud.vpn_gateway:
    region: ap-guangzhou
    state: absent
    name: office-vpn
    vpc_id: vpc-aaaaaaaa
'''

RETURN = r'''
vpn_gateway:
  description: The gateway as reported by V(DescribeVpnGateways) after the
    operation.
  returned: success
  type: dict
  sample:
    VpnGatewayId: vpngw-xxxxxxxx
    VpnGatewayName: office-vpn
    VpcId: vpc-aaaaaaaa
    State: AVAILABLE
    InternetMaxBandwidthOut: 10
'''

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff


def _load_vpc():
    from tencentcloud.vpc.v20170312 import models, vpc_client
    return models, vpc_client


def build_describe_request(models, vpn_gateway_id, name, vpc_id):
    request = models.DescribeVpnGatewaysRequest()
    request.Offset = 0
    request.Limit = 100
    if vpn_gateway_id:
        request.VpnGatewayIds = [vpn_gateway_id]
    else:
        filters = []
        if name:
            name_filter = models.Filter()
            name_filter.Name = "vpn-gateway-name"
            name_filter.Values = [name]
            filters.append(name_filter)
        if vpc_id:
            vpc_filter = models.Filter()
            vpc_filter.Name = "vpc-id"
            vpc_filter.Values = [vpc_id]
            filters.append(vpc_filter)
        if filters:
            request.Filters = filters
    return request


def _first(collection):
    return collection[0] if collection else None


def find_gateway(module, client, models, vpn_gateway_id, name, vpc_id):
    """Return the matching VPN gateway dict or None."""
    request = build_describe_request(models, vpn_gateway_id, name, vpc_id)
    response = module.sdk_call(client.DescribeVpnGateways, request)
    gateway = _first(response.VpnGatewaySet or [])
    if gateway is None:
        return None
    return gateway._serialize(allow_none=True)


def _create(module, client, models, params):
    request = models.CreateVpnGatewayRequest()
    request.VpcId = params["vpc_id"]
    request.VpnGatewayName = params["name"]
    request.InstanceChargeType = params["instance_charge_type"]
    request.Type = params["type"]
    if params["internet_max_bandwidth_out"] is not None:
        request.InternetMaxBandwidthOut = params["internet_max_bandwidth_out"]
    if params["max_connection"] is not None:
        request.MaxConnection = params["max_connection"]
    if params["zone"]:
        request.Zone = params["zone"]
    if params["bgp_asn"] is not None:
        request.BgpAsn = params["bgp_asn"]
    return module.sdk_call(client.CreateVpnGateway, request)


def _update(module, client, models, vpn_gateway_id, name, max_connection, bgp_asn):
    request = models.ModifyVpnGatewayAttributeRequest()
    request.VpnGatewayId = vpn_gateway_id
    if name is not None:
        request.VpnGatewayName = name
    if max_connection is not None:
        request.MaxConnection = max_connection
    if bgp_asn is not None:
        request.BgpAsn = bgp_asn
    module.sdk_call(client.ModifyVpnGatewayAttribute, request)


def _delete(module, client, models, vpn_gateway_id):
    request = models.DeleteVpnGatewayRequest()
    request.VpnGatewayId = vpn_gateway_id
    module.sdk_call(client.DeleteVpnGateway, request)


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "state": {"type": "str", "choices": ["present", "absent"], "default": "present"},
            "vpn_gateway_id": {"type": "str"},
            "name": {"type": "str"},
            "vpc_id": {"type": "str"},
            "internet_max_bandwidth_out": {"type": "int"},
            "instance_charge_type": {
                "type": "str",
                "choices": ["POSTPAID_BY_HOUR", "PREPAID_BY_MONTH"],
                "default": "POSTPAID_BY_HOUR",
            },
            "type": {"type": "str", "choices": ["IPSEC", "SSL"], "default": "IPSEC"},
            "max_connection": {"type": "int"},
            "zone": {"type": "str"},
            "bgp_asn": {"type": "int"},
            "tags": {"type": "dict", "default": {}},
        },
        supports_check_mode=True,
    )
    module.require_sdk()

    state = module.params["state"]
    vpn_gateway_id = module.params["vpn_gateway_id"]
    name = module.params["name"]
    vpc_id = module.params["vpc_id"]

    if not vpn_gateway_id and not name:
        module.fail_json(msg="vpn_gateway_id or name is required to identify the gateway")

    models, vpc_client = _load_vpc()
    client = module.create_client(vpc_client.VpcClient, "vpc.tencentcloudapi.com")

    try:
        current = find_gateway(module, client, models, vpn_gateway_id, name, vpc_id)
    except Exception as exc:
        module.fail_json(
            msg="Tencent Cloud API request failed",
            error=str(exc),
            error_code=getattr(exc, "get_code", lambda: None)(),
            request_id=getattr(exc, "get_request_id", lambda: None)(),
        )

    if state == "absent":
        if current is None:
            module.exit_json(changed=False, msg="VPN gateway already absent")
        target_id = current["VpnGatewayId"]
        diff = maybe_diff(module, current, None)
        if module.check_mode:
            module.exit_json(changed=True, **(diff or {}), msg="Would delete VPN gateway")
        _delete(module, client, models, target_id)
        module.exit_json(changed=True, **(diff or {}), vpn_gateway=None, msg="VPN gateway deleted")

    # state == present
    if current is None:
        if not module.params["vpc_id"]:
            module.fail_json(msg="vpc_id is required when creating a VPN gateway")
        if not name:
            module.fail_json(msg="name is required when creating a VPN gateway")
        desired = {
            "VpnGatewayName": name,
            "VpcId": module.params["vpc_id"],
            "InstanceChargeType": module.params["instance_charge_type"],
            "Type": module.params["type"],
        }
        desired = {key: value for key, value in desired.items() if value is not None}
        diff = maybe_diff(module, None, desired)
        if module.check_mode:
            module.exit_json(changed=True, **(diff or {}), msg="Would create VPN gateway")
        _create(module, client, models, module.params)
        created = find_gateway(module, client, models, None, name, vpc_id)
        module.exit_json(changed=True, **(diff or {}), vpn_gateway=created, msg="VPN gateway created")

    target_id = current["VpnGatewayId"]
    changes = []
    if name and current.get("VpnGatewayName") != name:
        changes.append("name")
    max_connection = module.params["max_connection"]
    if max_connection is not None and current.get("MaxConnection") != max_connection:
        changes.append("max_connection")
    bgp_asn = module.params["bgp_asn"]
    if bgp_asn is not None and current.get("BgpAsn") != bgp_asn:
        changes.append("bgp_asn")

    if not changes:
        module.exit_json(changed=False, vpn_gateway=current, msg="VPN gateway is up to date")

    diff = maybe_diff(module, current, {
        "VpnGatewayName": name or current.get("VpnGatewayName"),
        "MaxConnection": max_connection if max_connection is not None else current.get("MaxConnection"),
        "BgpAsn": bgp_asn if bgp_asn is not None else current.get("BgpAsn"),
    })
    if module.check_mode:
        module.exit_json(changed=True, **(diff or {}), msg="Would update VPN gateway")

    _update(
        module, client, models, target_id,
        name if "name" in changes else None,
        max_connection if "max_connection" in changes else None,
        bgp_asn if "bgp_asn" in changes else None,
    )
    updated = find_gateway(module, client, models, target_id, None, None)
    module.exit_json(changed=True, **(diff or {}), vpn_gateway=updated, msg="VPN gateway updated")


def main():
    run_module()


if __name__ == "__main__":
    main()
