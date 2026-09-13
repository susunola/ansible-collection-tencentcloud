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

from ansible_collections.susunola.tencentcloud.plugins.modules import cfw_nat_dnat_rule_info


class FakeRequest:
    pass


class FakeModels:
    DescribeNatFwDnatRuleRequest = FakeRequest


def test_build_request_sets_pagination():
    request = cfw_nat_dnat_rule_info.build_request(FakeModels, 100, 50)
    assert request.Offset == 100
    assert request.Limit == 50


def test_matches_uses_public_endpoint_identity():
    item = {
        "FwInsId": "cfwnat-x",
        "IpProtocol": "TCP",
        "PublicIpAddress": "203.0.113.10",
        "PublicPort": 443,
    }
    assert cfw_nat_dnat_rule_info._matches(item, "cfwnat-x", "TCP", "203.0.113.10", 443) is True
    assert cfw_nat_dnat_rule_info._matches(item, "cfwnat-x", "UDP", "203.0.113.10", 443) is False
