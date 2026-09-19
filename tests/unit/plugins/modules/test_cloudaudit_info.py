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

from ansible_collections.susunola.tencentcloud.plugins.modules import cloudaudit_audit_info, cloudaudit_track_info


class FakeRequest:
    pass


class FakeModels:
    DescribeAuditRequest = FakeRequest
    DescribeAuditTrackRequest = FakeRequest
    DescribeAuditTracksRequest = FakeRequest


def test_track_list_request_sets_page_shape():
    request = cloudaudit_track_info.list_request(FakeModels, 3, 50)
    assert (request.PageNumber, request.PageSize) == (3, 50)


def test_track_detail_request_sets_track_id():
    assert cloudaudit_track_info.detail_request(FakeModels, 42).TrackId == 42


def test_audit_request_sets_audit_name():
    assert cloudaudit_audit_info.build_request(FakeModels, "default").AuditName == "default"
