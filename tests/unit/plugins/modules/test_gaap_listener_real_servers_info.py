from __future__ import absolute_import, division, print_function
import sys
import types
basic = types.ModuleType("ansible.module_utils.basic")
basic.AnsibleModule = object
basic.env_fallback = lambda names, default=None: default
sys.modules.setdefault("ansible", types.ModuleType("ansible"))
sys.modules.setdefault("ansible.module_utils", types.ModuleType("ansible.module_utils"))
sys.modules.setdefault("ansible.module_utils.basic", basic)
from ansible_collections.susunola.tencentcloud.plugins.modules.gaap_listener_real_servers import canonical

def test_canonical_normalizes_and_sorts_bindings():
    values = [
        {"real_server_id": "rs-2", "address": "10.0.0.2", "port": 3306},
        {"RealServerId": "rs-1", "RealServerIP": "10.0.0.1", "RealServerPort": 3306, "RealServerWeight": 10},
    ]
    result = canonical(values)
    assert [item["RealServerId"] for item in result] == ["rs-1", "rs-2"]
    assert result[1]["RealServerWeight"] == 1
