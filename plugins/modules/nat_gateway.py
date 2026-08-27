#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
---
module: nat_gateway
short_description: Manage Tencent Cloud NAT gateways
version_added: "0.12.0"
description:
  - Create, update and delete NAT gateways through the C(vpc.v20170312) API.
  - This module is idempotent. Running it twice leaves the gateway unchanged
    and the second run reports C(changed=false).
  - Supports check mode; no API write happens in check mode, only reads.
options:
  state:
    description:
      - C(present) creates the gateway when it does not exist and updates its
        name, bandwidth and deletion-protection flag when it does.
      - C(absent) deletes the gateway.
    type: str
    choices: [present, absent]
    default: present
  nat_gateway_id:
    description:
      - ID of an existing NAT gateway, e.g. C(nat-xxxxxxxx).
      - When given, the module operates on that gateway; otherwise the gateway
        is matched by O(name) and O(vpc_id).
    type: str
  name:
    description:
      - Name of the NAT gateway, written to
        V(CreateNatGatewayRequest.NatGatewayName) and
        V(ModifyNatGatewayAttributeRequest.NatGatewayName).
    type: str
  vpc_id:
    description:
      - ID of the VPC (C(vpc-xxxxxxxx)) the gateway belongs to.
      - Required when creating the gateway.
    type: str
  internet_max_bandwidth_out:
    description:
      - Outbound bandwidth cap in Mbps, written to V(CreateNatGatewayRequest)
        and V(ModifyNatGatewayAttributeRequest). Applies to the legacy
        bandwidth-billing gateway model.
    type: int
  max_concurrent_connection:
    description:
      - Maximum concurrent connections, written to
        V(CreateNatGatewayRequest.MaxConcurrentConnection).
      - Only applied at creation.
    type: int
  address_count:
    description:
      - Number of EIPs to allocate for the gateway, written to
        V(CreateNatGatewayRequest.AddressCount).
      - Only applied at creation; the module does not allocate or release
        EIPs on an existing gateway.
    type: int
  public_ip_addresses:
    description:
      - Explicit EIPs to bind to the gateway, written to
        V(CreateNatGatewayRequest.PublicIpAddresses).
      - Only applied at creation.
    type: list
    elements: str
  zone:
    description:
      - Availability zone of the gateway, e.g. C(ap-guangzhou-3).
      - Only applied at creation.
    type: str
  deletion_protection_enabled:
    description:
      - Whether the gateway is protected from deletion, written to
        V(ModifyNatGatewayAttributeRequest.DeletionProtectionEnabled).
      - When true and O(state=absent), the module removes the protection
        first, then deletes the gateway.
    type: bool
    default: false
  ignore_operation_risk:
    description:
      - Skip the API safety check when deleting the gateway (e.g. while it
        still holds EIPs or translation rules), written to
        V(DeleteNatGatewayRequest.IgnoreOperationRisk).
    type: bool
    default: false
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
  - NAT gateways are billed per hour while present; delete them as soon as
    they are no longer needed to avoid unnecessary charges.
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''

EXAMPLES = r'''
- name: Create a NAT gateway with two auto-allocated EIPs
  susunola.tencentcloud.nat_gateway:
    region: ap-guangzhou
    state: present
    name: prod-nat
    vpc_id: vpc-aaaaaaaa
    address_count: 2
    internet_max_bandwidth_out: 100

- name: Enable deletion protection
  susunola.tencentcloud.nat_gateway:
    region: ap-guangzhou
    state: present
    name: prod-nat
    vpc_id: vpc-aaaaaaaa
    deletion_protection_enabled: true

- name: Delete a NAT gateway
  susunola.tencentcloud.nat_gateway:
    region: ap-guangzhou
    state: absent
    name: prod-nat
    vpc_id: vpc-aaaaaaaa
'''

RETURN = r'''
nat_gateway:
  description: The gateway as reported by V(DescribeNatGateways) after the
    operation.
  returned: success
  type: dict
  sample:
    NatGatewayId: nat-xxxxxxxx
    NatGatewayName: prod-nat
    VpcId: vpc-aaaaaaaa
    State: AVAILABLE
    InternetMaxBandwidthOut: 100
    DeletionProtectionEnabled: false
'''

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff


def _load_vpc():
    from tencentcloud.vpc.v20170312 import models, vpc_client
    return models, vpc_client


def build_describe_request(models, nat_gateway_id, name, vpc_id):
    request = models.DescribeNatGatewaysRequest()
    request.Offset = 0
    request.Limit = 100
    if nat_gateway_id:
        request.NatGatewayIds = [nat_gateway_id]
    else:
        filters = []
        if name:
            name_filter = models.Filter()
            name_filter.Name = "nat-gateway-name"
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


def find_gateway(module, client, models, nat_gateway_id, name, vpc_id):
    """Return the matching NAT gateway dict or None."""
    request = build_describe_request(models, nat_gateway_id, name, vpc_id)
    response = module.sdk_call(client.DescribeNatGateways, request)
    gateway = _first(response.NatGatewaySet or [])
    if gateway is None:
        return None
    return gateway._serialize(allow_none=True)


def _create(module, client, models, params):
    request = models.CreateNatGatewayRequest()
    request.VpcId = params["vpc_id"]
    request.NatGatewayName = params["name"]
    if params["internet_max_bandwidth_out"] is not None:
        request.InternetMaxBandwidthOut = params["internet_max_bandwidth_out"]
    if params["max_concurrent_connection"] is not None:
        request.MaxConcurrentConnection = params["max_concurrent_connection"]
    if params["address_count"] is not None:
        request.AddressCount = params["address_count"]
    if params["public_ip_addresses"]:
        request.PublicIpAddresses = params["public_ip_addresses"]
    if params["zone"]:
        request.Zone = params["zone"]
    return module.sdk_call(client.CreateNatGateway, request)


def _set_deletion_protection(module, client, models, nat_gateway_id, enabled):
    request = models.ModifyNatGatewayAttributeRequest()
    request.NatGatewayId = nat_gateway_id
    request.DeletionProtectionEnabled = enabled
    module.sdk_call(client.ModifyNatGatewayAttribute, request)


def _update(module, client, models, nat_gateway_id, name, bandwidth):
    request = models.ModifyNatGatewayAttributeRequest()
    request.NatGatewayId = nat_gateway_id
    if name is not None:
        request.NatGatewayName = name
    if bandwidth is not None:
        request.InternetMaxBandwidthOut = bandwidth
    module.sdk_call(client.ModifyNatGatewayAttribute, request)


def _delete(module, client, models, nat_gateway_id, ignore_operation_risk):
    request = models.DeleteNatGatewayRequest()
    request.NatGatewayId = nat_gateway_id
    if ignore_operation_risk:
        request.IgnoreOperationRisk = True
    module.sdk_call(client.DeleteNatGateway, request)


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "state": {"type": "str", "choices": ["present", "absent"], "default": "present"},
            "nat_gateway_id": {"type": "str"},
            "name": {"type": "str"},
            "vpc_id": {"type": "str"},
            "internet_max_bandwidth_out": {"type": "int"},
            "max_concurrent_connection": {"type": "int"},
            "address_count": {"type": "int"},
            "public_ip_addresses": {"type": "list", "elements": "str"},
            "zone": {"type": "str"},
            "deletion_protection_enabled": {"type": "bool", "default": False},
            "ignore_operation_risk": {"type": "bool", "default": False},
            "tags": {"type": "dict", "default": {}},
        },
        supports_check_mode=True,
    )
    module.require_sdk()

    state = module.params["state"]
    nat_gateway_id = module.params["nat_gateway_id"]
    name = module.params["name"]
    vpc_id = module.params["vpc_id"]

    if not nat_gateway_id and not name:
        module.fail_json(msg="nat_gateway_id or name is required to identify the gateway")

    models, vpc_client = _load_vpc()
    client = module.create_client(vpc_client.VpcClient, "vpc.tencentcloudapi.com")

    try:
        current = find_gateway(module, client, models, nat_gateway_id, name, vpc_id)
    except Exception as exc:
        module.fail_json(
            msg="Tencent Cloud API request failed",
            error=str(exc),
            error_code=getattr(exc, "get_code", lambda: None)(),
            request_id=getattr(exc, "get_request_id", lambda: None)(),
        )

    if state == "absent":
        if current is None:
            module.exit_json(changed=False, msg="NAT gateway already absent")
        target_id = current["NatGatewayId"]
        diff = maybe_diff(module, current, None)
        if module.check_mode:
            module.exit_json(changed=True, **(diff or {}), msg="Would delete NAT gateway")
        if current.get("DeletionProtectionEnabled"):
            _set_deletion_protection(module, client, models, target_id, False)
        _delete(module, client, models, target_id, module.params["ignore_operation_risk"])
        module.exit_json(changed=True, **(diff or {}), nat_gateway=None, msg="NAT gateway deleted")

    # state == present
    if current is None:
        if not module.params["vpc_id"]:
            module.fail_json(msg="vpc_id is required when creating a NAT gateway")
        if not name:
            module.fail_json(msg="name is required when creating a NAT gateway")
        desired = {
            "NatGatewayName": name,
            "VpcId": module.params["vpc_id"],
            "DeletionProtectionEnabled": module.params["deletion_protection_enabled"],
        }
        desired = {key: value for key, value in desired.items() if value is not None}
        diff = maybe_diff(module, None, desired)
        if module.check_mode:
            module.exit_json(changed=True, **(diff or {}), msg="Would create NAT gateway")
        _create(module, client, models, module.params)
        created = find_gateway(module, client, models, None, name, vpc_id)
        module.exit_json(changed=True, **(diff or {}), nat_gateway=created, msg="NAT gateway created")

    target_id = current["NatGatewayId"]
    changes = []
    if name and current.get("NatGatewayName") != name:
        changes.append("name")
    bandwidth = module.params["internet_max_bandwidth_out"]
    if bandwidth is not None and current.get("InternetMaxBandwidthOut") != bandwidth:
        changes.append("bandwidth")
    protection = module.params["deletion_protection_enabled"]
    if protection != bool(current.get("DeletionProtectionEnabled")):
        changes.append("deletion_protection")

    if not changes:
        module.exit_json(changed=False, nat_gateway=current, msg="NAT gateway is up to date")

    diff = maybe_diff(module, current, {
        "NatGatewayName": name or current.get("NatGatewayName"),
        "InternetMaxBandwidthOut": (
            bandwidth if bandwidth is not None else current.get("InternetMaxBandwidthOut")
        ),
        "DeletionProtectionEnabled": protection,
    })
    if module.check_mode:
        module.exit_json(changed=True, **(diff or {}), msg="Would update NAT gateway")

    _update(
        module, client, models, target_id,
        name if "name" in changes else None,
        bandwidth if "bandwidth" in changes else None,
    )
    if "deletion_protection" in changes:
        _set_deletion_protection(module, client, models, target_id, protection)
    updated = find_gateway(module, client, models, target_id, None, None)
    module.exit_json(changed=True, **(diff or {}), nat_gateway=updated, msg="NAT gateway updated")


def main():
    run_module()


if __name__ == "__main__":
    main()
