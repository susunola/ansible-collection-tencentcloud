#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
---
module: security_group_info
short_description: Gather information about Tencent Cloud security groups
version_added: "0.2.0"
description: Returns security groups visible in a Tencent Cloud region.
options:
  security_group_ids:
    description: Security group IDs to return. Mutually exclusive with O(filters).
    type: list
    elements: str
  filters:
    description: Security group API filter names mapped to lists of values.
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
- name: Find security groups by name
  susunola.tencentcloud.security_group_info:
    region: ap-guangzhou
    filters:
      security-group-name: [web]
'''

RETURN = r'''
security_groups:
  description: Matching security groups.
  returned: always
  type: list
  elements: dict
total_count:
  description: Number of security groups reported by the API.
  returned: always
  type: int
'''

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.tencentcloud import (
    create_client_profile, create_credential, sdk_call, serialize_sdk_object,
    tencentcloud_argument_spec,
)


def build_request(models, security_group_ids, filters, offset, limit):
    request = models.DescribeSecurityGroupsRequest()
    request.Offset = str(offset)
    request.Limit = str(limit)
    if security_group_ids:
        request.SecurityGroupIds = security_group_ids
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
        "security_group_ids": {"type": "list", "elements": "str"},
        "filters": {"type": "dict", "default": {}},
        "page_size": {"type": "int", "default": 100},
    })
    module = AnsibleModule(
        argument_spec=argument_spec,
        mutually_exclusive=[("security_group_ids", "filters")],
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
    security_groups = []
    offset = 0
    total_count = 0
    while True:
        request = build_request(models, module.params["security_group_ids"], module.params["filters"], offset, module.params["page_size"])
        response = sdk_call(module, client.DescribeSecurityGroups, request)
        batch = [serialize_sdk_object(item) for item in (response.SecurityGroupSet or [])]
        security_groups.extend(batch)
        total_count = response.TotalCount or 0
        offset += len(batch)
        if not batch or offset >= total_count:
            break
    module.exit_json(changed=False, security_groups=security_groups, total_count=total_count)


def main():
    run_module()


if __name__ == "__main__":
    main()
