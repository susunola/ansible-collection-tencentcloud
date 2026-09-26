"""Deep harness tests for security_group_info.

Covers build_request (string pagination fields, security group ids, sorted
filters, scalar value wrapping) and run_module() end to end through the shared
harness: multi-page collection driven by TotalCount, an empty result set, and
the sdk_call fail contract (msg/error/error_code/request_id).

The module builds its own SDK client, so the tests still inject a fake
``tencentcloud.vpc.v20170312`` service and patch the two factories. They no
longer replace ``AnsibleModule`` with a private double, which is what makes
the payload observable: the fixture returns ``SecurityGroupId`` rather than a
generic ``Marker`` because that payload is now what ``add_return_samples.py``
captures as the module's documented sample.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import sys
import types

import pytest

from ansible_collections.susunola.tencentcloud.plugins.modules import security_group_info
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
    DescribeSecurityGroupsRequest = FakeRequest


def test_build_request_maps_ids_and_string_pagination():
    request = security_group_info.build_request(FakeModels, ["sg-123"], {}, 20, 100)
    assert request.SecurityGroupIds == ["sg-123"]
    assert request.Offset == "20"
    assert request.Limit == "100"
    assert not hasattr(request, "Filters")


def test_build_request_sorts_filters():
    request = security_group_info.build_request(
        FakeModels, [], {"security-group-name": ["web"], "project-id": ["0"]}, 0, 100)
    assert [(item.Name, item.Values) for item in request.Filters] == [
        ("project-id", ["0"]), ("security-group-name", ["web"]),
    ]


def test_build_request_wraps_scalar_filter_values():
    request = security_group_info.build_request(FakeModels, [], {"security-group-name": "web"}, 0, 100)
    assert request.Filters[0].Values == ["web"]


class FakeItem:
    def __init__(self, marker):
        self.marker = marker

    def _serialize(self, allow_none=True):
        return {"SecurityGroupId": self.marker}


class FakeResponse:
    def __init__(self, items, total_count):
        self.SecurityGroupSet = items
        self.TotalCount = total_count
        self.RequestId = "req-page"


class FakeClient:
    def __init__(self, pages):
        self._pages = list(pages)
        self.requests = []

    def DescribeSecurityGroups(self, request):
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
    monkeypatch.setattr(security_group_info, "create_credential",
                        lambda module: object())
    monkeypatch.setattr(security_group_info, "create_client_profile",
                        lambda module, endpoint: object())


def _args(**extra):
    """Pass one of security_group_ids/filters: they are mutually exclusive."""
    params = {"region": "ap-guangzhou", "page_size": 2}
    params.update(extra or {"filters": {}})
    module_args(**params)


def test_run_module_paginates_until_total_count(monkeypatch, sdk):
    client = FakeClient([
        FakeResponse([FakeItem("sg-a"), FakeItem("sg-b")], 3),
        FakeResponse([FakeItem("sg-c")], 3),
    ])
    _inject_sdk(monkeypatch, client)
    _args()

    payload = run(security_group_info.run_module)

    assert payload["changed"] is False
    assert [item["SecurityGroupId"] for item in payload["security_groups"]] == [
        "sg-a", "sg-b", "sg-c"]
    assert payload["total_count"] == 3
    assert [request.Offset for request in client.requests] == ["0", "2"]


def test_run_module_returns_empty_on_empty_first_page(monkeypatch, sdk):
    client = FakeClient([FakeResponse([], 0)])
    _inject_sdk(monkeypatch, client)
    _args()

    payload = run(security_group_info.run_module)

    assert payload["security_groups"] == []
    assert payload["total_count"] == 0
    assert len(client.requests) == 1


def test_run_module_fails_cleanly_on_sdk_error(monkeypatch, sdk):
    class FailingClient:
        def DescribeSecurityGroups(self, request):
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
    monkeypatch.setattr(security_group_info, "sdk_call", failing_sdk_call)
    _args()

    with pytest.raises(AnsibleFailJson) as failure:
        run(security_group_info.run_module)

    payload = failure.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert payload["error_code"] == "UnauthorizedOperation"
    assert payload["request_id"] == "req-err"
