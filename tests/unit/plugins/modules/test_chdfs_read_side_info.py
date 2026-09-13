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

from ansible_collections.susunola.tencentcloud.plugins.modules import chdfs_access_group_info
from ansible_collections.susunola.tencentcloud.plugins.modules import chdfs_access_rules_info


class FakeRequest:
    pass


class FakeModels:
    DescribeAccessGroupsRequest = FakeRequest
    DescribeAccessRulesRequest = FakeRequest


def test_access_group_request_and_filter():
    request = chdfs_access_group_info.build_request(FakeModels, "marker-x")
    assert request.AccessGroupIdMarker == "marker-x"
    assert chdfs_access_group_info._matches({"AccessGroupId": "ag-x", "AccessGroupName": "analytics"}, "ag-x", None) is True
    assert chdfs_access_group_info._matches({"AccessGroupId": "ag-x", "AccessGroupName": "analytics"}, None, "other") is False


def test_access_rules_request_sets_group_id():
    request = chdfs_access_rules_info.build_request(FakeModels, "ag-x")
    assert request.AccessGroupId == "ag-x"
