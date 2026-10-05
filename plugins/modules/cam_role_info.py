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
extends_documentation_fragment:
  - susunola.tencentcloud.credentials
  - susunola.tencentcloud.region
  - susunola.tencentcloud.connection
  - susunola.tencentcloud.timeout
attributes:
  check_mode:
    description:
      - Can run in C(check_mode), reading the current state and predicting
        the result without issuing a write API call.
    support: full
  idempotent:
    description:
      - Read-only, so every run returns the current state and never changes
        the target, and a repeated run reports C(changed=false).
    support: full
seealso:
  - module: susunola.tencentcloud.cam_role
    description: Manage Tencent Cloud CAM roles.
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
  sample:
    # shape captured from this module's unit tests -- scripts/add_return_samples.py
    - RoleId: A1
      RoleName: role-a
total_count:
  description: Number of roles returned.
  returned: always
  type: int
  sample: 3
'''

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.tencentcloud import (
    create_client_profile, create_credential, paginate_read, serialize_sdk_object,
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
    if module.params["page_size"] < 1:
        module.fail_json(msg="page_size must be at least 1")
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
    item_set, _reported_total, _request_id = paginate_read(
        module,
        module.params["page_size"],
        lambda offset, limit: build_request(models, offset // limit + 1, limit),
        client.DescribeRoleList,
        lambda response: response.List,
        lambda response: response.TotalNum,
    )
    for role in item_set:
        if role_id and role.RoleId != role_id:
            continue
        if role_name and role.RoleName != role_name:
            continue
        roles.append(serialize_sdk_object(role))
    module.exit_json(changed=False, roles=roles, total_count=len(roles))


def main():
    run_module()


if __name__ == "__main__":
    main()
