from __future__ import absolute_import, division, print_function

import sys
import types

basic = types.ModuleType("ansible.module_utils.basic")
basic.AnsibleModule = object
basic.env_fallback = lambda names, default=None: default
sys.modules.setdefault("ansible", types.ModuleType("ansible"))
sys.modules.setdefault("ansible.module_utils", types.ModuleType("ansible.module_utils"))
sys.modules.setdefault("ansible.module_utils.basic", basic)

from ansible_collections.susunola.tencentcloud.plugins.modules.cos_bucket_intelligent_tiering import normalize as normalize_tiering
from ansible_collections.susunola.tencentcloud.plugins.modules.cos_bucket_referer import normalize as normalize_referer


def test_referer_normalize_sorts_domains_and_handles_disabled():
    assert normalize_referer({"Status": "Disabled"}) is None
    value = {"Status": "Enabled", "RefererType": "White-List", "EmptyReferConfiguration": "Deny", "DomainList": {"Domain": ["b.example", "a.example"]}}
    assert normalize_referer(value)["DomainList"]["Domain"] == ["a.example", "b.example"]


def test_intelligent_tiering_normalize_converts_numeric_fields():
    value = {"Id": "default", "Status": "Enabled", "Tiering": {"AccessTier": "INFREQUENT", "Days": "30", "RequestFrequent": "1"}}
    assert normalize_tiering(value)["Tiering"] == {"AccessTier": "INFREQUENT", "Days": 30, "RequestFrequent": 1}
