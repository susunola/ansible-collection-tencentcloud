"""Deep harness tests for key_pair_info.

Covers build_request (pagination, key ids, sorted filters, scalar value
wrapping) and run_module() end to end through the shared harness: multi-page
collection driven by TotalCount, an empty result set, and the sdk_call fail
contract (msg/error/error_code/request_id).

The module builds its own SDK client, so the tests still inject a fake
``tencentcloud.cvm.v20170312`` service and patch the two factories. They no
longer replace ``AnsibleModule`` with a private double, which is what makes
the payload observable: the fixture returns ``KeyId`` rather than a generic
``Marker``, because that payload is now what ``add_return_samples.py``
captures as the module's documented sample.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import sys
import types

import pytest

from ansible_collections.susunola.tencentcloud.plugins.modules import key_pair_info
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    module_args,
    run,
)


class FakeFilter:
    pass


class FakeRequest:
    pass


class FakeModels:
    Filter = FakeFilter
    DescribeKeyPairsRequest = FakeRequest


def test_build_request_maps_ids_and_integer_pagination():
    request = key_pair_info.build_request(FakeModels, ["skey-123"], {}, 20, 100)
    assert request.KeyIds == ["skey-123"]
    assert request.Offset == 20
    assert request.Limit == 100
    assert not hasattr(request, "Filters")


def test_build_request_sorts_filters():
    request = key_pair_info.build_request(FakeModels, [], {"key-name": ["deploy-key"], "project-id": [0]}, 0, 100)
    assert [(item.Name, item.Values) for item in request.Filters] == [
        ("key-name", ["deploy-key"]), ("project-id", [0]),
    ]


def test_build_request_wraps_scalar_filter_values():
    request = key_pair_info.build_request(FakeModels, [], {"key-name": "deploy-key"}, 0, 100)
    assert request.Filters[0].Values == ["deploy-key"]


class FakeItem:
    def __init__(self, marker):
        self.marker = marker

    def _serialize(self, allow_none=True):
        return {"KeyId": self.marker}


class FakeResponse:
    def __init__(self, items, total_count):
        self.KeyPairSet = items
        self.TotalCount = total_count
        self.RequestId = "req-page"


class FakeClient:
    def __init__(self, pages):
        self._pages = list(pages)
        self.requests = []

    def DescribeKeyPairs(self, request):
        self.requests.append(request)
        return self._pages.pop(0)


class SdkError(Exception):
    """The SDK exception shape the shared read wrapper catches.

    ``read_sdk_call`` resolves ``TencentCloudSDKException`` through its own
    module global, so ``_point_wrapper_at_sdk_error`` binds that name here and
    the fake client can raise something the real wrapper classifies.
    """

    def __init__(self, code, message, request_id):
        super(SdkError, self).__init__(message)
        self._code = code
        self._request_id = request_id

    def get_code(self):
        return self._code

    def get_request_id(self):
        return self._request_id


def _point_wrapper_at_sdk_error(monkeypatch):
    from ansible_collections.susunola.tencentcloud.plugins.module_utils import tencentcloud as wrapper

    monkeypatch.setattr(wrapper, "TencentCloudSDKException", SdkError)


def _inject_sdk(monkeypatch, client):
    service = types.ModuleType("tencentcloud.cvm.v20170312")
    service.models = FakeModels
    service.cvm_client = types.SimpleNamespace(CvmClient=lambda *args: client)
    monkeypatch.setitem(sys.modules, "tencentcloud", types.ModuleType("tencentcloud"))
    monkeypatch.setitem(sys.modules, "tencentcloud.cvm",
                        types.ModuleType("tencentcloud.cvm"))
    monkeypatch.setitem(sys.modules, "tencentcloud.cvm.v20170312", service)


@pytest.fixture
def sdk(monkeypatch):
    """Patch the credential/client factories the module builds its client with."""
    monkeypatch.setattr(key_pair_info, "create_credential", lambda module: object())
    monkeypatch.setattr(key_pair_info, "create_client_profile",
                        lambda module, endpoint: object())


def _args(**extra):
    """Pass one of key_ids/filters: the module makes them mutually exclusive."""
    params = {"region": "ap-guangzhou", "page_size": 2}
    params.update(extra or {"filters": {}})
    module_args(**params)


def test_run_module_paginates_until_total_count(monkeypatch, sdk):
    client = FakeClient([
        FakeResponse([FakeItem("skey-a"), FakeItem("skey-b")], 3),
        FakeResponse([FakeItem("skey-c")], 3),
    ])
    _inject_sdk(monkeypatch, client)
    _args()

    payload = run(key_pair_info.run_module)

    assert payload["changed"] is False
    assert [item["KeyId"] for item in payload["key_pairs"]] == [
        "skey-a", "skey-b", "skey-c"]
    assert payload["total_count"] == 3
    assert [request.Offset for request in client.requests] == [0, 2]


def test_run_module_returns_empty_on_empty_first_page(monkeypatch, sdk):
    client = FakeClient([FakeResponse([], 0)])
    _inject_sdk(monkeypatch, client)
    _args()

    payload = run(key_pair_info.run_module)

    assert payload["key_pairs"] == []
    assert payload["total_count"] == 0
    assert len(client.requests) == 1


def test_run_module_fails_cleanly_on_sdk_error(monkeypatch, sdk):
    """The shared wrapper's failure contract, exercised rather than restated.

    The read helper is no longer replaced: the client raises the SDK error and
    the real ``read_sdk_call`` classifies it, so the payload below is the one
    the shared code produces. The double that used to stand in for it pinned a
    hand-written copy of the contract, which could not notice the helper
    changing -- and this module now reaches the API through that helper.
    """
    class FailingClient:
        def DescribeKeyPairs(self, request):
            raise SdkError("UnauthorizedOperation", "api exploded", "req-err")

    _inject_sdk(monkeypatch, FailingClient())
    _point_wrapper_at_sdk_error(monkeypatch)
    _args()

    with pytest.raises(AnsibleFailJson) as failure:
        run(key_pair_info.run_module)

    payload = failure.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert payload["error_code"] == "UnauthorizedOperation"
    assert payload["request_id"] == "req-err"
    # The bucket the shared wrapper derives from the code.
    assert payload["error_class"] == "unauthorized"
