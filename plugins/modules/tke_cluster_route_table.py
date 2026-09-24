#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
---
module: tke_cluster_route_table
short_description: Create or delete a Tencent Cloud TKE cluster route table
version_added: "1.1.0"
description:
  - Creates or deletes a route table for a Tencent Cloud TKE cluster.
  - The route table name is usually the cluster ID. Route table attributes
    (CIDR block and VPC) are immutable once created, so this module treats the
    table as present when a table with the same name already exists and does
    not attempt to reconcile CIDR/VPC drift (delete and recreate to change them).
  - The module is idempotent; it reads the current route tables before changing
    anything.
options:
  state:
    description: Desired state of the route table.
    type: str
    choices: [present, absent]
    default: present
  route_table_name:
    description: Route table name, usually the cluster ID.
    type: str
    required: true
  route_table_cidr_block:
    description: Route table CIDR block. Required when I(state=present).
    type: str
  vpc_id:
    description: VPC the route table is bound to. Required when I(state=present).
    type: str
  ignore_cluster_cidr_conflict:
    description: >-
      Whether to ignore CIDR conflicts with the VPC route table (0 = do not
      ignore, 1 = ignore). Only used when I(state=present).
    type: int
    default: 0
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
- name: Create a route table bound to a cluster
  susunola.tencentcloud.tke_cluster_route_table:
    route_table_name: cls-xxxxxxxx
    route_table_cidr_block: 10.4.0.0/16
    vpc_id: vpc-xxxxxxxx

- name: Remove the route table
  susunola.tencentcloud.tke_cluster_route_table:
    route_table_name: cls-xxxxxxxx
    state: absent
'''

RETURN = r'''
route_table_name:
  description: Route table name the operation targeted.
  returned: always
  type: str
exists:
  description: Whether the route table exists after the operation.
  returned: always
  type: bool
'''

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule


def _load_tke():
    from tencentcloud.tke.v20180525 import tke_client, models
    return models, tke_client


def describe_state(module, client, models, route_table_name):
    request = models.DescribeClusterRouteTablesRequest()
    response = module.sdk_call(client.DescribeClusterRouteTables, request)
    tables = list(getattr(response, "RouteTableSet", None) or [])
    for table in tables:
        if getattr(table, "RouteTableName", None) == route_table_name:
            return table
    return None


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "state": {"type": "str", "choices": ["present", "absent"], "default": "present"},
            "route_table_name": {"type": "str", "required": True},
            "route_table_cidr_block": {"type": "str"},
            "vpc_id": {"type": "str"},
            "ignore_cluster_cidr_conflict": {"type": "int", "default": 0},
        },
        required_if=[
            ("state", "present", ("route_table_cidr_block", "vpc_id")),
        ],
        supports_check_mode=True,
    )
    p = module.params
    name = p["route_table_name"]
    desired_present = p["state"] == "present"
    module.require_sdk()
    models, client_module = _load_tke()
    client = module.create_client(client_module.TkeClient, "tke.tencentcloudapi.com")
    try:
        current = describe_state(module, client, models, name)
        if bool(current) == desired_present:
            module.exit_json(
                changed=False,
                route_table_name=name,
                exists=bool(current),
                msg="Route table %s already %s" % (name, "present" if desired_present else "absent"),
            )
        if module.check_mode:
            module.exit_json(
                changed=True,
                route_table_name=name,
                exists=desired_present,
                msg="Would %s route table %s" % ("create" if desired_present else "delete", name),
            )
        if desired_present:
            request = models.CreateClusterRouteTableRequest()
            request.RouteTableName = name
            request.RouteTableCidrBlock = p["route_table_cidr_block"]
            request.VpcId = p["vpc_id"]
            request.IgnoreClusterCidrConflict = p["ignore_cluster_cidr_conflict"]
            module.sdk_call(client.CreateClusterRouteTable, request)
        else:
            request = models.DeleteClusterRouteTableRequest()
            request.RouteTableName = name
            module.sdk_call(client.DeleteClusterRouteTable, request)
        final = describe_state(module, client, models, name)
        module.exit_json(
            changed=True,
            route_table_name=name,
            exists=bool(final),
            msg="Route table %s %s" % (name, "created" if desired_present else "deleted"),
        )
    except Exception as exc:
        module.fail_sdk_error(exc, "Tencent Cloud TKE route table request failed")


def main():
    run_module()


if __name__ == "__main__":
    main()
