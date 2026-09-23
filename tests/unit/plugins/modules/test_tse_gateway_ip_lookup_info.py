"""Deep harness tests for tse_gateway_ip_lookup_info.

Covers the single-call IP lookup request builder (public IP mapping) and
run_module() end to end: happy path gateway detail, missing result
falls back to an empty dict, and the sdk_error_payload fail contract.
This module performs one un-paginated DescribeCloudNativeAPIGatewayInfoByIp
call, so no paginator is exercised.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import sys
import types

import pytest

from ansible_collections.susunola.tencentcloud.plugins.modules import tse_gateway_ip_lookup_info


class FakeRequest:
    pass


class FakeModels:
    DescribeCloudNativeAPIGatewayInfoByIpRequest = FakeRequest


def test_request_maps_public_ip():
    value = tse_gateway_ip_lookup_info.request(FakeModels, "203.0.113.10")
    assert value.PublicNetworkIP == "203.0.113.10"


class FakeResult:
    def __init__(self, marker):
        self.marker = marker

    def _serialize(self, allow_none=True):
        return {"GatewayId": self.marker}


class FakeResponse:
    def __init__(self, result, request_id):
        self.Result = result
        self.RequestId = request_id


class FakeClient:
    def __init__(self, response):
        self._response = response
        self.requests = []

    def DescribeCloudNativeAPIGatewayInfoByIp(self, request):
        self.requests.append(request)
        return self._response


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

    def require_sdk(self):
        pass

    def create_client(self, client_class, endpoint):
        return self._client

    def sdk_call(self, operation, request=None):
        if request is not None:
            return operation(request)
        return operation()

    def exit_json(self, **kwargs):
        self.exit_payload = kwargs
        raise ModuleExit()

    def fail_json(self, **kwargs):
        self.fail_payload = kwargs
        raise ModuleFail(kwargs)


def _inject_sdk(monkeypatch, client):
    service = types.ModuleType("tencentcloud.tse.v20201207")
    service.models = FakeModels
    service.tse_client = types.SimpleNamespace(TseClient=lambda *args: object())
    monkeypatch.setitem(sys.modules, "tencentcloud", types.ModuleType("tencentcloud"))
    monkeypatch.setitem(sys.modules, "tencentcloud.tse",
                        types.ModuleType("tencentcloud.tse"))
    monkeypatch.setitem(sys.modules, "tencentcloud.tse.v20201207", service)


def _run(monkeypatch, client, **params):
    _inject_sdk(monkeypatch, client)
    fake = FakeModule(params)
    fake._client = client
    monkeypatch.setattr(tse_gateway_ip_lookup_info, "TencentCloudModule", lambda **kwargs: fake)
    with pytest.raises(ModuleExit):
        tse_gateway_ip_lookup_info.run_module()
    return fake


def test_run_module_returns_gateway_info(monkeypatch):
    client = FakeClient(FakeResponse(FakeResult("gateway-1"), "req-lookup"))
    fake = _run(monkeypatch, client, public_ip="203.0.113.10")
    payload = fake.exit_payload
    assert payload["changed"] is False
    assert payload["gateway_info"] == {"GatewayId": "gateway-1"}
    assert payload["request_id"] == "req-lookup"
    assert client.requests[0].PublicNetworkIP == "203.0.113.10"


def test_run_module_missing_result_returns_empty_dict(monkeypatch):
    client = FakeClient(FakeResponse(None, "req-none"))
    fake = _run(monkeypatch, client, public_ip="203.0.113.10")
    payload = fake.exit_payload
    assert payload["gateway_info"] == {}
    assert payload["request_id"] == "req-none"


class SdkError(Exception):
    def __init__(self, code, request_id):
        self._code = code
        self._request_id = request_id
        super(SdkError, self).__init__("api exploded")

    def get_code(self):
        return self._code

    def get_request_id(self):
        return self._request_id


def test_run_module_fails_cleanly_on_sdk_error(monkeypatch):
    class FailingClient:
        def DescribeCloudNativeAPIGatewayInfoByIp(self, request):
            raise SdkError("FailedOperation", "req-err")

    failing = FailingClient()
    _inject_sdk(monkeypatch, failing)
    fake = FakeModule({"public_ip": "203.0.113.10"})
    fake._client = failing
    monkeypatch.setattr(tse_gateway_ip_lookup_info, "TencentCloudModule", lambda **kwargs: fake)
    with pytest.raises(ModuleFail) as excinfo:
        tse_gateway_ip_lookup_info.run_module()
    payload = excinfo.value.payload
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert payload["error"] == "api exploded"
    assert payload["error_code"] == "FailedOperation"
    assert payload["request_id"] == "req-err"
