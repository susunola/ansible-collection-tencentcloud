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

from ansible_collections.susunola.tencentcloud.plugins.modules import ckafka_datahub_topic_info


class FakeRequest:
    pass


class FakeModels:
    DescribeDatahubTopicRequest = FakeRequest


def test_build_request_sets_name():
    request = ckafka_datahub_topic_info.build_request(FakeModels, "orders-stream")
    assert request.Name == "orders-stream"


def test_sanitize_removes_returned_credentials():
    assert ckafka_datahub_topic_info.sanitize({
        "Name": "orders-stream",
        "UserName": "leaked-user",
        "Password": "leaked-password",
        "RetentionMs": 86400000,
    }) == {"Name": "orders-stream", "RetentionMs": 86400000}
