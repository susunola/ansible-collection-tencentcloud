from __future__ import absolute_import, division, print_function

__metaclass__ = type

import sys
import types

import pytest

from ansible_collections.tencentcloud.cloud.plugins.modules import as_scaling_group_info


class FakeFilter:
    pass


class FakeRequest:
    pass


class FakeModels:
    Filter = FakeFilter
    DescribeAutoScalingGroupsRequest = FakeRequest


def test_build_request_maps_ids_and_int_pagination():
    request = as_scaling_group_info.build_request(FakeModels, ['asg-123'], {}, 20, 100)
    assert request.AutoScalingGroupIds == ["asg-123"]
    assert request.Offset == 20
    assert request.Limit == 100


def test_build_request_omits_ids_when_empty():
    request = as_scaling_group_info.build_request(FakeModels, [], {}, 20, 100)
    assert not hasattr(request, "AutoScalingGroupIds")


def test_build_request_sorts_filters():
    request = as_scaling_group_info.build_request(FakeModels, [], {'zone': ['ap-guangzhou-1'], 'auto-scaling-group-id': ['asg-123']}, 20, 100)
    assert [(item.Name, item.Values) for item in request.Filters] == [('auto-scaling-group-id', ['asg-123']), ('zone', ['ap-guangzhou-1'])]


class FakeItem:
    def __init__(self, marker):
        self.marker = marker

    def _serialize(self, allow_none=True):
        return {"Marker": self.marker}


class FakeResponse:
    def __init__(self, items, total_count):
        self.AutoScalingGroupSet = items
        self.TotalCount = total_count


class FakeClient:
    def __init__(self, pages):
        self._pages = list(pages)
        self.requests = []

    def DescribeAutoScalingGroups(self, request):
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
    service = types.ModuleType("tencentcloud.autoscaling.v20180419")
    service.models = FakeModels
    service.autoscaling_client = types.SimpleNamespace(AutoscalingClient=lambda *args: client)
    monkeypatch.setitem(sys.modules, "tencentcloud", types.ModuleType("tencentcloud"))
    monkeypatch.setitem(sys.modules, "tencentcloud.autoscaling", types.ModuleType("tencentcloud.autoscaling"))
    monkeypatch.setitem(sys.modules, "tencentcloud.autoscaling.v20180419", service)
    fake = FakeModule(params)
    monkeypatch.setattr(as_scaling_group_info, "AnsibleModule", lambda **kwargs: fake)
    monkeypatch.setattr(as_scaling_group_info, "create_credential", lambda module: object())
    monkeypatch.setattr(as_scaling_group_info, "create_client_profile", lambda module, endpoint: object())
    with pytest.raises(ModuleExit):
        as_scaling_group_info.run_module()
    return fake


def test_run_module_paginates_until_total_count(monkeypatch):
    client = FakeClient([
        FakeResponse([FakeItem("a"), FakeItem("b")], 3),
        FakeResponse([FakeItem("c")], 3),
    ])
    fake = _run(monkeypatch, client, region="ap-guangzhou", auto_scaling_group_ids=None, filters={}, page_size=2)
    payload = fake.exit_payload
    assert payload["changed"] is False
    assert [item["Marker"] for item in payload["scaling_groups"]] == ["a", "b", "c"]
    assert payload["total_count"] == 3
    assert [request.Offset for request in client.requests] == [0, 2]
