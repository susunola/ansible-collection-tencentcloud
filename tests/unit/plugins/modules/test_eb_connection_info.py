from __future__ import absolute_import, division, print_function
import sys
import types
basic = types.ModuleType("ansible.module_utils.basic")
basic.AnsibleModule = object
basic.env_fallback = lambda names, default=None: default
sys.modules.setdefault("ansible", types.ModuleType("ansible"))
sys.modules.setdefault("ansible.module_utils", types.ModuleType("ansible.module_utils"))
sys.modules.setdefault("ansible.module_utils.basic", basic)
from ansible_collections.susunola.tencentcloud.plugins.modules.eb_connection_info import list_request, matches

class FakeRequest: pass
class FakeModels:
    ListConnectionsRequest = FakeRequest

def test_list_request_sets_bus_and_pagination():
    request = list_request(FakeModels, "eb-1", 100, 50)
    assert (request.EventBusId, request.Offset, request.Limit) == ("eb-1", 100, 50)

def test_matches_exact_identity():
    value = {"ConnectionId": "conn-1", "ConnectionName": "orders"}
    assert matches(value, name="orders")
    assert not matches(value, connection_id="conn-2")
