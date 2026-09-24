from __future__ import absolute_import, division, print_function

import sys
import types

basic = types.ModuleType("ansible.module_utils.basic")
basic.AnsibleModule = object
basic.env_fallback = lambda names, default=None: default
sys.modules.setdefault("ansible", types.ModuleType("ansible"))
sys.modules.setdefault("ansible.module_utils", types.ModuleType("ansible.module_utils"))
sys.modules.setdefault("ansible.module_utils.basic", basic)

from ansible_collections.susunola.tencentcloud.plugins.module_utils.cos import normalize_bucket_object_lock as normalize_lock
from ansible_collections.susunola.tencentcloud.plugins.module_utils.cos import normalize_bucket_origin as normalize_origin


def test_object_lock_normalize_converts_retention_period():
    value = {"ObjectLockEnabled": "Enabled", "Rule": {"DefaultRetention": {"Mode": "COMPLIANCE", "Years": "7"}}}
    assert normalize_lock(value)["Rule"]["DefaultRetention"]["Years"] == 7


def test_origin_normalize_sorts_rules_by_priority():
    value = {"OriginRule": [{"RulePriority": "2"}, {"RulePriority": "1"}]}
    assert [item["RulePriority"] for item in normalize_origin(value)["OriginRule"]] == ["1", "2"]
