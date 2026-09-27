"""Deep harness tests for tione_training_model_version_info.

Covers the exact version detail request (stable version_id), the
parent-scoped list request (TrainingModelId plus stably sorted filters
with scalar-to-list coercion), argument validation, and run_module()
end to end through the shared harness: the single-call detail branch, the
single-call list branch, empty results and the sdk_error_payload fail
contract.

The module subclasses ``TencentCloudModule``, so the migration patches the
base class's ``create_client`` and the module's own ``_load`` (which is where
it imports its models and client class), and lets ``module_args()`` supply the
credentials the base class validates. ``params()`` carries the selectors as
``None`` for the request-builder tests, but Ansible counts an explicitly passed
``None`` as specified, so ``module_params()`` leaves the unused selectors out --
and drops the filters in detail mode, where the module's ``mutually_exclusive``
forbids them. The fixture serialises ``TrainingModelVersionId``, the identity
field the sibling ``tione_training_model_version`` module reads off a
``TrainingModelVersionDTO``, rather than a generic ``Marker``, so the payload
is what ``add_return_samples.py`` captures as the module's documented sample.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import types

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import tione_training_model_version_info
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
    DescribeTrainingModelVersionRequest = FakeRequest
    DescribeTrainingModelVersionsRequest = FakeRequest
    Filter = FakeFilter


def params(**overrides):
    options = {"model_id": None, "version_id": None, "filters": {}}
    options.update(overrides)
    return options


def module_params(**overrides):
    """Module arguments with the unsupplied selectors omitted, not passed as None.

    Ansible counts an explicitly passed ``None`` as specified, so
    ``version_id=None`` next to the explicit ``filters`` trips the module's
    ``("version_id", "filters")`` mutual exclusion. Detail mode is mutually
    exclusive with the filter option as well, so the filters are dropped
    whenever ``version_id`` is supplied; the ``{}`` default fills them back in
    for list mode.
    """
    values = {key: value for key, value in params().items() if value is not None}
    values.update(overrides)
    if values.get("version_id"):
        values.pop("filters", None)
    return values


def test_detail_request_uses_stable_version_id():
    request = tione_training_model_version_info.detail_request(FakeModels, "mv-1")
    assert request.TrainingModelVersionId == "mv-1"


def test_list_request_is_parent_scoped_stably_filtered_and_coerces_scalars():
    request = tione_training_model_version_info.list_request(
        FakeModels, "model-1", {"ModelVersionType": "NORMAL", "AlgorithmFramework": ["PYTORCH"], "Status": ["RUNNING"]})
    assert request.TrainingModelId == "model-1"
    assert [(item.Name, item.Values) for item in request.Filters] == [
        ("AlgorithmFramework", ["PYTORCH"]), ("ModelVersionType", ["NORMAL"]), ("Status", ["RUNNING"])]


def test_list_request_leaves_filters_unset_when_empty():
    request = tione_training_model_version_info.list_request(FakeModels, "model-1", {})
    assert request.TrainingModelId == "model-1"
    assert not hasattr(request, "Filters")


class FakeItem:
    def __init__(self, marker):
        self.marker = marker

    def _serialize(self, allow_none=True):
        return {"TrainingModelVersionId": self.marker}


class FakeVersionResponse:
    def __init__(self, item, request_id):
        self.TrainingModelVersion = item
        self.RequestId = request_id


class FakeVersionsResponse:
    def __init__(self, items, request_id):
        self.TrainingModelVersions = items
        self.RequestId = request_id


class FakeClient:
    def __init__(self):
        self.version_request = None
        self.versions_request = None
        self.version_response = None
        self.versions_response = None

    def DescribeTrainingModelVersion(self, request):
        self.version_request = request
        return self.version_response

    def DescribeTrainingModelVersions(self, request):
        self.versions_request = request
        return self.versions_response


def _patch_sdk(monkeypatch, client):
    """Hand the module its models/client class and the client itself."""
    monkeypatch.setattr(tione_training_model_version_info, "_load", lambda: (
        FakeModels, types.SimpleNamespace(TioneClient=lambda *args: client)))
    monkeypatch.setattr(TencentCloudModule, "create_client",
                        lambda self, client_class, endpoint: client)


@pytest.mark.parametrize("detail,expected", [(FakeItem("mv-1"), {"TrainingModelVersionId": "mv-1"}), (None, None)])
def test_run_module_describes_exact_version(monkeypatch, detail, expected):
    client = FakeClient()
    client.version_response = FakeVersionResponse(detail, "req-detail")
    _patch_sdk(monkeypatch, client)
    module_args(**module_params(version_id="mv-1"))

    payload = run(tione_training_model_version_info.run_module)

    assert payload["changed"] is False
    assert payload["model_version"] == expected
    assert payload["request_id"] == "req-detail"
    assert client.version_request.TrainingModelVersionId == "mv-1"
    assert client.versions_request is None


@pytest.mark.parametrize("items,expected_total", [([FakeItem("v1"), FakeItem("v2")], 2), ([], 0)])
def test_run_module_lists_versions_within_parent_model(monkeypatch, items, expected_total):
    client = FakeClient()
    client.versions_response = FakeVersionsResponse(items, "req-list")
    _patch_sdk(monkeypatch, client)
    module_args(**module_params(model_id="model-1", filters={"ModelVersionType": "NORMAL"}))

    payload = run(tione_training_model_version_info.run_module)

    assert payload["changed"] is False
    assert payload["model_versions"] == [item._serialize() for item in items]
    assert payload["total_count"] == expected_total
    assert payload["request_id"] == "req-list"
    assert client.versions_request.TrainingModelId == "model-1"
    assert client.version_request is None


def test_run_module_requires_model_id_in_list_mode():
    module_args(**module_params())

    with pytest.raises(AnsibleFailJson) as failure:
        run(tione_training_model_version_info.run_module)

    assert failure.value.args[0]["msg"] == "model_id is required in list mode"


@pytest.mark.parametrize("filters,message", [
    ({"f%02d" % index: ["v"] for index in range(11)}, "filters accepts at most ten filter names"),
    ({"ModelVersionType": ["v%d" % index for index in range(101)]}, "each filter accepts at most 100 values"),
])
def test_run_module_rejects_oversized_filters(filters, message):
    module_args(**module_params(model_id="model-1", filters=filters))

    with pytest.raises(AnsibleFailJson) as failure:
        run(tione_training_model_version_info.run_module)

    assert failure.value.args[0]["msg"] == message


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
        def DescribeTrainingModelVersions(self, request):
            raise SdkError("FailedOperation", "req-err")

    _patch_sdk(monkeypatch, FailingClient())
    module_args(**module_params(model_id="model-1"))

    with pytest.raises(AnsibleFailJson) as failure:
        run(tione_training_model_version_info.run_module)

    payload = failure.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert payload["error"] == "api exploded"
    assert payload["error_code"] == "FailedOperation"
    assert payload["request_id"] == "req-err"
