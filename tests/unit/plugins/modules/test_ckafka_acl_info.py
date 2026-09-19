from __future__ import absolute_import, division, print_function

__metaclass__ = type

import sys
import types

basic = types.ModuleType("ansible.module_utils.basic")
basic.AnsibleModule = object
basic.env_fallback = lambda names, default=None: default
sys.modules.setdefault("ansible", types.ModuleType("ansible"))
sys.modules.setdefault("ansible.module_utils", types.ModuleType("ansible.module_utils"))
sys.modules.setdefault("ansible.module_utils.basic", basic)

from ansible_collections.susunola.tencentcloud.plugins.modules import ckafka_acl_info, ckafka_acl_rule_info


class FakeRequest:
    pass


class FakeModels:
    DescribeACLRequest = FakeRequest
    DescribeAclRuleRequest = FakeRequest


def test_acl_request_maps_resource_type_and_pagination():
    request = ckafka_acl_info.build_request(FakeModels, "ckafka-1", "TOPIC", "orders", 100, 100)
    assert (request.InstanceId, request.ResourceType, request.ResourceName) == ("ckafka-1", 2, "orders")
    assert (request.Offset, request.Limit) == (100, 100)


def test_acl_filter_maps_human_readable_values():
    value = {"Operation": 4, "PermissionType": 3, "Host": "*", "Principal": "User:producer"}
    assert ckafka_acl_info.matches(value, "WRITE", "ALLOW", "*", "User:producer")
    assert not ckafka_acl_info.matches(value, operation="READ")


def test_acl_rule_request_sets_exact_identity():
    request = ckafka_acl_rule_info.build_request(FakeModels, "ckafka-1", "orders", "PREFIXED")
    assert (request.InstanceId, request.RuleName, request.PatternType) == ("ckafka-1", "orders", "PREFIXED")
