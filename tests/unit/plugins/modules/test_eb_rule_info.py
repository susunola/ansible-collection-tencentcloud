from __future__ import absolute_import, division, print_function
import sys
import types
basic = types.ModuleType("ansible.module_utils.basic")
basic.AnsibleModule = object
basic.env_fallback = lambda names, default=None: default
sys.modules.setdefault("ansible", types.ModuleType("ansible"))
sys.modules.setdefault("ansible.module_utils", types.ModuleType("ansible.module_utils"))
sys.modules.setdefault("ansible.module_utils.basic", basic)
from ansible_collections.susunola.tencentcloud.plugins.modules.eb_rule import get_request
from ansible_collections.susunola.tencentcloud.plugins.modules.eb_rule_info import list_request

class FakeRequest: pass
class FakeModels:
    ListRulesRequest = FakeRequest
    GetRuleRequest = FakeRequest

def test_list_request_sets_bus_and_pagination():
    request = list_request(FakeModels, "eb-1", 100, 50)
    assert (request.EventBusId, request.Offset, request.Limit) == ("eb-1", 100, 50)

def test_get_request_sets_exact_rule_identity():
    request = get_request(FakeModels, {"event_bus_id": "eb-1"}, "rule-1")
    assert (request.EventBusId, request.RuleId) == ("eb-1", "rule-1")
