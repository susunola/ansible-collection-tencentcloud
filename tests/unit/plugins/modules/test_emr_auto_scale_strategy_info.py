from __future__ import absolute_import, division, print_function
import sys
import types
basic = types.ModuleType("ansible.module_utils.basic")
basic.AnsibleModule = object
basic.env_fallback = lambda names, default=None: default
sys.modules.setdefault("ansible", types.ModuleType("ansible"))
sys.modules.setdefault("ansible.module_utils", types.ModuleType("ansible.module_utils"))
sys.modules.setdefault("ansible.module_utils.basic", basic)
from ansible_collections.susunola.tencentcloud.plugins.modules.emr_auto_scale_strategy_info import describe_request, select

class FakeRequest: pass
class FakeModels:
    DescribeAutoScaleStrategiesRequest = FakeRequest

class Item:
    def __init__(self, name): self.name = name
    def _serialize(self, allow_none=True): return {"StrategyName": self.name}

def test_describe_request_sets_cluster_and_group():
    request = describe_request(FakeModels, "emr-1", 2)
    assert (request.InstanceId, request.GroupId) == ("emr-1", 2)

def test_select_uses_requested_strategy_family():
    response = types.SimpleNamespace(LoadAutoScaleStrategies=[Item("load")], TimeBasedAutoScaleStrategies=[Item("time")])
    assert select(response, "load") == [{"StrategyName": "load"}]
    assert select(response, "time") == [{"StrategyName": "time"}]
