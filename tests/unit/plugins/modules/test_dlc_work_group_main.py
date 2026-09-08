"""Unit tests for the dlc_work_group write module (run_module flows)."""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import dlc_work_group as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

GROUP = {
    "WorkGroupId": 10042,
    "WorkGroupName": "analytics-engineers",
    "WorkGroupDescription": "Production lakehouse users",
    "UserSet": [],
    "PolicySet": [],
}


def _group(**overrides):
    item = copy.deepcopy(GROUP)
    item.update(overrides)
    return item


class FakeDlcClient(object):
    """In-memory DLC client mutating a work-group store."""

    def __init__(self, groups=None):
        self.groups = [copy.deepcopy(t) for t in (groups or [])]
        self.calls = []
        self._next = 0

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def _find(self, group_id=None, name=None):
        for item in self.groups:
            if group_id is not None and item.get("WorkGroupId") == group_id:
                return item
            if name is not None and item.get("WorkGroupName") == name:
                return item
        return None

    def DescribeWorkGroups(self, request):
        self._record("DescribeWorkGroups", request)
        return SimpleNamespace(WorkGroupSet=[FakeResource(dict(t)) for t in self.groups], TotalCount=len(self.groups))

    def CreateWorkGroup(self, request):
        self._record("CreateWorkGroup", request)
        self._next += 1
        item = {
            "WorkGroupId": 20000 + self._next,
            "WorkGroupName": getattr(request, "WorkGroupName", None),
            "WorkGroupDescription": getattr(request, "WorkGroupDescription", None) or "",
            "UserSet": [],
            "PolicySet": [],
        }
        self.groups.append(item)
        return SimpleNamespace(WorkGroupId=item["WorkGroupId"], RequestId="req-fake")

    def ModifyWorkGroup(self, request):
        self._record("ModifyWorkGroup", request)
        item = self._find(group_id=getattr(request, "WorkGroupId", None))
        if item is not None:
            item["WorkGroupDescription"] = getattr(request, "WorkGroupDescription", None) or ""
        return SimpleNamespace(RequestId="req-fake")

    def DeleteWorkGroup(self, request):
        self._record("DeleteWorkGroup", request)
        ids = list(getattr(request, "WorkGroupIds", None) or [])
        self.groups = [t for t in self.groups if t.get("WorkGroupId") not in ids]
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake, models=None):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (models or FakeModels(), SimpleNamespace(DlcClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


def _base(**overrides):
    params = {"name": "analytics-engineers"}
    params.update(overrides)
    return module_args(**params)


# ---------------------------------------------------------------------------
# absent flows
# ---------------------------------------------------------------------------


def test_absent_missing_is_idempotent(monkeypatch):
    fake = FakeDlcClient(groups=[])
    _make_module(monkeypatch, fake)
    _base(state="absent", name="ghost")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["work_group"] is None
    assert result["work_group_id"] is None
    assert [c for c, unused in fake.calls] == ["DescribeWorkGroups"]


def test_absent_nonempty_requires_allow_delete_nonempty(monkeypatch):
    fake = FakeDlcClient(groups=[_group(UserSet=[{"UserId": "10001"}])])
    _make_module(monkeypatch, fake)
    _base(state="absent")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "allow_delete_nonempty=true" in exc.value.args[0]["msg"]


def test_absent_by_id_deletes(monkeypatch):
    fake = FakeDlcClient(groups=[_group()])
    _make_module(monkeypatch, fake)
    module_args(state="absent", work_group_id=10042, allow_delete_nonempty=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["work_group"] is None
    assert fake.groups == []
    ops = [c for c, unused in fake.calls]
    assert "DeleteWorkGroup" in ops


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeDlcClient(groups=[_group()])
    _make_module(monkeypatch, fake)
    _base(_ansible_check_mode=True, state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert len(fake.groups) == 1
    assert "DeleteWorkGroup" not in [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# creation flows
# ---------------------------------------------------------------------------


def test_create_requires_name(monkeypatch):
    fake = FakeDlcClient(groups=[])
    _make_module(monkeypatch, fake)
    module_args(state="present", work_group_id=999)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "name is required to create a DLC work group" in exc.value.args[0]["msg"]


def test_create_group(monkeypatch):
    fake = FakeDlcClient(groups=[])
    _make_module(monkeypatch, fake)
    _base(state="present", name="analytics-engineers", description="Production lakehouse users")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["work_group"]["WorkGroupName"] == "analytics-engineers"
    assert result["work_group"]["WorkGroupDescription"] == "Production lakehouse users"
    assert result["work_group_id"] == 20001
    assert len(fake.groups) == 1
    ops = [c for c, unused in fake.calls]
    assert ops[0] == "DescribeWorkGroups"
    assert "CreateWorkGroup" in ops


def test_create_check_mode_is_dry_run(monkeypatch):
    fake = FakeDlcClient(groups=[])
    _make_module(monkeypatch, fake)
    _base(_ansible_check_mode=True, state="present", name="analytics-engineers", description="Production lakehouse users")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["work_group"]["WorkGroupName"] == "analytics-engineers"
    assert result["work_group_id"] is None
    assert fake.groups == []
    assert "CreateWorkGroup" not in [c for c, unused in fake.calls]


def test_create_without_description(monkeypatch):
    fake = FakeDlcClient(groups=[])
    _make_module(monkeypatch, fake)
    _base(state="present", name="analytics-engineers")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["work_group"]["WorkGroupDescription"] == ""
    assert result["work_group_id"] == 20001


# ---------------------------------------------------------------------------
# existing-group flows
# ---------------------------------------------------------------------------


def test_existing_no_drift_is_idempotent(monkeypatch):
    fake = FakeDlcClient(groups=[_group()])
    _make_module(monkeypatch, fake)
    _base(state="present", name="analytics-engineers", description="Production lakehouse users")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["work_group"]["WorkGroupId"] == 10042
    assert result["work_group_id"] == 10042
    ops = [c for c, unused in fake.calls]
    assert ops == ["DescribeWorkGroups"]


def test_update_description(monkeypatch):
    fake = FakeDlcClient(groups=[_group()])
    _make_module(monkeypatch, fake)
    _base(state="present", description="renamed group")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["work_group"]["WorkGroupDescription"] == "renamed group"
    ops = [c for c, unused in fake.calls]
    assert "ModifyWorkGroup" in ops


def test_update_check_mode_is_dry_run(monkeypatch):
    fake = FakeDlcClient(groups=[_group()])
    _make_module(monkeypatch, fake)
    _base(_ansible_check_mode=True, state="present", description="renamed group")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["work_group"]["WorkGroupDescription"] == "renamed group"
    assert fake.groups[0]["WorkGroupDescription"] == "Production lakehouse users"
    assert "ModifyWorkGroup" not in [c for c, unused in fake.calls]


def test_name_immutable_drift_fails(monkeypatch):
    fake = FakeDlcClient(groups=[_group()])
    _make_module(monkeypatch, fake)
    module_args(state="present", work_group_id=10042, name="different-name")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "work-group name is immutable" in payload["msg"]
    assert "WorkGroupName" in payload["immutable_drift"]


def test_multiple_matches_fail(monkeypatch):
    fake = FakeDlcClient(groups=[_group(), _group(WorkGroupId=10043)])
    _make_module(monkeypatch, fake)
    _base(state="present")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "Multiple DLC work groups matched" in exc.value.args[0]["msg"]


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeWorkGroups(self, request):
            raise Boom("connection dropped")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    _base(state="present", name="ghost")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]
