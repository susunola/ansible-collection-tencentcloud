#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
---
module: key_pair_info
short_description: Gather information about Tencent Cloud CVM key pairs
version_added: "0.4.0"
description: Returns CVM key pairs (SSH keys) visible in a Tencent Cloud region.
options:
  key_ids:
    description:
      - Key pair IDs to return, e.g. C(skey-xxxxxxxx).
      - Mutually exclusive with O(filters).
    type: list
    elements: str
  filters:
    description:
      - CVM key pair API filter names mapped to lists of values, e.g.
        I(key-name), I(project-id), I(tag-key) or I(tag-value).
    type: dict
    default: {}
  page_size:
    description: Number of results requested per API call (maximum 100).
    type: int
    default: 100
extends_documentation_fragment: tencentcloud.cloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''

EXAMPLES = r'''
- name: List all key pairs in a region
  tencentcloud.cloud.key_pair_info:
    region: ap-guangzhou

- name: Find a key pair by name
  tencentcloud.cloud.key_pair_info:
    region: ap-guangzhou
    filters:
      key-name: [deploy-key]

- name: Describe specific key pairs
  tencentcloud.cloud.key_pair_info:
    region: ap-guangzhou
    key_ids:
      - skey-xxxxxxxx
'''

RETURN = r'''
key_pairs:
  description: Matching key pairs represented as dictionaries.
  returned: always
  type: list
  elements: dict
total_count:
  description: Number of key pairs reported by the API.
  returned: always
  type: int
'''

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.tencentcloud.cloud.plugins.module_utils.tencentcloud import (
    create_client_profile, create_credential, sdk_call, serialize_sdk_object,
    tencentcloud_argument_spec,
)


def build_request(models, key_ids, filters, offset, limit):
    request = models.DescribeKeyPairsRequest()
    request.Offset = offset
    request.Limit = limit
    if key_ids:
        request.KeyIds = key_ids
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
        "key_ids": {"type": "list", "elements": "str", "no_log": False},
        "filters": {"type": "dict", "default": {}},
        "page_size": {"type": "int", "default": 100},
    })
    module = AnsibleModule(
        argument_spec=argument_spec,
        mutually_exclusive=[("key_ids", "filters")],
        supports_check_mode=True,
    )
    try:
        from tencentcloud.cvm.v20170312 import cvm_client, models
    except ImportError:
        module.fail_json(msg="The tencentcloud-sdk-python package with CVM support is required.")

    client = cvm_client.CvmClient(
        create_credential(module),
        module.params["region"],
        create_client_profile(module, "cvm.tencentcloudapi.com"),
    )
    key_pairs = []
    offset = 0
    total_count = 0
    while True:
        request = build_request(models, module.params["key_ids"], module.params["filters"], offset, module.params["page_size"])
        response = sdk_call(module, client.DescribeKeyPairs, request)
        batch = [serialize_sdk_object(item) for item in (response.KeyPairSet or [])]
        key_pairs.extend(batch)
        total_count = response.TotalCount or 0
        offset += len(batch)
        if not batch or offset >= total_count:
            break
    module.exit_json(changed=False, key_pairs=key_pairs, total_count=total_count)


def main():
    run_module()


if __name__ == "__main__":
    main()
