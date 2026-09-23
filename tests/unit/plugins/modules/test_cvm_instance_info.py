"""Deep harness tests for the cvm_instance_info module.

Covers build_request (instance-id passthrough, stable filter ordering,
offset/limit pagination), run_module offset pagination until the reported
total count is reached, empty-page termination and the sdk_call failure
contract.
"""
from __future__ import absolute_import, division, print_function

__metaclass__ = type

import sys
import types

import pytest

from ansible_collections.susunola.tencentcloud.plugins.modules import cvm_instance_info


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


class FakeClient:
    def __init__(self, pages):
        self._pages = list(pages)
        self.requests = []

    def DescribeInstances(self, request):
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

    def exit_json(self, **kwargs):
        self.exit_payload = kwargs
        raise ModuleExit()

    def fail_json(self, **kwargs):
        self.fail_payload = kwargs
        raise ModuleFail(kwargs)


def _inject_sdk(monkeypatch, client):
    service = types.ModuleType("tencentcloud.cvm.v20170312")
    service.models = FakeModels
    service.cvm_client = types.SimpleNamespace(CvmClient=lambda *args: client)
    monkeypatch.setitem(sys.modules, "tencentcloud", types.ModuleType("tencentcloud"))
    monkeypatch.setitem(sys.modules, "tencentcloud.cvm",
                        types.ModuleType("tencentcloud.cvm"))
    monkeypatch.setitem(sys.modules, "tencentcloud.cvm.v20170312", service)


def _run(monkeypatch, client, **params):
    _inject_sdk(monkeypatch, client)
    fake = FakeModule(params)
    monkeypatch.setattr(cvm_instance_info, "AnsibleModule", lambda **kwargs: fake)
    monkeypatch.setattr(cvm_instance_info, "create_credential", lambda module: object())
    monkeypatch.setattr(cvm_instance_info, "create_client_profile", lambda module, endpoint: object())
    with pytest.raises(ModuleExit):
        cvm_instance_info.run_module()
    return fake


def test_run_module_paginates_until_total_count(monkeypatch):
    client = FakeClient([
        FakeResponse([FakeItem("ins-a"), FakeItem("ins-b")], 3),
        FakeResponse([FakeItem("ins-c")], 3),
    ])
    fake = _run(monkeypatch, client, region="ap-guangzhou",
                instance_ids=None, filters={}, page_size=2)
    payload = fake.exit_payload
    assert payload["changed"] is False
    assert [item["InstanceId"] for item in payload["instances"]] == ["ins-a", "ins-b", "ins-c"]
    assert payload["total_count"] == 3
    assert [request.Offset for request in client.requests] == [0, 2]
    assert [request.Limit for request in client.requests] == [2, 2]


def test_run_module_stops_on_empty_first_page(monkeypatch):
    client = FakeClient([FakeResponse([], 0)])
    fake = _run(monkeypatch, client, region="ap-guangzhou",
                instance_ids=None, filters={}, page_size=2)
    payload = fake.exit_payload
    assert payload["instances"] == []
    assert payload["total_count"] == 0
    assert len(client.requests) == 1


def test_run_module_fails_cleanly_on_sdk_error(monkeypatch):
    class FailingClient:
        def DescribeInstances(self, request):
            raise RuntimeError("api exploded")

    def failing_sdk_call(module, function, request):
        # Mirrors the real sdk_call failure contract pinned in
        # tests/unit/plugins/module_utils/test_tencentcloud.py.
        try:
            return function(request)
        except RuntimeError as exc:
            module.fail_json(
                msg="Tencent Cloud API request failed",
                error=str(exc),
                error_code="UnauthorizedOperation",
                request_id="req-err",
            )

    _inject_sdk(monkeypatch, FailingClient())
    fake = FakeModule({
        "region": "ap-guangzhou",
        "instance_ids": None,
        "filters": {},
        "page_size": 2,
    })
    monkeypatch.setattr(cvm_instance_info, "AnsibleModule", lambda **kwargs: fake)
    monkeypatch.setattr(cvm_instance_info, "create_credential", lambda module: object())
    monkeypatch.setattr(cvm_instance_info, "create_client_profile", lambda module, endpoint: object())
    monkeypatch.setattr(cvm_instance_info, "sdk_call", failing_sdk_call)
    with pytest.raises(ModuleFail) as excinfo:
        cvm_instance_info.run_module()
    payload = excinfo.value.payload
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert payload["error_code"] == "UnauthorizedOperation"
    assert payload["request_id"] == "req-err"
