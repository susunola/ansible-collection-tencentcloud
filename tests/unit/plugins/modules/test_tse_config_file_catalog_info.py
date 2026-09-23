"""Deep harness tests for tse_config_file_catalog_info.

Covers the config-file catalog request builder (namespace/group/name/id
filters plus ConfigFileTag payloads hydrated from user dicts and offset
pagination), the fetch_all helper loop, and run_module() end to end:
happy-path pagination until TotalCount, empty results, page_size
validation and the sdk_error_payload fail contract.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import json
import sys
import types

import pytest

from ansible_collections.susunola.tencentcloud.plugins.modules import tse_config_file_catalog_info


class FakeRequest:
    pass


class FakeTag:
    def __init__(self):
        self.json = None

    def from_json_string(self, value):
        self.json = value


class FakeModels:
    DescribeConfigFilesRequest = FakeRequest
    ConfigFileTag = FakeTag


def params():
    return {
        "instance_id": "ins-1",
        "namespace": "prod",
        "group": "app",
        "name": None,
        "config_file_id": None,
        "tags": [{"Key": "team", "Value": "payments"}],
        "page_size": 2,
    }


def test_catalog_request_maps_filters_and_pagination():
    value = tse_config_file_catalog_info.request(FakeModels, params(), 4)
    assert value.InstanceId == "ins-1"
    assert value.Namespace == "prod" and value.Group == "app"
    assert value.Offset == 4 and value.Limit == 2
    assert json.loads(value.Tags[0].json) == {"Key": "team", "Value": "payments"}


def test_catalog_request_maps_optional_ids():
    p = params()
    p["name"] = "orders.yaml"
    p["config_file_id"] = "file-1"
    p["tags"] = None
    value = tse_config_file_catalog_info.request(FakeModels, p, 0)
    assert value.Name == "orders.yaml" and value.Id == "file-1"
    assert not hasattr(value, "Tags")


class FakeItem:
    def __init__(self, marker):
        self.marker = marker

    def _serialize(self, allow_none=True):
        return {"FileName": self.marker}


class FakeResponse:
    def __init__(self, items, total_count, request_id):
        self.ConfigFiles = items
        self.TotalCount = total_count
        self.RequestId = request_id


class FakeClient:
    def __init__(self, pages=None):
        self._pages = list(pages or [])
        self.requests = []

    def DescribeConfigFiles(self, request):
        self.requests.append(request)
        return self._pages.pop(0)


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
    monkeypatch.setattr(tse_config_file_catalog_info, "TencentCloudModule", lambda **kwargs: fake)
    with pytest.raises(ModuleExit):
        tse_config_file_catalog_info.run_module()
    return fake


def _expect_fail(monkeypatch, fake):
    monkeypatch.setattr(tse_config_file_catalog_info, "TencentCloudModule", lambda **kwargs: fake)
    with pytest.raises(ModuleFail) as excinfo:
        tse_config_file_catalog_info.run_module()
    return excinfo.value.payload


def test_fetch_all_paginates_catalog():
    client = FakeClient([
        FakeResponse([FakeItem("a"), FakeItem("b")], 3, "request-0"),
        FakeResponse([FakeItem("c")], 3, "request-2"),
    ])
    fake = FakeModule(params())
    fake._client = client
    values, total, request_id = tse_config_file_catalog_info.fetch_all(fake, client, FakeModels, params())
    assert values == [{"FileName": "a"}, {"FileName": "b"}, {"FileName": "c"}]
    assert (total, request_id) == (3, "request-2")
    assert [request.Offset for request in client.requests] == [0, 2]


def test_run_module_paginates_config_files_until_total_count(monkeypatch):
    client = FakeClient([
        FakeResponse([FakeItem("a"), FakeItem("b")], 3, "req-1"),
        FakeResponse([FakeItem("c")], 3, "req-2"),
    ])
    fake = _run(monkeypatch, client, **params())
    payload = fake.exit_payload
    assert payload["changed"] is False
    assert [item["FileName"] for item in payload["config_files"]] == ["a", "b", "c"]
    assert payload["total_count"] == 3
    assert payload["request_id"] == "req-2"
    assert [request.Offset for request in client.requests] == [0, 2]


def test_run_module_empty_page_stops_with_zero_total(monkeypatch):
    client = FakeClient([FakeResponse([], 0, "req-empty")])
    fake = _run(monkeypatch, client, **params())
    payload = fake.exit_payload
    assert payload["config_files"] == []
    assert payload["total_count"] == 0
    assert payload["request_id"] == "req-empty"


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
        def DescribeConfigFiles(self, request):
            raise SdkError("FailedOperation", "req-err")

    failing = FailingClient()
    _inject_sdk(monkeypatch, failing)
    fake = FakeModule(params())
    fake._client = failing
    monkeypatch.setattr(tse_config_file_catalog_info, "TencentCloudModule", lambda **kwargs: fake)
    with pytest.raises(ModuleFail) as excinfo:
        tse_config_file_catalog_info.run_module()
    payload = excinfo.value.payload
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert payload["error"] == "api exploded"
    assert payload["error_code"] == "FailedOperation"
    assert payload["request_id"] == "req-err"
