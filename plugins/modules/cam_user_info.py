#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
---
module: cam_user_info
short_description: Gather information about Tencent Cloud CAM sub-users
version_added: "0.5.0"
description:
  - Returns CAM sub-users visible to the account.
  - Sub-users are listed with the parameterless ListUsers API, which returns
    every sub-user in a single call; O(name) and O(name_keyword) filter the
    result client-side.
options:
  name:
    description: Return only the sub-user with this exact name.
    type: str
  name_keyword:
    description: Return only sub-users whose name contains this substring.
    type: str
notes:
  - Requires the C(tencentcloud-sdk-python-cam) package on the controller.
  - CAM is a global service. O(region) is accepted but ignored; the global
    C(cam.tencentcloudapi.com) endpoint is used.
extends_documentation_fragment: tencentcloud.cloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''

EXAMPLES = r'''
- name: List all CAM sub-users
  tencentcloud.cloud.cam_user_info:
    region: ap-guangzhou

- name: Find a sub-user by exact name
  tencentcloud.cloud.cam_user_info:
    region: ap-guangzhou
    name: deploy-bot

- name: Find sub-users whose name contains a keyword
  tencentcloud.cloud.cam_user_info:
    region: ap-guangzhou
    name_keyword: bot
'''

RETURN = r'''
users:
  description: Matching CAM sub-users.
  returned: always
  type: list
  elements: dict
  sample:
    - Uin: 100000000001
      Name: deploy-bot
      Uid: 2000001
      Remark: CI deployment account
      ConsoleLogin: 1
      CreateTime: "2026-08-26 12:00:00"
total_count:
  description: Number of sub-users returned after client-side filtering.
  returned: always
  type: int
'''

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.tencentcloud.cloud.plugins.module_utils.tencentcloud import (
    create_client_profile, create_credential, sdk_call, serialize_sdk_object,
    tencentcloud_argument_spec,
)


def build_request(models):
    """Build a ListUsers request; the API takes no parameters."""
    return models.ListUsersRequest()


def matches(user, name=None, name_keyword=None):
    """True when a SubAccountInfo passes the client-side filters."""
    if name and user.Name != name:
        return False
    if name_keyword and name_keyword not in (user.Name or ""):
        return False
    return True


def run_module():
    argument_spec = tencentcloud_argument_spec()
    argument_spec.update({
        "name": {"type": "str"},
        "name_keyword": {"type": "str", "no_log": False},
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
    response = sdk_call(module, client.ListUsers, build_request(models))
    name = module.params["name"]
    name_keyword = module.params["name_keyword"]
    users = [
        serialize_sdk_object(user)
        for user in (response.Data or [])
        if matches(user, name, name_keyword)
    ]
    module.exit_json(changed=False, users=users, total_count=len(users))


def main():
    run_module()


if __name__ == "__main__":
    main()
