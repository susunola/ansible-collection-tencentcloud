#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
---
module: peering_connection
short_description: Manage Tencent Cloud VPC peering connections
version_added: "0.12.0"
description:
  - Create, update, accept and delete VPC peering connections through the
    C(vpc.v20170312) API.
  - This module is idempotent. Running it twice leaves the connection
    unchanged and the second run reports C(changed=false).
  - Supports check mode; no API write happens in check mode, only reads.
options:
  state:
    description:
      - C(present) creates the peering connection when it does not exist and
        updates its name, bandwidth and charge type when it does.
      - C(absent) deletes the peering connection.
    type: str
    choices: [present, absent]
    default: present
  peering_connection_id:
    description:
      - ID of an existing peering connection, e.g. C(pcx-xxxxxxxx).
      - When given, the module operates on that connection; otherwise the
        connection is matched by O(name) and O(source_vpc_id).
    type: str
  name:
    description:
      - Name of the peering connection, written to
        V(CreateVpcPeeringConnectionRequest.PeeringConnectionName) and
        V(ModifyVpcPeeringConnectionRequest.PeeringConnectionName).
      - Used to look up the connection when O(peering_connection_id) is not
        given.
    type: str
  source_vpc_id:
    description:
      - ID of the source VPC (C(vpc-xxxxxxxx)).
      - Required when creating the connection; used to look up the connection
        when O(peering_connection_id) is not given.
    type: str
  destination_vpc_id:
    description:
      - ID of the destination VPC (C(vpc-xxxxxxxx)).
      - Required when creating the connection; only applied at creation.
    type: str
  destination_region:
    description:
      - Region of the destination VPC, e.g. C(ap-shanghai).
      - Defaults to the module region. Only applied at creation.
    type: str
  destination_uin:
    description:
      - Account UIN of the destination VPC owner.
      - Defaults to the caller's own account. Only applied at creation.
    type: str
  bandwidth:
    description:
      - Bandwidth cap of the connection in Mbps, written to
        V(CreateVpcPeeringConnectionRequest.Bandwidth) and
        V(ModifyVpcPeeringConnectionRequest.Bandwidth).
    type: int
  charge_type:
    description:
      - Billing mode of the connection.
    type: str
    choices:
      - POSTPAID_BY_DAY
      - BANDWIDTH_POSTPAID_BY_HOUR
  qos_level:
    description:
      - Quality-of-service level of the connection, written to
        V(CreateVpcPeeringConnectionRequest.QosLevel).
    type: str
    choices:
      - PT
      - AU
      - AG
  accept:
    description:
      - When true and the created connection stays in C(PENDING_ACCEPTANCE)
        state, the module calls V(AcceptVpcPeeringConnection) to accept it.
      - Cross-account connections may still require the peer to accept
        explicitly; in that case set this to false and accept manually.
    type: bool
    default: true
  tags:
    description:
      - Tags to apply to the connection as a dict, for example I(env=prod).
      - Only applied at creation; existing connections are left untouched.
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
  - Deleting a peering connection does not require the peer's consent.
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''

EXAMPLES = r'''
- name: Create a peering connection between two VPCs in the same account
  susunola.tencentcloud.peering_connection:
    region: ap-guangzhou
    state: present
    name: app-to-db
    source_vpc_id: vpc-aaaaaaaa
    destination_vpc_id: vpc-bbbbbbbb
    bandwidth: 100

- name: Cross-region peering with an explicit bandwidth cap
  susunola.tencentcloud.peering_connection:
    region: ap-guangzhou
    state: present
    name: gz-to-sh
    source_vpc_id: vpc-aaaaaaaa
    destination_vpc_id: vpc-cccccccc
    destination_region: ap-shanghai
    bandwidth: 500

- name: Delete a peering connection
  susunola.tencentcloud.peering_connection:
    region: ap-guangzhou
    state: absent
    name: app-to-db
    source_vpc_id: vpc-aaaaaaaa
'''

RETURN = r'''
peering_connection:
  description: The connection as reported by V(DescribeVpcPeeringConnections)
    after the operation.
  returned: success
  type: dict
  sample:
    PeeringConnectionId: pcx-xxxxxxxx
    PeeringConnectionName: app-to-db
    SourceVpcId: vpc-aaaaaaaa
    DestinationVpcId: vpc-bbbbbbbb
    State: ACTIVE
'''

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff


def _load_vpc():
    from tencentcloud.vpc.v20170312 import models, vpc_client
    return models, vpc_client


def build_describe_request(models, peering_connection_id, name, source_vpc_id):
    request = models.DescribeVpcPeeringConnectionsRequest()
    request.Offset = 0
    request.Limit = 100
    if peering_connection_id:
        request.PeeringConnectionIds = [peering_connection_id]
    else:
        filters = []
        if name:
            name_filter = models.Filter()
            name_filter.Name = "peering-connection-name"
            name_filter.Values = [name]
            filters.append(name_filter)
        if source_vpc_id:
            vpc_filter = models.Filter()
            vpc_filter.Name = "vpc-id"
            vpc_filter.Values = [source_vpc_id]
            filters.append(vpc_filter)
        if filters:
            request.Filters = filters
    return request


def _first(collection):
    return collection[0] if collection else None


def find_connection(module, client, models, peering_connection_id, name, source_vpc_id):
    """Return the matching peering connection dict or None."""
    request = build_describe_request(models, peering_connection_id, name, source_vpc_id)
    response = module.sdk_call(client.DescribeVpcPeeringConnections, request)
    connection = _first(response.PeerConnectionSet or [])
    if connection is None:
        return None
    return connection._serialize(allow_none=True)


def _create(module, client, models, params):
    request = models.CreateVpcPeeringConnectionRequest()
    request.SourceVpcId = params["source_vpc_id"]
    request.DestinationVpcId = params["destination_vpc_id"]
    request.PeeringConnectionName = params["name"]
    if params["destination_region"]:
        request.DestinationRegion = params["destination_region"]
    if params["destination_uin"]:
        request.DestinationUin = params["destination_uin"]
    if params["bandwidth"] is not None:
        request.Bandwidth = params["bandwidth"]
    if params["charge_type"]:
        request.ChargeType = params["charge_type"]
    if params["qos_level"]:
        request.QosLevel = params["qos_level"]
    return module.sdk_call(client.CreateVpcPeeringConnection, request)


def _accept(module, client, models, peering_connection_id):
    request = models.AcceptVpcPeeringConnectionRequest()
    request.PeeringConnectionId = peering_connection_id
    module.sdk_call(client.AcceptVpcPeeringConnection, request)


def _update(module, client, models, peering_connection_id, name, bandwidth, charge_type):
    request = models.ModifyVpcPeeringConnectionRequest()
    request.PeeringConnectionId = peering_connection_id
    if name is not None:
        request.PeeringConnectionName = name
    if bandwidth is not None:
        request.Bandwidth = bandwidth
    if charge_type is not None:
        request.ChargeType = charge_type
    module.sdk_call(client.ModifyVpcPeeringConnection, request)


def _delete(module, client, models, peering_connection_id):
    request = models.DeleteVpcPeeringConnectionRequest()
    request.PeeringConnectionId = peering_connection_id
    module.sdk_call(client.DeleteVpcPeeringConnection, request)


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "state": {"type": "str", "choices": ["present", "absent"], "default": "present"},
            "peering_connection_id": {"type": "str"},
            "name": {"type": "str"},
            "source_vpc_id": {"type": "str"},
            "destination_vpc_id": {"type": "str"},
            "destination_region": {"type": "str"},
            "destination_uin": {"type": "str"},
            "bandwidth": {"type": "int"},
            "charge_type": {
                "type": "str",
                "choices": ["POSTPAID_BY_DAY", "BANDWIDTH_POSTPAID_BY_HOUR"],
            },
            "qos_level": {"type": "str", "choices": ["PT", "AU", "AG"]},
            "accept": {"type": "bool", "default": True},
            "tags": {"type": "dict", "default": {}},
        },
        supports_check_mode=True,
    )
    module.require_sdk()

    state = module.params["state"]
    peering_connection_id = module.params["peering_connection_id"]
    name = module.params["name"]
    source_vpc_id = module.params["source_vpc_id"]

    if not peering_connection_id and not name:
        module.fail_json(
            msg="peering_connection_id or name is required to identify the connection"
        )

    models, vpc_client = _load_vpc()
    client = module.create_client(vpc_client.VpcClient, "vpc.tencentcloudapi.com")

    try:
        current = find_connection(
            module, client, models, peering_connection_id, name, source_vpc_id
        )
    except Exception as exc:
        module.fail_json(
            msg="Tencent Cloud API request failed",
            error=str(exc),
            error_code=getattr(exc, "get_code", lambda: None)(),
            request_id=getattr(exc, "get_request_id", lambda: None)(),
        )

    if state == "absent":
        if current is None:
            module.exit_json(changed=False, msg="Peering connection already absent")
        target_id = current["PeeringConnectionId"]
        diff = maybe_diff(module, current, None)
        if module.check_mode:
            module.exit_json(changed=True, **(diff or {}), msg="Would delete peering connection")
        _delete(module, client, models, target_id)
        module.exit_json(
            changed=True, **(diff or {}), peering_connection=None, msg="Peering connection deleted"
        )

    # state == present
    if current is None:
        if not module.params["source_vpc_id"]:
            module.fail_json(msg="source_vpc_id is required when creating a peering connection")
        if not module.params["destination_vpc_id"]:
            module.fail_json(msg="destination_vpc_id is required when creating a peering connection")
        desired = {
            "PeeringConnectionName": name,
            "SourceVpcId": module.params["source_vpc_id"],
            "DestinationVpcId": module.params["destination_vpc_id"],
        }
        diff = maybe_diff(module, None, desired)
        if module.check_mode:
            module.exit_json(changed=True, **(diff or {}), msg="Would create peering connection")
        _create(module, client, models, module.params)
        created = find_connection(module, client, models, None, name, source_vpc_id)
        if created is None:
            module.exit_json(
                changed=True, **(diff or {}),
                msg="Peering connection created but not yet visible; please re-run",
            )
        if (
            module.params["accept"]
            and created.get("State") == "PENDING_ACCEPTANCE"
        ):
            _accept(module, client, models, created["PeeringConnectionId"])
            created = find_connection(module, client, models, None, name, source_vpc_id)
        module.exit_json(changed=True, **(diff or {}), peering_connection=created, msg="Peering connection created")

    target_id = current["PeeringConnectionId"]
    changes = []
    if name and current.get("PeeringConnectionName") != name:
        changes.append("name")
    bandwidth = module.params["bandwidth"]
    if bandwidth is not None and current.get("Bandwidth") != bandwidth:
        changes.append("bandwidth")
    charge_type = module.params["charge_type"]
    if charge_type is not None and current.get("ChargeType") != charge_type:
        changes.append("charge_type")

    if not changes:
        module.exit_json(changed=False, peering_connection=current, msg="Peering connection is up to date")

    diff = maybe_diff(module, current, {
        "PeeringConnectionName": name or current.get("PeeringConnectionName"),
        "Bandwidth": bandwidth if bandwidth is not None else current.get("Bandwidth"),
        "ChargeType": charge_type if charge_type is not None else current.get("ChargeType"),
    })
    if module.check_mode:
        module.exit_json(changed=True, **(diff or {}), msg="Would update peering connection")

    _update(
        module, client, models, target_id,
        name if "name" in changes else None,
        bandwidth if "bandwidth" in changes else None,
        charge_type if "charge_type" in changes else None,
    )
    updated = find_connection(module, client, models, target_id, None, None)
    module.exit_json(changed=True, **(diff or {}), peering_connection=updated, msg="Peering connection updated")


def main():
    run_module()


if __name__ == "__main__":
    main()
