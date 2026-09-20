from __future__ import absolute_import, division, print_function
import sys
import types
basic = types.ModuleType("ansible.module_utils.basic")
basic.AnsibleModule = object
basic.env_fallback = lambda names, default=None: default
sys.modules.setdefault("ansible", types.ModuleType("ansible"))
sys.modules.setdefault("ansible.module_utils", types.ModuleType("ansible.module_utils"))
sys.modules.setdefault("ansible.module_utils.basic", basic)
from ansible_collections.susunola.tencentcloud.plugins.modules.lighthouse_disk import describe_request

class FakeRequest: pass
class FakeFilter: pass
class FakeModels:
    DescribeDisksRequest = FakeRequest
    Filter = FakeFilter

def test_disk_request_filters_by_id_and_paginates():
    request = describe_request(FakeModels, {"disk_id": "disk-1"}, 100)
    assert request.DiskIds == ["disk-1"]
    assert (request.Offset, request.Limit) == (100, 100)

def test_disk_request_filters_by_name():
    request = describe_request(FakeModels, {"name": "app-data"}, 0)
    assert [(item.Name, item.Values) for item in request.Filters] == [("disk-name", ["app-data"])]
