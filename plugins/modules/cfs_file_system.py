#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
---
module: cfs_file_system
short_description: Manage Tencent Cloud CFS file systems
version_added: "0.12.0"
description:
  - Create, update, describe and delete Tencent Cloud CFS file systems
    through the C(cfs.v20190719) API.
  - This module is idempotent. Running it twice leaves the file system
    unchanged and the second run reports C(changed=false).
  - Supports check mode; no API write happens in check mode, only reads.
options:
  state:
    description:
      - C(present) creates the file system when it does not exist, and
        updates its name and size limit when it does.
      - C(absent) deletes the file system.
    type: str
    choices: [present, absent]
    default: present
  file_system_id:
    description:
      - ID of an existing file system, e.g. C(cfs-xxxxxxxx).
      - When given, the module operates on that file system; otherwise the
        file system is matched by O(name) and the first match is used.
    type: str
  name:
    description:
      - Display name of the file system.
      - Used to look up the file system when O(file_system_id) is not given,
        and as the desired name to enforce on an existing file system.
    type: str
  zone:
    description:
      - Availability zone for creation, e.g. C(ap-guangzhou-3).
      - Required when the file system does not exist yet; only applied at
        creation.
    type: str
  protocol:
    description:
      - Protocol type written to V(CreateCfsFileSystemRequest.Protocol).
      - Only applied at creation.
    type: str
    choices: [NFS, CIFS]
    default: NFS
  storage_type:
    description:
      - Storage type written to V(CreateCfsFileSystemRequest.StorageType).
      - Only applied at creation.
    type: str
    choices: [SD, HP, SD_HP, TP, SD_HIGH_AVAIL]
    default: SD
  capacity:
    description:
      - Capacity in GiB written to V(CreateCfsFileSystemRequest.Capacity).
      - Only applied at creation.
    type: int
    default: 10
  vpc_id:
    description:
      - VPC ID for the file system network, written to
        V(CreateCfsFileSystemRequest.VpcId). Only applied at creation.
    type: str
  subnet_id:
    description:
      - Subnet ID for the file system network, written to
        V(CreateCfsFileSystemRequest.SubnetId). Only applied at creation.
    type: str
  pgroup_id:
    description:
      - Permission group ID written to V(CreateCfsFileSystemRequest.PGroupId).
      - Only applied at creation.
    type: str
  size_limit:
    description:
      - Desired size limit in GiB enforced through
        V(UpdateCfsFileSystemSizeLimitRequest.FsLimit).
      - When given, the size limit of an existing file system is
        reconciled; a differing limit counts as a change.
    type: int
  retries:
    description: Number of retries for transient SDK failures.
    type: int
    default: 5
  waiter_delay:
    description: Seconds to wait between state-polling attempts.
    type: int
    default: 5
  waiter_timeout:
    description: Overall timeout in seconds for state polling.
    type: int
    default: 120
  user_agent:
    description:
      - Value appended to the SDK User-Agent header so API usage can be
        attributed to this collection.
    type: str
    default: ansible-collection.susunola.tencentcloud
notes:
  - Requires the C(tencentcloud-sdk-python-cfs) package on the controller.
  - CFS file systems are zone-scoped, so O(zone) is required at creation.
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''

EXAMPLES = r'''
- name: Create a CFS file system
  susunola.tencentcloud.cfs_file_system:
    region: ap-guangzhou
    state: present
    name: app-share
    zone: ap-guangzhou-3
    protocol: NFS
    storage_type: SD
    capacity: 100
    vpc_id: vpc-xxxxxxxx
    subnet_id: subnet-xxxxxxxx

- name: Enforce a size limit on an existing file system
  susunola.tencentcloud.cfs_file_system:
    region: ap-guangzhou
    state: present
    name: app-share
    size_limit: 200

- name: Delete a file system
  susunola.tencentcloud.cfs_file_system:
    region: ap-guangzhou
    state: absent
    name: app-share
'''

RETURN = r'''
file_system:
  description: The file system as reported by V(DescribeCfsFileSystems) after the operation.
  returned: success
  type: dict
  sample:
    FileSystemId: cfs-xxxxxxxx
    Name: app-share
    Protocol: NFS
    StorageType: SD
    Zone: ap-guangzhou-3
    Capacity: 100
'''

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff


def _load_cfs():
    from tencentcloud.cfs.v20190719 import models, cfs_client
    return models, cfs_client


def build_describe_request(models, file_system_id, name):
    request = models.DescribeCfsFileSystemsRequest()
    request.Offset = 0
    request.Limit = 100
    if file_system_id:
        request.FileSystemId = file_system_id
    return request


def _first(collection):
    return collection[0] if collection else None


def find_file_system(module, client, models, file_system_id, name):
    """Return the matching file system dict or None.

    The CFS describe API filters by ``FileSystemId`` (or subnet/VPC), not by
    name, so a name lookup scans pages and compares the ``Name`` field.
    """
    request = build_describe_request(models, file_system_id, None)
    offset = 0
    while True:
        request.Offset = offset
        response = module.sdk_call(client.DescribeCfsFileSystems, request)
        page = response.FileSystems or []
        for item in page:
            serialized = item._serialize(allow_none=True)
            if file_system_id:
                return serialized
            if name is not None and serialized.get("Name") == name:
                return serialized
        offset += len(page)
        total = response.TotalCount or 0
        if not page or offset >= total:
            return None


def _create(module, client, models, params):
    request = models.CreateCfsFileSystemRequest()
    request.Zone = params["zone"]
    request.Protocol = params["protocol"]
    request.StorageType = params["storage_type"]
    request.Capacity = params["capacity"]
    if params["name"]:
        request.FsName = params["name"]
    if params["vpc_id"]:
        request.VpcId = params["vpc_id"]
    if params["subnet_id"]:
        request.SubnetId = params["subnet_id"]
    if params["pgroup_id"]:
        request.PGroupId = params["pgroup_id"]
    return module.sdk_call(client.CreateCfsFileSystem, request)


def _update_name(module, client, models, file_system_id, name):
    request = models.UpdateCfsFileSystemNameRequest()
    request.FileSystemId = file_system_id
    request.FsName = name
    module.sdk_call(client.UpdateCfsFileSystemName, request)


def _update_size_limit(module, client, models, file_system_id, size_limit):
    request = models.UpdateCfsFileSystemSizeLimitRequest()
    request.FileSystemId = file_system_id
    request.FsLimit = size_limit
    module.sdk_call(client.UpdateCfsFileSystemSizeLimit, request)


def _delete(module, client, models, file_system_id):
    request = models.DeleteCfsFileSystemRequest()
    request.FileSystemId = file_system_id
    module.sdk_call(client.DeleteCfsFileSystem, request)


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "state": {"type": "str", "choices": ["present", "absent"], "default": "present"},
            "file_system_id": {"type": "str"},
            "name": {"type": "str"},
            "zone": {"type": "str"},
            "protocol": {"type": "str", "choices": ["NFS", "CIFS"], "default": "NFS"},
            "storage_type": {"type": "str", "choices": ["SD", "HP", "SD_HP", "TP", "SD_HIGH_AVAIL"], "default": "SD"},
            "capacity": {"type": "int", "default": 10},
            "vpc_id": {"type": "str"},
            "subnet_id": {"type": "str"},
            "pgroup_id": {"type": "str"},
            "size_limit": {"type": "int"},
        },
        supports_check_mode=True,
    )
    module.require_sdk()

    state = module.params["state"]
    file_system_id = module.params["file_system_id"]
    name = module.params["name"]

    if state == "absent" and not file_system_id and not name:
        module.fail_json(msg="file_system_id or name is required when state=absent")

    models, cfs_client = _load_cfs()
    client = module.create_client(cfs_client.CfsClient, "cfs.tencentcloudapi.com")

    try:
        current = find_file_system(module, client, models, file_system_id, name)
    except Exception as exc:
        module.fail_json(
            msg="Tencent Cloud API request failed",
            error=str(exc),
            error_code=getattr(exc, "get_code", lambda: None)(),
            request_id=getattr(exc, "get_request_id", lambda: None)(),
        )

    if state == "absent":
        if current is None:
            module.exit_json(changed=False, msg="File system already absent")
        target_id = current["FileSystemId"]
        diff = maybe_diff(module, current, None)
        if module.check_mode:
            module.exit_json(changed=True, **(diff or {}), msg="Would delete file system")
        _delete(module, client, models, target_id)
        module.exit_json(changed=True, **(diff or {}), file_system=None, msg="File system deleted")

    # state == present
    if current is None:
        if not module.params["zone"]:
            module.fail_json(msg="zone is required when creating a file system")
        if not name:
            module.fail_json(msg="name is required when creating a file system")
        desired = {
            "Name": name,
            "Zone": module.params["zone"],
            "Protocol": module.params["protocol"],
            "StorageType": module.params["storage_type"],
            "Capacity": module.params["capacity"],
        }
        diff = maybe_diff(module, None, desired)
        if module.check_mode:
            module.exit_json(changed=True, **(diff or {}), msg="Would create file system")
        _create(module, client, models, module.params)
        created = find_file_system(module, client, models, None, name)
        module.exit_json(changed=True, **(diff or {}), file_system=created, msg="File system created")

    target_id = current["FileSystemId"]
    changes = []
    if name and current.get("Name") != name:
        changes.append("name")
    size_limit = module.params["size_limit"]
    current_size = current.get("SizeLimit") or current.get("Capacity") or 0
    if size_limit is not None and int(current_size) != size_limit:
        changes.append("size_limit")

    if not changes:
        module.exit_json(changed=False, file_system=current, msg="File system is up to date")

    diff = maybe_diff(module, current, {
        "Name": name or current.get("Name"),
        "SizeLimit": size_limit if size_limit is not None else current_size,
    })
    if module.check_mode:
        module.exit_json(changed=True, **(diff or {}), msg="Would update file system")

    if "name" in changes:
        _update_name(module, client, models, target_id, name)
    if "size_limit" in changes:
        _update_size_limit(module, client, models, target_id, size_limit)
    updated = find_file_system(module, client, models, target_id, None)
    module.exit_json(changed=True, **(diff or {}), file_system=updated, msg="File system updated")


def main():
    run_module()


if __name__ == "__main__":
    main()
