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

from ansible_collections.susunola.tencentcloud.plugins.modules import ckafka_datahub_connection_info, ckafka_datahub_task_info


class FakeRequest:
    pass


class FakeModels:
    DescribeConnectResourceRequest = FakeRequest
    DescribeConnectResourcesRequest = FakeRequest
    DescribeDatahubTaskRequest = FakeRequest
    DescribeDatahubTasksRequest = FakeRequest


def test_connection_requests_set_identity_and_filters():
    assert ckafka_datahub_connection_info.detail_request(FakeModels, "resource-1").ResourceId == "resource-1"
    request = ckafka_datahub_connection_info.list_request(FakeModels, "KAFKA", "analytics", 100)
    assert (request.Type, request.SearchWord, request.Offset, request.Limit) == ("KAFKA", "analytics", 100, 100)


def test_task_requests_set_identity_and_filters():
    assert ckafka_datahub_task_info.detail_request(FakeModels, "task-1").TaskId == "task-1"
    request = ckafka_datahub_task_info.list_request(FakeModels, "SOURCE", "orders", 100)
    assert (request.TaskType, request.SearchWord, request.Offset, request.Limit) == ("SOURCE", "orders", 100, 100)


def test_scrub_removes_nested_credentials():
    value = {"Name": "resource", "Config": {"Password": "bad", "Nested": [{"AccessKeyId": "bad", "Region": "ap-guangzhou"}]}}
    expected = {"Name": "resource", "Config": {"Nested": [{"Region": "ap-guangzhou"}]}}
    assert ckafka_datahub_connection_info.scrub(value) == expected
    assert ckafka_datahub_task_info.scrub(value) == expected
