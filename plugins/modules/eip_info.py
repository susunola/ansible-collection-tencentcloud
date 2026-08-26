#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
---
module: eip_info
short_description: Gather information about Tencent Cloud elastic IP addresses (EIP)
version_added: "0.4.0"
description: Returns elastic IP addresses visible in a Tencent Cloud region.
options:
  address_ids:
    description:
      - Address IDs to return, e.g. C(eip-xxxxxxxx).
      - Mutually exclusive with O(address_ips) and O(filters).
    type: list
    elements: str
  address_ips:
    description:
      - Public IP addresses to return, e.g. C(1.2.3.4).
      - Translated into an C(address-ip) filter; do not combine with an
        C(address-ip) key in O(filters).
    type: list
    elements: str
  filters:
    description: Address API filter names mapped to lists of values.
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
- name: List all addresses in a region
  tencentcloud.cloud.eip_info:
    region: ap-guangzhou

- name: Find addresses bound to an instance
  tencentcloud.cloud.eip_info:
    region: ap-guangzhou
    filters:
      instance-id: [ins-xxxxxxxx]

- name: Look up specific addresses by IP
  tencentcloud.cloud.eip_info:
    region: ap-guangzhou
    address_ips:
      - 1.2.3.4
'''

RETURN = r'''
addresses:
  description: Matching addresses.
  returned: always
  type: list
  elements: dict
total_count:
  description: Number of addresses reported by the API.
  returned: always
  type: int
'''

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.tencentcloud.cloud.plugins.module_utils.tencentcloud import (
    create_client_profile, create_credential, sdk_call, serialize_sdk_object,
    tencentcloud_argument_spec,
)


def build_request(models, address_ids, address_ips, filters, offset, limit):
    request = models.DescribeAddressesRequest()
    request.Offset = offset
    request.Limit = limit
    if address_ids:
        request.AddressIds = address_ids
    else:
        merged = dict(filters or {})
        if address_ips:
            merged["address-ip"] = list(address_ips)
        if merged:
            request.Filters = []
            for name, values in sorted(merged.items()):
                api_filter = models.Filter()
                api_filter.Name = name
                api_filter.Values = values if isinstance(values, list) else [values]
                request.Filters.append(api_filter)
    return request


def run_module():
    argument_spec = tencentcloud_argument_spec()
    argument_spec.update({
        "address_ids": {"type": "list", "elements": "str"},
        "address_ips": {"type": "list", "elements": "str"},
        "filters": {"type": "dict", "default": {}},
        "page_size": {"type": "int", "default": 100},
    })
    module = AnsibleModule(
        argument_spec=argument_spec,
        mutually_exclusive=[("address_ids", "address_ips"), ("address_ids", "filters")],
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
    addresses = []
    offset = 0
    total_count = 0
    while True:
        request = build_request(
            models,
            module.params["address_ids"],
            module.params["address_ips"],
            module.params["filters"],
            offset,
            module.params["page_size"],
        )
        response = sdk_call(module, client.DescribeAddresses, request)
        batch = [serialize_sdk_object(item) for item in (response.AddressSet or [])]
        addresses.extend(batch)
        total_count = response.TotalCount or 0
        offset += len(batch)
        if not batch or offset >= total_count:
            break
    module.exit_json(changed=False, addresses=addresses, total_count=total_count)


def main():
    run_module()


if __name__ == "__main__":
    main()
