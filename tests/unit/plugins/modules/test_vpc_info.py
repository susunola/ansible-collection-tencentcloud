"""Deep harness tests for vpc_info.

Covers the legacy build_request helper (string-typed offset/limit
pagination, vpc_ids passthrough, stably sorted filters) and run_module()
end to end through the shared harness: inline offset pagination across pages
until TotalCount, empty results and the legacy sdk_call fail contract.
vpc_info exits without a request_id, so the payload assertions do not include
one.

The module builds its own SDK client, so the tests still inject a fake
``tencentcloud.vpc.v20170312`` service and patch the two factories; what they
no longer do is replace ``AnsibleModule`` with a private double, which is why
the payload now passes through the real ``exit_json`` -- and can be captured
for the RETURN sample.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import sys
import types

import pytest

from ansible_collections.susunola.tencentcloud.plugins.modules import vpc_info
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
    DescribeVpcsRequest = FakeRequest


def test_build_request_maps_ids_and_string_pagination():
    request = vpc_info.build_request(FakeModels, ["vpc-123"], {}, 20, 100)
    assert request.Offset == "20"
    assert request.Limit == "100"
    assert request.VpcIds == ["vpc-123"]


def test_build_request_sorts_filters():
    request = vpc_info.build_request(FakeModels, [], {"vpc-name": ["prod"], "is-default": ["true"]}, 0, 100)
    assert [(item.Name, item.Values) for item in request.Filters] == [
        ("is-default", ["true"]), ("vpc-name", ["prod"]),
    ]
    assert not hasattr(request, "VpcIds")


def test_build_request_coerces_scalar_filter_values():
    request = vpc_info.build_request(FakeModels, [], {"vpc-name": "prod"}, 0, 100)
    assert request.Filters[0].Values == ["prod"]


class FakeItem:
    def __init__(self, marker):
        self.marker = marker

    def _serialize(self, allow_none=True):
        return {"VpcId": self.marker}


class FakeResponse:
    def __init__(self, items, total_count):
        self.VpcSet = items
        self.TotalCount = total_count
        self.RequestId = "req-page"


class FakeClient:
    def __init__(self, pages):
        self._pages = list(pages)
        self.requests = []

    def DescribeVpcs(self, request):
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
    monkeypatch.setattr(vpc_info, "create_credential", lambda module: object())
    monkeypatch.setattr(vpc_info, "create_client_profile",
                        lambda module, endpoint: object())


def _args(**extra):
    """Pass one of vpc_ids/filters: the module declares them mutually exclusive.

    Ansible counts an explicitly passed ``None`` as specified, so the unused
    one is omitted rather than set to None.
    """
    params = {"region": "ap-guangzhou", "page_size": 2}
    params.update(extra or {"filters": {}})
    module_args(**params)


def test_run_module_paginates_vpcs_until_total_count(monkeypatch, sdk):
    client = FakeClient([
        FakeResponse([FakeItem("vpc-a"), FakeItem("vpc-b")], 3),
        FakeResponse([FakeItem("vpc-c")], 3),
    ])
    _inject_sdk(monkeypatch, client)
    _args()

    payload = run(vpc_info.run_module)

    assert payload["changed"] is False
    assert [item["VpcId"] for item in payload["vpcs"]] == ["vpc-a", "vpc-b", "vpc-c"]
    assert payload["total_count"] == 3
    assert "request_id" not in payload
    assert [request.Offset for request in client.requests] == ["0", "2"]
    assert [request.Limit for request in client.requests] == ["2", "2"]


def test_run_module_empty_result_reports_zero_total(monkeypatch, sdk):
    client = FakeClient([FakeResponse([], 0)])
    _inject_sdk(monkeypatch, client)
    _args()

    payload = run(vpc_info.run_module)

    assert payload["vpcs"] == []
    assert payload["total_count"] == 0


def test_run_module_passes_ids_through_each_request(monkeypatch, sdk):
    client = FakeClient([FakeResponse([FakeItem("vpc-a")], 1)])
    _inject_sdk(monkeypatch, client)
    _args(vpc_ids=["vpc-a"])

    payload = run(vpc_info.run_module)

    assert [item["VpcId"] for item in payload["vpcs"]] == ["vpc-a"]
    assert client.requests[0].VpcIds == ["vpc-a"]
    assert not hasattr(client.requests[0], "Filters")


def test_run_module_fails_cleanly_on_sdk_error(monkeypatch, sdk):
    class FailingClient:
        def DescribeVpcs(self, request):
            raise RuntimeError("api exploded")

    def failing_sdk_call(module, function, request):
        # Mirrors the real legacy sdk_call failure contract pinned in
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
    monkeypatch.setattr(vpc_info, "sdk_call", failing_sdk_call)
    _args()

    with pytest.raises(AnsibleFailJson) as failure:
        run(vpc_info.run_module)

    payload = failure.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert payload["error_code"] == "UnauthorizedOperation"
    assert payload["request_id"] == "req-err"
