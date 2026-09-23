#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
---
module: chdfs_mount_access_groups_info
short_description: Gather CHDFS mount point access-group bindings
version_added: "1.4.0"
description:
  - Returns access-group IDs associated with a CHDFS mount point.
options:
  file_system_id:
    description: Parent CHDFS file system ID.
    type: str
    required: true
  mount_point_id:
    description: CHDFS mount point ID.
    type: str
    required: true
extends_documentation_fragment:
  - susunola.tencentcloud.credentials
  - susunola.tencentcloud.region
  - susunola.tencentcloud.connection
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''

EXAMPLES = r'''
- name: Read CHDFS mount access-group bindings
  susunola.tencentcloud.chdfs_mount_access_groups_info:
    region: ap-guangzhou
    file_system_id: f-xxxxxxxx
    mount_point_id: mp-xxxxxxxx
'''

RETURN = r'''
access_group_ids:
  description: Associated access-group IDs.
  returned: always
  type: list
  elements: str
mount_point:
  description: Matching CHDFS mount point metadata.
  returned: always
  type: dict
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


def build_request(models, file_system_id):
    request = models.DescribeMountPointsRequest()
    request.FileSystemId = file_system_id
    return request


def run_module():
    argument_spec = tencentcloud_argument_spec()
    argument_spec.update({
        "file_system_id": {"type": "str", "required": True},
        "mount_point_id": {"type": "str", "required": True},
    })
    module = AnsibleModule(argument_spec=argument_spec, supports_check_mode=True)
    try:
        from tencentcloud.chdfs.v20201112 import chdfs_client, models
    except ImportError:
        module.fail_json(msg="The tencentcloud-sdk-python-chdfs package is required.")

    client = chdfs_client.ChdfsClient(create_credential(module), module.params["region"], create_client_profile(module, "chdfs.tencentcloudapi.com"))
    response = sdk_call(module, client.DescribeMountPoints, build_request(models, module.params["file_system_id"]))
    matches = [
        serialize_sdk_object(item) for item in getattr(response, "MountPoints", None) or []
        if getattr(item, "MountPointId", None) == module.params["mount_point_id"]
    ]
    if not matches:
        module.fail_json(msg="CHDFS mount point was not found", mount_point_id=module.params["mount_point_id"])
    mount_point = matches[0]
    module.exit_json(
        changed=False,
        access_group_ids=sorted(mount_point.get("AccessGroupIds") or []),
        mount_point=mount_point,
        request_id=getattr(response, "RequestId", None),
    )


def main():
    run_module()


if __name__ == "__main__":
    main()
