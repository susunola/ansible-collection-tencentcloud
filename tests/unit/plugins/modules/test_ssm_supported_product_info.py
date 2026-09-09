"""Deep harness tests for ssm_supported_product_info.

This module has no pagination or selectors: request() returns an empty
DescribeSupportedProductsRequest and run_module() makes a single
DescribeSupportedProducts call, sorts the returned identifiers and
surfaces total_count/request_id. Covers request(), the end-to-end call
path, and the sdk_error_payload fail contract.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import sys
import types

import pytest

from ansible_collections.susunola.tencentcloud.plugins.modules import ssm_supported_product_info


class FakeRequest:
    pass


class FakeModels:
    DescribeSupportedProductsRequest = FakeRequest


def test_request_has_no_hidden_required_fields():
    value = ssm_supported_product_info.request(FakeModels)
    assert isinstance(value, FakeRequest)
    assert vars(value) == {}


class FakeResponse:
    def __init__(self, products, total_count, request_id):
        self.Products = products
        self.TotalCount = total_count
        self.RequestId = request_id


class FakeClient:
    def __init__(self, response):
        self._response = response
        self.requests = []

    def DescribeSupportedProducts(self, request):
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
    service = types.ModuleType("tencentcloud.ssm.v20190923")
    service.models = FakeModels
    service.ssm_client = types.SimpleNamespace(SsmClient=lambda *args: object())
    monkeypatch.setitem(sys.modules, "tencentcloud", types.ModuleType("tencentcloud"))
    monkeypatch.setitem(sys.modules, "tencentcloud.ssm",
                        types.ModuleType("tencentcloud.ssm"))
    monkeypatch.setitem(sys.modules, "tencentcloud.ssm.v20190923", service)


def _run(monkeypatch, client):
    _inject_sdk(monkeypatch, client)
    fake = FakeModule({})
    fake._client = client
    monkeypatch.setattr(ssm_supported_product_info, "TencentCloudModule", lambda **kwargs: fake)
    with pytest.raises(ModuleExit):
        ssm_supported_product_info.run_module()
    return fake


def test_run_module_returns_sorted_products(monkeypatch):
    client = FakeClient(FakeResponse(["ssm", "redis", "cvm"], 3, "req-ok"))
    fake = _run(monkeypatch, client)
    payload = fake.exit_payload
    assert payload["changed"] is False
    assert payload["products"] == ["cvm", "redis", "ssm"]
    assert payload["total_count"] == 3
    assert payload["request_id"] == "req-ok"
    assert len(client.requests) == 1


def test_run_module_falls_back_to_product_count_when_total_missing(monkeypatch):
    client = FakeClient(FakeResponse(["cvm"], None, "req-ok"))
    fake = _run(monkeypatch, client)
    payload = fake.exit_payload
    assert payload["products"] == ["cvm"]
    assert payload["total_count"] == 1


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
        def DescribeSupportedProducts(self, request):
            raise SdkError("AuthFailure", "req-err")

    failing = FailingClient()
    _inject_sdk(monkeypatch, failing)
    fake = FakeModule({})
    fake._client = failing
    monkeypatch.setattr(ssm_supported_product_info, "TencentCloudModule", lambda **kwargs: fake)
    with pytest.raises(ModuleFail) as excinfo:
        ssm_supported_product_info.run_module()
    payload = excinfo.value.payload
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert payload["error"] == "api exploded"
    assert payload["error_code"] == "AuthFailure"
    assert payload["request_id"] == "req-err"
