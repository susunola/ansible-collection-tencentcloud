"""Deep harness tests for the ssm_supported_product_info module.

Covers the parameterless request, run_module end to end through the shared
harness (sorted products, the TotalCount fallback, request_id passthrough) and
the sdk_call failure contract.

This module subclasses ``TencentCloudModule`` rather than ``AnsibleModule``, so
the migration patches the base class's ``create_client`` instead of module-level
factories: the harness supplies the credentials the base class validates, and
the fake SDK service is still injected through ``sys.modules`` because the
module imports its models and client class directly.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import sys
import types

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import ssm_supported_product_info
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    module_args,
    run,
)


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


def _inject_sdk(monkeypatch, client):
    service = types.ModuleType("tencentcloud.ssm.v20190923")
    service.models = FakeModels
    service.ssm_client = types.SimpleNamespace(SsmClient=lambda *args: client)
    monkeypatch.setitem(sys.modules, "tencentcloud", types.ModuleType("tencentcloud"))
    monkeypatch.setitem(sys.modules, "tencentcloud.ssm",
                        types.ModuleType("tencentcloud.ssm"))
    monkeypatch.setitem(sys.modules, "tencentcloud.ssm.v20190923", service)


def _patch_create_client(monkeypatch, client):
    """The module asks its base class for a client; hand it the fake one."""
    monkeypatch.setattr(TencentCloudModule, "create_client",
                        lambda self, client_class, endpoint: client)


def test_run_module_returns_sorted_products(monkeypatch):
    client = FakeClient(FakeResponse(["ssm", "redis", "cvm"], 3, "req-ok"))
    _inject_sdk(monkeypatch, client)
    _patch_create_client(monkeypatch, client)
    module_args()

    payload = run(ssm_supported_product_info.run_module)

    assert payload["changed"] is False
    assert payload["products"] == ["cvm", "redis", "ssm"]
    assert payload["total_count"] == 3
    assert payload["request_id"] == "req-ok"
    assert len(client.requests) == 1


def test_run_module_falls_back_to_product_count_when_total_missing(monkeypatch):
    client = FakeClient(FakeResponse(["cvm"], None, "req-ok"))
    _inject_sdk(monkeypatch, client)
    _patch_create_client(monkeypatch, client)
    module_args()

    payload = run(ssm_supported_product_info.run_module)

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
    _patch_create_client(monkeypatch, failing)
    module_args()

    with pytest.raises(AnsibleFailJson) as failure:
        run(ssm_supported_product_info.run_module)

    payload = failure.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert payload["error"] == "api exploded"
    assert payload["error_code"] == "AuthFailure"
    assert payload["request_id"] == "req-err"
