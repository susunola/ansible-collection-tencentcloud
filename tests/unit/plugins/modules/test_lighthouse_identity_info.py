from __future__ import absolute_import, division, print_function
import sys
import types
basic = types.ModuleType("ansible.module_utils.basic")
basic.AnsibleModule = object
basic.env_fallback = lambda names, default=None: default
sys.modules.setdefault("ansible", types.ModuleType("ansible"))
sys.modules.setdefault("ansible.module_utils", types.ModuleType("ansible.module_utils"))
sys.modules.setdefault("ansible.module_utils.basic", basic)
from ansible_collections.susunola.tencentcloud.plugins.modules.lighthouse_key_pair import describe_request as key_request
from ansible_collections.susunola.tencentcloud.plugins.modules.lighthouse_snapshot import describe_request as snapshot_request

class FakeRequest:
    pass


class FakeFilter:
    pass
class FakeModels:
    DescribeKeyPairsRequest = FakeRequest
    DescribeSnapshotsRequest = FakeRequest
    Filter = FakeFilter

def test_key_request_filters_by_id_and_paginates():
    request = key_request(FakeModels, {"key_id": "key-1"}, 100)
    assert request.KeyIds == ["key-1"]
    assert (request.Offset, request.Limit) == (100, 100)

def test_snapshot_request_builds_instance_and_name_filters():
    request = snapshot_request(FakeModels, {"instance_id": "lhins-1", "name": "daily"}, 0)
    assert [(item.Name, item.Values) for item in request.Filters] == [("instance-id", ["lhins-1"]), ("snapshot-name", ["daily"])]
