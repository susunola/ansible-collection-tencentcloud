"""Deep harness tests for the cam_user_info module.

Covers the parameterless build_request, the client-side matches() helper
(exact name and name-keyword substring), and run_module end-to-end over the
single ListUsers API response, including the empty-data and sdk_call failure
paths.
"""
from __future__ import absolute_import, division, print_function

__metaclass__ = type

import sys
import types

import pytest

from ansible_collections.susunola.tencentcloud.plugins.modules import cam_user_info


class FakeRequest:
    pass


class FakeModels:
    ListUsersRequest = FakeRequest


class FakeUser:
    def __init__(self, name):
        self.Name = name

    def _serialize(self, allow_none=True):
        return {"Name": self.Name}


def test_build_request_takes_no_parameters():
    request = cam_user_info.build_request(FakeModels)
    assert isinstance(request, FakeRequest)


def test_matches_exact_name_and_keyword_substring():
    assert cam_user_info.matches(FakeUser("deploy-bot")) is True
    assert cam_user_info.matches(FakeUser("deploy-bot"), name="deploy-bot") is True
    assert cam_user_info.matches(FakeUser("deploy-bot"), name="deploy") is False
    assert cam_user_info.matches(FakeUser("deploy-bot"), name_keyword="bot") is True
    assert cam_user_info.matches(FakeUser("deploy-bot"), name_keyword="ci") is False


def test_matches_combines_filters_and_tolerates_none_name():
    assert cam_user_info.matches(FakeUser("deploy-bot"), name="deploy-bot", name_keyword="bot") is True
    assert cam_user_info.matches(FakeUser("deploy-bot"), name="deploy-bot", name_keyword="ci") is False
    assert cam_user_info.matches(FakeUser(None), name_keyword="bot") is False


class FakeResponse:
    def __init__(self, data):
        self.Data = data


class FakeClient:
    def __init__(self, data):
        self._data = data
        self.requests = []

    def ListUsers(self, request):
        self.requests.append(request)
        return FakeResponse(self._data)


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
    monkeypatch.setattr(cam_user_info, "AnsibleModule", lambda **kwargs: fake)
    monkeypatch.setattr(cam_user_info, "create_credential", lambda module: object())
    monkeypatch.setattr(cam_user_info, "create_client_profile", lambda module, endpoint: object())
    with pytest.raises(ModuleExit):
        cam_user_info.run_module()
    return fake


def test_run_module_returns_all_users_when_unfiltered(monkeypatch):
    client = FakeClient([FakeUser("deploy-bot"), FakeUser("ci-runner")])
    fake = _run(monkeypatch, client, region="ap-guangzhou", name=None, name_keyword=None)
    payload = fake.exit_payload
    assert payload["changed"] is False
    assert [user["Name"] for user in payload["users"]] == ["deploy-bot", "ci-runner"]
    assert payload["total_count"] == 2
    assert len(client.requests) == 1


def test_run_module_filters_by_exact_name_and_keyword(monkeypatch):
    client = FakeClient([FakeUser("deploy-bot"), FakeUser("deploy-bot-old"), FakeUser("web-app")])
    fake = _run(monkeypatch, client, region="ap-guangzhou", name="deploy-bot", name_keyword="bot")
    payload = fake.exit_payload
    assert [user["Name"] for user in payload["users"]] == ["deploy-bot"]
    assert payload["total_count"] == 1

    client = FakeClient([FakeUser("deploy-bot"), FakeUser("web-app")])
    fake = _run(monkeypatch, client, region="ap-guangzhou", name=None, name_keyword="app")
    payload = fake.exit_payload
    assert [user["Name"] for user in payload["users"]] == ["web-app"]
    assert payload["total_count"] == 1


def test_run_module_returns_empty_when_no_users(monkeypatch):
    client = FakeClient([])
    fake = _run(monkeypatch, client, region="ap-guangzhou", name=None, name_keyword=None)
    payload = fake.exit_payload
    assert payload["users"] == []
    assert payload["total_count"] == 0


def test_run_module_fails_cleanly_on_sdk_error(monkeypatch):
    class FailingClient:
        def ListUsers(self, request):
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
    fake = FakeModule({"region": "ap-guangzhou", "name": None, "name_keyword": None})
    monkeypatch.setattr(cam_user_info, "AnsibleModule", lambda **kwargs: fake)
    monkeypatch.setattr(cam_user_info, "create_credential", lambda module: object())
    monkeypatch.setattr(cam_user_info, "create_client_profile", lambda module, endpoint: object())
    monkeypatch.setattr(cam_user_info, "sdk_call", failing_sdk_call)
    with pytest.raises(ModuleFail) as excinfo:
        cam_user_info.run_module()
    payload = excinfo.value.payload
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert payload["error_code"] == "UnauthorizedOperation"
    assert payload["request_id"] == "req-err"
