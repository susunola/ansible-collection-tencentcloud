from __future__ import absolute_import, division, print_function

__metaclass__ = type

import sys
import types

import pytest

basic = types.ModuleType("ansible.module_utils.basic")
basic.AnsibleModule = object
basic.env_fallback = lambda names, default=None: default
sys.modules.setdefault("ansible", types.ModuleType("ansible"))
sys.modules.setdefault("ansible.module_utils", types.ModuleType("ansible.module_utils"))
sys.modules.setdefault("ansible.module_utils.basic", basic)

from ansible_collections.susunola.tencentcloud.plugins.modules import cdwch_backup_config_info
from ansible_collections.susunola.tencentcloud.plugins.modules import cdwch_parameter_info


class FakeRequest:
    pass


class FakeModels:
    DescribeBackUpScheduleRequest = FakeRequest
    DescribeInstanceKeyValConfigsRequest = FakeRequest


class FakeResource:
    def __init__(self, value):
        self.value = dict(value)

    def _serialize(self, allow_none=True):
        return dict(self.value)


def test_backup_config_build_request_sets_instance_id():
    request = cdwch_backup_config_info.build_request(FakeModels, "cdwch-x")
    assert request.InstanceId == "cdwch-x"


def test_backup_config_serializes_schedule_and_tables():
    response = types.SimpleNamespace(
        ErrorMsg="",
        BackUpOpened=True,
        MetaStrategy=FakeResource({"RetainDays": 30, "WeekDays": "1,3,5"}),
        DataStrategy=FakeResource({"RetainDays": 14, "WeekDays": "0,6"}),
        BackUpContents=[
            FakeResource({"Database": "analytics", "Table": "events"}),
            FakeResource({"database": "analytics", "table": "users"}),
        ],
    )
    module = types.SimpleNamespace(fail_json=lambda **kwargs: (_ for _ in ()).throw(AssertionError(kwargs)))
    assert cdwch_backup_config_info.serialize_config(module, response) == {
        "enabled": True,
        "meta_strategy": {"RetainDays": 30, "WeekDays": "1,3,5"},
        "data_strategy": {"RetainDays": 14, "WeekDays": "0,6"},
        "backup_tables": [
            {"Database": "analytics", "Table": "events"},
            {"Database": "analytics", "Table": "users"},
        ],
    }


def test_parameter_info_build_request_sets_search_name():
    request = cdwch_parameter_info.build_request(FakeModels, "cdwch-x", "max_threads")
    assert request.InstanceId == "cdwch-x"
    assert request.SearchConfigName == "max_threads"


def test_parameter_info_filters_by_name():
    assert cdwch_parameter_info._filter_by_name(
        [{"ConfKey": "a", "ConfValue": "1"}, {"ConfKey": "b", "ConfValue": "2"}],
        "b",
    ) == [{"ConfKey": "b", "ConfValue": "2"}]
