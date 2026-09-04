"""Unit tests for the goosefs_file_system write module (helpers + run_module).

Covers the create / expand / destroy flows of
``plugins/modules/goosefs_file_system.py`` with an in-memory fake GooseFS
client whose write operations mutate the file-system store, so the module's
post-write ``find`` refetch converges immediately. DescribeFileSystems is a
single (non-paged) call returning ``FSAttributeList`` at the top level;
CreateFileSystem returns the new id on the bare response. Capacity is the
only mutable field (expansion only, via ExpandCapacity); name/vpc/subnet/
zone/type are immutable and shrinking capacity fails. ``GooseFSxBuildElement``
payloads round-trip through ``from_json_string``. In check mode a would-be
create reports the desired dict and a would-be update the pre-change dict.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
import json
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import goosefs_file_system as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

FS = {
    "FileSystemId": "fs-1",
    "Name": "analytics-cache",
    "Description": "Analytics cache",
    "VpcId": "vpc-1",
    "SubnetId": "subnet-1",
    "Zone": "ap-guangzhou-3",
    "Type": "GooseFSx",
    "GooseFSxAttribute": {"Capacity": 10},
}


def _fs(**overrides):
    """API-shaped file system dict isolated from the shared constant."""
    item = copy.deepcopy(FS)
    item.update(overrides)
    return item


def _params(**overrides):
    """Module parameters pre-filled from the argument spec."""
    params = {
        "state": "present",
        "file_system_id": None,
        "name": "analytics-cache",
        "description": "Analytics cache",
        "vpc_id": "vpc-1",
        "subnet_id": "subnet-1",
        "zone": "ap-guangzhou-3",
        "file_system_type": "GooseFSx",
        "build_elements": None,
        "capacity": 10,
        "security_group_id": None,
        "cluster_port": None,
        "tags": None,
    }
    params.update(overrides)
    return params


def _run_args(**extra):
    """module_args() pre-filled with every module parameter (None dropped)."""
    args = dict(_params())
    args.update(extra)
    return module_args(**{k: v for k, v in args.items() if v is not None})


class _JsonModel(object):
    """SDK model whose payload round-trips through from_json_string."""

    def from_json_string(self, payload):
        for key, value in json.loads(payload).items():
            setattr(self, key, value)
        return self


class FakeGoosefsModels(FakeModels):
    """FakeModels whose GooseFSxBuildElement implements from_json_string."""

    def __getattr__(self, name):
        if name == "GooseFSxBuildElement":
            return _JsonModel
        return super(FakeGoosefsModels, self).__getattr__(name)


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
    """In-memory GoosefsClient stand-in for file systems.

    Stores API-shaped file system dicts. DescribeFileSystems returns the
    whole store in ``FSAttributeList``; write operations mutate the store so
    post-write refetches converge.
    """

    def __init__(self, file_systems=None):
        self.file_systems = [copy.deepcopy(f) for f in (file_systems or [])]
        self.calls = []
        self._next_id = 100

    def _record(self, name, request):
        self.calls.append((name, request))
        return request

    def _new_id(self):
        self._next_id += 1
        return "fs-%d" % self._next_id

    def DescribeFileSystems(self, request):
        self._record("DescribeFileSystems", request)
        return SimpleNamespace(
            FSAttributeList=[FakeResource(dict(f)) for f in self.file_systems],
            RequestId="req-fake",
        )

    def CreateFileSystem(self, request):
        self._record("CreateFileSystem", request)
        fs_id = self._new_id()
        fs = {
            "FileSystemId": fs_id,
            "Name": request.Name,
            "Description": request.Description,
            "VpcId": request.VpcId,
            "SubnetId": request.SubnetId,
            "Zone": request.Zone,
            "Type": request.Type,
        }
        self.file_systems.append(fs)
        return SimpleNamespace(FileSystemId=fs_id, RequestId="req-fake")

    def ExpandCapacity(self, request):
        self._record("ExpandCapacity", request)
        for stored in self.file_systems:
            if stored.get("FileSystemId") != request.FileSystemId:
                continue
            attribute = stored.setdefault("GooseFSxAttribute", {})
            attribute["Capacity"] = request.ExpandedCapacity
        return SimpleNamespace(RequestId="req-fake")

    def DeleteFileSystem(self, request):
        self._record("DeleteFileSystem", request)
        self.file_systems = [f for f in self.file_systems if f.get("FileSystemId") != request.FileSystemId]
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake):
    """Wire the shared monkeypatches and return the fake client."""
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(
        mod,
        "_load",
        lambda: (FakeGoosefsModels(), SimpleNamespace(GoosefsClient=object)),
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
            raise RuntimeError("service exploded")

        return boom


# ---------------------------------------------------------------------------
# request-builder / normalisation helper tests
# ---------------------------------------------------------------------------


def test_describe_request_fields():
    request = mod.describe_request(FakeGoosefsModels())
    assert request.Offset == 0
    assert request.Limit == 100


def test_describe_request_with_offset():
    request = mod.describe_request(FakeGoosefsModels(), offset=100)
    assert request.Offset == 100


def test_tags_builder_sorted():
    items = mod._tags(FakeGoosefsModels(), {"z": "2", "a": "1"})
    assert [(x.Key, x.Value) for x in items] == [("a", "1"), ("z", "2")]


def test_tags_builder_empty_and_none():
    assert mod._tags(FakeGoosefsModels(), None) == []
    assert mod._tags(FakeGoosefsModels(), {}) == []


def test_create_request_fields():
    request = mod.create_request(
        FakeGoosefsModels(),
        _params(
            description="New cache",
            security_group_id="sg-1",
            cluster_port=80,
            tags={"env": "prod"},
            build_elements=[{"Model": "GOOSFSX_C60", "Capacity": 10}],
        ),
    )
    assert request.Name == "analytics-cache"
    assert request.Description == "New cache"
    assert request.VpcId == "vpc-1"
    assert request.SubnetId == "subnet-1"
    assert request.Zone == "ap-guangzhou-3"
    assert request.Type == "GooseFSx"
    assert request.SecurityGroupId == "sg-1"
    assert request.ClusterPort == 80
    assert request.GooseFSxBuildElements[0].Model == "GOOSFSX_C60"
    assert request.GooseFSxBuildElements[0].Capacity == 10
    assert [(t.Key, t.Value) for t in request.Tag] == [("env", "prod")]


def test_create_request_omits_build_elements_when_absent():
    request = mod.create_request(FakeGoosefsModels(), _params(build_elements=None, tags=None))
    assert request.GooseFSxBuildElements == []
    assert request.Tag == []
    assert request.SecurityGroupId is None


def test_expand_request_fields():
    request = mod.expand_request(FakeGoosefsModels(), "fs-1", 20)
    assert request.FileSystemId == "fs-1"
    assert request.ExpandedCapacity == 20
    assert request.ModifyType == "EXPAND"


def test_delete_request_fields():
    request = mod.delete_request(FakeGoosefsModels(), "fs-1")
    assert request.FileSystemId == "fs-1"


def test_capacity_reads_nested_attribute():
    assert mod._capacity(_fs()) == 10
    assert mod._capacity(_fs(GooseFSxAttribute=None)) is None
    assert mod._capacity({"Name": "x"}) is None


# ---------------------------------------------------------------------------
# find tests
# ---------------------------------------------------------------------------


def test_find_by_file_system_id(monkeypatch):
    fake = FakeGoosefsClient([_fs(), _fs(FileSystemId="fs-2", Name="other")])
    _make_module(monkeypatch, fake)
    module = FakeModule(_params(file_system_id="fs-2", name=None))
    value = mod.find(module, fake, FakeGoosefsModels(), module.params)
    assert value["FileSystemId"] == "fs-2"


def test_find_by_name(monkeypatch):
    fake = FakeGoosefsClient([_fs(Name="other"), _fs()])
    _make_module(monkeypatch, fake)
    module = FakeModule(_params(name="analytics-cache"))
    value = mod.find(module, fake, FakeGoosefsModels(), module.params)
    assert value["FileSystemId"] == "fs-1"


def test_find_no_match_returns_none(monkeypatch):
    fake = FakeGoosefsClient([_fs()])
    _make_module(monkeypatch, fake)
    module = FakeModule(_params(name="ghost"))
    assert mod.find(module, fake, FakeGoosefsModels(), module.params) is None


def test_find_multiple_name_matches_fails(monkeypatch):
    fake = FakeGoosefsClient([_fs(), _fs(FileSystemId="fs-2")])
    _make_module(monkeypatch, fake)
    module = FakeModule(_params(name="analytics-cache"))
    with pytest.raises(AnsibleFailJson) as exc:
        mod.find(module, fake, FakeGoosefsModels(), module.params)
    assert "Multiple GooseFS file systems matched" in exc.value.args[0]["msg"]


# ---------------------------------------------------------------------------
# run_module main-path tests
# ---------------------------------------------------------------------------


def test_required_one_of_enforced():
    module_args(state="present")  # neither file_system_id nor name
    with pytest.raises(AnsibleFailJson):
        run(mod.run_module)


def test_present_creates_file_system(monkeypatch):
    fake = FakeGoosefsClient()
    _make_module(monkeypatch, fake)
    _run_args()
    result = run(mod.run_module)
    assert result["changed"] is True
    fs = result["file_system"]
    assert fs["FileSystemId"] == "fs-101"
    assert fs["Name"] == "analytics-cache"
    names = [c[0] for c in fake.calls]
    assert names.count("DescribeFileSystems") == 2  # find + refetch
    assert names.count("CreateFileSystem") == 1
    create = [c for c in fake.calls if c[0] == "CreateFileSystem"][0][1]
    assert create.VpcId == "vpc-1"
    assert create.Type == "GooseFSx"


def test_present_requires_creation_parameters(monkeypatch):
    fake = FakeGoosefsClient()
    _make_module(monkeypatch, fake)
    _run_args(name="analytics-cache", vpc_id=None, subnet_id=None)  # absent + incomplete
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "creation parameters are required for a GooseFS file system" in payload["msg"]
    assert set(payload["missing"]) == {"vpc_id", "subnet_id"}
    assert not any("CreateFileSystem" == c[0] for c in fake.calls)


def test_present_noop_returns_unchanged(monkeypatch):
    fake = FakeGoosefsClient([_fs()])
    _make_module(monkeypatch, fake)
    _run_args()
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["file_system"]["FileSystemId"] == "fs-1"
    names = [c[0] for c in fake.calls]
    assert "ExpandCapacity" not in names
    assert "CreateFileSystem" not in names


def test_present_capacity_expansion_triggers_expand(monkeypatch):
    fake = FakeGoosefsClient([_fs()])
    _make_module(monkeypatch, fake)
    _run_args(file_system_id="fs-1", capacity=20)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["file_system"]["GooseFSxAttribute"]["Capacity"] == 20
    expand = [c for c in fake.calls if c[0] == "ExpandCapacity"][0][1]
    assert expand.FileSystemId == "fs-1"
    assert expand.ExpandedCapacity == 20
    assert expand.ModifyType == "EXPAND"


def test_present_capacity_shrink_fails(monkeypatch):
    fake = FakeGoosefsClient([_fs()])
    _make_module(monkeypatch, fake)
    _run_args(file_system_id="fs-1", capacity=5)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "GooseFS capacity cannot be reduced" in payload["msg"]
    assert payload["before"] == 10
    assert payload["after"] == 5
    assert not any("ExpandCapacity" == c[0] for c in fake.calls)


def test_present_immutable_name_drift_fails(monkeypatch):
    fake = FakeGoosefsClient([_fs()])
    _make_module(monkeypatch, fake)
    _run_args(file_system_id="fs-1", name="renamed")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "Immutable fields cannot be changed" in payload["msg"]
    assert payload["replacement_required"] is True
    assert payload["immutable_changes"]["Name"]["before"] == "analytics-cache"
    assert payload["immutable_changes"]["Name"]["after"] == "renamed"
    assert not any("ExpandCapacity" == c[0] for c in fake.calls)


def test_check_mode_create_is_dry_run(monkeypatch):
    fake = FakeGoosefsClient()
    _make_module(monkeypatch, fake)
    module_args(_ansible_check_mode=True, **{k: v for k, v in _params().items() if v is not None})
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["file_system"]["Name"] == "analytics-cache"  # desired reported
    assert result["file_system"]["Capacity"] == 10
    assert not any("CreateFileSystem" == c[0] for c in fake.calls)


def test_check_mode_update_is_dry_run(monkeypatch):
    fake = FakeGoosefsClient([_fs()])
    _make_module(monkeypatch, fake)
    module_args(_ansible_check_mode=True, **{k: v for k, v in _params(file_system_id="fs-1", capacity=20).items() if v is not None})
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["file_system"]["FileSystemId"] == "fs-1"  # pre-change reported
    assert not any("ExpandCapacity" == c[0] for c in fake.calls)


def test_sdk_error_is_reported(monkeypatch):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(
        mod,
        "_load",
        lambda: (FakeGoosefsModels(), SimpleNamespace(GoosefsClient=object)),
    )
    monkeypatch.setattr(
        TencentCloudModule,
        "create_client",
        lambda self, client_class, endpoint: _BoomClient(),
    )
    _run_args()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert payload["error"] == "service exploded"


def test_absent_deletes_file_system(monkeypatch):
    fake = FakeGoosefsClient([_fs()])
    _make_module(monkeypatch, fake)
    _run_args(state="absent", name="analytics-cache")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["file_system"] is None
    delete = [c for c in fake.calls if c[0] == "DeleteFileSystem"][0][1]
    assert delete.FileSystemId == "fs-1"
    assert fake.file_systems == []


def test_absent_not_found_is_noop(monkeypatch):
    fake = FakeGoosefsClient([_fs()])
    _make_module(monkeypatch, fake)
    _run_args(state="absent", name="ghost")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["file_system"] is None
    assert not any("DeleteFileSystem" == c[0] for c in fake.calls)


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeGoosefsClient([_fs()])
    _make_module(monkeypatch, fake)
    module_args(_ansible_check_mode=True, **{k: v for k, v in _params(state="absent").items() if v is not None})
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["file_system"] is None  # module always clears it on absent
    assert not any("DeleteFileSystem" == c[0] for c in fake.calls)
    assert len(fake.file_systems) == 1
