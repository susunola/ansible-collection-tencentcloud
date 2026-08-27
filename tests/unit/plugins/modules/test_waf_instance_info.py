from __future__ import absolute_import, division, print_function

__metaclass__ = type

import sys
import types

import pytest

from ansible_collections.tencentcloud.cloud.plugins.modules import waf_instance_info


class FakeFiltersItemNew:
    pass


class FakeRequest:
    pass


class FakeModels:
    FiltersItemNew = FakeFiltersItemNew
    DescribeInstancesRequest = FakeRequest


def test_build_request_uses_int_pagination():
    request = waf_instance_info.build_request(FakeModels, {}, 20, 100)
    assert request.Offset == 20
    assert request.Limit == 100
    assert not hasattr(request, "Filters")


def test_build_request_sorts_filters():
    request = waf_instance_info.build_request(
        FakeModels, {"InstanceName": ["waf-prod"], "InstanceId": ["waf_123"]}, 0, 100)
    assert [(item.Name, item.Values) for item in request.Filters] == [
        ("InstanceId", ["waf_123"]), ("InstanceName", ["waf-prod"]),
    ]


class FakeItem:
    def __init__(self, marker):
        self.marker = marker

    def _serialize(self, allow_none=True):
        return {"Marker": self.marker}


class FakeResponse:
    def __init__(self, items, total):
        self.Instances = items
        self.Total = total


class FakeClient:
    def __init__(self, pages):
        self._pages = list(pages)
        self.requests = []

    def DescribeInstances(self, request):
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
    service = types.ModuleType("tencentcloud.waf.v20180125")
    service.models = FakeModels
    service.waf_client = types.SimpleNamespace(WafClient=lambda *args: client)
    monkeypatch.setitem(sys.modules, "tencentcloud", types.ModuleType("tencentcloud"))
    monkeypatch.setitem(sys.modules, "tencentcloud.waf", types.ModuleType("tencentcloud.waf"))
    monkeypatch.setitem(sys.modules, "tencentcloud.waf.v20180125", service)
    fake = FakeModule(params)
    monkeypatch.setattr(waf_instance_info, "AnsibleModule", lambda **kwargs: fake)
    monkeypatch.setattr(waf_instance_info, "create_credential", lambda module: object())
    monkeypatch.setattr(waf_instance_info, "create_client_profile", lambda module, endpoint: object())
    with pytest.raises(ModuleExit):
        waf_instance_info.run_module()
    return fake


def test_run_module_paginates_until_total(monkeypatch):
    client = FakeClient([
        FakeResponse([FakeItem("a"), FakeItem("b")], 3),
        FakeResponse([FakeItem("c")], 3),
    ])
    fake = _run(monkeypatch, client, region="ap-guangzhou", filters={}, page_size=2)
    payload = fake.exit_payload
    assert payload["changed"] is False
    assert [item["Marker"] for item in payload["instances"]] == ["a", "b", "c"]
    assert payload["total_count"] == 3
    assert [request.Offset for request in client.requests] == [0, 2]
