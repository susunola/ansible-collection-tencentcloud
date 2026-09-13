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

from ansible_collections.susunola.tencentcloud.plugins.modules import cdwdoris_cooldown_policy_info
from ansible_collections.susunola.tencentcloud.plugins.modules import cdwdoris_user_workload_group_info
from ansible_collections.susunola.tencentcloud.plugins.modules import cdwdoris_workload_group_info


class FakeRequest:
    pass


class FakeModels:
    DescribeCoolDownPoliciesRequest = FakeRequest
    DescribeWorkloadGroupRequest = FakeRequest
    DescribeUserBindWorkloadGroupRequest = FakeRequest


def test_cooldown_policy_request_and_filter():
    request = cdwdoris_cooldown_policy_info.build_request(FakeModels, "cdwdoris-x")
    assert request.InstanceId == "cdwdoris-x"
    assert cdwdoris_cooldown_policy_info._filter_by_name(
        [{"PolicyName": "hot"}, {"PolicyName": "archive"}], "archive"
    ) == [{"PolicyName": "archive"}]


def test_workload_group_request_and_filter():
    request = cdwdoris_workload_group_info.build_request(FakeModels, "cdwdoris-x")
    assert request.InstanceId == "cdwdoris-x"
    assert cdwdoris_workload_group_info._filter_by_name(
        [{"WorkloadGroupName": "interactive"}, {"WorkloadGroupName": "batch"}], "batch"
    ) == [{"WorkloadGroupName": "batch"}]


def test_user_workload_group_request_and_filter():
    request = cdwdoris_user_workload_group_info.build_request(FakeModels, "cdwdoris-x")
    assert request.InstanceId == "cdwdoris-x"
    assert cdwdoris_user_workload_group_info._filter_by_user(
        [{"UserName": "analyst"}, {"UserName": "loader"}], "loader"
    ) == [{"UserName": "loader"}]
