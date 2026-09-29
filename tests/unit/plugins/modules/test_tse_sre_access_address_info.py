"""Deep harness tests for tse_sre_access_address_info.

Covers the single-call access-address request builder (optional VPC,
subnet, workload and engine-region scoping), the response serialiser
that strips RequestId, and run_module() end to end: happy path access
address payload, missing RequestId handling and the
sdk_error_payload fail contract. This module performs one un-paginated
DescribeSREInstanceAccessAddress call, so no paginator is exercised.

The module subclasses ``TencentCloudModule``, so the migration patches the
base class's ``create_client`` and the module's own ``_load`` (which is where
it imports its models and client class), and lets ``module_args()`` supply the
credentials the base class validates. The fake response serialises the real
``IntranetAddress`` / ``InternetAddress`` / ``RequestId`` fields of
``DescribeSREInstanceAccessAddressResponse``. Tests that need the optional
scope fields absent leave them out of the module args instead of passing them
as explicit ``None``.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import types

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import tse_sre_access_address_info
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    module_args,
    run,
)


class FakeRequest:
    pass


class FakeModels:
    DescribeSREInstanceAccessAddressRequest = FakeRequest


def params():
    return {"instance_id": "ins1", "vpc_id": "vpc1", "subnet_id": "subnet1",
            "workload": "polaris-limiter", "engine_region": "ap-guangzhou"}


def test_request_maps_optional_scope_fields():
    value = tse_sre_access_address_info.request(FakeModels, params())
    assert value.InstanceId == "ins1"
    assert value.VpcId == "vpc1"
    assert value.SubnetId == "subnet1"
    assert value.Workload == "polaris-limiter"
    assert value.EngineRegion == "ap-guangzhou"


def test_request_allows_missing_optional_fields():
    value = tse_sre_access_address_info.request(FakeModels, {"instance_id": "ins1"})
    assert value.InstanceId == "ins1"
    assert value.VpcId is None and value.Workload is None


class FakeResponse:
    RequestId = "request-1"

    def _serialize(self, allow_none=True):
        return {"IntranetAddress": "10.0.0.8:8848", "InternetAddress": "203.0.113.8:8848",
                "RequestId": self.RequestId}


def test_serialize_response_strips_request_id():
    assert tse_sre_access_address_info.serialize_response(FakeResponse()) == {
        "IntranetAddress": "10.0.0.8:8848", "InternetAddress": "203.0.113.8:8848"}


def test_serialize_response_falls_back_for_plain_objects():
    assert tse_sre_access_address_info.serialize_response(object()) == {}


class FakeClient:
    def __init__(self, response):
        self._response = response
        self.requests = []

    def DescribeSREInstanceAccessAddress(self, request):
        self.requests.append(request)
        return self._response


def _patch_sdk(monkeypatch, client):
    """Hand the module its models/client class and the client itself."""
    monkeypatch.setattr(tse_sre_access_address_info, "_load", lambda: (
        FakeModels, types.SimpleNamespace(TseClient=lambda *args: client)))
    monkeypatch.setattr(TencentCloudModule, "create_client",
                        lambda self, client_class, endpoint: client)


def test_run_module_returns_access_address(monkeypatch):
    client = FakeClient(FakeResponse())
    _patch_sdk(monkeypatch, client)
    module_args(region="ap-guangzhou", **params())

    payload = run(tse_sre_access_address_info.run_module)

    assert payload["changed"] is False
    assert payload["access_address"] == {
        "IntranetAddress": "10.0.0.8:8848", "InternetAddress": "203.0.113.8:8848"}
    assert payload["request_id"] == "request-1"
    assert client.requests[0].InstanceId == "ins1"
    assert client.requests[0].Workload == "polaris-limiter"


def test_run_module_tolerates_missing_request_id(monkeypatch):
    class BareResponse:
        def _serialize(self, allow_none=True):
            return {"IntranetAddress": "10.0.0.8:8848"}

    client = FakeClient(BareResponse())
    _patch_sdk(monkeypatch, client)
    module_args(region="ap-guangzhou", instance_id="ins1")

    payload = run(tse_sre_access_address_info.run_module)

    assert payload["access_address"] == {"IntranetAddress": "10.0.0.8:8848"}
    assert payload["request_id"] is None


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
        def DescribeSREInstanceAccessAddress(self, request):
            raise SdkError("FailedOperation", "req-err")

    _patch_sdk(monkeypatch, FailingClient())
    module_args(region="ap-guangzhou", instance_id="ins1")

    with pytest.raises(AnsibleFailJson) as failure:
        run(tse_sre_access_address_info.run_module)

    payload = failure.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert payload["error"] == "api exploded"
    assert payload["error_code"] == "FailedOperation"
    assert payload["request_id"] == "req-err"
