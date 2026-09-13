#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
---
module: chdfs_access_rules_info
short_description: Gather Tencent Cloud CHDFS access rules
version_added: "1.4.0"
description:
  - Returns the access-rule set of a CHDFS access group.
options:
  access_group_id:
    description: CHDFS access group ID.
    type: str
    required: true
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''

EXAMPLES = r'''
- name: Read CHDFS access rules
  susunola.tencentcloud.chdfs_access_rules_info:
    region: ap-guangzhou
    access_group_id: ag-xxxxxxxx
'''

RETURN = r'''
rules:
  description: CHDFS access rules.
  returned: always
  type: list
  elements: dict
request_id:
  description: Request ID returned by the API, for cross-referencing cloud audit logs.
  returned: always
  type: str
'''

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.tencentcloud import (
    create_client_profile,
    create_credential,
    sdk_call,
    serialize_sdk_object,
    tencentcloud_argument_spec,
)


def build_request(models, access_group_id):
    request = models.DescribeAccessRulesRequest()
    request.AccessGroupId = access_group_id
    return request


def run_module():
    argument_spec = tencentcloud_argument_spec()
    argument_spec.update({"access_group_id": {"type": "str", "required": True}})
    module = AnsibleModule(argument_spec=argument_spec, supports_check_mode=True)
    try:
        from tencentcloud.chdfs.v20201112 import chdfs_client, models
    except ImportError:
        module.fail_json(msg="The tencentcloud-sdk-python-chdfs package is required.")

    client = chdfs_client.ChdfsClient(create_credential(module), module.params["region"], create_client_profile(module, "chdfs.tencentcloudapi.com"))
    response = sdk_call(module, client.DescribeAccessRules, build_request(models, module.params["access_group_id"]))
    module.exit_json(
        changed=False,
        rules=[serialize_sdk_object(item) for item in getattr(response, "AccessRules", None) or []],
        request_id=getattr(response, "RequestId", None),
    )


def main():
    run_module()


if __name__ == "__main__":
    main()
