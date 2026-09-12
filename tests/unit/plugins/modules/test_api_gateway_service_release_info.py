from __future__ import absolute_import, division, print_function

__metaclass__ = type

import sys
import types

import pytest

ansible = types.ModuleType("ansible")
module_utils = types.ModuleType("ansible.module_utils")
basic = types.ModuleType("ansible.module_utils.basic")
basic.AnsibleModule = object
basic.env_fallback = lambda names, default=None: default
monkey_modules = {
    "ansible": ansible,
    "ansible.module_utils": module_utils,
    "ansible.module_utils.basic": basic,
}
for name, module in monkey_modules.items():
    sys.modules.setdefault(name, module)

from ansible_collections.susunola.tencentcloud.plugins.modules import api_gateway_service_release_info


class FakeRequest:
    pass


class FakeModels:
    DescribeServiceEnvironmentListRequest = FakeRequest


def test_build_request_sets_service_id():
    request = api_gateway_service_release_info.build_request(FakeModels, "service-x")
    assert request.ServiceId == "service-x"


@pytest.mark.parametrize(
    ("item", "environment", "expected"),
    [
        ({"EnvironmentName": "release", "Status": 1}, None, True),
        ({"EnvironmentName": "release", "Status": "1"}, "release", True),
        ({"EnvironmentName": "test", "Status": 1}, "release", False),
        ({"EnvironmentName": "release", "Status": 0}, "release", False),
    ],
)
def test_matches_only_released_environment(item, environment, expected):
    assert api_gateway_service_release_info._matches(item, environment) is expected


class FakeItem:
    def __init__(self, environment, status):
        self.environment = environment
        self.status = status

    def _serialize(self, allow_none=True):
        return {"EnvironmentName": self.environment, "Status": self.status}


class FakeResponse:
    RequestId = "req-release"

    def __init__(self):
        self.Result = types.SimpleNamespace(EnvironmentList=[
            FakeItem("test", 1),
            FakeItem("release", 1),
            FakeItem("prepub", 0),
        ])


class FakeClient:
    def __init__(self):
        self.requests = []

    def DescribeServiceEnvironmentList(self, request):
        self.requests.append(request)
        return FakeResponse()


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
    service = types.ModuleType("tencentcloud.apigateway.v20180808")
    service.models = FakeModels
    service.apigateway_client = types.SimpleNamespace(ApigatewayClient=lambda *args: client)
    monkeypatch.setitem(sys.modules, "tencentcloud", types.ModuleType("tencentcloud"))
    monkeypatch.setitem(sys.modules, "tencentcloud.apigateway", types.ModuleType("tencentcloud.apigateway"))
    monkeypatch.setitem(sys.modules, "tencentcloud.apigateway.v20180808", service)


def _run(monkeypatch, client, **params):
    _inject_sdk(monkeypatch, client)
    fake = FakeModule(params)
    monkeypatch.setattr(api_gateway_service_release_info, "AnsibleModule", lambda **kwargs: fake)
    monkeypatch.setattr(api_gateway_service_release_info, "create_credential", lambda module: object())
    monkeypatch.setattr(api_gateway_service_release_info, "create_client_profile", lambda module, endpoint: object())
    with pytest.raises(ModuleExit):
        api_gateway_service_release_info.run_module()
    return fake


def test_run_module_lists_only_released_environments(monkeypatch):
    client = FakeClient()
    fake = _run(monkeypatch, client, region="ap-guangzhou", service_id="service-x", environment=None)
    payload = fake.exit_payload
    assert payload["changed"] is False
    assert [item["EnvironmentName"] for item in payload["releases"]] == ["test", "release"]
    assert payload["release"] is None
    assert payload["request_id"] == "req-release"
    assert client.requests[0].ServiceId == "service-x"


def test_run_module_returns_selected_environment(monkeypatch):
    fake = _run(monkeypatch, FakeClient(), region="ap-guangzhou", service_id="service-x", environment="release")
    assert [item["EnvironmentName"] for item in fake.exit_payload["releases"]] == ["release"]
    assert fake.exit_payload["release"]["EnvironmentName"] == "release"


def test_run_module_fails_cleanly_on_sdk_error(monkeypatch):
    class FailingClient:
        def DescribeServiceEnvironmentList(self, request):
            raise RuntimeError("api exploded")

    def failing_sdk_call(module, function, request):
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
    fake = FakeModule({"region": "ap-guangzhou", "service_id": "service-x", "environment": None})
    monkeypatch.setattr(api_gateway_service_release_info, "AnsibleModule", lambda **kwargs: fake)
    monkeypatch.setattr(api_gateway_service_release_info, "create_credential", lambda module: object())
    monkeypatch.setattr(api_gateway_service_release_info, "create_client_profile", lambda module, endpoint: object())
    monkeypatch.setattr(api_gateway_service_release_info, "sdk_call", failing_sdk_call)
    with pytest.raises(ModuleFail) as excinfo:
        api_gateway_service_release_info.run_module()
    payload = excinfo.value.payload
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert payload["error_code"] == "UnauthorizedOperation"
    assert payload["request_id"] == "req-err"
