from __future__ import absolute_import, division, print_function

__metaclass__ = type

import sys
import types

basic = types.ModuleType("ansible.module_utils.basic")
basic.AnsibleModule = object
basic.env_fallback = lambda names, default=None: default
sys.modules.setdefault("ansible", types.ModuleType("ansible"))
sys.modules.setdefault("ansible.module_utils", types.ModuleType("ansible.module_utils"))
sys.modules.setdefault("ansible.module_utils.basic", basic)

from ansible_collections.susunola.tencentcloud.plugins.modules import chdfs_mount_access_groups_info
from ansible_collections.susunola.tencentcloud.plugins.modules import chdfs_mount_point_info


class FakeRequest:
    pass


class FakeModels:
    DescribeMountPointsRequest = FakeRequest


def test_mount_point_request_and_filter():
    request = chdfs_mount_point_info.build_request(FakeModels, "fs-x")
    assert request.FileSystemId == "fs-x"
    assert chdfs_mount_point_info._matches({"MountPointId": "mp-x", "MountPointName": "analytics"}, "mp-x", None) is True
    assert chdfs_mount_point_info._matches({"MountPointId": "mp-x", "MountPointName": "analytics"}, None, "other") is False


def test_mount_access_groups_request_sets_file_system_id():
    request = chdfs_mount_access_groups_info.build_request(FakeModels, "fs-x")
    assert request.FileSystemId == "fs-x"
