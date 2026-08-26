#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
---
module: vpc_info
short_description: Gather information about Tencent Cloud VPCs
version_added: "0.2.0"
description: Returns VPCs visible in a Tencent Cloud region.
options:
  vpc_ids:
    description: VPC IDs to return. Mutually exclusive with O(filters).
    type: list
    elements: str
  filters:
    description: VPC API filter names mapped to lists of values.
    type: dict
    default: {}
  page_size:
    description: Number of results requested per API call.
    type: int
    default: 100
extends_documentation_fragment: tencentcloud.cloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors
'''

EXAMPLES = r'''
- name: Find the default VPC
  tencentcloud.cloud.vpc_info:
    region: ap-guangzhou
    filters:
      is-default: [true]
'''

RETURN = r'''
vpcs:
  description: Matching VPCs.
  returned: always
  type: list
  elements: dict
total_count:
  description: Number of VPCs reported by the API.
  returned: always
  type: int
'''

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.tencentcloud.cloud.plugins.module_utils.tencentcloud import (
    create_client_profile, create_credential, sdk_call, serialize_sdk_object,
    tencentcloud_argument_spec,
)


def build_request(models, vpc_ids, filters, offset, limit):
    request = models.DescribeVpcsRequest()
    request.Offset = str(offset)
    request.Limit = str(limit)
    if vpc_ids:
        request.VpcIds = vpc_ids
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
        "vpc_ids": {"type": "list", "elements": "str"},
        "filters": {"type": "dict", "default": {}},
        "page_size": {"type": "int", "default": 100},
    })
    module = AnsibleModule(
        argument_spec=argument_spec,
        mutually_exclusive=[("vpc_ids", "filters")],
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
    vpcs = []
    offset = 0
    total_count = 0
    while True:
        request = build_request(models, module.params["vpc_ids"], module.params["filters"], offset, module.params["page_size"])
        response = sdk_call(module, client.DescribeVpcs, request)
        batch = [serialize_sdk_object(item) for item in (response.VpcSet or [])]
        vpcs.extend(batch)
        total_count = response.TotalCount or 0
        offset += len(batch)
        if not batch or offset >= total_count:
            break
    module.exit_json(changed=False, vpcs=vpcs, total_count=total_count)


def main():
    run_module()


if __name__ == "__main__":
    main()
