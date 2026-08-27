from __future__ import absolute_import, division, print_function

__metaclass__ = type

import sys
import types

import pytest

from ansible_collections.tencentcloud.cloud.plugins.modules import ckafka_instance_info


class FakeFilter:
    pass


class FakeRequest:
    pass


class FakeModels:
    Filter = FakeFilter
    DescribeInstancesDetailRequest = FakeRequest


def test_build_request_maps_ids_and_int_pagination():
    request = ckafka_instance_info.build_request(FakeModels, ['ckafka-123'], {}, 20, 100)
    assert request.InstanceIdList == ["ckafka-123"]
    assert request.Offset == 20
    assert request.Limit == 100


def test_build_request_omits_ids_when_empty():
    request = ckafka_instance_info.build_request(FakeModels, [], {}, 20, 100)
    assert not hasattr(request, "InstanceIdList")


def test_build_request_sorts_filters():
    request = ckafka_instance_info.build_request(FakeModels, [], {'VpcId': ['vpc-123'], 'InstanceId': ['ckafka-123']}, 20, 100)
    assert [(item.Name, item.Values) for item in request.Filters] == [('InstanceId', ['ckafka-123']), ('VpcId', ['vpc-123'])]


class FakeItem:
    def __init__(self, marker):
        self.marker = marker

    def _serialize(self, allow_none=True):
        return {"Marker": self.marker}


class FakeResult:
    def __init__(self, items, total_count):
        self.InstanceList = items
        self.TotalCount = total_count


class FakeResponse:
    def __init__(self, items, total_count):
        self.Result = FakeResult(items, total_count)


class FakeNullResponse:
    Result = None


class FakeClient:
    def __init__(self, pages):
        self._pages = list(pages)
        self.requests = []

    def DescribeInstancesDetail(self, request):
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
    service = types.ModuleType("tencentcloud.ckafka.v20190819")
    service.models = FakeModels
    service.ckafka_client = types.SimpleNamespace(CkafkaClient=lambda *args: client)
    monkeypatch.setitem(sys.modules, "tencentcloud", types.ModuleType("tencentcloud"))
    monkeypatch.setitem(sys.modules, "tencentcloud.ckafka", types.ModuleType("tencentcloud.ckafka"))
    monkeypatch.setitem(sys.modules, "tencentcloud.ckafka.v20190819", service)
    fake = FakeModule(params)
    monkeypatch.setattr(ckafka_instance_info, "AnsibleModule", lambda **kwargs: fake)
    monkeypatch.setattr(ckafka_instance_info, "create_credential", lambda module: object())
    monkeypatch.setattr(ckafka_instance_info, "create_client_profile", lambda module, endpoint: object())
    with pytest.raises(ModuleExit):
        ckafka_instance_info.run_module()
    return fake


def test_run_module_paginates_until_total_count(monkeypatch):
    client = FakeClient([
        FakeResponse([FakeItem("a"), FakeItem("b")], 3),
        FakeResponse([FakeItem("c")], 3),
    ])
    fake = _run(monkeypatch, client, region="ap-guangzhou", instance_ids=None, filters={}, page_size=2)
    payload = fake.exit_payload
    assert payload["changed"] is False
    assert [item["Marker"] for item in payload["instances"]] == ["a", "b", "c"]
    assert payload["total_count"] == 3
    assert [request.Offset for request in client.requests] == [0, 2]


def test_run_module_handles_null_result(monkeypatch):
    client = FakeClient([FakeNullResponse()])
    fake = _run(monkeypatch, client, region="ap-guangzhou", instance_ids=None, filters={}, page_size=2)
    payload = fake.exit_payload
    assert payload["instances"] == []
    assert payload["total_count"] == 0
