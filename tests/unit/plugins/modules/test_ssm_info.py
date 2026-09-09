"""Deep harness tests for the SSM info family.

test_ssm_info.py historically aggregates the Secrets Manager readers
(no single ssm_info module exists), so it drives three modules that
share tencentcloud.ssm.v20190923: ssm_secret_info (exact describe and
bounded list pagination), ssm_rotation_info (detail plus optional
history) and ssm_secret_version_info (metadata list or sensitive exact
value). Covers the request builders and run_module() end to end for
each, plus the sdk_error_payload fail contract.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import sys
import types

import pytest

from ansible_collections.susunola.tencentcloud.plugins.modules import ssm_rotation_info
from ansible_collections.susunola.tencentcloud.plugins.modules import ssm_secret_info
from ansible_collections.susunola.tencentcloud.plugins.modules import ssm_secret_version_info


def secret_params():
    return {
        "secret_name": None,
        "state_filter": 0,
        "search_name": None,
        "tag_filters": {},
        "secret_type": None,
        "product_name": None,
        "encrypt_type": None,
        "instance_id": None,
        "order": "descending",
        "page_size": 2,
        "max_pages": 5,
    }


class FakeRequest:
    pass


class FakeTagFilter:
    pass


class FakeModels:
    ListSecretsRequest = FakeRequest
    DescribeSecretRequest = FakeRequest
    GetSecretValueRequest = FakeRequest
    ListSecretVersionIdsRequest = FakeRequest
    DescribeRotationDetailRequest = FakeRequest
    DescribeRotationHistoryRequest = FakeRequest
    TagFilter = FakeTagFilter


def test_secret_list_request_maps_filters_tags_and_order():
    request = ssm_secret_info.list_request(FakeModels, {
        "order": "ascending", "state_filter": 1, "search_name": "prod",
        "secret_type": 0, "encrypt_type": 1, "tag_filters": {"env": "prod"},
        "page_size": 2,
    }, 2)
    assert (request.Offset, request.Limit, request.OrderType, request.State) == (2, 2, 1, 1)
    assert request.SearchSecretName == "prod"
    assert request.SecretType == 0 and request.EncryptType == 1
    assert request.TagFilters[0].TagKey == "env"
    assert request.TagFilters[0].TagValue == ["prod"]


def test_version_value_request_keeps_exact_identity_and_encryption():
    request = ssm_secret_version_info.value_request(FakeModels, {
        "secret_name": "prod/db", "version_id": "v2",
        "encryption_public_key": "pk", "encryption_algorithm": "RSAES_OAEP_SHA_256",
    })
    assert (request.SecretName, request.VersionId) == ("prod/db", "v2")
    assert request.EncryptionPublicKey == "pk"
    assert request.EncryptionAlgorithm == "RSAES_OAEP_SHA_256"


def test_version_list_and_rotation_requests_map_identity():
    version = ssm_secret_version_info.list_request(FakeModels, "prod/db")
    rotation = ssm_rotation_info.request(FakeModels.DescribeRotationDetailRequest, "prod/db")
    assert version.SecretName == "prod/db"
    assert rotation.SecretName == "prod/db"


class FakeItem:
    def __init__(self, marker):
        self.marker = marker

    def _serialize(self, allow_none=True):
        return {"SecretName": self.marker}


class FakeValue:
    def __init__(self, serialized, request_id):
        self._serialized = dict(serialized)
        self.RequestId = request_id

    def _serialize(self, allow_none=True):
        return dict(self._serialized)


class FakeListResponse:
    def __init__(self, attr, markers, total_count, request_id):
        setattr(self, attr, [FakeItem(marker) for marker in markers])
        self.TotalCount = total_count
        self.RequestId = request_id


class FakeClient:
    def __init__(self):
        self._responses = {}
        self.requests = {}

    def _call(self, name, request):
        self.requests.setdefault(name, []).append(request)
        return self._responses[name].pop(0)

    def DescribeSecret(self, request):
        return self._call("DescribeSecret", request)

    def ListSecrets(self, request):
        return self._call("ListSecrets", request)

    def DescribeRotationDetail(self, request):
        return self._call("DescribeRotationDetail", request)

    def DescribeRotationHistory(self, request):
        return self._call("DescribeRotationHistory", request)

    def GetSecretValue(self, request):
        return self._call("GetSecretValue", request)

    def ListSecretVersionIds(self, request):
        return self._call("ListSecretVersionIds", request)


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


def _run(monkeypatch, module, client, **params):
    _inject_sdk(monkeypatch, client)
    fake = FakeModule(params)
    fake._client = client
    monkeypatch.setattr(module, "TencentCloudModule", lambda **kwargs: fake)
    with pytest.raises(ModuleExit):
        module.run_module()
    return fake


def test_secret_list_run_paginates_until_total_count(monkeypatch):
    client = FakeClient()
    client._responses["ListSecrets"] = [
        FakeListResponse("SecretMetadatas", ["a", "b"], 3, "req-1"),
        FakeListResponse("SecretMetadatas", ["c"], 3, "req-2"),
    ]
    fake = _run(monkeypatch, ssm_secret_info, client, **secret_params())
    payload = fake.exit_payload
    assert payload["changed"] is False
    assert [item["SecretName"] for item in payload["secrets"]] == ["a", "b", "c"]
    assert payload["total_count"] == 3
    assert payload["truncated"] is False
    assert payload["request_id"] == "req-2"
    assert [request.Offset for request in client.requests["ListSecrets"]] == [0, 2]


def test_exact_secret_run_describes_single_secret(monkeypatch):
    client = FakeClient()
    client._responses["DescribeSecret"] = [FakeValue({"SecretName": "prod/db"}, "req-exact")]
    p = secret_params()
    p["secret_name"] = "prod/db"
    fake = _run(monkeypatch, ssm_secret_info, client, **p)
    payload = fake.exit_payload
    assert payload["secret"] == {"SecretName": "prod/db"}
    assert payload["request_id"] == "req-exact"


def test_rotation_run_appends_history_when_requested(monkeypatch):
    client = FakeClient()
    client._responses["DescribeRotationDetail"] = [
        FakeValue({"RotationEnabled": True, "RequestId": "req-det"}, "req-det"),
    ]
    client._responses["DescribeRotationHistory"] = [
        FakeValue({"RotationStatus": "Rotating", "RequestId": "req-hist"}, "req-hist"),
    ]
    fake = _run(monkeypatch, ssm_rotation_info, client, secret_name="prod/db", include_history=True)
    payload = fake.exit_payload
    assert payload["rotation"] == {"RotationEnabled": True}
    assert payload["history"] == {"RotationStatus": "Rotating"}
    assert payload["request_id"] == "req-hist"


def test_version_value_run_returns_sensitive_exact_value(monkeypatch):
    client = FakeClient()
    client._responses["GetSecretValue"] = [
        FakeValue({"SecretString": "top", "VersionId": "v2", "RequestId": "req-val"}, "req-val"),
    ]
    fake = _run(monkeypatch, ssm_secret_version_info, client,
                secret_name="prod/db", version_id="v2", include_secret_value=True,
                encryption_public_key=None, encryption_algorithm=None)
    payload = fake.exit_payload
    assert payload["secret_value"] == {"SecretString": "top", "VersionId": "v2"}
    assert payload["request_id"] == "req-val"


def test_version_list_run_filters_on_requested_version_id(monkeypatch):
    class VersionItem(FakeItem):
        def _serialize(self, allow_none=True):
            return {"VersionId": self.marker}

    client = FakeClient()
    client._responses["ListSecretVersionIds"] = [types.SimpleNamespace(
        Versions=[VersionItem("v1"), VersionItem("v2"), VersionItem("v3")],
        RequestId="req-vers")]
    fake = _run(monkeypatch, ssm_secret_version_info, client,
                secret_name="prod/db", version_id="v2", include_secret_value=False,
                encryption_public_key=None, encryption_algorithm=None)
    payload = fake.exit_payload
    assert payload["versions"] == [{"VersionId": "v2"}]
    assert payload["request_id"] == "req-vers"


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
        def ListSecrets(self, request):
            raise SdkError("FailedOperation", "req-err")

    failing = FailingClient()
    _inject_sdk(monkeypatch, failing)
    fake = FakeModule(secret_params())
    fake._client = failing
    monkeypatch.setattr(ssm_secret_info, "TencentCloudModule", lambda **kwargs: fake)
    with pytest.raises(ModuleFail) as excinfo:
        ssm_secret_info.run_module()
    payload = excinfo.value.payload
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert payload["error_code"] == "FailedOperation"
    assert payload["request_id"] == "req-err"
