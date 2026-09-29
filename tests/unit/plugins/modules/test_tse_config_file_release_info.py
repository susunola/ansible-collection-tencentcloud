"""Deep harness tests for tse_config_file_release_info.

Covers the release/history/version request builders (config-file
identity plus release filters), the generic fetch_pages loop, and
run_module() end to end: happy-path release and history pagination plus
the single version lookup, empty results, page_size validation and the
sdk_error_payload fail contract.

The module subclasses ``TencentCloudModule`` and loads its models and
client in its own ``_load()``, so the migration patches that helper and
the base class's ``create_client``, and lets ``module_args()`` supply the
credentials the base class validates. The fake item serialises ``Name``, a
real field of ``ConfigFileRelease``, ``ConfigFileReleaseHistory`` and
``ReleaseVersion`` (the API never returns ``Value``), because that payload
is what ``add_return_samples.py`` captures as the module's documented
sample.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import types

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import tse_config_file_release_info
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    module_args,
    run,
)


class FakeRequest:
    pass


class FakeModels:
    DescribeConfigFileReleasesRequest = FakeRequest
    DescribeConfigFileReleaseHistoriesRequest = FakeRequest
    DescribeConfigFileReleaseVersionsRequest = FakeRequest


def params():
    return {
        "instance_id": "ins-1",
        "namespace": "prod",
        "group": "app",
        "name": "a.yaml",
        "config_file_id": "file-1",
        "release_name": "stable",
        "only_in_use": True,
        "page_size": 2,
    }


def test_audit_requests_map_release_identity():
    release = tse_config_file_release_info.release_request(FakeModels, params(), 4)
    history = tse_config_file_release_info.history_request(FakeModels, params(), 6)
    version = tse_config_file_release_info.version_request(FakeModels, params())
    assert release.FileName == "a.yaml" and release.ReleaseName == "stable"
    assert release.OnlyUse is True and release.Offset == 4 and release.Limit == 2
    assert history.Name == "a.yaml" and history.ConfigFileId == "file-1"
    assert history.Offset == 6 and history.Limit == 2
    assert version.FileName == "a.yaml" and version.ConfigFileId == "file-1"


class FakeItem:
    def __init__(self, name):
        self.name = name

    def _serialize(self, allow_none=True):
        return {"Name": self.name}


class FakeListResponse:
    def __init__(self, field, items, total_count, request_id):
        setattr(self, field, items)
        self.TotalCount = total_count
        self.RequestId = request_id


class FakeVersionsResponse:
    def __init__(self, items, request_id):
        self.ReleaseVersions = items
        self.RequestId = request_id


class FakeClient:
    def __init__(self):
        self.release_pages = []
        self.history_pages = []
        self.release_requests = []
        self.history_requests = []
        self.version_request = None
        self.versions_response = None

    def DescribeConfigFileReleases(self, request):
        self.release_requests.append(request)
        return self.release_pages.pop(0)

    def DescribeConfigFileReleaseHistories(self, request):
        self.history_requests.append(request)
        return self.history_pages.pop(0)

    def DescribeConfigFileReleaseVersions(self, request):
        self.version_request = request
        return self.versions_response


def _patch_sdk(monkeypatch, client):
    """Hand the module its models/client class and the client itself."""
    monkeypatch.setattr(tse_config_file_release_info, "_load", lambda: (
        FakeModels, types.SimpleNamespace(TseClient=lambda *args: client)))
    monkeypatch.setattr(TencentCloudModule, "create_client",
                        lambda self, client_class, endpoint: client)


def _run(monkeypatch, client, **module_params):
    _patch_sdk(monkeypatch, client)
    module_args(**module_params)
    return run(tse_config_file_release_info.run_module)


def _expect_fail(monkeypatch, module_params):
    _patch_sdk(monkeypatch, FakeClient())
    module_args(**module_params)
    with pytest.raises(AnsibleFailJson) as failure:
        run(tse_config_file_release_info.run_module)
    return failure.value.args[0]


def _response(field, names, total, request_id):
    return FakeListResponse(field, [FakeItem(name) for name in names], total, request_id)


def test_run_module_collects_releases_histories_and_versions(monkeypatch):
    client = FakeClient()
    client.release_pages = [
        _response("Releases", ["r1", "r2"], 3, "req-rel-1"),
        _response("Releases", ["r3"], 3, "req-rel-2"),
    ]
    client.history_pages = [_response("ConfigFileReleaseHistories", ["h1", "h2"], 2, "req-hist-1")]
    client.versions_response = FakeVersionsResponse([FakeItem("v1")], "req-ver-1")

    payload = _run(monkeypatch, client, **params())

    assert payload["changed"] is False
    assert [item["Name"] for item in payload["releases"]] == ["r1", "r2", "r3"]
    assert [item["Name"] for item in payload["histories"]] == ["h1", "h2"]
    assert [item["Name"] for item in payload["versions"]] == ["v1"]
    assert payload["release_count"] == 3
    assert payload["history_count"] == 2
    assert payload["request_ids"] == {"releases": "req-rel-2", "histories": "req-hist-1",
                                      "versions": "req-ver-1"}
    assert [request.Offset for request in client.release_requests] == [0, 2]
    assert [request.Offset for request in client.history_requests] == [0]
    assert client.version_request.ConfigFileId == "file-1"


def test_run_module_empty_audit_trail_reports_zero_counts(monkeypatch):
    client = FakeClient()
    client.release_pages = [_response("Releases", [], 0, "req-rel-empty")]
    client.history_pages = [_response("ConfigFileReleaseHistories", [], 0, "req-hist-empty")]
    client.versions_response = FakeVersionsResponse([], "req-ver-empty")

    payload = _run(monkeypatch, client, **params())

    assert payload["releases"] == [] and payload["histories"] == []
    assert payload["versions"] == []
    assert payload["release_count"] == 0 and payload["history_count"] == 0


@pytest.mark.parametrize("page_size,message", [
    (0, "page_size must be between 1 and 100"),
    (101, "page_size must be between 1 and 100"),
])
def test_run_module_validates_page_size_bounds(monkeypatch, page_size, message):
    p = params()
    p["page_size"] = page_size
    payload = _expect_fail(monkeypatch, p)
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
        def DescribeConfigFileReleases(self, request):
            raise SdkError("FailedOperation", "req-err")

    _patch_sdk(monkeypatch, FailingClient())
    module_args(**params())

    with pytest.raises(AnsibleFailJson) as failure:
        run(tse_config_file_release_info.run_module)

    payload = failure.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert payload["error"] == "api exploded"
    assert payload["error_code"] == "FailedOperation"
    assert payload["request_id"] == "req-err"
