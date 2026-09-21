from __future__ import absolute_import, division, print_function
import sys
import types
basic = types.ModuleType("ansible.module_utils.basic")
basic.AnsibleModule = object
basic.env_fallback = lambda names, default=None: default
sys.modules.setdefault("ansible", types.ModuleType("ansible"))
sys.modules.setdefault("ansible.module_utils", types.ModuleType("ansible.module_utils"))
sys.modules.setdefault("ansible.module_utils.basic", basic)
from ansible_collections.susunola.tencentcloud.plugins.modules.dnspod_custom_line import describe_request as custom_request
from ansible_collections.susunola.tencentcloud.plugins.modules.dnspod_line_group import describe_request as group_request
from ansible_collections.susunola.tencentcloud.plugins.modules.dnspod_line_group_info import matches

class FakeRequest: pass
class FakeModels:
    DescribeDomainCustomLineListRequest = FakeRequest
    DescribeLineGroupListRequest = FakeRequest

def test_group_request_sets_scope_and_pagination():
    request = group_request(FakeModels, {"domain": "example.com", "domain_id": None}, 100)
    assert (request.Domain, request.Offset, request.Length) == ("example.com", 100, 100)

def test_custom_request_sets_domain_id_scope():
    assert custom_request(FakeModels, {"domain": None, "domain_id": 42}).DomainId == 42

def test_group_matches_exact_identity():
    value = {"Id": 7, "Name": "office"}
    assert matches(value, name="office") and not matches(value, group_id=8)
