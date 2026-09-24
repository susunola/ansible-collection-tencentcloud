from __future__ import absolute_import, division, print_function
import sys
import types
basic = types.ModuleType("ansible.module_utils.basic")
basic.AnsibleModule = object
basic.env_fallback = lambda names, default=None: default
sys.modules.setdefault("ansible", types.ModuleType("ansible"))
sys.modules.setdefault("ansible.module_utils", types.ModuleType("ansible.module_utils"))
sys.modules.setdefault("ansible.module_utils.basic", basic)
from ansible_collections.susunola.tencentcloud.plugins.module_utils.cos import normalize_bucket_inventory as normalize_inventory
from ansible_collections.susunola.tencentcloud.plugins.module_utils.cos import normalize_bucket_replication as normalize_replication
from ansible_collections.susunola.tencentcloud.plugins.module_utils.cos import normalize_bucket_response_control as normalize_control

def test_replication_normalize_sorts_rules():
    value = {"Role": "role", "Rule": [{"ID": "b"}, {"ID": "a"}]}
    assert [x["ID"] for x in normalize_replication(value)["Rule"]] == ["a", "b"]

def test_response_control_normalize_sorts_parameters():
    value = {"ControlParamList": {"Param": ["response-expires", "response-content-type"]}}
    assert normalize_control(value)["ControlParamList"]["Param"] == ["response-content-type", "response-expires"]

def test_inventory_normalize_sets_id_and_sorts_optional_fields():
    value = {"OptionalFields": {"Field": ["Size", "ETag"]}}
    normalized = normalize_inventory(value, "daily")
    assert normalized["Id"] == "daily"
    assert normalized["OptionalFields"]["Field"] == ["ETag", "Size"]
