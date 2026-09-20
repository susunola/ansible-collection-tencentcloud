from __future__ import absolute_import, division, print_function

import sys
import types

basic = types.ModuleType("ansible.module_utils.basic")
basic.AnsibleModule = object
basic.env_fallback = lambda names, default=None: default
sys.modules.setdefault("ansible", types.ModuleType("ansible"))
sys.modules.setdefault("ansible.module_utils", types.ModuleType("ansible.module_utils"))
sys.modules.setdefault("ansible.module_utils.basic", basic)

from ansible_collections.susunola.tencentcloud.plugins.modules import config_aggregator_info


class FakeRequest:
    pass


class FakeModels:
    ListAggregatorsRequest = FakeRequest
    DescribeAggregatorRequest = FakeRequest


def test_list_request_sets_pagination():
    request = config_aggregator_info.list_request(FakeModels, 100, 50)
    assert (request.Offset, request.Limit) == (100, 50)


def test_detail_request_sets_account_group_id():
    assert config_aggregator_info.detail_request(FakeModels, "group-1").AccountGroupId == "group-1"
