from __future__ import absolute_import, division, print_function

import sys
import types

basic = types.ModuleType("ansible.module_utils.basic")
basic.AnsibleModule = object
basic.env_fallback = lambda names, default=None: default
sys.modules.setdefault("ansible", types.ModuleType("ansible"))
sys.modules.setdefault("ansible.module_utils", types.ModuleType("ansible.module_utils"))
sys.modules.setdefault("ansible.module_utils.basic", basic)

from ansible_collections.susunola.tencentcloud.plugins.modules import config_alarm_policy_info, config_compliance_pack_info


class FakeRequest:
    pass


class FakeModels:
    ListAlarmPolicyRequest = FakeRequest
    ListCompliancePacksRequest = FakeRequest
    DescribeCompliancePackRequest = FakeRequest


def test_compliance_pack_requests_set_filters_and_identity():
    request = config_compliance_pack_info.list_request(FakeModels, "baseline", 100, 50)
    assert (request.CompliancePackName, request.Offset, request.Limit) == ("baseline", 100, 50)
    assert config_compliance_pack_info.detail_request(FakeModels, "pack-1").CompliancePackId == "pack-1"


def test_alarm_policy_request_sets_pagination():
    request = config_alarm_policy_info.list_request(FakeModels, 100, 50)
    assert (request.Offset, request.Limit) == (100, 50)
