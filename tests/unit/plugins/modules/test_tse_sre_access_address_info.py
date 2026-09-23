"""Deep harness tests for tse_sre_access_address_info.

Covers the single-call access-address request builder (optional VPC,
subnet, workload and engine-region scoping), the response serialiser
that strips RequestId, and run_module() end to end: happy path access
address payload, missing RequestId handling and the
sdk_error_payload fail contract. This module performs one un-paginated
DescribeSREInstanceAccessAddress call, so no paginator is exercised.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import sys
import types

import pytest

from ansible_collections.susunola.tencentcloud.plugins.modules import tse_sre_access_address_info


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
    monkeypatch.setattr(tse_sre_access_address_info, "TencentCloudModule", lambda **kwargs: fake)
    with pytest.raises(ModuleExit):
        tse_sre_access_address_info.run_module()
    return fake


def test_run_module_returns_access_address(monkeypatch):
    client = FakeClient(FakeResponse())
    fake = _run(monkeypatch, client, **params())
    payload = fake.exit_payload
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
    fake = _run(monkeypatch, client, instance_id="ins1")
    payload = fake.exit_payload
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

    failing = FailingClient()
    _inject_sdk(monkeypatch, failing)
    fake = FakeModule({"instance_id": "ins1"})
    fake._client = failing
    monkeypatch.setattr(tse_sre_access_address_info, "TencentCloudModule", lambda **kwargs: fake)
    with pytest.raises(ModuleFail) as excinfo:
        tse_sre_access_address_info.run_module()
    payload = excinfo.value.payload
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert payload["error"] == "api exploded"
    assert payload["error_code"] == "FailedOperation"
    assert payload["request_id"] == "req-err"
