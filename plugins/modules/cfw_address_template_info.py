#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
---
module: cfw_address_template_info
short_description: Gather information about Tencent Cloud Cloud Firewall address templates
version_added: "1.3.0"
description: Returns Cloud Firewall address templates visible in a Tencent Cloud region.
options:
  uuid:
    description: Address template UUID to return.
    type: str
  name:
    description: Address template name used to narrow the returned templates.
    type: str
  page_size:
    description: Number of results requested per API call.
    type: int
    default: 100
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''

EXAMPLES = r'''
- name: List Cloud Firewall address templates
  susunola.tencentcloud.cfw_address_template_info:
    region: ap-guangzhou

- name: Find a Cloud Firewall address template by name
  susunola.tencentcloud.cfw_address_template_info:
    region: ap-guangzhou
    name: trusted-networks
'''

RETURN = r'''
templates:
  description: Matching Cloud Firewall address templates.
  returned: always
  type: list
  elements: dict
total_count:
  description: Number of address templates reported by the API.
  returned: always
  type: int
request_id:
  description: Request ID of the last API call, for cross-referencing cloud audit logs.
  returned: always
  type: str
'''

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.paging import Paginator
from ansible_collections.susunola.tencentcloud.plugins.module_utils.tencentcloud import (
    create_client_profile,
    create_credential,
    sdk_call,
    serialize_sdk_object,
    tencentcloud_argument_spec,
)


def build_request(models, uuid, name, offset, limit):
    request = models.DescribeAddressTemplateListRequest()
    request.Offset = offset
    request.Limit = limit
    if uuid:
        request.Uuid = uuid
    if name:
        request.SearchValue = name
    return request


def _matches(item, uuid, name):
    if uuid and item.get("Uuid") != uuid:
        return False
    if name and item.get("Name") != name:
        return False
    return True


def run_module():
    argument_spec = tencentcloud_argument_spec()
    argument_spec.update({
        "uuid": {"type": "str"},
        "name": {"type": "str"},
        "page_size": {"type": "int", "default": 100},
    })
    module = AnsibleModule(argument_spec=argument_spec, supports_check_mode=True)
    try:
        from tencentcloud.cfw.v20190904 import cfw_client, models
    except ImportError:
        module.fail_json(msg="The tencentcloud-sdk-python-cfw package is required.")

    client = cfw_client.CfwClient(
        create_credential(module),
        module.params["region"],
        create_client_profile(module, "cfw.tencentcloudapi.com"),
    )
    paginator = Paginator(
        module.params["page_size"],
        lambda offset, limit: build_request(models, module.params["uuid"], module.params["name"], offset, limit),
        lambda request: sdk_call(module, client.DescribeAddressTemplateList, request),
        lambda response: response.Data,
        lambda response: response.Total,
    )
    item_set, total_count = paginator.fetch_all()
    templates = [
        item for item in (serialize_sdk_object(value) for value in item_set)
        if _matches(item, module.params["uuid"], module.params["name"])
    ]
    module.exit_json(changed=False, templates=templates, total_count=total_count, request_id=paginator.request_id)


def main():
    run_module()


if __name__ == "__main__":
    main()
