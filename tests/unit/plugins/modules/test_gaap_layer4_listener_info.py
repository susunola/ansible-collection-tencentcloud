from __future__ import absolute_import, division, print_function
import sys
import types
basic = types.ModuleType("ansible.module_utils.basic")
basic.AnsibleModule = object
basic.env_fallback = lambda names, default=None: default
sys.modules.setdefault("ansible", types.ModuleType("ansible"))
sys.modules.setdefault("ansible.module_utils", types.ModuleType("ansible.module_utils"))
sys.modules.setdefault("ansible.module_utils.basic", basic)
from ansible_collections.susunola.tencentcloud.plugins.modules.gaap_layer4_listener_info import describe_request, matches

class TCPRequest: pass
class UDPRequest: pass
class FakeModels:
    DescribeTCPListenersRequest = TCPRequest
    DescribeUDPListenersRequest = UDPRequest

def test_describe_request_selects_protocol_and_paginates():
    request = describe_request(FakeModels, {"protocol": "UDP", "proxy_id": "proxy-1", "group_id": None, "listener_id": None, "name": None, "port": None}, 100, 50)
    assert isinstance(request, UDPRequest)
    assert (request.ProxyId, request.Offset, request.Limit) == ("proxy-1", 100, 50)

def test_matches_exact_listener_identity():
    value = {"ListenerId": "listener-1", "ListenerName": "dns", "Port": 53}
    assert matches(value, {"listener_id": None, "name": "dns", "port": 53})
    assert not matches(value, {"listener_id": "listener-2", "name": None, "port": None})
