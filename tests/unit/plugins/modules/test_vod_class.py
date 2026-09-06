"""Unit tests for the vod_class write module (helpers + run_module).

Creates and deletes VOD media classes through DescribeAllClass,
CreateClass and DeleteClass. A class is matched by its name and parent
class id; there is no multi-match failure (first match wins) and every
field is create-only — the module never renames or moves an existing
class. The find/create/delete requests all thread an optional SubAppId,
and the module does not re-find after a create (the ClassId returned by
CreateClass is reported directly).
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import vod_class as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)


class _SdkError(Exception):
    """Stand-in for TencentCloudSDKException carrying a code/request id."""

    def __init__(self, code, message="", request_id=None):
        super(_SdkError, self).__init__(message)
        self._code = code
        self._request_id = request_id

    def get_code(self):
        return self._code

    def get_request_id(self):
        return self._request_id


def _cls(**overrides):
    """API-shaped class-info dict; fresh copy per call."""
    item = {
        "ClassId": 101,
        "ClassName": "marketing",
        "ParentId": -1,
        "Level": 0,
    }
    item.update(overrides)
    return item


def _params(**overrides):
    """Module parameters pre-filled from the argument spec defaults."""
    params = {
        "class_name": "marketing",
        "state": "present",
        "parent_id": -1,
        "sub_app_id": None,
    }
    params.update(overrides)
    return params


def _run_args(**extra):
    """module_args() pre-filled with every non-None module parameter."""
    params = _params(**extra)
    args = {k: v for k, v in params.items() if v is not None}
    for key, value in extra.items():
        if key.startswith("_"):
            args[key] = value
    return module_args(**args)


class FakeModule(object):
    """Minimal stand-in for helpers that need sdk_call / fail_json."""

    def __init__(self, params=None):
        self.params = params or {}
        self.sdk_calls = []

    def sdk_call(self, operation, request):
        self.sdk_calls.append((operation, request))
        return operation(request)

    def fail_json(self, **kwargs):
        raise AnsibleFailJson(kwargs)


class FakeVodClient(object):
    """In-memory VodClient stand-in storing class dicts.

    DescribeAllClass returns ClassInfoSet of serializable items; a client
    constructed with ``classes=None`` emulates a response without the
    ClassInfoSet field. CreateClass synthesizes sequential ClassIds and
    may omit the ClassId attribute (``no_class_id=True``); DeleteClass
    removes by id.
    """

    def __init__(self, classes=None, no_class_id=False):
        self.classes = None if classes is None else [dict(c) for c in classes]
        self.no_class_id = no_class_id
        self.calls = []
        self._seq = 2001

    def _record(self, name, request):
        self.calls.append((name, request))
        return request

    def DescribeAllClass(self, request):
        self._record("DescribeAllClass", request)
        if self.classes is None:
            return SimpleNamespace(ClassInfoSet=None, RequestId="req-fake")
        return SimpleNamespace(
            ClassInfoSet=[FakeResource(dict(c)) for c in self.classes],
            RequestId="req-fake",
        )

    def CreateClass(self, request):
        self._record("CreateClass", request)
        if self.no_class_id:
            return SimpleNamespace(RequestId="req-fake")
        class_id = self._seq
        self._seq += 1
        stored = {
            "ClassId": class_id,
            "ClassName": request.ClassName,
            "ParentId": request.ParentId,
            "SubAppId": getattr(request, "SubAppId", None),
        }
        if self.classes is not None:
            self.classes.append(stored)
        return SimpleNamespace(ClassId=class_id, RequestId="req-fake")

    def DeleteClass(self, request):
        self._record("DeleteClass", request)
        if self.classes is not None:
            self.classes = [c for c in self.classes if c["ClassId"] != request.ClassId]
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake):
    """Wire the shared monkeypatches and return the fake client."""
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(
        mod,
        "_load_vod",
        lambda: (FakeModels(), SimpleNamespace(VodClient=object)),
    )
    monkeypatch.setattr(
        TencentCloudModule,
        "create_client",
        lambda self, client_class, endpoint: fake,
    )
    return fake


class _BoomClient(object):
    """Every SDK call raises, so the module's wrapped error path is hit."""

    def __getattr__(self, name):
        def boom(*args, **kwargs):
            raise _SdkError("AuthFailure", "auth rejected", request_id="req-err")

        return boom


# ---------------------------------------------------------------------------
# find_class helper tests
# ---------------------------------------------------------------------------


def test_find_sets_sub_app_id_when_given():
    fake = FakeVodClient([_cls()])
    module = FakeModule()
    value = mod.find_class(module, fake, FakeModels(), "marketing", -1, 1688)
    assert value["ClassId"] == 101
    assert module.sdk_calls[0][1].SubAppId == 1688


def test_find_omits_sub_app_id_when_none():
    fake = FakeVodClient([_cls()])
    module = FakeModule()
    mod.find_class(module, fake, FakeModels(), "marketing", -1, None)
    assert not hasattr(module.sdk_calls[0][1], "SubAppId")


def test_find_returns_matching_class():
    fake = FakeVodClient([_cls(), _cls(ClassId=102, ClassName="2026", ParentId=101)])
    module = FakeModule()
    value = mod.find_class(module, fake, FakeModels(), "2026", 101, None)
    assert value["ClassId"] == 102


def test_find_no_match_returns_none():
    fake = FakeVodClient([_cls(ClassId=102, ClassName="2026", ParentId=101)])
    module = FakeModule()
    assert mod.find_class(module, fake, FakeModels(), "marketing", -1, None) is None


def test_find_same_name_under_other_parent_is_not_a_match():
    fake = FakeVodClient([_cls(ClassName="marketing", ParentId=777)])
    module = FakeModule()
    assert mod.find_class(module, fake, FakeModels(), "marketing", -1, None) is None


def test_find_returns_first_match_when_duplicates_exist():
    fake = FakeVodClient([_cls(), _cls(ClassId=999)])
    module = FakeModule()
    value = mod.find_class(module, fake, FakeModels(), "marketing", -1, None)
    assert value["ClassId"] == 101


def test_find_tolerates_absent_class_info_set():
    fake = FakeVodClient(classes=None)
    module = FakeModule()
    assert mod.find_class(module, fake, FakeModels(), "marketing", -1, None) is None


# ---------------------------------------------------------------------------
# run_module main-path tests
# ---------------------------------------------------------------------------


def test_absent_noop_when_missing(monkeypatch):
    fake = FakeVodClient([])
    _make_module(monkeypatch, fake)
    _run_args(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["msg"] == "VOD class not present"
    assert result["class_name"] == "marketing"
    assert result["parent_id"] == -1
    assert "class_id" not in result
    assert [c[0] for c in fake.calls] == ["DescribeAllClass"]


def test_absent_check_mode_delete_is_dry_run(monkeypatch):
    fake = FakeVodClient([_cls()])
    _make_module(monkeypatch, fake)
    _run_args(state="absent", _ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["msg"] == "Would delete VOD class 101"
    assert result["class_id"] == 101
    assert result["diff"]["before"]["ClassName"] == "marketing"
    assert result["diff"]["after"] is None
    assert [c[0] for c in fake.calls] == ["DescribeAllClass"]
    assert fake.classes == [_cls()]


def test_absent_deletes_class(monkeypatch):
    fake = FakeVodClient([_cls()])
    _make_module(monkeypatch, fake)
    _run_args(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["msg"] == "Deleted VOD class 101"
    assert result["class_id"] == 101
    assert [c[0] for c in fake.calls] == ["DescribeAllClass", "DeleteClass"]
    assert fake.calls[1][1].ClassId == 101
    assert not hasattr(fake.calls[1][1], "SubAppId")
    assert fake.classes == []


def test_absent_delete_threads_sub_app_id(monkeypatch):
    fake = FakeVodClient([_cls()])
    _make_module(monkeypatch, fake)
    _run_args(state="absent", sub_app_id=1688)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["msg"] == "Deleted VOD class 101"
    assert [c[0] for c in fake.calls] == ["DescribeAllClass", "DeleteClass"]
    assert fake.calls[0][1].SubAppId == 1688
    assert fake.calls[1][1].SubAppId == 1688


def test_present_noop_when_class_exists(monkeypatch):
    fake = FakeVodClient([_cls()])
    _make_module(monkeypatch, fake)
    _run_args()
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["msg"] == "VOD class already present"
    assert result["class_id"] == 101
    assert [c[0] for c in fake.calls] == ["DescribeAllClass"]


def test_present_check_mode_create_is_dry_run(monkeypatch):
    fake = FakeVodClient([])
    _make_module(monkeypatch, fake)
    _run_args(_ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["msg"] == "Would create VOD class marketing"
    assert "class_id" not in result
    assert result["diff"]["before"] is None
    assert result["diff"]["after"] == {"ClassName": "marketing", "ParentId": -1}
    assert [c[0] for c in fake.calls] == ["DescribeAllClass"]
    assert fake.classes == []


def test_present_creates_class(monkeypatch):
    fake = FakeVodClient([])
    _make_module(monkeypatch, fake)
    _run_args()
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["msg"] == "VOD class created"
    assert result["class_id"] == 2001
    assert [c[0] for c in fake.calls] == ["DescribeAllClass", "CreateClass"]
    created = fake.calls[1][1]
    assert created.ClassName == "marketing"
    assert created.ParentId == -1
    assert not hasattr(created, "SubAppId")
    assert fake.classes == [
        {"ClassId": 2001, "ClassName": "marketing", "ParentId": -1, "SubAppId": None}
    ]


def test_present_create_threads_sub_app_id(monkeypatch):
    fake = FakeVodClient([])
    _make_module(monkeypatch, fake)
    _run_args(sub_app_id=1688)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["class_id"] == 2001
    assert [c[0] for c in fake.calls] == ["DescribeAllClass", "CreateClass"]
    assert fake.calls[0][1].SubAppId == 1688
    assert fake.calls[1][1].SubAppId == 1688
    assert fake.classes[0]["SubAppId"] == 1688


def test_present_create_response_without_class_id(monkeypatch):
    fake = FakeVodClient([], no_class_id=True)
    _make_module(monkeypatch, fake)
    _run_args()
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["msg"] == "VOD class created"
    assert result["class_id"] is None


def test_sdk_failure_reports_error_payload(monkeypatch):
    fake = _BoomClient()
    _make_module(monkeypatch, fake)
    _run_args(state="absent")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert payload["error"] == "auth rejected"
    assert payload["error_code"] == "AuthFailure"
    assert payload["request_id"] == "req-err"


def test_main_entrypoint_runs_module(monkeypatch):
    fake = FakeVodClient([])
    _make_module(monkeypatch, fake)
    _run_args(state="absent")
    result = run(mod.main)
    assert result["changed"] is False
    assert result["msg"] == "VOD class not present"
