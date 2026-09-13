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

from ansible_collections.susunola.tencentcloud.plugins.modules import cdwpg_hba_config_info
from ansible_collections.susunola.tencentcloud.plugins.modules import cdwpg_parameter_info


class FakeRequest:
    pass


class FakeModels:
    DescribeUserHbaConfigRequest = FakeRequest
    DescribeDBParamsRequest = FakeRequest


class FakeResource:
    def __init__(self, value):
        self.value = dict(value)

    def _serialize(self, allow_none=True):
        return dict(self.value)


def test_hba_request_and_normalization():
    request = cdwpg_hba_config_info.build_request(FakeModels, "cdwpg-x")
    assert request.InstanceId == "cdwpg-x"
    assert cdwpg_hba_config_info.normalize([
        FakeResource({"type": "hostssl", "database": "all", "user": "analyst", "address": "10.0.0.0/16", "method": "md5"})
    ]) == [{"Type": "hostssl", "Database": "all", "User": "analyst", "Address": "10.0.0.0/16", "Method": "md5"}]


def test_parameter_request_sets_node_type_and_pagination():
    request = cdwpg_parameter_info.build_request(FakeModels, "cdwpg-x", "cn", 100, 50)
    assert request.InstanceId == "cdwpg-x"
    assert request.NodeTypes == ["cn"]
    assert request.Offset == 100
    assert request.Limit == 50


def test_extract_parameters_counts_seen_items_separately_from_matches():
    group = types.SimpleNamespace(
        NodeType="cn",
        Details=[
            FakeResource({"ParamName": "max_connections", "LatestValue": "", "RunningValue": "200"}),
            FakeResource({"ParamName": "work_mem", "LatestValue": "16MB", "RunningValue": "4MB"}),
        ],
    )
    response = types.SimpleNamespace(Items=[group])
    params, seen = cdwpg_parameter_info._extract_parameters(response, "cn", "work_mem")
    assert seen == 2
    assert params == [{"ParamName": "work_mem", "LatestValue": "16MB", "RunningValue": "4MB", "EffectiveValue": "16MB"}]
