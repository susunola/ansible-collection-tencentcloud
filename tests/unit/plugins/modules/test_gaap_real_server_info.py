from __future__ import absolute_import, division, print_function
import sys
import types
basic = types.ModuleType("ansible.module_utils.basic")
basic.AnsibleModule = object
basic.env_fallback = lambda names, default=None: default
sys.modules.setdefault("ansible", types.ModuleType("ansible"))
sys.modules.setdefault("ansible.module_utils", types.ModuleType("ansible.module_utils"))
sys.modules.setdefault("ansible.module_utils.basic", basic)
from ansible_collections.susunola.tencentcloud.plugins.modules.gaap_real_server_info import describe_request, matches

class FakeRequest: pass
class FakeModels:
    DescribeRealServersRequest = FakeRequest

def test_describe_request_sets_search_and_pagination():
    request = describe_request(FakeModels, 7, "203.0.113.10", 50, 25)
    assert (request.ProjectId, request.SearchValue, request.Offset, request.Limit) == (7, "203.0.113.10", 50, 25)

def test_matches_exact_identity():
    value = {"RealServerId": "rs-1", "RealServerIP": "203.0.113.10"}
    assert matches(value, address="203.0.113.10") and not matches(value, real_server_id="rs-2")
