"""Deep harness tests for the cvm_instance_info module.

Covers build_request (instance-id passthrough, stable filter ordering,
offset/limit pagination), run_module offset pagination until the reported
total count is reached, empty-page termination and the sdk_call failure
contract -- driven through the shared harness rather than a private double.

The module builds its own SDK client, so the tests still inject a fake
``tencentcloud.cvm.v20170312`` service and patch the two factories. Driving
the real ``AnsibleModule`` is what makes the payload observable, and the
fixture already serialises ``InstanceId``, so the captured payload is what
``add_return_samples.py`` writes into the module's RETURN sample.
"""
from __future__ import absolute_import, division, print_function

__metaclass__ = type

import sys
import types

import pytest

from ansible_collections.susunola.tencentcloud.plugins.modules import cvm_instance_info
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
    DescribeInstancesRequest = FakeRequest


def test_build_request_sets_pagination():
    request = cvm_instance_info.build_request(FakeModels, None, {}, 200, 100)
    assert request.Offset == 200
    assert request.Limit == 100
    assert not hasattr(request, "InstanceIds")


def test_build_request_maps_ids_and_sorts_filters():
    request = cvm_instance_info.build_request(
        FakeModels,
        ["ins-123"],
        {"zone": ["ap-guangzhou-3"], "instance-state": "RUNNING"},
        0,
        100,
    )
    assert request.InstanceIds == ["ins-123"]
    assert [(item.Name, item.Values) for item in request.Filters] == [
        ("instance-state", ["RUNNING"]), ("zone", ["ap-guangzhou-3"]),
    ]


class FakeItem:
    def __init__(self, marker):
        self.marker = marker

    def _serialize(self, allow_none=True):
        return {"InstanceId": self.marker}


class FakeResponse:
    def __init__(self, items, total_count):
        self.InstanceSet = items
        self.TotalCount = total_count
        self.RequestId = "req-page"


class FakeClient:
    def __init__(self, pages):
        self._pages = list(pages)
        self.requests = []

    def DescribeInstances(self, request):
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
    monkeypatch.setattr(cvm_instance_info, "create_credential",
                        lambda module: object())
    monkeypatch.setattr(cvm_instance_info, "create_client_profile",
                        lambda module, endpoint: object())


def _args(**extra):
    """Pass one of instance_ids/filters: they are mutually exclusive.

    ``page_size`` has choices (20/50/100) rather than a free integer -- the
    private harness never validated it, which is one of the reasons the real
    one is worth the migration.
    """
    params = {"region": "ap-guangzhou", "page_size": 20}
    params.update(extra or {"filters": {}})
    module_args(**params)


def test_run_module_paginates_until_total_count(monkeypatch, sdk):
    client = FakeClient([
        FakeResponse([FakeItem("ins-a"), FakeItem("ins-b")], 3),
        FakeResponse([FakeItem("ins-c")], 3),
    ])
    _inject_sdk(monkeypatch, client)
    _args()

    payload = run(cvm_instance_info.run_module)

    assert payload["changed"] is False
    assert [item["InstanceId"] for item in payload["instances"]] == [
        "ins-a", "ins-b", "ins-c"]
    assert payload["total_count"] == 3
    assert [request.Offset for request in client.requests] == [0, 2]
    assert [request.Limit for request in client.requests] == [20, 20]


def test_run_module_stops_on_empty_first_page(monkeypatch, sdk):
    client = FakeClient([FakeResponse([], 0)])
    _inject_sdk(monkeypatch, client)
    _args()

    payload = run(cvm_instance_info.run_module)

    assert payload["instances"] == []
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
        def DescribeInstances(self, request):
            raise SdkError("UnauthorizedOperation", "api exploded", "req-err")

    _inject_sdk(monkeypatch, FailingClient())
    _point_wrapper_at_sdk_error(monkeypatch)
    _args()

    with pytest.raises(AnsibleFailJson) as failure:
        run(cvm_instance_info.run_module)

    payload = failure.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert payload["error_code"] == "UnauthorizedOperation"
    assert payload["request_id"] == "req-err"
    # The bucket the shared wrapper derives from the code.
    assert payload["error_class"] == "unauthorized"
