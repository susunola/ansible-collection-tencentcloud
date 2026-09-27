"""Deep harness tests for the dlc_notebook_session_info module.

Covers build_request (offset pagination, exact engine/state filters, ordered
notebook-keyword and engine-generation filter pairs, sort fields) plus
run_module offset pagination over DescribeNotebookSessions, empty results,
page_size validation and the sdk_error_payload failure contract.

The module subclasses ``TencentCloudModule``, so the migration patches the base
class's ``create_client`` and the module's own ``_load`` (which is where it
imports its models and client class), and lets ``module_args()`` supply the
credentials the base class validates. The fake item already serialised
``Name``, a real ``NotebookSessions`` field, so no field is renamed; the empty
result test leaves its absent filters out of the module args instead of passing
them as explicit ``None``, which AnsibleModule would count as specified.
"""
from __future__ import absolute_import, division, print_function

__metaclass__ = type

import types

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import dlc_notebook_session_info
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    module_args,
    run,
)


class Object:
    pass


class FakeModels:
    Filter = Object
    DescribeNotebookSessionsRequest = Object


def params(**overrides):
    options = {
        "data_engine_name": "spark-prod",
        "states": ["idle", "busy"],
        "keyword": "analyst",
        "engine_generation": "supersql",
        "sort_fields": ["create_time"],
        "ascending": True,
        "page_size": 2,
    }
    options.update(overrides)
    return options


def absent_filter_params():
    """Module args for a run with every filter absent.

    The filter options are left out rather than passed as ``None``: an
    explicit ``None`` counts as specified for AnsibleModule, and an absent
    option reaches ``build_request`` as ``None`` all the same.
    """
    return {"ascending": False, "page_size": 2}


def test_build_request_maps_filters_sort_and_pagination():
    request = dlc_notebook_session_info.build_request(FakeModels, params(), 4)
    assert request.Offset == 4
    assert request.Limit == 2
    assert request.Asc is True
    assert request.DataEngineName == "spark-prod"
    assert request.State == ["idle", "busy"]
    assert request.SortFields == ["create_time"]
    assert [(item.Name, item.Values) for item in request.Filters] == [
        ("engine-generation", ["supersql"]), ("notebook-keyword", ["analyst"]),
    ]


def test_build_request_defaults_offset_and_omits_absent_filters():
    p = {"data_engine_name": None, "states": None, "keyword": None, "engine_generation": None,
         "sort_fields": None, "ascending": False, "page_size": 2}
    request = dlc_notebook_session_info.build_request(FakeModels, p)
    assert request.Offset == 0
    assert request.Limit == 2
    assert request.Asc is False
    for attribute in ("DataEngineName", "State", "SortFields", "Filters"):
        assert not hasattr(request, attribute)


class FakeItem:
    def __init__(self, name):
        self.name = name

    def _serialize(self, allow_none=True):
        return {"Name": self.name}


class FakeResponse:
    def __init__(self, sessions, total_elements, request_id):
        self.Sessions = sessions
        self.TotalElements = total_elements
        self.RequestId = request_id


class FakeClient:
    def __init__(self, pages):
        self._pages = list(pages)
        self.requests = []

    def DescribeNotebookSessions(self, request):
        self.requests.append(request)
        return self._pages.pop(0)


class SDKError(Exception):
    def get_code(self):
        return "UnauthorizedOperation"

    def get_request_id(self):
        return "req-err"


def _patch_sdk(monkeypatch, client):
    """Hand the module its models/client class and the client itself."""
    monkeypatch.setattr(dlc_notebook_session_info, "_load", lambda: (
        FakeModels, types.SimpleNamespace(DlcClient=lambda *args: client)))
    monkeypatch.setattr(TencentCloudModule, "create_client",
                        lambda self, client_class, endpoint: client)


def test_run_module_fetches_all_session_pages(monkeypatch):
    client = FakeClient([
        FakeResponse([FakeItem("a"), FakeItem("b")], 3, "r1"),
        FakeResponse([FakeItem("c")], 3, "r2"),
    ])
    _patch_sdk(monkeypatch, client)
    module_args(region="ap-guangzhou", **params())

    payload = run(dlc_notebook_session_info.run_module)

    assert payload["changed"] is False
    assert [item["Name"] for item in payload["sessions"]] == ["a", "b", "c"]
    assert payload["total_count"] == 3
    assert payload["request_id"] == "r2"
    assert [request.Offset for request in client.requests] == [0, 2]
    assert [request.Limit for request in client.requests] == [2, 2]


def test_run_module_returns_empty_when_no_sessions(monkeypatch):
    client = FakeClient([FakeResponse([], 0, "r-empty")])
    _patch_sdk(monkeypatch, client)
    module_args(region="ap-guangzhou", **absent_filter_params())

    payload = run(dlc_notebook_session_info.run_module)

    assert payload["sessions"] == []
    assert payload["total_count"] == 0
    assert payload["request_id"] == "r-empty"
    assert len(client.requests) == 1


def test_run_module_validates_page_size_range(monkeypatch):
    _patch_sdk(monkeypatch, FakeClient([]))
    module_args(region="ap-guangzhou", **params(page_size=200))

    with pytest.raises(AnsibleFailJson) as failure:
        run(dlc_notebook_session_info.run_module)

    assert failure.value.args[0]["msg"] == "page_size must be between 1 and 100"


def test_run_module_fails_cleanly_on_sdk_error(monkeypatch):
    class FailingClient:
        def DescribeNotebookSessions(self, request):
            raise SDKError("api exploded")

    _patch_sdk(monkeypatch, FailingClient())
    module_args(region="ap-guangzhou", **params())

    with pytest.raises(AnsibleFailJson) as failure:
        run(dlc_notebook_session_info.run_module)

    payload = failure.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert payload["error"] == "api exploded"
    assert payload["error_code"] == "UnauthorizedOperation"
    assert payload["request_id"] == "req-err"
