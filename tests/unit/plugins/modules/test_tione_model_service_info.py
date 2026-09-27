"""Deep harness tests for tione_model_service_info.

Covers the exact service/group request builders, the list-mode request
builder (offset pagination, workspace scoping, stable filters, tag
filters, ordering) and run_module() end to end through the shared
harness: exact service and group lookups, bounded service-group list
pagination with global totals, argument validation, and the
sdk_error_payload fail contract.

The module subclasses ``TencentCloudModule``, so the migration patches the
base class's ``create_client`` and the module's own ``_load`` (which is where
it imports its models and client class), and lets ``module_args()`` supply the
credentials the base class validates. ``params()`` carries the selectors as
``None`` for the request-builder tests, but Ansible counts an explicitly passed
``None`` as specified, so ``module_params()`` leaves the unused selectors out --
both the selectors the mode does not use and, in exact-lookup mode, the filter
options that ``mutually_exclusive`` forbids beside a selector. The fixture
serialises the identity field of the model it stands in for (``ServiceId`` on
``Service``, ``ServiceGroupId`` on ``ServiceGroup``) rather than a generic
``Marker``, so the payload is what ``add_return_samples.py`` captures as the
module's documented sample.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import types

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import tione_model_service_info
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    module_args,
    run,
)


def params(**overrides):
    options = {
        "service_id": None,
        "service_group_id": None,
        "project_id": "p1",
        "filters": {"Status": "Normal", "ModelVersionId": ["mv1"]},
        "tag_filters": {"env": "prod"},
        "order_field": "UpdateTime",
        "order": "DESC",
        "page_size": 2,
        "max_pages": 5,
    }
    options.update(overrides)
    return options


def module_params(**overrides):
    """Module arguments with the unsupplied selectors omitted, not passed as None.

    Ansible counts an explicitly passed ``None`` as specified, so
    ``service_id=None`` next to the filter options trips the module's
    ``("service_id", "filters")`` mutual exclusion. Exact-lookup mode is
    mutually exclusive with both filter options as well, so they are dropped
    whenever a selector is supplied; their ``{}`` defaults fill them back in
    for list mode.
    """
    values = {key: value for key, value in params().items() if value is not None}
    values.update(overrides)
    if values.get("service_id") or values.get("service_group_id"):
        values.pop("filters", None)
        values.pop("tag_filters", None)
    return values


class FakeRequest:
    pass


class FakeFilter:
    pass


class FakeTagFilter:
    pass


class FakeModels:
    DescribeModelServiceRequest = FakeRequest
    DescribeModelServiceGroupRequest = FakeRequest
    DescribeModelServiceGroupsRequest = FakeRequest
    Filter = FakeFilter
    TagFilter = FakeTagFilter


def test_exact_requests_use_distinct_strong_identities():
    service = tione_model_service_info.service_request(FakeModels, params(service_id="ms-1"))
    group = tione_model_service_info.group_request(FakeModels, params(service_group_id="msg-1"))
    assert service.ServiceId == "ms-1"
    assert service.TiProjectId == "p1"
    assert group.ServiceGroupId == "msg-1"
    assert group.TiProjectId == "p1"


def test_exact_requests_skip_missing_workspace():
    p = params(project_id=None, service_id="ms-1", service_group_id="msg-1")
    assert not hasattr(tione_model_service_info.service_request(FakeModels, p), "TiProjectId")
    assert not hasattr(tione_model_service_info.group_request(FakeModels, p), "TiProjectId")


def test_list_request_maps_filters_tags_and_order_stably():
    request = tione_model_service_info.list_request(FakeModels, params(), 2)
    assert request.Offset == 2 and request.Limit == 2 and request.TiProjectId == "p1"
    assert [(x.Name, x.Values) for x in request.Filters] == [("ModelVersionId", ["mv1"]), ("Status", ["Normal"])]
    assert request.TagFilters[0].TagKey == "env"
    assert request.OrderField == "UpdateTime" and request.Order == "DESC"


class FakeItem:
    """SDK-shaped resource; ``field`` is the identity field it serialises.

    The list payload and the exact group lookup return ``ServiceGroup``, whose
    identity is ``ServiceGroupId``; the exact service lookup returns ``Service``,
    whose identity is ``ServiceId``.
    """

    def __init__(self, marker, field="ServiceGroupId"):
        self.marker = marker
        self.field = field

    def _serialize(self, allow_none=True):
        return {self.field: self.marker}


class FakeResponse:
    def __init__(self, items, total_count, global_total, request_id):
        self.ServiceGroups = items
        self.TotalCount = total_count
        self.GlobalTotalCount = global_total
        self.RequestId = request_id


class FakeClient:
    def __init__(self, pages=None):
        self._pages = list(pages or [])
        self.service_requests = []
        self.group_requests = []
        self.list_requests = []
        self.service_response = None
        self.group_response = None

    def DescribeModelService(self, request):
        self.service_requests.append(request)
        return self.service_response

    def DescribeModelServiceGroup(self, request):
        self.group_requests.append(request)
        return self.group_response

    def DescribeModelServiceGroups(self, request):
        self.list_requests.append(request)
        return self._pages.pop(0)


def _patch_sdk(monkeypatch, client):
    """Hand the module its models/client class and the client itself."""
    monkeypatch.setattr(tione_model_service_info, "_load", lambda: (
        FakeModels, types.SimpleNamespace(TioneClient=lambda *args: client)))
    monkeypatch.setattr(TencentCloudModule, "create_client",
                        lambda self, client_class, endpoint: client)


def test_run_module_paginates_service_groups_until_total_count(monkeypatch):
    client = FakeClient([
        FakeResponse([FakeItem("g1"), FakeItem("g2")], 3, 8, "req-1"),
        FakeResponse([FakeItem("g3")], 3, 8, "req-2"),
    ])
    _patch_sdk(monkeypatch, client)
    module_args(**module_params())

    payload = run(tione_model_service_info.run_module)

    assert payload["changed"] is False
    assert [item["ServiceGroupId"] for item in payload["service_groups"]] == ["g1", "g2", "g3"]
    assert payload["total_count"] == 3
    assert payload["global_total_count"] == 8
    assert payload["truncated"] is False
    assert payload["request_id"] == "req-2"
    assert [request.Offset for request in client.list_requests] == [0, 2]


def test_run_module_describes_exact_service(monkeypatch):
    client = FakeClient()
    client.service_response = types.SimpleNamespace(Service=FakeItem("ms-1", "ServiceId"), RequestId="req-svc")
    _patch_sdk(monkeypatch, client)
    module_args(**module_params(service_id="ms-1"))

    payload = run(tione_model_service_info.run_module)

    assert payload["service"] == {"ServiceId": "ms-1"}
    assert payload["request_id"] == "req-svc"
    assert len(client.service_requests) == 1


def test_run_module_describes_exact_service_group(monkeypatch):
    client = FakeClient()
    client.group_response = types.SimpleNamespace(ServiceGroup=FakeItem("msg-1"), RequestId="req-grp")
    _patch_sdk(monkeypatch, client)
    module_args(**module_params(service_group_id="msg-1"))

    payload = run(tione_model_service_info.run_module)

    assert payload["service_group"] == {"ServiceGroupId": "msg-1"}
    assert payload["request_id"] == "req-grp"
    assert len(client.group_requests) == 1


def test_run_module_validates_page_size_bounds():
    module_args(**module_params(page_size=101))

    with pytest.raises(AnsibleFailJson) as failure:
        run(tione_model_service_info.run_module)

    assert failure.value.args[0]["msg"] == "page_size must be between 1 and 100"


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
        def DescribeModelServiceGroups(self, request):
            raise SdkError("FailedOperation", "req-err")

    _patch_sdk(monkeypatch, FailingClient())
    module_args(**module_params())

    with pytest.raises(AnsibleFailJson) as failure:
        run(tione_model_service_info.run_module)

    payload = failure.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert payload["error_code"] == "FailedOperation"
    assert payload["request_id"] == "req-err"
