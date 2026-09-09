"""Deep harness tests for key_pair_info.

Covers build_request (pagination, key ids, sorted filters, scalar
value wrapping) and run_module() end to end: multi-page collection
driven by TotalCount, an empty result set, and the sdk_call fail
contract (msg/error/error_code/request_id).
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import sys
import types

import pytest

from ansible_collections.susunola.tencentcloud.plugins.modules import key_pair_info


class FakeFilter:
    pass


class FakeRequest:
    pass


class FakeModels:
    Filter = FakeFilter
    DescribeKeyPairsRequest = FakeRequest


def test_build_request_maps_ids_and_integer_pagination():
    request = key_pair_info.build_request(FakeModels, ["skey-123"], {}, 20, 100)
    assert request.KeyIds == ["skey-123"]
    assert request.Offset == 20
    assert request.Limit == 100
    assert not hasattr(request, "Filters")


def test_build_request_sorts_filters():
    request = key_pair_info.build_request(FakeModels, [], {"key-name": ["deploy-key"], "project-id": [0]}, 0, 100)
    assert [(item.Name, item.Values) for item in request.Filters] == [
        ("key-name", ["deploy-key"]), ("project-id", [0]),
    ]


def test_build_request_wraps_scalar_filter_values():
    request = key_pair_info.build_request(FakeModels, [], {"key-name": "deploy-key"}, 0, 100)
    assert request.Filters[0].Values == ["deploy-key"]


class FakeItem:
    def __init__(self, marker):
        self.marker = marker

    def _serialize(self, allow_none=True):
        return {"Marker": self.marker}


class FakeResponse:
    def __init__(self, items, total_count):
        self.KeyPairSet = items
        self.TotalCount = total_count
        self.RequestId = "req-page"


class FakeClient:
    def __init__(self, pages):
        self._pages = list(pages)
        self.requests = []

    def DescribeKeyPairs(self, request):
        self.requests.append(request)
        return self._pages.pop(0)


class ModuleExit(Exception):
    pass


class ModuleFail(Exception):
    def __init__(self, payload):
        self.payload = payload
        super(ModuleFail, self).__init__("module failed: %r" % (payload,))


class FakeModule:
    def __init__(self, params):
        self.params = params
        self.exit_payload = None
        self.fail_payload = None

    def exit_json(self, **kwargs):
        self.exit_payload = kwargs
        raise ModuleExit()

    def fail_json(self, **kwargs):
        self.fail_payload = kwargs
        raise ModuleFail(kwargs)


def _inject_sdk(monkeypatch, client):
    service = types.ModuleType("tencentcloud.cvm.v20170312")
    service.models = FakeModels
    service.cvm_client = types.SimpleNamespace(CvmClient=lambda *args: client)
    monkeypatch.setitem(sys.modules, "tencentcloud", types.ModuleType("tencentcloud"))
    monkeypatch.setitem(sys.modules, "tencentcloud.cvm",
                        types.ModuleType("tencentcloud.cvm"))
    monkeypatch.setitem(sys.modules, "tencentcloud.cvm.v20170312", service)


def _run(monkeypatch, client, **params):
    _inject_sdk(monkeypatch, client)
    fake = FakeModule(params)
    monkeypatch.setattr(key_pair_info, "AnsibleModule", lambda **kwargs: fake)
    monkeypatch.setattr(key_pair_info, "create_credential", lambda module: object())
    monkeypatch.setattr(key_pair_info, "create_client_profile", lambda module, endpoint: object())
    with pytest.raises(ModuleExit):
        key_pair_info.run_module()
    return fake


def test_run_module_paginates_until_total_count(monkeypatch):
    client = FakeClient([
        FakeResponse([FakeItem("a"), FakeItem("b")], 3),
        FakeResponse([FakeItem("c")], 3),
    ])
    fake = _run(monkeypatch, client, region="ap-guangzhou", key_ids=None, filters={}, page_size=2)
    payload = fake.exit_payload
    assert payload["changed"] is False
    assert [item["Marker"] for item in payload["key_pairs"]] == ["a", "b", "c"]
    assert payload["total_count"] == 3
    assert [request.Offset for request in client.requests] == [0, 2]


def test_run_module_returns_empty_on_empty_first_page(monkeypatch):
    client = FakeClient([FakeResponse([], 0)])
    fake = _run(monkeypatch, client, region="ap-guangzhou", key_ids=None, filters={}, page_size=2)
    payload = fake.exit_payload
    assert payload["key_pairs"] == []
    assert payload["total_count"] == 0
    assert len(client.requests) == 1


def test_run_module_fails_cleanly_on_sdk_error(monkeypatch):
    class FailingClient:
        def DescribeKeyPairs(self, request):
            raise RuntimeError("api exploded")

    def failing_sdk_call(module, function, request):
        # Mirrors the real sdk_call failure contract pinned in
        # tests/unit/plugins/module_utils/test_tencentcloud.py.
        try:
            return function(request)
        except RuntimeError as exc:
            module.fail_json(
                msg="Tencent Cloud API request failed",
                error=str(exc),
                error_code="UnauthorizedOperation",
                request_id="req-err",
            )

    _inject_sdk(monkeypatch, FailingClient())
    fake = FakeModule({"region": "ap-guangzhou", "key_ids": None, "filters": {}, "page_size": 2})
    monkeypatch.setattr(key_pair_info, "AnsibleModule", lambda **kwargs: fake)
    monkeypatch.setattr(key_pair_info, "create_credential", lambda module: object())
    monkeypatch.setattr(key_pair_info, "create_client_profile", lambda module, endpoint: object())
    monkeypatch.setattr(key_pair_info, "sdk_call", failing_sdk_call)
    with pytest.raises(ModuleFail) as excinfo:
        key_pair_info.run_module()
    payload = excinfo.value.payload
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert payload["error_code"] == "UnauthorizedOperation"
    assert payload["request_id"] == "req-err"
