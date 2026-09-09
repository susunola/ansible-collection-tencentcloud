"""Deep harness tests for tione_training_model_version_info.

Covers the exact version detail request (stable version_id), the
parent-scoped list request (TrainingModelId plus stably sorted filters
with scalar-to-list coercion), argument validation, and run_module()
end to end: the single-call detail branch, the single-call list branch,
empty results and the sdk_error_payload fail contract.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import sys
import types

import pytest

from ansible_collections.susunola.tencentcloud.plugins.modules import tione_training_model_version_info


class FakeFilter:
    pass


class FakeRequest:
    pass


class FakeModels:
    DescribeTrainingModelVersionRequest = FakeRequest
    DescribeTrainingModelVersionsRequest = FakeRequest
    Filter = FakeFilter


def params():
    return {"model_id": None, "version_id": None, "filters": {}}


def test_detail_request_uses_stable_version_id():
    request = tione_training_model_version_info.detail_request(FakeModels, "mv-1")
    assert request.TrainingModelVersionId == "mv-1"


def test_list_request_is_parent_scoped_stably_filtered_and_coerces_scalars():
    request = tione_training_model_version_info.list_request(
        FakeModels, "model-1", {"ModelVersionType": "NORMAL", "AlgorithmFramework": ["PYTORCH"], "Status": ["RUNNING"]})
    assert request.TrainingModelId == "model-1"
    assert [(item.Name, item.Values) for item in request.Filters] == [
        ("AlgorithmFramework", ["PYTORCH"]), ("ModelVersionType", ["NORMAL"]), ("Status", ["RUNNING"])]


def test_list_request_leaves_filters_unset_when_empty():
    request = tione_training_model_version_info.list_request(FakeModels, "model-1", {})
    assert request.TrainingModelId == "model-1"
    assert not hasattr(request, "Filters")


class FakeItem:
    def __init__(self, marker):
        self.marker = marker

    def _serialize(self, allow_none=True):
        return {"Marker": self.marker}


class FakeVersionResponse:
    def __init__(self, item, request_id):
        self.TrainingModelVersion = item
        self.RequestId = request_id


class FakeVersionsResponse:
    def __init__(self, items, request_id):
        self.TrainingModelVersions = items
        self.RequestId = request_id


class FakeClient:
    def __init__(self):
        self.version_request = None
        self.versions_request = None
        self.version_response = None
        self.versions_response = None

    def DescribeTrainingModelVersion(self, request):
        self.version_request = request
        return self.version_response

    def DescribeTrainingModelVersions(self, request):
        self.versions_request = request
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
    service = types.ModuleType("tencentcloud.tione.v20211111")
    service.models = FakeModels
    service.tione_client = types.SimpleNamespace(TioneClient=lambda *args: object())
    monkeypatch.setitem(sys.modules, "tencentcloud", types.ModuleType("tencentcloud"))
    monkeypatch.setitem(sys.modules, "tencentcloud.tione",
                        types.ModuleType("tencentcloud.tione"))
    monkeypatch.setitem(sys.modules, "tencentcloud.tione.v20211111", service)


def _run(monkeypatch, client, **params):
    _inject_sdk(monkeypatch, client)
    fake = FakeModule(params)
    fake._client = client
    monkeypatch.setattr(tione_training_model_version_info, "TencentCloudModule", lambda **kwargs: fake)
    with pytest.raises(ModuleExit):
        tione_training_model_version_info.run_module()
    return fake


def _expect_fail(monkeypatch, fake):
    monkeypatch.setattr(tione_training_model_version_info, "TencentCloudModule", lambda **kwargs: fake)
    with pytest.raises(ModuleFail) as excinfo:
        tione_training_model_version_info.run_module()
    return excinfo.value.payload


@pytest.mark.parametrize("detail,expected", [(FakeItem("mv-1"), {"Marker": "mv-1"}), (None, None)])
def test_run_module_describes_exact_version(monkeypatch, detail, expected):
    client = FakeClient()
    client.version_response = FakeVersionResponse(detail, "req-detail")
    fake = _run(monkeypatch, client, **dict(params(), version_id="mv-1"))
    payload = fake.exit_payload
    assert payload["changed"] is False
    assert payload["model_version"] == expected
    assert payload["request_id"] == "req-detail"
    assert client.version_request.TrainingModelVersionId == "mv-1"
    assert client.versions_request is None


@pytest.mark.parametrize("items,expected_total", [([FakeItem("v1"), FakeItem("v2")], 2), ([], 0)])
def test_run_module_lists_versions_within_parent_model(monkeypatch, items, expected_total):
    client = FakeClient()
    client.versions_response = FakeVersionsResponse(items, "req-list")
    p = params()
    p["model_id"] = "model-1"
    p["filters"] = {"ModelVersionType": "NORMAL"}
    fake = _run(monkeypatch, client, **p)
    payload = fake.exit_payload
    assert payload["changed"] is False
    assert payload["model_versions"] == [item._serialize() for item in items]
    assert payload["total_count"] == expected_total
    assert payload["request_id"] == "req-list"
    assert client.versions_request.TrainingModelId == "model-1"
    assert client.version_request is None


def test_run_module_requires_model_id_in_list_mode(monkeypatch):
    payload = _expect_fail(monkeypatch, FakeModule(params()))
    assert payload["msg"] == "model_id is required in list mode"


@pytest.mark.parametrize("filters,message", [
    ({"f%02d" % index: ["v"] for index in range(11)}, "filters accepts at most ten filter names"),
    ({"ModelVersionType": ["v%d" % index for index in range(101)]}, "each filter accepts at most 100 values"),
])
def test_run_module_rejects_oversized_filters(monkeypatch, filters, message):
    p = params()
    p["model_id"] = "model-1"
    p["filters"] = filters
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
        def DescribeTrainingModelVersions(self, request):
            raise SdkError("FailedOperation", "req-err")

    failing = FailingClient()
    _inject_sdk(monkeypatch, failing)
    p = params()
    p["model_id"] = "model-1"
    fake = FakeModule(p)
    fake._client = failing
    monkeypatch.setattr(tione_training_model_version_info, "TencentCloudModule", lambda **kwargs: fake)
    with pytest.raises(ModuleFail) as excinfo:
        tione_training_model_version_info.run_module()
    payload = excinfo.value.payload
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert payload["error"] == "api exploded"
    assert payload["error_code"] == "FailedOperation"
    assert payload["request_id"] == "req-err"
