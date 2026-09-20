from __future__ import absolute_import, division, print_function

import sys
import types

basic = types.ModuleType("ansible.module_utils.basic")
basic.AnsibleModule = object
basic.env_fallback = lambda names, default=None: default
sys.modules.setdefault("ansible", types.ModuleType("ansible"))
sys.modules.setdefault("ansible.module_utils", types.ModuleType("ansible.module_utils"))
sys.modules.setdefault("ansible.module_utils.basic", basic)

from ansible_collections.susunola.tencentcloud.plugins.modules import cos_bucket_policy_info, cos_bucket_website_info


def test_website_normalize_unwraps_configuration():
    value = {"WebsiteConfiguration": {"IndexDocument": {"Suffix": "index.html"}}}
    assert cos_bucket_website_info.normalize(value) == value["WebsiteConfiguration"]


def test_policy_normalize_unwraps_and_decodes_policy():
    value = {"Policy": '{"version":"2.0","statement":[]}'}
    assert cos_bucket_policy_info.normalize(value) == {"version": "2.0", "statement": []}
