"""Deep harness tests for the cam_policy_info module.

Covers build_request (scope map, keyword, page-based pagination), the
client-side exact-name filter, the direct GetPolicy branch, page-list
pagination through run_module and the sdk_call failure contract.
"""
from __future__ import absolute_import, division, print_function

__metaclass__ = type

import sys
import types

import pytest

from ansible_collections.susunola.tencentcloud.plugins.modules import cam_policy_info


class FakeRequest:
    pass


class FakeModels:
    ListPoliciesRequest = FakeRequest
    GetPolicyRequest = FakeRequest


def test_build_request_maps_scope_and_pagination():
    request = cam_policy_info.build_request(FakeModels, "local", None, 2, 100)
    assert request.Scope == "Local"
    assert request.Page == 2
    assert request.Rp == 100
    assert not hasattr(request, "Keyword") or request.Keyword is None


def test_build_request_passes_keyword():
    request = cam_policy_info.build_request(FakeModels, "qcs", "app-read-only", 1, 50)
    assert request.Scope == "QCS"
    assert request.Keyword == "app-read-only"


def test_scope_map_covers_all_choices():
    assert cam_policy_info.SCOPE_MAP == {"all": "All", "local": "Local", "qcs": "QCS"}


class FakeItem:
    def __init__(self, data):
        self._data = dict(data)

    def __getattr__(self, name):
        try:
            return self._data[name]
        except KeyError:
            raise AttributeError(name)

    def _serialize(self, allow_none=True):
        return dict(self._data)


class FakeListResponse:
    def __init__(self, items, total_num):
        self.List = items
        self.TotalNum = total_num


class FakeClient:
    def __init__(self, pages=None, get_policy=None):
        self._pages = list(pages or [])
        self._get_policy = get_policy
        self.list_requests = []
        self.get_requests = []

    def ListPolicies(self, request):
        self.list_requests.append(request)
        return self._pages.pop(0)

    def GetPolicy(self, request):
        self.get_requests.append(request)
        return self._get_policy


class ModuleExit(BaseException):
    pass


class ModuleFail(BaseException):
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
    service = types.ModuleType("tencentcloud.cam.v20190116")
    service.models = FakeModels
    service.cam_client = types.SimpleNamespace(CamClient=lambda *args: client)
    monkeypatch.setitem(sys.modules, "tencentcloud", types.ModuleType("tencentcloud"))
    monkeypatch.setitem(sys.modules, "tencentcloud.cam",
                        types.ModuleType("tencentcloud.cam"))
    monkeypatch.setitem(sys.modules, "tencentcloud.cam.v20190116", service)


def _run(monkeypatch, client, **params):
    _inject_sdk(monkeypatch, client)
    fake = FakeModule(params)
    monkeypatch.setattr(cam_policy_info, "AnsibleModule", lambda **kwargs: fake)
    monkeypatch.setattr(cam_policy_info, "create_credential", lambda module: object())
    monkeypatch.setattr(cam_policy_info, "create_client_profile", lambda module, endpoint: object())
    with pytest.raises(ModuleExit):
        cam_policy_info.run_module()
    return fake


def test_run_module_lists_policies_across_pages(monkeypatch):
    client = FakeClient([
        FakeListResponse([FakeItem({"PolicyName": "app-a"}), FakeItem({"PolicyName": "app-b"})], 3),
        FakeListResponse([FakeItem({"PolicyName": "app-c"})], 3),
    ])
    fake = _run(monkeypatch, client, region="ap-guangzhou", policy_id=None,
                policy_name=None, scope="all", page_size=2)
    payload = fake.exit_payload
    assert payload["changed"] is False
    assert [item["PolicyName"] for item in payload["policies"]] == ["app-a", "app-b", "app-c"]
    assert payload["total_count"] == 3
    assert [request.Page for request in client.list_requests] == [1, 2]
    assert [request.Rp for request in client.list_requests] == [2, 2]


def test_run_module_filters_by_exact_policy_name(monkeypatch):
    client = FakeClient([
        FakeListResponse([FakeItem({"PolicyName": "app-read-only"}), FakeItem({"PolicyName": "other"})], 2),
    ])
    fake = _run(monkeypatch, client, region="ap-guangzhou", policy_id=None,
                policy_name="app-read-only", scope="local", page_size=2)
    payload = fake.exit_payload
    assert [item["PolicyName"] for item in payload["policies"]] == ["app-read-only"]
    assert payload["total_count"] == 1
    assert client.list_requests[0].Scope == "Local"
    assert client.list_requests[0].Keyword == "app-read-only"


def test_run_module_fetches_policy_by_id(monkeypatch):
    client = FakeClient(get_policy=FakeItem({"PolicyName": "app-x", "RequestId": "req-get"}))
    fake = _run(monkeypatch, client, region="ap-guangzhou", policy_id=42,
                policy_name=None, scope="all", page_size=100)
    payload = fake.exit_payload
    assert payload["total_count"] == 1
    assert payload["policies"] == [{"PolicyName": "app-x", "PolicyId": 42}]
    assert [request.PolicyId for request in client.get_requests] == [42]
    assert client.list_requests == []


def test_run_module_stops_on_empty_page(monkeypatch):
    client = FakeClient([FakeListResponse([], 0)])
    fake = _run(monkeypatch, client, region="ap-guangzhou", policy_id=None,
                policy_name=None, scope="all", page_size=2)
    payload = fake.exit_payload
    assert payload["policies"] == []
    assert payload["total_count"] == 0
    assert len(client.list_requests) == 1


def test_run_module_fails_cleanly_on_sdk_error(monkeypatch):
    class FailingClient:
        def ListPolicies(self, request):
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
    fake = FakeModule({
        "region": "ap-guangzhou",
        "policy_id": None,
        "policy_name": None,
        "scope": "all",
        "page_size": 2,
    })
    monkeypatch.setattr(cam_policy_info, "AnsibleModule", lambda **kwargs: fake)
    monkeypatch.setattr(cam_policy_info, "create_credential", lambda module: object())
    monkeypatch.setattr(cam_policy_info, "create_client_profile", lambda module, endpoint: object())
    monkeypatch.setattr(cam_policy_info, "sdk_call", failing_sdk_call)
    with pytest.raises(ModuleFail) as excinfo:
        cam_policy_info.run_module()
    payload = excinfo.value.payload
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert payload["error_code"] == "UnauthorizedOperation"
    assert payload["request_id"] == "req-err"
