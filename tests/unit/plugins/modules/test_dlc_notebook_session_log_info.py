"""Deep harness tests for the dlc_notebook_session_log_info module.

Covers build_request (exact session identity, offset pagination) plus
run_module log-line pagination that stops on a short page, page-cap
truncation, empty results, page_size/max_pages validation and the
sdk_error_payload failure contract.

The module subclasses ``TencentCloudModule``, so the migration patches the
base class's ``create_client`` and the module's own ``_load`` (which is where
it imports its models and client class), and lets ``module_args()`` supply the
credentials the base class validates. The fake response serialises ``Logs`` /
``RequestId``, the real fields of ``DescribeNotebookSessionLogResponse``.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import types

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import dlc_notebook_session_log_info
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    module_args,
    run,
)


class Object:
    pass


class FakeModels:
    DescribeNotebookSessionLogRequest = Object


def test_build_request_uses_exact_session_and_offset():
    request = dlc_notebook_session_log_info.build_request(FakeModels, "session-1", 200, 200)
    assert request.SessionId == "session-1"
    assert request.Offset == 200
    assert request.Limit == 200


class FakeResponse:
    def __init__(self, logs, request_id):
        self.Logs = logs
        self.RequestId = request_id


class FakeClient:
    def __init__(self, pages):
        self._pages = list(pages)
        self.requests = []

    def DescribeNotebookSessionLog(self, request):
        self.requests.append(request)
        return self._pages.pop(0)


class SDKError(Exception):
    def get_code(self):
        return "UnauthorizedOperation"

    def get_request_id(self):
        return "req-err"


def _patch_sdk(monkeypatch, client):
    """Hand the module its models/client class and the client itself."""
    monkeypatch.setattr(dlc_notebook_session_log_info, "_load", lambda: (
        FakeModels, types.SimpleNamespace(DlcClient=lambda *args: client)))
    monkeypatch.setattr(TencentCloudModule, "create_client",
                        lambda self, client_class, endpoint: client)


def test_run_module_stops_on_short_page(monkeypatch):
    client = FakeClient([FakeResponse(["a", "b"], "r1"), FakeResponse(["c"], "r2")])
    _patch_sdk(monkeypatch, client)
    module_args(region="ap-guangzhou", session_id="session-1", page_size=2, max_pages=5)

    payload = run(dlc_notebook_session_log_info.run_module)

    assert payload["changed"] is False
    assert payload["logs"] == ["a", "b", "c"]
    assert payload["truncated"] is False
    assert payload["request_id"] == "r2"
    assert [request.Offset for request in client.requests] == [0, 2]
    assert [request.SessionId for request in client.requests] == ["session-1", "session-1"]


def test_run_module_reports_page_cap_on_full_pages(monkeypatch):
    client = FakeClient([FakeResponse(["a"], "r1")])
    _patch_sdk(monkeypatch, client)
    module_args(region="ap-guangzhou", session_id="session-1", page_size=1, max_pages=1)

    payload = run(dlc_notebook_session_log_info.run_module)

    assert payload["logs"] == ["a"]
    assert payload["truncated"] is True
    assert payload["request_id"] == "r1"
    assert [request.Offset for request in client.requests] == [0]


def test_run_module_returns_empty_when_no_logs(monkeypatch):
    client = FakeClient([FakeResponse([], "r-empty")])
    _patch_sdk(monkeypatch, client)
    module_args(region="ap-guangzhou", session_id="session-1", page_size=2, max_pages=5)

    payload = run(dlc_notebook_session_log_info.run_module)

    assert payload["logs"] == []
    assert payload["truncated"] is False
    assert payload["request_id"] == "r-empty"
    assert [request.Offset for request in client.requests] == [0]


def test_run_module_validates_page_size_and_max_pages(monkeypatch):
    module_args(region="ap-guangzhou", session_id="session-1", page_size=0, max_pages=5)

    with pytest.raises(AnsibleFailJson) as failure:
        run(dlc_notebook_session_log_info.run_module)

    assert failure.value.args[0]["msg"] == "page_size must be between 1 and 1000"

    module_args(region="ap-guangzhou", session_id="session-1", page_size=2, max_pages=1001)

    with pytest.raises(AnsibleFailJson) as failure:
        run(dlc_notebook_session_log_info.run_module)

    assert failure.value.args[0]["msg"] == "max_pages must be between 1 and 1000"


def test_run_module_fails_cleanly_on_sdk_error(monkeypatch):
    class FailingClient:
        def DescribeNotebookSessionLog(self, request):
            raise SDKError("api exploded")

    _patch_sdk(monkeypatch, FailingClient())
    module_args(region="ap-guangzhou", session_id="session-1", page_size=2, max_pages=5)

    with pytest.raises(AnsibleFailJson) as failure:
        run(dlc_notebook_session_log_info.run_module)

    payload = failure.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert payload["error"] == "api exploded"
    assert payload["error_code"] == "UnauthorizedOperation"
    assert payload["request_id"] == "req-err"
