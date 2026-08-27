from __future__ import absolute_import, division, print_function

__metaclass__ = type

import sys
import types

import pytest

from ansible_collections.susunola.tencentcloud.plugins.modules import kms_key_info


class FakeRequest:
    pass


class FakeModels:
    ListKeysRequest = FakeRequest
    DescribeKeysRequest = FakeRequest


def test_build_list_request_uses_int_pagination():
    request = kms_key_info.build_list_request(FakeModels, 20, 100)
    assert request.Offset == 20
    assert request.Limit == 100


def test_build_describe_request_maps_key_ids():
    request = kms_key_info.build_describe_request(FakeModels, ["key-123"])
    assert request.KeyIds == ["key-123"]


class FakeItem:
    def __init__(self, marker):
        self.marker = marker

    def _serialize(self, allow_none=True):
        return {"Marker": self.marker}


class FakeListResponse:
    def __init__(self, items, total_count):
        self.Keys = items
        self.TotalCount = total_count
        self.RequestId = "req-list"


class FakeDescribeResponse:
    def __init__(self, items):
        self.KeyMetadatas = items
        self.RequestId = "req-describe"


class FakeClient:
    def __init__(self, pages, described=None):
        self._pages = list(pages)
        self._described = described
        self.list_requests = []
        self.describe_requests = []

    def ListKeys(self, request):
        self.list_requests.append(request)
        return self._pages.pop(0)

    def DescribeKeys(self, request):
        self.describe_requests.append(request)
        return self._described


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
    service = types.ModuleType("tencentcloud.kms.v20190118")
    service.models = FakeModels
    service.kms_client = types.SimpleNamespace(KmsClient=lambda *args: client)
    monkeypatch.setitem(sys.modules, "tencentcloud", types.ModuleType("tencentcloud"))
    monkeypatch.setitem(sys.modules, "tencentcloud.kms", types.ModuleType("tencentcloud.kms"))
    monkeypatch.setitem(sys.modules, "tencentcloud.kms.v20190118", service)
    fake = FakeModule(params)
    monkeypatch.setattr(kms_key_info, "AnsibleModule", lambda **kwargs: fake)
    monkeypatch.setattr(kms_key_info, "create_credential", lambda module: object())
    monkeypatch.setattr(kms_key_info, "create_client_profile", lambda module, endpoint: object())
    with pytest.raises(ModuleExit):
        kms_key_info.run_module()
    return fake


def test_run_module_lists_keys_with_pagination(monkeypatch):
    client = FakeClient([
        FakeListResponse([FakeItem("a"), FakeItem("b")], 3),
        FakeListResponse([FakeItem("c")], 3),
    ])
    fake = _run(monkeypatch, client, region="ap-guangzhou", key_ids=None, page_size=2)
    payload = fake.exit_payload
    assert payload["changed"] is False
    assert [item["Marker"] for item in payload["kms_keys"]] == ["a", "b", "c"]
    assert payload["total_count"] == 3
    assert payload["request_id"] == "req-list"
    assert [request.Offset for request in client.list_requests] == [0, 2]
    assert client.describe_requests == []


def test_run_module_describes_keys_without_pagination(monkeypatch):
    client = FakeClient([], described=FakeDescribeResponse([FakeItem("x"), FakeItem("y")]))
    fake = _run(monkeypatch, client, region="ap-guangzhou",
                key_ids=["key-1", "key-2"], page_size=100)
    payload = fake.exit_payload
    assert [item["Marker"] for item in payload["kms_keys"]] == ["x", "y"]
    assert payload["total_count"] == 2
    assert payload["request_id"] == "req-describe"
    assert client.describe_requests[0].KeyIds == ["key-1", "key-2"]
    assert client.list_requests == []
