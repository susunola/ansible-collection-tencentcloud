from __future__ import absolute_import, division, print_function
import sys
import types
basic = types.ModuleType("ansible.module_utils.basic")
basic.AnsibleModule = object
basic.env_fallback = lambda names, default=None: default
sys.modules.setdefault("ansible", types.ModuleType("ansible"))
sys.modules.setdefault("ansible.module_utils", types.ModuleType("ansible.module_utils"))
sys.modules.setdefault("ansible.module_utils.basic", basic)
from ansible_collections.susunola.tencentcloud.plugins.modules.gwlb_target_group_instances_info import describe_request, normalize

class FakeRequest: pass
class FakeFilter: pass
class FakeModels:
    DescribeTargetGroupInstancesRequest = FakeRequest
    Filter = FakeFilter

def test_describe_request_sets_filter_and_pagination():
    request = describe_request(FakeModels, "tg-1", 100, 50)
    assert (request.Offset, request.Limit) == (100, 50)
    assert [(item.Name, item.Values) for item in request.Filters] == [("TargetGroupId", ["tg-1"])]

def test_normalize_sorts_instances():
    first = types.SimpleNamespace(BindIP="10.0.0.2", Port=6081, Weight=10)
    second = types.SimpleNamespace(BindIP="10.0.0.1", Port=6081, Weight=20)
    assert [item["ip"] for item in normalize([first, second])] == ["10.0.0.1", "10.0.0.2"]
