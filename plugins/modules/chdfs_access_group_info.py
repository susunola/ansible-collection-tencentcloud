#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
---
module: chdfs_access_group_info
short_description: Gather Tencent Cloud CHDFS access groups
version_added: "1.4.0"
description:
  - Returns CHDFS access groups visible in a Tencent Cloud region.
options:
  access_group_id:
    description: Optional access group ID to return.
    type: str
  name:
    description: Optional access group name to return.
    type: str
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''

EXAMPLES = r'''
- name: List CHDFS access groups
  susunola.tencentcloud.chdfs_access_group_info:
    region: ap-guangzhou
'''

RETURN = r'''
access_groups:
  description: Matching CHDFS access groups.
  returned: always
  type: list
  elements: dict
access_group:
  description: First matching access group when C(access_group_id) or C(name) is supplied.
  returned: always
  type: dict
request_id:
  description: Request ID of the last API call, for cross-referencing cloud audit logs.
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


def build_request(models, marker=None):
    request = models.DescribeAccessGroupsRequest()
    request.AccessGroupIdMarker = marker
    return request


def _matches(item, access_group_id, name):
    if access_group_id and item.get("AccessGroupId") != access_group_id:
        return False
    if name and item.get("AccessGroupName") != name:
        return False
    return True


def run_module():
    argument_spec = tencentcloud_argument_spec()
    argument_spec.update({
        "access_group_id": {"type": "str"},
        "name": {"type": "str"},
    })
    module = AnsibleModule(argument_spec=argument_spec, supports_check_mode=True)
    try:
        from tencentcloud.chdfs.v20201112 import chdfs_client, models
    except ImportError:
        module.fail_json(msg="The tencentcloud-sdk-python-chdfs package is required.")

    client = chdfs_client.ChdfsClient(create_credential(module), module.params["region"], create_client_profile(module, "chdfs.tencentcloudapi.com"))
    marker = None
    request_id = None
    access_groups = []
    while True:
        response = sdk_call(module, client.DescribeAccessGroups, build_request(models, marker))
        request_id = getattr(response, "RequestId", None)
        access_groups.extend(
            item for item in (serialize_sdk_object(value) for value in getattr(response, "AccessGroups", None) or [])
            if _matches(item, module.params["access_group_id"], module.params["name"])
        )
        marker = getattr(response, "NextAccessGroupIdMarker", None)
        if getattr(response, "IsOver", True) or not marker:
            break
    selected = access_groups[0] if (module.params["access_group_id"] or module.params["name"]) and access_groups else None
    module.exit_json(changed=False, access_groups=access_groups, access_group=selected, request_id=request_id)


def main():
    run_module()


if __name__ == "__main__":
    main()
