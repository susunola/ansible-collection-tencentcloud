from __future__ import absolute_import, division, print_function
import sys
import types
basic = types.ModuleType("ansible.module_utils.basic")
basic.AnsibleModule = object
basic.env_fallback = lambda names, default=None: default
sys.modules.setdefault("ansible", types.ModuleType("ansible"))
sys.modules.setdefault("ansible.module_utils", types.ModuleType("ansible.module_utils"))
sys.modules.setdefault("ansible.module_utils.basic", basic)
from ansible_collections.susunola.tencentcloud.plugins.modules.goosefs_fileset import describe_request
from ansible_collections.susunola.tencentcloud.plugins.modules.goosefs_fileset_info import matches

class FakeRequest: pass
class FakeModels:
    DescribeFilesetsRequest = FakeRequest

def test_request_sets_filesystem_and_server_filter():
    request = describe_request(FakeModels, {"file_system_id": "fs-1", "directory": "/analytics"})
    assert request.FileSystemId == "fs-1"
    assert request.FilesetDirs == ["/analytics"]

def test_matches_exact_observable_identity():
    value = {"FsetId": "fset-1", "FsetName": "analytics", "FsetDir": "/analytics"}
    assert matches(value, {"fileset_id": None, "name": "analytics", "directory": None})
    assert not matches(value, {"fileset_id": None, "name": "archive", "directory": None})
