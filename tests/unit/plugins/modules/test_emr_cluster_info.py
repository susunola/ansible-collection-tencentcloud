from __future__ import absolute_import, division, print_function
import sys
import types
basic = types.ModuleType("ansible.module_utils.basic")
basic.AnsibleModule = object
basic.env_fallback = lambda names, default=None: default
sys.modules.setdefault("ansible", types.ModuleType("ansible"))
sys.modules.setdefault("ansible.module_utils", types.ModuleType("ansible.module_utils"))
sys.modules.setdefault("ansible.module_utils.basic", basic)
from ansible_collections.susunola.tencentcloud.plugins.modules.emr_cluster import describe_request
from ansible_collections.susunola.tencentcloud.plugins.modules.emr_cluster_info import matches

class FakeRequest: pass
class FakeModels:
    DescribeInstancesRequest = FakeRequest

def test_describe_request_sets_cluster_id_and_pagination():
    request = describe_request(FakeModels, "emr-1", 100)
    assert request.InstanceIds == ["emr-1"]
    assert (request.Offset, request.Limit, request.DisplayStrategy) == (100, 100, "clusterList")

def test_matches_exact_cluster_identity():
    value = {"ClusterId": "emr-1", "ClusterName": "analytics"}
    assert matches(value, name="analytics") and not matches(value, cluster_id="emr-2")
