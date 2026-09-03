"""Unit tests for the chdfs_file_system write module (helpers + run_module).

Creates, updates and deletes CHDFS file systems. A file system is found
by ``file_system_id`` when given, otherwise by exact ``name`` match;
find() walks the marker-paginated DescribeFileSystems response and fails
on multiple name matches. Present drift on any of the seven mutable
fields (name/description/quota/super users/posix acl/ranger flags)
becomes ModifyFileSystem; absent deletes by id. Everything is wrapped in
sdk_error_payload so SDK errors surface as a uniform failure envelope.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import chdfs_file_system as mod
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


def _fs(**overrides):
    """API-shaped file system dict; fresh copy per call."""
    item = {
        "FileSystemId": "f4mp1e-0000",
        "FileSystemName": "analytics",
        "Description": "ETL output",
        "CapacityQuota": 1099511627776,
        "SuperUsers": ["root"],
        "PosixAcl": True,
        "EnableRanger": False,
        "RangerServiceAddresses": [],
    }
    item.update(overrides)
    return item


def _params(**overrides):
    """Module parameters pre-filled from the argument spec defaults."""
    params = {
        "state": "present",
        "file_system_id": None,
        "name": "analytics",
        "description": None,
        "capacity_quota": None,
        "super_users": None,
        "posix_acl": None,
        "root_inode_user": None,
        "root_inode_group": None,
        "enable_ranger": None,
        "ranger_service_addresses": None,
        "tags": None,
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


class FakeChdfsClient(object):
    """In-memory ChdfsClient stand-in storing file system dicts.

    DescribeFileSystems pages by marker with a configurable page size
    (page 1 of 2 returns IsOver=False plus a NextFileSystemIdMarker);
    CreateFileSystem synthesizes ``f4mp1e-NNNN`` ids and returns the
    ``FileSystem.FileSystemId`` envelope the module reads; Modify updates
    the seven mutable fields; Delete removes by id.
    """

    def __init__(self, file_systems=None, page_size=None):
        self.file_systems = [dict(f) for f in (file_systems or [])]
        self.page_size = page_size
        self.calls = []
        self._seq = 1

    def _record(self, name, request):
        self.calls.append((name, request))
        return request

    def DescribeFileSystems(self, request):
        self._record("DescribeFileSystems", request)
        ordered = sorted(self.file_systems, key=lambda f: f["FileSystemId"])
        marker = getattr(request, "FileSystemIdMarker", None)
        if marker is None:
            remaining = ordered
        else:
            # Resume strictly after the marker id (the real API's page token
            # is the last FileSystemId the previous page returned).
            remaining = []
            past_marker = False
            for stored in ordered:
                if past_marker:
                    remaining.append(stored)
                elif stored["FileSystemId"] == marker:
                    past_marker = True
        if not self.page_size or len(remaining) <= self.page_size:
            return SimpleNamespace(
                FileSystems=[FakeResource(dict(f)) for f in remaining],
                NextFileSystemIdMarker=None,
                IsOver=True,
                RequestId="req-fake",
            )
        page = remaining[: self.page_size]
        return SimpleNamespace(
            FileSystems=[FakeResource(dict(f)) for f in page],
            NextFileSystemIdMarker=page[-1]["FileSystemId"],
            IsOver=False,
            RequestId="req-fake",
        )

    def CreateFileSystem(self, request):
        self._record("CreateFileSystem", request)
        stored = {
            "FileSystemId": "f4mp1e-%04d" % self._seq,
            "FileSystemName": request.FileSystemName,
            "Description": getattr(request, "Description", None),
            "CapacityQuota": getattr(request, "CapacityQuota", None),
            "SuperUsers": list(getattr(request, "SuperUsers", None) or []),
            "PosixAcl": bool(getattr(request, "PosixAcl", None)),
            "EnableRanger": bool(getattr(request, "EnableRanger", None)),
            "RangerServiceAddresses": list(getattr(request, "RangerServiceAddresses", None) or []),
        }
        self._seq += 1
        self.file_systems.append(stored)
        return SimpleNamespace(
            FileSystem=SimpleNamespace(FileSystemId=stored["FileSystemId"]),
            RequestId="req-fake",
        )

    def ModifyFileSystem(self, request):
        self._record("ModifyFileSystem", request)
        for stored in self.file_systems:
            if stored["FileSystemId"] == request.FileSystemId:
                stored["FileSystemName"] = request.FileSystemName
                stored["Description"] = getattr(request, "Description", None)
                stored["CapacityQuota"] = getattr(request, "CapacityQuota", None)
                stored["SuperUsers"] = list(getattr(request, "SuperUsers", None) or [])
                stored["PosixAcl"] = bool(getattr(request, "PosixAcl", None))
                stored["EnableRanger"] = bool(getattr(request, "EnableRanger", None))
                stored["RangerServiceAddresses"] = list(
                    getattr(request, "RangerServiceAddresses", None) or []
                )
        return SimpleNamespace(RequestId="req-fake")

    def DeleteFileSystem(self, request):
        self._record("DeleteFileSystem", request)
        self.file_systems = [
            f for f in self.file_systems if f["FileSystemId"] != request.FileSystemId
        ]
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake):
    """Wire the shared monkeypatches and return the fake client."""
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(
        mod,
        "_load",
        lambda: (FakeModels(), SimpleNamespace(ChdfsClient=object)),
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


def test_tags_sorts_and_builds_tag_models():
    tags = mod._tags(FakeModels(), {"z": "1", "a": "2"})
    assert [(t.Key, t.Value) for t in tags] == [("a", "2"), ("z", "1")]


def test_tags_empty_when_none():
    assert mod._tags(FakeModels(), None) == []


def test_describe_request_sets_marker():
    request = mod.describe_request(FakeModels(), marker="fs-x")
    assert request.FileSystemIdMarker == "fs-x"


def test_describe_request_defaults_marker_none():
    request = mod.describe_request(FakeModels())
    assert request.FileSystemIdMarker is None


def test_create_request_carries_all_fields():
    request = mod.create_request(
        FakeModels(),
        _params(
            description="ETL output",
            capacity_quota=1024,
            super_users=["root", "hdfs"],
            posix_acl=True,
            root_inode_user="u1",
            root_inode_group="g1",
            enable_ranger=True,
            ranger_service_addresses=["host:9000"],
            tags={"env": "prod"},
        ),
    )
    assert request.FileSystemName == "analytics"
    assert request.Description == "ETL output"
    assert request.CapacityQuota == 1024
    assert request.SuperUsers == ["root", "hdfs"]
    assert request.PosixAcl is True
    assert request.RootInodeUser == "u1"
    assert request.RootInodeGroup == "g1"
    assert request.EnableRanger is True
    assert request.RangerServiceAddresses == ["host:9000"]
    assert [(t.Key, t.Value) for t in request.Tags] == [("env", "prod")]


def test_update_request_carries_mutable_fields_only():
    request = mod.update_request(FakeModels(), "f4mp1e-0000", _fs())
    assert request.FileSystemId == "f4mp1e-0000"
    assert request.FileSystemName == "analytics"
    assert request.Description == "ETL output"
    assert request.CapacityQuota == 1099511627776
    assert request.SuperUsers == ["root"]
    assert request.PosixAcl is True
    assert request.EnableRanger is False
    assert request.RangerServiceAddresses == []
    assert not hasattr(request, "Tags")


def test_delete_request_sets_id():
    request = mod.delete_request(FakeModels(), "f4mp1e-0000")
    assert request.FileSystemId == "f4mp1e-0000"


def test_comparable_selects_seven_mutable_keys():
    value = mod.comparable(_fs())
    assert set(value.keys()) == {
        "FileSystemName",
        "Description",
        "CapacityQuota",
        "SuperUsers",
        "PosixAcl",
        "EnableRanger",
        "RangerServiceAddresses",
    }
    assert value["FileSystemName"] == "analytics"


def test_find_matches_by_id(monkeypatch):
    fake = FakeChdfsClient([_fs(), _fs(FileSystemId="f4mp1e-0001", FileSystemName="other")])
    _make_module(monkeypatch, fake)
    module = FakeModule(_params(file_system_id="f4mp1e-0001"))
    value = mod.find(module, fake, FakeModels(), module.params)
    assert value["FileSystemId"] == "f4mp1e-0001"


def test_find_matches_by_name(monkeypatch):
    fake = FakeChdfsClient([_fs()])
    _make_module(monkeypatch, fake)
    module = FakeModule(_params())
    value = mod.find(module, fake, FakeModels(), module.params)
    assert value["FileSystemId"] == "f4mp1e-0000"


def test_find_no_match_returns_none(monkeypatch):
    fake = FakeChdfsClient([_fs(FileSystemName="other")])
    _make_module(monkeypatch, fake)
    module = FakeModule(_params(name="missing"))
    assert mod.find(module, fake, FakeModels(), module.params) is None


def test_find_multiple_name_matches_fails(monkeypatch):
    fake = FakeChdfsClient([_fs(), _fs(FileSystemId="f4mp1e-0001")])
    _make_module(monkeypatch, fake)
    module = FakeModule(_params())
    with pytest.raises(AnsibleFailJson) as exc:
        mod.find(module, fake, FakeModels(), module.params)
    assert "Multiple CHDFS file systems matched" in exc.value.args[0]["msg"]


def test_find_paginates_when_not_over(monkeypatch):
    # The matched system is only on the second page (page size 1).
    fake = FakeChdfsClient(
        [
            _fs(FileSystemId="f4mp1e-0000", FileSystemName="page1"),
            _fs(FileSystemId="f4mp1e-0001", FileSystemName="target"),
        ],
        page_size=1,
    )
    _make_module(monkeypatch, fake)
    module = FakeModule(_params(name="target"))
    value = mod.find(module, fake, FakeModels(), module.params)
    assert value["FileSystemId"] == "f4mp1e-0001"
    assert [c[0] for c in fake.calls] == ["DescribeFileSystems", "DescribeFileSystems"]


# ---------------------------------------------------------------------------
# run_module main-path tests
# ---------------------------------------------------------------------------


def test_absent_noop_when_missing(monkeypatch):
    fake = FakeChdfsClient()
    _make_module(monkeypatch, fake)
    _run_args(state="absent", name="missing")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["file_system"] is None
    assert [c[0] for c in fake.calls] == ["DescribeFileSystems"]


def test_absent_check_mode_delete_is_dry_run(monkeypatch):
    fake = FakeChdfsClient([_fs()])
    _make_module(monkeypatch, fake)
    _run_args(state="absent", _ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["file_system"] is None
    assert [c[0] for c in fake.calls] == ["DescribeFileSystems"]


def test_absent_deletes_by_id(monkeypatch):
    fake = FakeChdfsClient([_fs()])
    _make_module(monkeypatch, fake)
    _run_args(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["file_system"] is None
    assert [c[0] for c in fake.calls] == ["DescribeFileSystems", "DeleteFileSystem"]
    assert fake.calls[1][1].FileSystemId == "f4mp1e-0000"
    assert fake.file_systems == []


def test_create_requires_name(monkeypatch):
    fake = FakeChdfsClient()
    _make_module(monkeypatch, fake)
    # file_system_id passes required_one_of, but with no current match and
    # no name the module cannot create.
    _run_args(file_system_id="f4mp1e-ghost", name=None)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "name is required to create" in exc.value.args[0]["msg"]


def test_present_noop_by_name(monkeypatch):
    fake = FakeChdfsClient([_fs()])
    _make_module(monkeypatch, fake)
    _run_args()
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["file_system"]["FileSystemId"] == "f4mp1e-0000"
    assert [c[0] for c in fake.calls] == ["DescribeFileSystems"]


def test_present_check_mode_create_is_dry_run(monkeypatch):
    fake = FakeChdfsClient()
    _make_module(monkeypatch, fake)
    _run_args(capacity_quota=1024, posix_acl=True, _ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["file_system"]["FileSystemName"] == "analytics"
    assert result["file_system"]["CapacityQuota"] == 1024
    assert result["file_system"]["PosixAcl"] is True
    assert [c[0] for c in fake.calls] == ["DescribeFileSystems"]


def test_present_create_creates_and_confirms(monkeypatch):
    fake = FakeChdfsClient()
    _make_module(monkeypatch, fake)
    _run_args(description="fresh", capacity_quota=1024)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["file_system"]["FileSystemId"] == "f4mp1e-0001"
    assert result["file_system"]["FileSystemName"] == "analytics"
    assert [c[0] for c in fake.calls] == [
        "DescribeFileSystems",
        "CreateFileSystem",
        "DescribeFileSystems",
    ]
    assert fake.calls[1][1].FileSystemName == "analytics"


def test_present_description_drift_triggers_update(monkeypatch):
    fake = FakeChdfsClient([_fs()])
    _make_module(monkeypatch, fake)
    _run_args(description="new description")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["file_system"]["Description"] == "new description"
    assert [c[0] for c in fake.calls] == [
        "DescribeFileSystems",
        "ModifyFileSystem",
        "DescribeFileSystems",
    ]
    assert fake.calls[1][1].FileSystemId == "f4mp1e-0000"
    assert fake.calls[1][1].Description == "new description"


def test_present_capacity_quota_drift_triggers_update(monkeypatch):
    fake = FakeChdfsClient([_fs()])
    _make_module(monkeypatch, fake)
    _run_args(capacity_quota=2048)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["file_system"]["CapacityQuota"] == 2048


def test_present_super_users_drift_triggers_update(monkeypatch):
    fake = FakeChdfsClient([_fs()])
    _make_module(monkeypatch, fake)
    _run_args(super_users=["root", "etl"])
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["file_system"]["SuperUsers"] == ["root", "etl"]


def test_present_enable_ranger_drift_triggers_update(monkeypatch):
    fake = FakeChdfsClient([_fs()])
    _make_module(monkeypatch, fake)
    _run_args(enable_ranger=True, ranger_service_addresses=["rm:9000"])
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["file_system"]["EnableRanger"] is True
    assert fake.calls[1][1].RangerServiceAddresses == ["rm:9000"]


def test_present_name_drift_by_id_triggers_update(monkeypatch):
    # Renaming is only addressable through file_system_id; by name the
    # lookup would simply not find the old name any more.
    fake = FakeChdfsClient([_fs()])
    _make_module(monkeypatch, fake)
    _run_args(file_system_id="f4mp1e-0000", name="warehouse")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["file_system"]["FileSystemName"] == "warehouse"
    assert fake.calls[1][1].FileSystemName == "warehouse"


def test_present_check_mode_update_reports_target(monkeypatch):
    fake = FakeChdfsClient([_fs()])
    _make_module(monkeypatch, fake)
    _run_args(description="new description", _ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["file_system"]["Description"] == "new description"
    assert [c[0] for c in fake.calls] == ["DescribeFileSystems"]


def test_absent_find_failure_reports_sdk_error(monkeypatch):
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
