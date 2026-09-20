from __future__ import absolute_import, division, print_function

import sys
import types

basic = types.ModuleType("ansible.module_utils.basic")
basic.AnsibleModule = object
basic.env_fallback = lambda names, default=None: default
sys.modules.setdefault("ansible", types.ModuleType("ansible"))
sys.modules.setdefault("ansible.module_utils", types.ModuleType("ansible.module_utils"))
sys.modules.setdefault("ansible.module_utils.basic", basic)

from ansible_collections.susunola.tencentcloud.plugins.modules import config_rule_info


class FakeRequest:
    pass


class FakeModels:
    ListConfigRulesRequest = FakeRequest
    DescribeConfigRuleRequest = FakeRequest


def test_list_request_sets_name_and_pagination():
    request = config_rule_info.list_request(FakeModels, "encrypted-disks", 200, 100)
    assert (request.RuleName, request.Offset, request.Limit) == ("encrypted-disks", 200, 100)


def test_detail_request_sets_rule_id():
    assert config_rule_info.detail_request(FakeModels, "rule-1").RuleId == "rule-1"
