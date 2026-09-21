from __future__ import absolute_import, division, print_function
import sys
import types
basic = types.ModuleType("ansible.module_utils.basic")
basic.AnsibleModule = object
basic.env_fallback = lambda names, default=None: default
sys.modules.setdefault("ansible", types.ModuleType("ansible"))
sys.modules.setdefault("ansible.module_utils", types.ModuleType("ansible.module_utils"))
sys.modules.setdefault("ansible.module_utils.basic", basic)
from ansible_collections.susunola.tencentcloud.plugins.modules.dnspod_domain_info import list_request, matches

class FakeRequest: pass
class FakeModels:
    DescribeDomainListRequest = FakeRequest

def test_list_request_sets_keyword_and_pagination():
    request = list_request(FakeModels, "example.com", 100, 50)
    assert (request.Type, request.Keyword, request.Offset, request.Limit) == ("ALL", "example.com", 100, 50)

def test_matches_exact_domain_identity():
    value = {"DomainId": 42, "Name": "example.com"}
    assert matches(value, name="example.com")
    assert not matches(value, domain_id=43)
