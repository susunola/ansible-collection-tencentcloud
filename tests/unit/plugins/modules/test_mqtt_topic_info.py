from __future__ import absolute_import, division, print_function
import sys
import types
basic = types.ModuleType("ansible.module_utils.basic")
basic.AnsibleModule = object
basic.env_fallback = lambda names, default=None: default
sys.modules.setdefault("ansible", types.ModuleType("ansible"))
sys.modules.setdefault("ansible.module_utils", types.ModuleType("ansible.module_utils"))
sys.modules.setdefault("ansible.module_utils.basic", basic)
from ansible_collections.susunola.tencentcloud.plugins.modules.mqtt_topic import describe_request

class FakeRequest: pass
class FakeModels:
    DescribeTopicRequest = FakeRequest

def test_describe_request_sets_exact_topic_identity():
    request = describe_request(FakeModels, {"instance_id": "mqtt-1", "topic": "orders"})
    assert (request.InstanceId, request.Topic) == ("mqtt-1", "orders")
