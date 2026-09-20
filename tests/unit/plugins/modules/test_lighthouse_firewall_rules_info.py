from __future__ import absolute_import, division, print_function
import sys
import types
basic = types.ModuleType("ansible.module_utils.basic")
basic.AnsibleModule = object
basic.env_fallback = lambda names, default=None: default
sys.modules.setdefault("ansible", types.ModuleType("ansible"))
sys.modules.setdefault("ansible.module_utils", types.ModuleType("ansible.module_utils"))
sys.modules.setdefault("ansible.module_utils.basic", basic)
from ansible_collections.susunola.tencentcloud.plugins.modules.lighthouse_firewall_rules import describe_request, normalize_rules

class FakeRequest: pass
class FakeModels:
    DescribeFirewallRulesRequest = FakeRequest

def test_describe_request_sets_instance_and_pagination():
    request = describe_request(FakeModels, "lhins-1", 100)
    assert (request.InstanceId, request.Offset, request.Limit) == ("lhins-1", 100, 100)

def test_normalize_rules_sorts_and_fills_optional_fields():
    values = [{"Protocol": "TCP", "Port": "443", "Action": "ACCEPT"}, {"Protocol": "TCP", "Port": "22", "Action": "ACCEPT"}]
    rules = normalize_rules(values)
    assert [item["Port"] for item in rules] == ["22", "443"]
    assert all("FirewallRuleDescription" in item for item in rules)
