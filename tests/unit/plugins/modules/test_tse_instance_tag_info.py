"""Deep harness tests for tse_instance_tag_info.

Covers the single-call tag request builder (instance scoping) and
run_module() end to end: happy path tag list, instance_id fallback when
the API omits it, empty results and the sdk_error_payload fail
contract. This module performs one un-paginated DescribeInstanceTagInfos
call, so no paginator is exercised.

The module subclasses ``TencentCloudModule``, so the migration patches the
base class's ``create_client`` and the module's own ``_load`` (which is where
it imports its models and client class), and lets ``module_args()`` supply the
credentials the base class validates. The fake tag serialises ``TagKey`` /
``TagValue``, the two fields of the SDK's ``InstanceTagInfo`` model.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import types

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import tse_instance_tag_info
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    module_args,
    run,
)


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


def _patch_sdk(monkeypatch, client):
    """Hand the module its models/client class and the client itself."""
    monkeypatch.setattr(tse_instance_tag_info, "_load", lambda: (
        FakeModels, types.SimpleNamespace(TseClient=lambda *args: client)))
    monkeypatch.setattr(TencentCloudModule, "create_client",
                        lambda self, client_class, endpoint: client)


def test_run_module_returns_tags(monkeypatch):
    items = [FakeItem("env", "prod"), FakeItem("team", "payments")]
    client = FakeClient(FakeResponse(items, "ins-1", "req-tags"))
    _patch_sdk(monkeypatch, client)
    module_args(region="ap-guangzhou", instance_id="ins-1")

    payload = run(tse_instance_tag_info.run_module)

    assert payload["changed"] is False
    assert payload["instance_id"] == "ins-1"
    assert payload["tags"] == [item._serialize() for item in items]
    assert payload["request_id"] == "req-tags"
    assert client.requests[0].InstanceId == "ins-1"


def test_run_module_falls_back_to_requested_instance_id(monkeypatch):
    client = FakeClient(FakeResponse([], None, "req-fallback"))
    _patch_sdk(monkeypatch, client)
    module_args(region="ap-guangzhou", instance_id="ins-1")

    payload = run(tse_instance_tag_info.run_module)

    assert payload["instance_id"] == "ins-1"
    assert payload["tags"] == []


def test_run_module_empty_result_reports_no_tags(monkeypatch):
    client = FakeClient(FakeResponse([], "ins-1", "req-empty"))
    _patch_sdk(monkeypatch, client)
    module_args(region="ap-guangzhou", instance_id="ins-1")

    payload = run(tse_instance_tag_info.run_module)

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

    _patch_sdk(monkeypatch, FailingClient())
    module_args(region="ap-guangzhou", instance_id="ins-1")

    with pytest.raises(AnsibleFailJson) as failure:
        run(tse_instance_tag_info.run_module)

    payload = failure.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert payload["error"] == "api exploded"
    assert payload["error_code"] == "FailedOperation"
    assert payload["request_id"] == "req-err"
