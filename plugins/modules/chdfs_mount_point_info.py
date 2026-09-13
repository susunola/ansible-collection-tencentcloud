#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
---
module: chdfs_mount_point_info
short_description: Gather Tencent Cloud CHDFS mount points
version_added: "1.4.0"
description:
  - Returns CHDFS mount points of a file system.
options:
  file_system_id:
    description: Parent CHDFS file system ID.
    type: str
    required: true
  mount_point_id:
    description: Optional mount point ID to return.
    type: str
  name:
    description: Optional mount point name to return.
    type: str
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''

EXAMPLES = r'''
- name: List CHDFS mount points
  susunola.tencentcloud.chdfs_mount_point_info:
    region: ap-guangzhou
    file_system_id: f-xxxxxxxx
'''

RETURN = r'''
mount_points:
  description: Matching CHDFS mount points.
  returned: always
  type: list
  elements: dict
mount_point:
  description: First matching mount point when C(mount_point_id) or C(name) is supplied.
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


def _matches(item, mount_point_id, name):
    if mount_point_id and item.get("MountPointId") != mount_point_id:
        return False
    if name and item.get("MountPointName") != name:
        return False
    return True


def run_module():
    argument_spec = tencentcloud_argument_spec()
    argument_spec.update({
        "file_system_id": {"type": "str", "required": True},
        "mount_point_id": {"type": "str"},
        "name": {"type": "str"},
    })
    module = AnsibleModule(argument_spec=argument_spec, supports_check_mode=True)
    try:
        from tencentcloud.chdfs.v20201112 import chdfs_client, models
    except ImportError:
        module.fail_json(msg="The tencentcloud-sdk-python-chdfs package is required.")

    client = chdfs_client.ChdfsClient(create_credential(module), module.params["region"], create_client_profile(module, "chdfs.tencentcloudapi.com"))
    response = sdk_call(module, client.DescribeMountPoints, build_request(models, module.params["file_system_id"]))
    mount_points = [
        item for item in (serialize_sdk_object(value) for value in getattr(response, "MountPoints", None) or [])
        if _matches(item, module.params["mount_point_id"], module.params["name"])
    ]
    selected = mount_points[0] if (module.params["mount_point_id"] or module.params["name"]) and mount_points else None
    module.exit_json(changed=False, mount_points=mount_points, mount_point=selected, request_id=getattr(response, "RequestId", None))


def main():
    run_module()


if __name__ == "__main__":
    main()
