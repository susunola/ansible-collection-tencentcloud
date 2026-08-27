#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
---
module: cam_role_info
short_description: Gather information about Tencent Cloud CAM roles
version_added: "0.5.0"
description:
  - Returns CAM roles visible to the account.
  - Roles are listed with the page-based DescribeRoleList API; O(role_id) and
    O(role_name) filter the result client-side.
options:
  role_id:
    description: Return only the role with this ID.
    type: str
  role_name:
    description: Return only the role with this exact name.
    type: str
  page_size:
    description: Number of results requested per API call (maximum 200).
    type: int
    default: 100
notes:
  - Requires the C(tencentcloud-sdk-python-cam) package on the controller.
  - CAM is a global service. O(region) is accepted but ignored; the global
    C(cam.tencentcloudapi.com) endpoint is used.
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''

EXAMPLES = r'''
- name: List all CAM roles
  susunola.tencentcloud.cam_role_info:
    region: ap-guangzhou

- name: Find a role by name
  susunola.tencentcloud.cam_role_info:
    region: ap-guangzhou
    role_name: app-instance-role
'''

RETURN = r'''
roles:
  description: Matching CAM roles.
  returned: always
  type: list
  elements: dict
total_count:
  description: Number of roles returned.
  returned: always
  type: int
'''

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.tencentcloud import (
    create_client_profile, create_credential, sdk_call, serialize_sdk_object,
    tencentcloud_argument_spec,
)


def build_request(models, page, page_size):
    request = models.DescribeRoleListRequest()
    request.Page = page
    request.Rp = page_size
    return request


def run_module():
    argument_spec = tencentcloud_argument_spec()
    argument_spec.update({
        "role_id": {"type": "str"},
        "role_name": {"type": "str"},
        "page_size": {"type": "int", "default": 100},
    })
    module = AnsibleModule(
        argument_spec=argument_spec,
        supports_check_mode=True,
    )
    try:
        from tencentcloud.cam.v20190116 import models, cam_client
    except ImportError:
        module.fail_json(msg="The tencentcloud-sdk-python package with CAM support is required.")

    client = cam_client.CamClient(
        create_credential(module), module.params["region"],
        create_client_profile(module, "cam.tencentcloudapi.com"),
    )
    role_id = module.params["role_id"]
    role_name = module.params["role_name"]
    roles = []
    page = 1
    while True:
        request = build_request(models, page, module.params["page_size"])
        response = sdk_call(module, client.DescribeRoleList, request)
        batch = response.List or []
        for role in batch:
            if role_id and role.RoleId != role_id:
                continue
            if role_name and role.RoleName != role_name:
                continue
            roles.append(serialize_sdk_object(role))
        total = response.TotalNum or 0
        page += 1
        if not batch or (page - 1) * module.params["page_size"] >= total:
            break
    module.exit_json(changed=False, roles=roles, total_count=len(roles))


def main():
    run_module()


if __name__ == "__main__":
    main()
