#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
---
module: tke_cluster_route
short_description: Create or delete a route in a Tencent Cloud TKE cluster route table
version_added: "1.1.0"
description:
  - Creates or deletes a route (destination CIDR -> next-hop gateway) inside a
    Tencent Cloud TKE cluster route table.
  - A route is uniquely identified within a route table by its destination CIDR
    block. The module is idempotent; it reads the current routes before changing
    anything.
options:
  state:
    description: Desired state of the route.
    type: str
    choices: [present, absent]
    default: present
  route_table_name:
    description: Route table name (usually the cluster ID) the route belongs to.
    type: str
    required: true
  destination_cidr_block:
    description: Destination PodCIDR of the route.
    type: str
    required: true
  gateway_ip:
    description: Next-hop address, i.e. the private IP of the destination node.
    type: str
    required: true
extends_documentation_fragment:
  - susunola.tencentcloud.credentials
  - susunola.tencentcloud.region
  - susunola.tencentcloud.connection
  - susunola.tencentcloud.retry
  - susunola.tencentcloud.user_agent
  - susunola.tencentcloud.waiter
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''

EXAMPLES = r'''
- name: Add a route to a cluster route table
  susunola.tencentcloud.tke_cluster_route:
    route_table_name: cls-xxxxxxxx
    destination_cidr_block: 10.4.0.0/16
    gateway_ip: 10.4.0.12

- name: Remove a route
  susunola.tencentcloud.tke_cluster_route:
    route_table_name: cls-xxxxxxxx
    destination_cidr_block: 10.4.0.0/16
    gateway_ip: 10.4.0.12
    state: absent
'''

RETURN = r'''
route_table_name:
  description: Route table the operation targeted.
  returned: always
  type: str
destination_cidr_block:
  description: Destination CIDR block of the route.
  returned: always
  type: str
gateway_ip:
  description: Next-hop gateway IP of the route.
  returned: always
  type: str
exists:
  description: Whether the route exists after the operation.
  returned: always
  type: bool
'''

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule


def _load_tke():
    from tencentcloud.tke.v20180525 import tke_client, models
    return models, tke_client


def describe_state(module, client, models, route_table_name, destination_cidr_block):
    request = models.DescribeClusterRoutesRequest()
    request.RouteTableName = route_table_name
    response = module.sdk_call(client.DescribeClusterRoutes, request)
    routes = list(getattr(response, "RouteSet", None) or [])
    for route in routes:
        if getattr(route, "DestinationCidrBlock", None) == destination_cidr_block:
            return route
    return None


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "state": {"type": "str", "choices": ["present", "absent"], "default": "present"},
            "route_table_name": {"type": "str", "required": True},
            "destination_cidr_block": {"type": "str", "required": True},
            "gateway_ip": {"type": "str", "required": True},
        },
        supports_check_mode=True,
    )
    p = module.params
    name = p["route_table_name"]
    dest = p["destination_cidr_block"]
    desired_present = p["state"] == "present"
    module.require_sdk()
    models, client_module = _load_tke()
    client = module.create_client(client_module.TkeClient, "tke.tencentcloudapi.com")
    try:
        current = describe_state(module, client, models, name, dest)
        if bool(current) == desired_present:
            module.exit_json(
                changed=False,
                route_table_name=name,
                destination_cidr_block=dest,
                gateway_ip=p["gateway_ip"],
                exists=bool(current),
                msg="Route %s/%s already %s" % (name, dest, "present" if desired_present else "absent"),
            )
        if module.check_mode:
            module.exit_json(
                changed=True,
                route_table_name=name,
                destination_cidr_block=dest,
                gateway_ip=p["gateway_ip"],
                exists=desired_present,
                msg="Would %s route %s/%s" % ("create" if desired_present else "delete", name, dest),
            )
        if desired_present:
            request = models.CreateClusterRouteRequest()
            request.RouteTableName = name
            request.DestinationCidrBlock = dest
            request.GatewayIp = p["gateway_ip"]
            module.sdk_call(client.CreateClusterRoute, request)
        else:
            request = models.DeleteClusterRouteRequest()
            request.RouteTableName = name
            request.DestinationCidrBlock = dest
            request.GatewayIp = p["gateway_ip"]
            module.sdk_call(client.DeleteClusterRoute, request)
        final = describe_state(module, client, models, name, dest)
        module.exit_json(
            changed=True,
            route_table_name=name,
            destination_cidr_block=dest,
            gateway_ip=p["gateway_ip"],
            exists=bool(final),
            msg="Route %s/%s %s" % (name, dest, "created" if desired_present else "deleted"),
        )
    except Exception as exc:
        module.fail_sdk_error(exc, "Tencent Cloud TKE route request failed")


def main():
    run_module()


if __name__ == "__main__":
    main()
