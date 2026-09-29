"""Deep harness tests for tse_gateway_ip_lookup_info.

Covers the single-call IP lookup request builder (public IP mapping) and
run_module() end to end: happy path gateway detail, missing result
falls back to an empty dict, and the sdk_error_payload fail contract.
This module performs one un-paginated DescribeCloudNativeAPIGatewayInfoByIp
call, so no paginator is exercised.

The module subclasses ``TencentCloudModule`` and loads its models and
client in its own ``_load()``, so the migration patches that helper and
the base class's ``create_client``, and lets ``module_args()`` supply the
credentials the base class validates. The fake result serialises
``GatewayId``, a real ``DescribeInstanceInfoByIpResult`` field, because
that payload is what ``add_return_samples.py`` captures as the module's
documented sample.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import types

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import tse_gateway_ip_lookup_info
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    module_args,
    run,
)


class FakeRequest:
    pass


class FakeModels:
    DescribeCloudNativeAPIGatewayInfoByIpRequest = FakeRequest


def test_request_maps_public_ip():
    value = tse_gateway_ip_lookup_info.request(FakeModels, "203.0.113.10")
    assert value.PublicNetworkIP == "203.0.113.10"


class FakeResult:
    def __init__(self, gateway_id):
        self.gateway_id = gateway_id

    def _serialize(self, allow_none=True):
        return {"GatewayId": self.gateway_id}


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


def _patch_sdk(monkeypatch, client):
    """Hand the module its models/client class and the client itself."""
    monkeypatch.setattr(tse_gateway_ip_lookup_info, "_load", lambda: (
        FakeModels, types.SimpleNamespace(TseClient=lambda *args: client)))
    monkeypatch.setattr(TencentCloudModule, "create_client",
                        lambda self, client_class, endpoint: client)


def test_run_module_returns_gateway_info(monkeypatch):
    client = FakeClient(FakeResponse(FakeResult("gateway-1"), "req-lookup"))
    _patch_sdk(monkeypatch, client)
    module_args(public_ip="203.0.113.10")

    payload = run(tse_gateway_ip_lookup_info.run_module)

    assert payload["changed"] is False
    assert payload["gateway_info"] == {"GatewayId": "gateway-1"}
    assert payload["request_id"] == "req-lookup"
    assert client.requests[0].PublicNetworkIP == "203.0.113.10"


def test_run_module_missing_result_returns_empty_dict(monkeypatch):
    client = FakeClient(FakeResponse(None, "req-none"))
    _patch_sdk(monkeypatch, client)
    module_args(public_ip="203.0.113.10")

    payload = run(tse_gateway_ip_lookup_info.run_module)

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

    _patch_sdk(monkeypatch, FailingClient())
    module_args(public_ip="203.0.113.10")

    with pytest.raises(AnsibleFailJson) as failure:
        run(tse_gateway_ip_lookup_info.run_module)

    payload = failure.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert payload["error"] == "api exploded"
    assert payload["error_code"] == "FailedOperation"
    assert payload["request_id"] == "req-err"
