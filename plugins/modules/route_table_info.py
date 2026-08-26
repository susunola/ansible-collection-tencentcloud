#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
---
module: route_table_info
short_description: Gather information about Tencent Cloud VPC route tables
version_added: "0.4.0"
description: Returns route tables, including their route entries, visible in a Tencent Cloud region.
options:
  route_table_ids:
    description:
      - Route table IDs to return, e.g. C(rtb-xxxxxxxx).
      - Mutually exclusive with O(filters); the API does not accept both.
    type: list
    elements: str
  filters:
    description:
      - Route table API filter names mapped to lists of values, e.g.
        C(vpc-id), C(route-table-name), C(association.main), C(tag-key).
    type: dict
    default: {}
  page_size:
    description: Number of results requested per API call.
    type: int
    default: 100
extends_documentation_fragment: tencentcloud.cloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''

EXAMPLES = r'''
- name: List all route tables in a VPC
  tencentcloud.cloud.route_table_info:
    region: ap-guangzhou
    filters:
      vpc-id: [vpc-xxxxxxxx]

- name: Describe a specific route table
  tencentcloud.cloud.route_table_info:
    region: ap-guangzhou
    route_table_ids:
      - rtb-xxxxxxxx
'''

RETURN = r'''
route_tables:
  description: Matching route tables, each including its route entries in C(RouteSet).
  returned: always
  type: list
  elements: dict
total_count:
  description: Number of route tables reported by the API.
  returned: always
  type: int
'''

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.tencentcloud.cloud.plugins.module_utils.tencentcloud import (
    create_client_profile, create_credential, sdk_call, serialize_sdk_object,
    tencentcloud_argument_spec,
)


def build_request(models, route_table_ids, filters, offset, limit):
    request = models.DescribeRouteTablesRequest()
    request.Offset = str(offset)
    request.Limit = str(limit)
    if route_table_ids:
        request.RouteTableIds = route_table_ids
    if filters:
        request.Filters = []
        for name, values in sorted(filters.items()):
            api_filter = models.Filter()
            api_filter.Name = name
            api_filter.Values = values if isinstance(values, list) else [values]
            request.Filters.append(api_filter)
    return request


def run_module():
    argument_spec = tencentcloud_argument_spec()
    argument_spec.update({
        "route_table_ids": {"type": "list", "elements": "str"},
        "filters": {"type": "dict", "default": {}},
        "page_size": {"type": "int", "default": 100},
    })
    module = AnsibleModule(
        argument_spec=argument_spec,
        mutually_exclusive=[("route_table_ids", "filters")],
        supports_check_mode=True,
    )
    try:
        from tencentcloud.vpc.v20170312 import models, vpc_client
    except ImportError:
        module.fail_json(msg="The tencentcloud-sdk-python package with VPC support is required.")

    client = vpc_client.VpcClient(
        create_credential(module), module.params["region"],
        create_client_profile(module, "vpc.tencentcloudapi.com"),
    )
    route_tables = []
    offset = 0
    total_count = 0
    while True:
        request = build_request(models, module.params["route_table_ids"], module.params["filters"], offset, module.params["page_size"])
        response = sdk_call(module, client.DescribeRouteTables, request)
        batch = [serialize_sdk_object(item) for item in (response.RouteTableSet or [])]
        route_tables.extend(batch)
        total_count = response.TotalCount or 0
        offset += len(batch)
        if not batch or offset >= total_count:
            break
    module.exit_json(changed=False, route_tables=route_tables, total_count=total_count)


def main():
    run_module()


if __name__ == "__main__":
    main()
