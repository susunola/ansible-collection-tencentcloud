from __future__ import absolute_import, division, print_function

import sys
import types

basic = types.ModuleType("ansible.module_utils.basic")
basic.AnsibleModule = object
basic.env_fallback = lambda names, default=None: default
sys.modules.setdefault("ansible", types.ModuleType("ansible"))
sys.modules.setdefault("ansible.module_utils", types.ModuleType("ansible.module_utils"))
sys.modules.setdefault("ansible.module_utils.basic", basic)

from ansible_collections.susunola.tencentcloud.plugins.modules import config_aggregate_delivery_info


class FakeRequest:
    pass


class FakeModels:
    DescribeAggregateConfigDeliverRequest = FakeRequest


def test_build_request_sets_account_group_id():
    assert config_aggregate_delivery_info.build_request(FakeModels, "ag-1").AccountGroupId == "ag-1"
