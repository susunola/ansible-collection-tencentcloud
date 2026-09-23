from __future__ import absolute_import, division, print_function
import sys
import types
basic = types.ModuleType("ansible.module_utils.basic")
basic.AnsibleModule = object
basic.env_fallback = lambda names, default=None: default
sys.modules.setdefault("ansible", types.ModuleType("ansible"))
sys.modules.setdefault("ansible.module_utils", types.ModuleType("ansible.module_utils"))
sys.modules.setdefault("ansible.module_utils.basic", basic)
from ansible_collections.susunola.tencentcloud.plugins.modules.elasticsearch_index import describe_request as index_request
from ansible_collections.susunola.tencentcloud.plugins.modules.elasticsearch_snapshot import describe_request as snapshot_request

class FakeRequest:
    pass
class FakeModels:
    DescribeIndexMetaRequest = FakeRequest
    DescribeClusterSnapshotRequest = FakeRequest

def test_index_request_sets_exact_identity_and_credentials():
    request = index_request(FakeModels, {"instance_id": "es-1", "index_type": "normal", "name": "orders", "username": "elastic", "password": "secret"})
    assert (request.InstanceId, request.IndexName, request.Username) == ("es-1", "orders", "elastic")

def test_snapshot_request_sets_exact_identity():
    request = snapshot_request(FakeModels, {"instance_id": "es-1", "repository_name": "repo", "name": "daily"})
    assert (request.InstanceId, request.RepositoryName, request.SnapshotName) == ("es-1", "repo", "daily")
