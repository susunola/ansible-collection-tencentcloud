from __future__ import absolute_import, division, print_function
import sys
import types
basic = types.ModuleType("ansible.module_utils.basic")
basic.AnsibleModule = object
basic.env_fallback = lambda names, default=None: default
sys.modules.setdefault("ansible", types.ModuleType("ansible"))
sys.modules.setdefault("ansible.module_utils", types.ModuleType("ansible.module_utils"))
sys.modules.setdefault("ansible.module_utils.basic", basic)
from ansible_collections.susunola.tencentcloud.plugins.modules.elasticsearch_instance_info import describe_request, matches

class FakeRequest: pass
class FakeModels:
    DescribeInstancesRequest = FakeRequest

def test_describe_request_sets_name_and_pagination():
    request = describe_request(FakeModels, name="production", offset=100, limit=50)
    assert request.InstanceNames == ["production"]
    assert (request.Offset, request.Limit) == (100, 50)

def test_matches_exact_instance_identity():
    value = {"InstanceId": "es-1", "InstanceName": "production"}
    assert matches(value, name="production") and not matches(value, instance_id="es-2")
