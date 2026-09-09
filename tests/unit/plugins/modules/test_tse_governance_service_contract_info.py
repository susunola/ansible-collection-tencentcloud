"""Deep harness tests for tse_governance_service_contract_info.

Covers the paginated contract request builder (service identity plus
name/version/protocol/brief filters), the single-call version request
builder, the fetch_contracts helper loop, and run_module() end to end:
happy-path contract pagination followed by the version lookup, empty
results, page_size validation and the sdk_error_payload fail contract.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import sys
import types

import pytest

from ansible_collections.susunola.tencentcloud.plugins.modules import tse_governance_service_contract_info


class FakeRequest:
    pass


class FakeModels:
    DescribeGovernanceServiceContractsRequest = FakeRequest
    DescribeGovernanceServiceContractVersionsRequest = FakeRequest


def params():
    return {
        "instance_id": "ins-1",
        "namespace": "prod",
        "service": "orders",
        "name": "openapi",
        "contract_version": "v2",
        "protocol": "http",
        "brief": False,
        "page_size": 2,
    }


def test_contract_request_maps_service_and_filters():
    contract = tse_governance_service_contract_info.contract_request(FakeModels, params(), 4)
    assert contract.InstanceId == "ins-1"
    assert contract.Namespace == "prod" and contract.Service == "orders"
    assert contract.Name == "openapi" and contract.ContractVersion == "v2"
    assert contract.Protocol == "http" and contract.Brief is False
    assert contract.Offset == 4 and contract.Limit == 2


def test_version_request_maps_service_identity():
    version = tse_governance_service_contract_info.version_request(FakeModels, params())
    assert version.InstanceId == "ins-1"
    assert version.Namespace == "prod" and version.Service == "orders"


class FakeItem:
    def __init__(self, marker):
        self.marker = marker

    def _serialize(self, allow_none=True):
        return {"Name": self.marker}


class FakeContractsResponse:
    def __init__(self, items, total_count, request_id):
        self.ServiceContracts = items
        self.TotalCount = total_count
        self.RequestId = request_id


class FakeVersionsResponse:
    def __init__(self, items, request_id):
        self.GovernanceServiceContractVersions = items
        self.RequestId = request_id


class FakeClient:
    def __init__(self, pages=None):
        self._pages = list(pages or [])
        self.contract_requests = []
        self.version_request = None
        self.versions_response = None

    def DescribeGovernanceServiceContracts(self, request):
        self.contract_requests.append(request)
        return self._pages.pop(0)

    def DescribeGovernanceServiceContractVersions(self, request):
        self.version_request = request
        return self.versions_response


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
    monkeypatch.setattr(tse_governance_service_contract_info, "TencentCloudModule", lambda **kwargs: fake)
    with pytest.raises(ModuleExit):
        tse_governance_service_contract_info.run_module()
    return fake


def _expect_fail(monkeypatch, fake):
    monkeypatch.setattr(tse_governance_service_contract_info, "TencentCloudModule", lambda **kwargs: fake)
    with pytest.raises(ModuleFail) as excinfo:
        tse_governance_service_contract_info.run_module()
    return excinfo.value.payload


def test_fetch_contracts_paginates():
    client = FakeClient([
        FakeContractsResponse([FakeItem("c1"), FakeItem("c2")], 3, "request-0"),
        FakeContractsResponse([FakeItem("c3")], 3, "request-2"),
    ])
    fake = FakeModule(params())
    fake._client = client
    contracts, total, request_id = tse_governance_service_contract_info.fetch_contracts(
        fake, client, FakeModels, params())
    assert contracts == [{"Name": "c1"}, {"Name": "c2"}, {"Name": "c3"}]
    assert (total, request_id) == (3, "request-2")
    assert [request.Offset for request in client.contract_requests] == [0, 2]


def test_run_module_paginates_contracts_and_returns_versions(monkeypatch):
    client = FakeClient([
        FakeContractsResponse([FakeItem("c1"), FakeItem("c2")], 3, "req-1"),
        FakeContractsResponse([FakeItem("c3")], 3, "req-2"),
    ])
    client.versions_response = FakeVersionsResponse([FakeItem("v1"), FakeItem("v2")], "req-versions")
    fake = _run(monkeypatch, client, **params())
    payload = fake.exit_payload
    assert payload["changed"] is False
    assert [item["Name"] for item in payload["contracts"]] == ["c1", "c2", "c3"]
    assert [item["Name"] for item in payload["versions"]] == ["v1", "v2"]
    assert payload["total_count"] == 3
    assert payload["request_ids"] == {"contracts": "req-2", "versions": "req-versions"}
    assert [request.Offset for request in client.contract_requests] == [0, 2]
    assert client.version_request.Namespace == "prod"


def test_run_module_empty_page_stops_with_zero_total(monkeypatch):
    client = FakeClient([FakeContractsResponse([], 0, "req-empty")])
    client.versions_response = FakeVersionsResponse([], "req-versions-empty")
    fake = _run(monkeypatch, client, **params())
    payload = fake.exit_payload
    assert payload["contracts"] == [] and payload["versions"] == []
    assert payload["total_count"] == 0


@pytest.mark.parametrize("page_size,message", [
    (0, "page_size must be between 1 and 100"),
    (101, "page_size must be between 1 and 100"),
])
def test_run_module_validates_page_size_bounds(monkeypatch, page_size, message):
    p = params()
    p["page_size"] = page_size
    payload = _expect_fail(monkeypatch, FakeModule(p))
    assert payload["msg"] == message


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
        def DescribeGovernanceServiceContracts(self, request):
            raise SdkError("FailedOperation", "req-err")

    failing = FailingClient()
    _inject_sdk(monkeypatch, failing)
    fake = FakeModule(params())
    fake._client = failing
    monkeypatch.setattr(tse_governance_service_contract_info, "TencentCloudModule", lambda **kwargs: fake)
    with pytest.raises(ModuleFail) as excinfo:
        tse_governance_service_contract_info.run_module()
    payload = excinfo.value.payload
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert payload["error"] == "api exploded"
    assert payload["error_code"] == "FailedOperation"
    assert payload["request_id"] == "req-err"
