from __future__ import absolute_import, division, print_function
import sys
import types
basic = types.ModuleType("ansible.module_utils.basic")
basic.AnsibleModule = object
basic.env_fallback = lambda names, default=None: default
sys.modules.setdefault("ansible", types.ModuleType("ansible"))
sys.modules.setdefault("ansible.module_utils", types.ModuleType("ansible.module_utils"))
sys.modules.setdefault("ansible.module_utils.basic", basic)
from ansible_collections.susunola.tencentcloud.plugins.modules.gwlb_target_group_info import describe_request, matches

class FakeRequest: pass
class FakeModels:
    DescribeTargetGroupsRequest = FakeRequest

def test_describe_request_sets_id_and_pagination():
    request = describe_request(FakeModels, "tg-1", 100, 50)
    assert request.TargetGroupIds == ["tg-1"]
    assert (request.Offset, request.Limit) == (100, 50)

def test_matches_exact_identity():
    value = {"TargetGroupId": "tg-1", "TargetGroupName": "inspection"}
    assert matches(value, name="inspection") and not matches(value, target_group_id="tg-2")
