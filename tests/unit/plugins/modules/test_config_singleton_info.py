from __future__ import absolute_import, division, print_function

import sys
import types

basic = types.ModuleType("ansible.module_utils.basic")
basic.AnsibleModule = object
basic.env_fallback = lambda names, default=None: default
sys.modules.setdefault("ansible", types.ModuleType("ansible"))
sys.modules.setdefault("ansible.module_utils", types.ModuleType("ansible.module_utils"))
sys.modules.setdefault("ansible.module_utils.basic", basic)

from ansible_collections.susunola.tencentcloud.plugins.modules import config_delivery_info, config_recorder_info


class FakeRequest:
    pass


class FakeModels:
    DescribeConfigDeliverRequest = FakeRequest
    DescribeConfigRecorderRequest = FakeRequest


def test_singleton_requests_use_expected_models():
    assert isinstance(config_delivery_info.build_request(FakeModels), FakeRequest)
    assert isinstance(config_recorder_info.build_request(FakeModels), FakeRequest)


def test_recorder_normalize_sorts_and_deduplicates_resource_types():
    class Item:
        def __init__(self, value):
            self.ResourceType = value

    class Response:
        Items = [Item("QCS::VPC::VPC"), Item("QCS::CVM::Instance"), Item("QCS::VPC::VPC")]

        def _serialize(self, allow_none=True):
            return {"RequestId": "request-1", "Status": 1}

    assert config_recorder_info.normalize(Response())["ResourceTypes"] == ["QCS::CVM::Instance", "QCS::VPC::VPC"]
