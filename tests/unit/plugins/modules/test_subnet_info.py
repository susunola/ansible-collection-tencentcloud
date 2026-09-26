"""Deep harness tests for subnet_info.

Covers build_request (string pagination fields, subnet ids, sorted filters,
scalar value wrapping) and run_module() end to end via the Paginator through
the shared harness: multi-page collection driven by TotalCount, an empty
result set, and the sdk_call fail contract (msg/error/error_code/request_id).

The module builds its own SDK client, so the tests still inject a fake
``tencentcloud.vpc.v20170312`` service and patch the two factories. They no
longer replace ``AnsibleModule`` with a private double, which is what makes
the payload observable: the fixture returns ``SubnetId`` rather than a generic
``Marker`` because that payload is now what ``add_return_samples.py`` captures
as the module's documented sample.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import sys
import types

import pytest

from ansible_collections.susunola.tencentcloud.plugins.modules import subnet_info
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
    DescribeSubnetsRequest = FakeRequest


def test_build_request_maps_ids_and_string_pagination():
    request = subnet_info.build_request(FakeModels, ["subnet-123"], {}, 20, 100)
    assert request.Offset == "20"
    assert request.Limit == "100"
    assert request.SubnetIds == ["subnet-123"]


def test_build_request_sorts_filters():
    request = subnet_info.build_request(
        FakeModels, [], {"zone": ["ap-guangzhou-3"], "vpc-id": ["vpc-1"]}, 0, 100)
    assert [(item.Name, item.Values) for item in request.Filters] == [
        ("vpc-id", ["vpc-1"]), ("zone", ["ap-guangzhou-3"]),
    ]


def test_build_request_wraps_scalar_filter_values():
    request = subnet_info.build_request(FakeModels, [], {"zone": "ap-guangzhou-3"}, 0, 100)
    assert request.Filters[0].Values == ["ap-guangzhou-3"]


class FakeItem:
    def __init__(self, marker):
        self.marker = marker

    def _serialize(self, allow_none=True):
        return {"SubnetId": self.marker}


class FakeResponse:
    def __init__(self, items, total_count):
        self.SubnetSet = items
        self.TotalCount = total_count
        self.RequestId = "req-page"


class FakeClient:
    def __init__(self, pages):
        self._pages = list(pages)
        self.requests = []

    def DescribeSubnets(self, request):
        self.requests.append(request)
        return self._pages.pop(0)


def _inject_sdk(monkeypatch, client):
    service = types.ModuleType("tencentcloud.vpc.v20170312")
    service.models = FakeModels
    service.vpc_client = types.SimpleNamespace(VpcClient=lambda *args: client)
    monkeypatch.setitem(sys.modules, "tencentcloud", types.ModuleType("tencentcloud"))
    monkeypatch.setitem(sys.modules, "tencentcloud.vpc",
                        types.ModuleType("tencentcloud.vpc"))
    monkeypatch.setitem(sys.modules, "tencentcloud.vpc.v20170312", service)


@pytest.fixture
def sdk(monkeypatch):
    """Patch the credential/client factories the module builds its client with."""
    monkeypatch.setattr(subnet_info, "create_credential", lambda module: object())
    monkeypatch.setattr(subnet_info, "create_client_profile",
                        lambda module, endpoint: object())


def _args(**extra):
    """Pass one of subnet_ids/filters: the module declares them exclusive."""
    params = {"region": "ap-guangzhou", "page_size": 2}
    params.update(extra or {"filters": {}})
    module_args(**params)


def test_run_module_paginates_until_total_count(monkeypatch, sdk):
    client = FakeClient([
        FakeResponse([FakeItem("subnet-a"), FakeItem("subnet-b")], 3),
        FakeResponse([FakeItem("subnet-c")], 3),
    ])
    _inject_sdk(monkeypatch, client)
    _args()

    payload = run(subnet_info.run_module)

    assert payload["changed"] is False
    assert [item["SubnetId"] for item in payload["subnets"]] == [
        "subnet-a", "subnet-b", "subnet-c"]
    assert payload["total_count"] == 3
    assert [request.Offset for request in client.requests] == ["0", "2"]


def test_run_module_returns_empty_on_empty_first_page(monkeypatch, sdk):
    client = FakeClient([FakeResponse([], 0)])
    _inject_sdk(monkeypatch, client)
    _args()

    payload = run(subnet_info.run_module)

    assert payload["subnets"] == []
    assert payload["total_count"] == 0
    assert len(client.requests) == 1


def test_run_module_fails_cleanly_on_sdk_error(monkeypatch, sdk):
    class FailingClient:
        def DescribeSubnets(self, request):
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
    monkeypatch.setattr(subnet_info, "sdk_call", failing_sdk_call)
    _args()

    with pytest.raises(AnsibleFailJson) as failure:
        run(subnet_info.run_module)

    payload = failure.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert payload["error_code"] == "UnauthorizedOperation"
    assert payload["request_id"] == "req-err"
