#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
---
module: subnet_info
short_description: Gather information about Tencent Cloud subnets
version_added: "0.4.0"
description: Returns subnets visible in a Tencent Cloud region.
options:
  subnet_ids:
    description: Subnet IDs to return. Mutually exclusive with O(filters).
    type: list
    elements: str
  filters:
    description:
      - Subnet API filter names mapped to lists of values, for example
        C(vpc-id), C(subnet-name), C(cidr-block), C(zone) or C(is-default).
    type: dict
    default: {}
  page_size:
    description: Number of results requested per API call.
    type: int
    default: 100
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''

EXAMPLES = r'''
- name: List all subnets in a VPC
  susunola.tencentcloud.subnet_info:
    region: ap-guangzhou
    filters:
      vpc-id: [vpc-xxxxxxxx]

- name: Find subnets by name
  susunola.tencentcloud.subnet_info:
    region: ap-guangzhou
    filters:
      subnet-name: [web-subnet]
  register: subnets
'''

RETURN = r'''
subnets:
  description: Matching subnets.
  returned: always
  type: list
  elements: dict
total_count:
  description: Number of subnets reported by the API.
  returned: always
  type: int
'''

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.paging import Paginator
from ansible_collections.susunola.tencentcloud.plugins.module_utils.tencentcloud import (
    create_client_profile, create_credential, sdk_call, serialize_sdk_object,
    tencentcloud_argument_spec,
)


def build_request(models, subnet_ids, filters, offset, limit):
    request = models.DescribeSubnetsRequest()
    request.Offset = str(offset)
    request.Limit = str(limit)
    if subnet_ids:
        request.SubnetIds = subnet_ids
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
        "subnet_ids": {"type": "list", "elements": "str"},
        "filters": {"type": "dict", "default": {}},
        "page_size": {"type": "int", "default": 100},
    })
    module = AnsibleModule(
        argument_spec=argument_spec,
        mutually_exclusive=[("subnet_ids", "filters")],
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
    paginator = Paginator(
        module.params["page_size"],
        lambda offset, limit: build_request(
            models, module.params["subnet_ids"], module.params["filters"], offset, limit),
        lambda request: sdk_call(module, client.DescribeSubnets, request),
        lambda response: response.SubnetSet,
        lambda response: response.TotalCount,
    )
    subnet_set, total_count = paginator.fetch_all()
    subnets = [serialize_sdk_object(item) for item in subnet_set]
    module.exit_json(changed=False, subnets=subnets, total_count=total_count)


def main():
    run_module()


if __name__ == "__main__":
    main()
