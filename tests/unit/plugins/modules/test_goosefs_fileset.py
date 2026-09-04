"""Unit tests for the goosefs_fileset write module (helpers + run_module).

Creates, updates and deletes GooseFS filesets and their quota limits. A
fileset is looked up through DescribeFilesets: when ``fileset_id`` is
given the request filters by FilesetIds, else by FilesetDirs when
``directory`` is given, else the full list is scanned for ``name``.
FsetName and FsetDir are immutable on an existing fileset; quota and
audit drift become UpdateFileset. Creation requires name + directory.
Create/update always send the fully merged effective target values.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import goosefs_fileset as mod
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


def _fileset(**overrides):
    """API-shaped fileset dict; fresh copy per call."""
    item = {
        "FileSystemId": "x-c60-abc",
        "FsetId": "fset-1001",
        "FsetName": "analytics",
        "FsetDir": "/analytics",
        "QuotaSizeLimit": "1099511627776",
        "QuotaFilesLimit": "1000000",
        "AuditState": "on",
    }
    item.update(overrides)
    return item


def _params(**overrides):
    """Module parameters pre-filled from the argument spec defaults."""
    params = {
        "state": "present",
        "file_system_id": "x-c60-abc",
        "fileset_id": None,
        "name": "analytics",
        "directory": "/analytics",
        "quota_size_limit": "1099511627776",
        "quota_files_limit": "1000000",
        "audit_state": None,
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
        self.params = params or _params()
        self.sdk_calls = []

    def sdk_call(self, operation, request):
        self.sdk_calls.append((operation, request))
        return operation(request)

    def fail_json(self, **kwargs):
        raise AnsibleFailJson(kwargs)


class FakeGoosefsClient(object):
    """In-memory GoosefsClient stand-in storing fileset dicts.

    DescribeFilesets mirrors the module's server-side filters: FilesetIds
    wins, then FilesetDirs, otherwise the whole file system's list;
    CreateFileset synthesizes sequential FsetIds; Update rewrites quota +
    audit fields; Delete removes by FsetId.
    """

    def __init__(self, filesets=None):
        self.filesets = [dict(f) for f in (filesets or [])]
        self.calls = []
        self._seq = 2001

    def _record(self, name, request):
        self.calls.append((name, request))
        return request

    def DescribeFilesets(self, request):
        self._record("DescribeFilesets", request)
        values = [f for f in self.filesets if f["FileSystemId"] == request.FileSystemId]
        ids = getattr(request, "FilesetIds", None) or []
        dirs = getattr(request, "FilesetDirs", None) or []
        if ids:
            values = [f for f in values if f["FsetId"] in ids]
        elif dirs:
            values = [f for f in values if f["FsetDir"] in dirs]
        return SimpleNamespace(
            FilesetList=[FakeResource(dict(f)) for f in values],
            RequestId="req-fake",
        )

    def CreateFileset(self, request):
        self._record("CreateFileset", request)
        stored = {
            "FileSystemId": request.FileSystemId,
            "FsetId": "fset-%04d" % self._seq,
            "FsetName": request.FsetName,
            "FsetDir": request.FsetDir,
            "QuotaSizeLimit": getattr(request, "QuotaSizeLimit", None),
            "QuotaFilesLimit": getattr(request, "QuotaFilesLimit", None),
            "AuditState": getattr(request, "AuditState", None),
        }
        self._seq += 1
        self.filesets.append(stored)
        return SimpleNamespace(FsetId=stored["FsetId"], RequestId="req-fake")

    def UpdateFileset(self, request):
        self._record("UpdateFileset", request)
        for stored in self.filesets:
            if stored["FileSystemId"] == request.FileSystemId and stored["FsetId"] == request.FsetId:
                stored["QuotaSizeLimit"] = getattr(request, "QuotaSizeLimit", None)
                stored["QuotaFilesLimit"] = getattr(request, "QuotaFilesLimit", None)
                stored["AuditState"] = getattr(request, "AuditState", None)
        return SimpleNamespace(RequestId="req-fake")

    def DeleteFileset(self, request):
        self._record("DeleteFileset", request)
        self.filesets = [
            f
            for f in self.filesets
            if not (f["FileSystemId"] == request.FileSystemId and f["FsetId"] == request.FsetId)
        ]
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake):
    """Wire the shared monkeypatches and return the fake client."""
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(
        mod,
        "_load",
        lambda: (FakeModels(), SimpleNamespace(GoosefsClient=object)),
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
# request-builder / helper tests
# ---------------------------------------------------------------------------


def test_describe_request_filters_by_fileset_id():
    request = mod.describe_request(FakeModels(), _params(fileset_id="fset-1001", name=None, directory=None))
    assert request.FileSystemId == "x-c60-abc"
    assert request.FilesetIds == ["fset-1001"]
    assert not hasattr(request, "FilesetDirs")


def test_describe_request_filters_by_directory():
    request = mod.describe_request(FakeModels(), _params(fileset_id=None, name=None, directory="/analytics"))
    assert request.FilesetDirs == ["/analytics"]
    assert not hasattr(request, "FilesetIds")


def test_describe_request_lists_all_when_name_only():
    request = mod.describe_request(FakeModels(), _params(fileset_id=None, directory=None))
    assert not hasattr(request, "FilesetIds")
    assert not hasattr(request, "FilesetDirs")


def test_create_request_carries_all_fields():
    request = mod.create_request(
        FakeModels(),
        _params(quota_size_limit="2048", quota_files_limit="99", audit_state="off"),
    )
    assert request.FileSystemId == "x-c60-abc"
    assert request.FsetName == "analytics"
    assert request.FsetDir == "/analytics"
    assert request.QuotaSizeLimit == "2048"
    assert request.QuotaFilesLimit == "99"
    assert request.AuditState == "off"


def test_update_request_carries_quota_and_audit_only():
    request = mod.update_request(FakeModels(), _params(quota_size_limit="2048", audit_state="off"), "fset-1001")
    assert request.FileSystemId == "x-c60-abc"
    assert request.FsetId == "fset-1001"
    assert request.QuotaSizeLimit == "2048"
    assert request.QuotaFilesLimit == "1000000"
    assert request.AuditState == "off"
    assert not hasattr(request, "FsetName")
    assert not hasattr(request, "FsetDir")


def test_delete_request_carries_id():
    request = mod.delete_request(FakeModels(), _params(), "fset-1001")
    assert request.FileSystemId == "x-c60-abc"
    assert request.FsetId == "fset-1001"


def test_comparable_selects_five_keys():
    value = mod.comparable(_fileset())
    assert set(value.keys()) == {
        "FsetName",
        "FsetDir",
        "QuotaSizeLimit",
        "QuotaFilesLimit",
        "AuditState",
    }
    assert value["FsetName"] == "analytics"


def test_find_by_fileset_id(monkeypatch):
    fake = FakeGoosefsClient([_fileset(), _fileset(FsetId="fset-1002", FsetName="other")])
    _make_module(monkeypatch, fake)
    module = FakeModule(_params(fileset_id="fset-1002", name=None, directory=None))
    value = mod.find(module, fake, FakeModels(), module.params)
    assert value["FsetId"] == "fset-1002"


def test_find_by_directory(monkeypatch):
    fake = FakeGoosefsClient([_fileset()])
    _make_module(monkeypatch, fake)
    module = FakeModule(_params(fileset_id=None, name=None, directory="/analytics"))
    value = mod.find(module, fake, FakeModels(), module.params)
    assert value["FsetId"] == "fset-1001"


def test_find_by_name_scans_full_list(monkeypatch):
    fake = FakeGoosefsClient([_fileset(), _fileset(FsetId="fset-1002", FsetName="other", FsetDir="/other")])
    _make_module(monkeypatch, fake)
    module = FakeModule(_params(fileset_id=None, directory=None))
    value = mod.find(module, fake, FakeModels(), module.params)
    assert value["FsetId"] == "fset-1001"


def test_find_no_match_returns_none(monkeypatch):
    fake = FakeGoosefsClient([_fileset(FsetName="other")])
    _make_module(monkeypatch, fake)
    module = FakeModule(_params(fileset_id=None, directory=None, name="missing"))
    assert mod.find(module, fake, FakeModels(), module.params) is None


def test_find_multiple_name_matches_fails(monkeypatch):
    fake = FakeGoosefsClient([_fileset(), _fileset(FsetId="fset-1002", FsetDir="/analytics-copy")])
    _make_module(monkeypatch, fake)
    module = FakeModule(_params(fileset_id=None, directory=None))
    with pytest.raises(AnsibleFailJson) as exc:
        mod.find(module, fake, FakeModels(), module.params)
    assert "Multiple GooseFS filesets matched" in exc.value.args[0]["msg"]


# ---------------------------------------------------------------------------
# run_module main-path tests
# ---------------------------------------------------------------------------


def test_absent_noop_when_missing(monkeypatch):
    fake = FakeGoosefsClient()
    _make_module(monkeypatch, fake)
    _run_args(state="absent", name=None, directory="/gone")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["fileset"] is None
    assert [c[0] for c in fake.calls] == ["DescribeFilesets"]


def test_absent_check_mode_delete_is_dry_run(monkeypatch):
    fake = FakeGoosefsClient([_fileset()])
    _make_module(monkeypatch, fake)
    _run_args(state="absent", _ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["fileset"] is None
    assert [c[0] for c in fake.calls] == ["DescribeFilesets"]


def test_absent_deletes_fileset(monkeypatch):
    fake = FakeGoosefsClient([_fileset()])
    _make_module(monkeypatch, fake)
    _run_args(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["fileset"] is None
    assert [c[0] for c in fake.calls] == ["DescribeFilesets", "DeleteFileset"]
    assert fake.calls[1][1].FsetId == "fset-1001"
    assert fake.filesets == []


def test_create_requires_name_and_directory(monkeypatch):
    fake = FakeGoosefsClient()
    _make_module(monkeypatch, fake)
    _run_args(fileset_id="fset-ghost", name=None, directory=None)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "creation parameters are required" in payload["msg"]
    assert payload["missing"] == ["name", "directory"]


def test_create_requires_directory_when_name_given(monkeypatch):
    fake = FakeGoosefsClient()
    _make_module(monkeypatch, fake)
    _run_args(fileset_id="fset-ghost", name="analytics", directory=None)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["missing"] == ["directory"]


def test_present_noop(monkeypatch):
    fake = FakeGoosefsClient([_fileset()])
    _make_module(monkeypatch, fake)
    _run_args()
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["fileset"]["FsetId"] == "fset-1001"
    assert [c[0] for c in fake.calls] == ["DescribeFilesets"]


def test_present_check_mode_create_reports_target(monkeypatch):
    fake = FakeGoosefsClient()
    _make_module(monkeypatch, fake)
    _run_args(_ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["fileset"]["FsetName"] == "analytics"
    assert result["fileset"]["FsetDir"] == "/analytics"
    assert result["fileset"]["QuotaSizeLimit"] == "1099511627776"
    assert [c[0] for c in fake.calls] == ["DescribeFilesets"]


def test_present_create_creates_and_confirms(monkeypatch):
    fake = FakeGoosefsClient()
    _make_module(monkeypatch, fake)
    _run_args()
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["fileset"]["FsetId"] == "fset-2001"
    assert [c[0] for c in fake.calls] == ["DescribeFilesets", "CreateFileset", "DescribeFilesets"]
    assert fake.calls[1][1].FsetName == "analytics"
    assert fake.calls[1][1].FsetDir == "/analytics"


def test_present_quota_drift_triggers_update(monkeypatch):
    fake = FakeGoosefsClient([_fileset()])
    _make_module(monkeypatch, fake)
    _run_args(quota_size_limit="2048")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["fileset"]["QuotaSizeLimit"] == "2048"
    assert [c[0] for c in fake.calls] == ["DescribeFilesets", "UpdateFileset", "DescribeFilesets"]
    assert fake.calls[1][1].FsetId == "fset-1001"
    assert fake.calls[1][1].QuotaFilesLimit == "1000000"


def test_present_audit_drift_triggers_update(monkeypatch):
    fake = FakeGoosefsClient([_fileset()])
    _make_module(monkeypatch, fake)
    _run_args(audit_state="off")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["fileset"]["AuditState"] == "off"


def test_present_immutable_name_drift_fails(monkeypatch):
    fake = FakeGoosefsClient([_fileset()])
    _make_module(monkeypatch, fake)
    _run_args(fileset_id="fset-1001", name="renamed", directory=None)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "Immutable fields cannot be changed" in payload["msg"]
    assert payload["replacement_required"] is True
    assert payload["immutable_changes"] == {
        "FsetName": {"before": "analytics", "after": "renamed"}
    }
    assert [c[0] for c in fake.calls] == ["DescribeFilesets"]


def test_present_immutable_directory_drift_fails(monkeypatch):
    fake = FakeGoosefsClient([_fileset()])
    _make_module(monkeypatch, fake)
    _run_args(fileset_id="fset-1001", directory="/moved", name=None)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["immutable_changes"] == {
        "FsetDir": {"before": "/analytics", "after": "/moved"}
    }


def test_present_check_mode_update_reports_target(monkeypatch):
    fake = FakeGoosefsClient([_fileset()])
    _make_module(monkeypatch, fake)
    _run_args(quota_size_limit="2048", _ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["fileset"]["QuotaSizeLimit"] == "2048"
    assert [c[0] for c in fake.calls] == ["DescribeFilesets"]


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
