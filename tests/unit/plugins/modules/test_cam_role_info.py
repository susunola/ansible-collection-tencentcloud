"""Deep harness tests for the cam_role_info module.

Covers build_request's page-based pagination, run_module pagination through
DescribeRoleList, the client-side role_id/role_name filters, empty-page
termination and the sdk_call failure contract.
"""
from __future__ import absolute_import, division, print_function

__metaclass__ = type

import sys
import types

import pytest

from ansible_collections.susunola.tencentcloud.plugins.modules import cam_role_info


class FakeRequest:
    pass


class FakeModels:
    DescribeRoleListRequest = FakeRequest


def test_build_request_uses_page_based_pagination():
    request = cam_role_info.build_request(FakeModels, 3, 100)
    assert request.Page == 3
    assert request.Rp == 100


class FakeItem:
    def __init__(self, role_id, role_name):
        self.RoleId = role_id
        self.RoleName = role_name

    def _serialize(self, allow_none=True):
        return {"RoleId": self.RoleId, "RoleName": self.RoleName}


class FakeListResponse:
    def __init__(self, items, total_num):
        self.List = items
        self.TotalNum = total_num


class FakeClient:
    def __init__(self, pages):
        self._pages = list(pages)
        self.requests = []

    def DescribeRoleList(self, request):
        self.requests.append(request)
        return self._pages.pop(0)


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
    monkeypatch.setattr(cam_role_info, "AnsibleModule", lambda **kwargs: fake)
    monkeypatch.setattr(cam_role_info, "create_credential", lambda module: object())
    monkeypatch.setattr(cam_role_info, "create_client_profile", lambda module, endpoint: object())
    with pytest.raises(ModuleExit):
        cam_role_info.run_module()
    return fake


def test_run_module_paginates_until_total_num_reached(monkeypatch):
    client = FakeClient([
        FakeListResponse([FakeItem("A1", "role-a"), FakeItem("A2", "role-b")], 3),
        FakeListResponse([FakeItem("A3", "role-c")], 3),
    ])
    fake = _run(monkeypatch, client, region="ap-guangzhou", role_id=None,
                role_name=None, page_size=2)
    payload = fake.exit_payload
    assert payload["changed"] is False
    assert [item["RoleName"] for item in payload["roles"]] == ["role-a", "role-b", "role-c"]
    assert payload["total_count"] == 3
    assert [request.Page for request in client.requests] == [1, 2]


def test_run_module_applies_role_id_and_name_filters(monkeypatch):
    client = FakeClient([
        FakeListResponse([FakeItem("A1", "role-a"), FakeItem("A1", "role-other"), FakeItem("A9", "role-a")], 3),
    ])
    fake = _run(monkeypatch, client, region="ap-guangzhou", role_id="A1",
                role_name="role-a", page_size=10)
    payload = fake.exit_payload
    assert payload["roles"] == [{"RoleId": "A1", "RoleName": "role-a"}]
    assert payload["total_count"] == 1


def test_run_module_stops_on_empty_page(monkeypatch):
    client = FakeClient([FakeListResponse([], 0)])
    fake = _run(monkeypatch, client, region="ap-guangzhou", role_id=None,
                role_name=None, page_size=2)
    payload = fake.exit_payload
    assert payload["roles"] == []
    assert payload["total_count"] == 0
    assert len(client.requests) == 1


def test_run_module_fails_cleanly_on_sdk_error(monkeypatch):
    class FailingClient:
        def DescribeRoleList(self, request):
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
        "role_id": None,
        "role_name": None,
        "page_size": 2,
    })
    monkeypatch.setattr(cam_role_info, "AnsibleModule", lambda **kwargs: fake)
    monkeypatch.setattr(cam_role_info, "create_credential", lambda module: object())
    monkeypatch.setattr(cam_role_info, "create_client_profile", lambda module, endpoint: object())
    monkeypatch.setattr(cam_role_info, "sdk_call", failing_sdk_call)
    with pytest.raises(ModuleFail) as excinfo:
        cam_role_info.run_module()
    payload = excinfo.value.payload
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert payload["error_code"] == "UnauthorizedOperation"
    assert payload["request_id"] == "req-err"
