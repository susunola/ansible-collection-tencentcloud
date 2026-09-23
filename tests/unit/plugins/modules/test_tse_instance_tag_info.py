"""Deep harness tests for tse_instance_tag_info.

Covers the single-call tag request builder (instance scoping) and
run_module() end to end: happy path tag list, instance_id fallback when
the API omits it, empty results and the sdk_error_payload fail
contract. This module performs one un-paginated DescribeInstanceTagInfos
call, so no paginator is exercised.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import sys
import types

import pytest

from ansible_collections.susunola.tencentcloud.plugins.modules import tse_instance_tag_info


class FakeRequest:
    pass


class FakeModels:
    DescribeInstanceTagInfosRequest = FakeRequest


def test_request_maps_instance_id():
    value = tse_instance_tag_info.request(FakeModels, "ins-1")
    assert value.InstanceId == "ins-1"


class FakeItem:
    def __init__(self, key, value):
        self.key = key
        self.value = value

    def _serialize(self, allow_none=True):
        return {"TagKey": self.key, "TagValue": self.value}


class FakeResponse:
    def __init__(self, items, instance_id, request_id):
        self.TagInfos = items
        self.InstanceId = instance_id
        self.RequestId = request_id


class FakeClient:
    def __init__(self, response):
        self._response = response
        self.requests = []

    def DescribeInstanceTagInfos(self, request):
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
    monkeypatch.setattr(tse_instance_tag_info, "TencentCloudModule", lambda **kwargs: fake)
    with pytest.raises(ModuleExit):
        tse_instance_tag_info.run_module()
    return fake


def test_run_module_returns_tags(monkeypatch):
    items = [FakeItem("env", "prod"), FakeItem("team", "payments")]
    client = FakeClient(FakeResponse(items, "ins-1", "req-tags"))
    fake = _run(monkeypatch, client, instance_id="ins-1")
    payload = fake.exit_payload
    assert payload["changed"] is False
    assert payload["instance_id"] == "ins-1"
    assert payload["tags"] == [item._serialize() for item in items]
    assert payload["request_id"] == "req-tags"
    assert client.requests[0].InstanceId == "ins-1"


def test_run_module_falls_back_to_requested_instance_id(monkeypatch):
    client = FakeClient(FakeResponse([], None, "req-fallback"))
    fake = _run(monkeypatch, client, instance_id="ins-1")
    payload = fake.exit_payload
    assert payload["instance_id"] == "ins-1"
    assert payload["tags"] == []


def test_run_module_empty_result_reports_no_tags(monkeypatch):
    client = FakeClient(FakeResponse([], "ins-1", "req-empty"))
    fake = _run(monkeypatch, client, instance_id="ins-1")
    payload = fake.exit_payload
    assert payload["tags"] == []
    assert payload["instance_id"] == "ins-1"


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
        def DescribeInstanceTagInfos(self, request):
            raise SdkError("FailedOperation", "req-err")

    failing = FailingClient()
    _inject_sdk(monkeypatch, failing)
    fake = FakeModule({"instance_id": "ins-1"})
    fake._client = failing
    monkeypatch.setattr(tse_instance_tag_info, "TencentCloudModule", lambda **kwargs: fake)
    with pytest.raises(ModuleFail) as excinfo:
        tse_instance_tag_info.run_module()
    payload = excinfo.value.payload
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert payload["error"] == "api exploded"
    assert payload["error_code"] == "FailedOperation"
    assert payload["request_id"] == "req-err"
