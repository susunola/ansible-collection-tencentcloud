"""Deep harness tests for tse_config_file_catalog_info.

Covers the config-file catalog request builder (namespace/group/name/id
filters plus ConfigFileTag payloads hydrated from user dicts and offset
pagination), the fetch_all helper loop, and run_module() end to end:
happy-path pagination until TotalCount, empty results, page_size
validation and the sdk_error_payload fail contract.

The module subclasses ``TencentCloudModule`` and loads its models and
client in its own ``_load()``, so the migration patches that helper and
the base class's ``create_client``, and lets ``module_args()`` supply the
credentials the base class validates. The fake item serialises ``Name``, a
real ``ConfigFile`` field (the API never returns ``FileName`` there),
because that payload is what ``add_return_samples.py`` captures as the
module's documented sample.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import json
import types

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import tse_config_file_catalog_info
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    module_args,
    run,
)


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


def params(**overrides):
    """Module arguments minus the optional name/config_file_id, which are omitted."""
    options = {
        "instance_id": "ins-1",
        "namespace": "prod",
        "group": "app",
        "tags": [{"Key": "team", "Value": "payments"}],
        "page_size": 2,
    }
    options.update(overrides)
    return options


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
    def __init__(self, name):
        self.name = name

    def _serialize(self, allow_none=True):
        return {"Name": self.name}


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


def _patch_sdk(monkeypatch, client):
    """Hand the module its models/client class and the client itself."""
    monkeypatch.setattr(tse_config_file_catalog_info, "_load", lambda: (
        FakeModels, types.SimpleNamespace(TseClient=lambda *args: client)))
    monkeypatch.setattr(TencentCloudModule, "create_client",
                        lambda self, client_class, endpoint: client)


def _run(monkeypatch, client, **module_params):
    _patch_sdk(monkeypatch, client)
    module_args(**module_params)
    return run(tse_config_file_catalog_info.run_module)


def _expect_fail(monkeypatch, module_params):
    _patch_sdk(monkeypatch, FakeClient([]))
    module_args(**module_params)
    with pytest.raises(AnsibleFailJson) as failure:
        run(tse_config_file_catalog_info.run_module)
    return failure.value.args[0]


def test_fetch_all_paginates_catalog():
    client = FakeClient([
        FakeResponse([FakeItem("a"), FakeItem("b")], 3, "request-0"),
        FakeResponse([FakeItem("c")], 3, "request-2"),
    ])
    # fetch_all only needs the module's real sdk_call (retry plus the
    # tc_api_calls audit trail), so it runs against the real base class.
    module_args()
    module = TencentCloudModule(argument_spec={})
    values, total, request_id = tse_config_file_catalog_info.fetch_all(module, client, FakeModels, params())
    assert values == [{"Name": "a"}, {"Name": "b"}, {"Name": "c"}]
    assert (total, request_id) == (3, "request-2")
    assert [request.Offset for request in client.requests] == [0, 2]


def test_run_module_paginates_config_files_until_total_count(monkeypatch):
    client = FakeClient([
        FakeResponse([FakeItem("a"), FakeItem("b")], 3, "req-1"),
        FakeResponse([FakeItem("c")], 3, "req-2"),
    ])
    payload = _run(monkeypatch, client, **params())
    assert payload["changed"] is False
    assert [item["Name"] for item in payload["config_files"]] == ["a", "b", "c"]
    assert payload["total_count"] == 3
    assert payload["request_id"] == "req-2"
    assert [request.Offset for request in client.requests] == [0, 2]


def test_run_module_empty_page_stops_with_zero_total(monkeypatch):
    client = FakeClient([FakeResponse([], 0, "req-empty")])
    payload = _run(monkeypatch, client, **params())
    assert payload["config_files"] == []
    assert payload["total_count"] == 0
    assert payload["request_id"] == "req-empty"


@pytest.mark.parametrize("page_size,message", [
    (0, "page_size must be between 1 and 100"),
    (101, "page_size must be between 1 and 100"),
])
def test_run_module_validates_page_size_bounds(monkeypatch, page_size, message):
    payload = _expect_fail(monkeypatch, params(page_size=page_size))
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

    _patch_sdk(monkeypatch, FailingClient())
    module_args(**params())

    with pytest.raises(AnsibleFailJson) as failure:
        run(tse_config_file_catalog_info.run_module)

    payload = failure.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert payload["error"] == "api exploded"
    assert payload["error_code"] == "FailedOperation"
    assert payload["request_id"] == "req-err"
