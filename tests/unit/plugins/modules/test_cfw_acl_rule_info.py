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

from ansible_collections.susunola.tencentcloud.plugins.modules import cfw_nat_acl_rule_info
from ansible_collections.susunola.tencentcloud.plugins.modules import cfw_vpc_acl_rule_info


class FakeRequest:
    pass


class FakeModels:
    DescribeNatAcRuleRequest = FakeRequest
    DescribeVpcAcRuleRequest = FakeRequest


def test_nat_acl_request_and_filter():
    request = cfw_nat_acl_rule_info.build_request(FakeModels, 100, 50)
    assert request.Offset == 100
    assert request.Limit == 50
    assert cfw_nat_acl_rule_info._matches({"Uuid": 8, "Description": "allow"}, 8, None) is True
    assert cfw_nat_acl_rule_info._matches({"Uuid": 8, "Description": "allow"}, None, "deny") is False


def test_vpc_acl_request_and_filter():
    request = cfw_vpc_acl_rule_info.build_request(FakeModels, 200, 100)
    assert request.Offset == 200
    assert request.Limit == 100
    item = {"Uuid": 9, "EdgeId": "edge-x", "Description": "allow-vpc"}
    assert cfw_vpc_acl_rule_info._matches(item, None, "edge-x", "allow-vpc") is True
    assert cfw_vpc_acl_rule_info._matches(item, None, "edge-y", "allow-vpc") is False
