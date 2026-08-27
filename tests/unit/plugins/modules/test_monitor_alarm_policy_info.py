from __future__ import absolute_import, division, print_function

__metaclass__ = type

import sys
import types

import pytest

from ansible_collections.tencentcloud.cloud.plugins.modules import monitor_alarm_policy_info


class FakeRequest:
    pass


class FakeModels:
    DescribeAlarmPoliciesRequest = FakeRequest


def test_build_request_maps_module_and_page_pagination():
    request = monitor_alarm_policy_info.build_request(FakeModels, "monitor", 200, 100)
    assert request.Module == "monitor"
    assert request.PageNumber == 3
    assert request.PageSize == 100


class FakeItem:
    def __init__(self, marker):
        self.marker = marker

    def _serialize(self, allow_none=True):
        return {"Marker": self.marker}


class FakeResponse:
    def __init__(self, items, total_count):
        self.Policies = items
        self.TotalCount = total_count


class FakeClient:
    def __init__(self, pages):
        self._pages = list(pages)
        self.requests = []

    def DescribeAlarmPolicies(self, request):
        self.requests.append(request)
        return self._pages.pop(0)


class ModuleExit(Exception):
    pass


class FakeModule:
    def __init__(self, params):
        self.params = params
        self.exit_payload = None

    def exit_json(self, **kwargs):
        self.exit_payload = kwargs
        raise ModuleExit()

    def fail_json(self, **kwargs):
        raise AssertionError("fail_json called: %r" % (kwargs,))


def _run(monkeypatch, client, **params):
    service = types.ModuleType("tencentcloud.monitor.v20180724")
    service.models = FakeModels
    service.monitor_client = types.SimpleNamespace(MonitorClient=lambda *args: client)
    monkeypatch.setitem(sys.modules, "tencentcloud", types.ModuleType("tencentcloud"))
    monkeypatch.setitem(
        sys.modules, "tencentcloud.monitor", types.ModuleType("tencentcloud.monitor"))
    monkeypatch.setitem(sys.modules, "tencentcloud.monitor.v20180724", service)
    fake = FakeModule(params)
    monkeypatch.setattr(monitor_alarm_policy_info, "AnsibleModule", lambda **kwargs: fake)
    monkeypatch.setattr(monitor_alarm_policy_info, "create_credential", lambda module: object())
    monkeypatch.setattr(
        monitor_alarm_policy_info, "create_client_profile", lambda module, endpoint: object())
    with pytest.raises(ModuleExit):
        monitor_alarm_policy_info.run_module()
    return fake


def test_run_module_paginates_page_numbers_until_total_count(monkeypatch):
    client = FakeClient([
        FakeResponse([FakeItem("a"), FakeItem("b")], 3),
        FakeResponse([FakeItem("c")], 3),
    ])
    fake = _run(monkeypatch, client, region="ap-guangzhou", module="monitor", page_size=2)
    payload = fake.exit_payload
    assert payload["changed"] is False
    assert [item["Marker"] for item in payload["alarm_policies"]] == ["a", "b", "c"]
    assert payload["total_count"] == 3
    assert [request.PageNumber for request in client.requests] == [1, 2]
    assert [request.PageSize for request in client.requests] == [2, 2]
