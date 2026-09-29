"""Deep harness tests for tse_config_file_template_info.

Covers the single-call template request builder (instance scoping) and
run_module() end to end: happy path template list, total_count fallback
when the API omits TotalCount, empty results and the
sdk_error_payload fail contract. This module performs one un-paginated
DescribeAllConfigFileTemplates call, so no paginator is exercised.

The module subclasses ``TencentCloudModule`` and loads its models and
client in its own ``_load()``, so the migration patches that helper and
the base class's ``create_client``, and lets ``module_args()`` supply the
credentials the base class validates. The fake item serialises ``Name``, a
real ``ConfigFileTemplate`` field (the API never returns ``TemplateName``),
because that payload is what ``add_return_samples.py`` captures as the
module's documented sample.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import types

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import tse_config_file_template_info
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    module_args,
    run,
)


class FakeRequest:
    pass


class FakeModels:
    DescribeAllConfigFileTemplatesRequest = FakeRequest


def test_request_maps_instance_id():
    value = tse_config_file_template_info.request(FakeModels, "ins-1")
    assert value.InstanceId == "ins-1"


class FakeItem:
    def __init__(self, name):
        self.name = name

    def _serialize(self, allow_none=True):
        return {"Name": self.name}


class FakeResponse:
    def __init__(self, items, total_count, request_id):
        self.ConfigFileTemplates = items
        self.TotalCount = total_count
        self.RequestId = request_id


class FakeClient:
    def __init__(self, response):
        self._response = response
        self.requests = []

    def DescribeAllConfigFileTemplates(self, request):
        self.requests.append(request)
        return self._response


def _patch_sdk(monkeypatch, client):
    """Hand the module its models/client class and the client itself."""
    monkeypatch.setattr(tse_config_file_template_info, "_load", lambda: (
        FakeModels, types.SimpleNamespace(TseClient=lambda *args: client)))
    monkeypatch.setattr(TencentCloudModule, "create_client",
                        lambda self, client_class, endpoint: client)


def test_run_module_returns_templates(monkeypatch):
    client = FakeClient(FakeResponse([FakeItem("mysql"), FakeItem("redis")], 2, "req-tpl"))
    _patch_sdk(monkeypatch, client)
    module_args(instance_id="ins-1")

    payload = run(tse_config_file_template_info.run_module)

    assert payload["changed"] is False
    assert payload["templates"] == [{"Name": "mysql"}, {"Name": "redis"}]
    assert payload["total_count"] == 2
    assert payload["request_id"] == "req-tpl"
    assert client.requests[0].InstanceId == "ins-1"


def test_run_module_falls_back_total_count_to_item_count(monkeypatch):
    client = FakeClient(FakeResponse([FakeItem("mysql")], None, "req-fallback"))
    _patch_sdk(monkeypatch, client)
    module_args(instance_id="ins-1")

    payload = run(tse_config_file_template_info.run_module)

    assert [item["Name"] for item in payload["templates"]] == ["mysql"]
    assert payload["total_count"] == 1


def test_run_module_empty_result_reports_zero(monkeypatch):
    client = FakeClient(FakeResponse([], 0, "req-empty"))
    _patch_sdk(monkeypatch, client)
    module_args(instance_id="ins-1")

    payload = run(tse_config_file_template_info.run_module)

    assert payload["templates"] == []
    assert payload["total_count"] == 0


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
        def DescribeAllConfigFileTemplates(self, request):
            raise SdkError("FailedOperation", "req-err")

    _patch_sdk(monkeypatch, FailingClient())
    module_args(instance_id="ins-1")

    with pytest.raises(AnsibleFailJson) as failure:
        run(tse_config_file_template_info.run_module)

    payload = failure.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert payload["error"] == "api exploded"
    assert payload["error_code"] == "FailedOperation"
    assert payload["request_id"] == "req-err"
