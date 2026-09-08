"""Unit tests for the oceanus_workspace write module (run_module flows).

Drives ``run_module()`` end to end against an in-memory fake Oceanus client
whose write operations mutate the workspace store so the post-write
``find``/``wait_workspace`` waiters converge immediately.

Scenario matrix:

* absent on a missing workspace (idempotent no-op)
* absent with a matching workspace (check-mode dry run and the real delete)
* creation when missing (missing-name guard, check mode, waiting)
* no-op when nothing drifts
* drift updates (rename, description)
* the multiple-match guard and the blanket ``sdk_error_payload`` path
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import oceanus_workspace as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

WORKSPACE = {
    "WorkSpaceId": "ws-1a2b3c4d",
    "WorkSpaceName": "prod-streaming",
    "Description": "Production Flink jobs and resources",
}


def _workspace(**overrides):
    item = copy.deepcopy(WORKSPACE)
    item.update(overrides)
    return item


def _base(**overrides):
    params = {"name": "prod-streaming"}
    params.update(overrides)
    return module_args(**params)


class FakeOceanusClient(object):
    """In-memory Oceanus client mutating a small workspace store."""

    def __init__(self, workspaces=None):
        self.workspaces = [copy.deepcopy(t) for t in (workspaces or [])]
        self.calls = []
        self._next = 0

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def _find(self, workspace_id):
        for item in self.workspaces:
            if item.get("WorkSpaceId") == workspace_id:
                return item
        return None

    def DescribeWorkSpaces(self, request):
        self._record("DescribeWorkSpaces", request)
        matched = list(self.workspaces)
        for item in list(getattr(request, "Filters", None) or []):
            name = getattr(item, "Name", None)
            value = (item.Values or [None])[0]
            if name == "WorkSpaceId":
                matched = [t for t in matched if t.get("WorkSpaceId") == value]
            elif name == "WorkSpaceName":
                matched = [t for t in matched if t.get("WorkSpaceName") == value]
        return SimpleNamespace(WorkSpaceSetItem=[FakeResource(t) for t in matched], TotalCount=len(matched))

    def CreateWorkSpace(self, request):
        self._record("CreateWorkSpace", request)
        self._next += 1
        item = {
            "WorkSpaceId": "ws-new-%03d" % self._next,
            "WorkSpaceName": getattr(request, "WorkSpaceName", None),
            "Description": getattr(request, "Description", None),
        }
        self.workspaces.append(item)
        return SimpleNamespace(WorkSpaceId=item["WorkSpaceId"], RequestId="req-fake")

    def ModifyWorkSpace(self, request):
        self._record("ModifyWorkSpace", request)
        item = self._find(getattr(request, "WorkSpaceId", None))
        if item is not None:
            item["WorkSpaceName"] = getattr(request, "WorkSpaceName", item.get("WorkSpaceName"))
            item["Description"] = getattr(request, "Description", item.get("Description"))
        return SimpleNamespace(RequestId="req-fake")

    def DeleteWorkSpace(self, request):
        self._record("DeleteWorkSpace", request)
        workspace_id = getattr(request, "WorkSpaceId", None)
        self.workspaces = [t for t in self.workspaces if t.get("WorkSpaceId") != workspace_id]
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake, models=None):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (models or FakeModels(), SimpleNamespace(OceanusClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


# ---------------------------------------------------------------------------
# absent flows
# ---------------------------------------------------------------------------


def test_absent_missing_workspace_is_idempotent(monkeypatch):
    fake = FakeOceanusClient(workspaces=[])
    _make_module(monkeypatch, fake)
    _base(state="absent", name="ghost-workspace")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["workspace"] is None
    assert [c for c, unused in fake.calls] == ["DescribeWorkSpaces"]


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeOceanusClient(workspaces=[_workspace()])
    _make_module(monkeypatch, fake)
    _base(_ansible_check_mode=True, state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["workspace"] is None
    assert len(fake.workspaces) == 1
    assert "DeleteWorkSpace" not in [c for c, unused in fake.calls]


def test_absent_deletes_workspace(monkeypatch):
    fake = FakeOceanusClient(workspaces=[_workspace()])
    _make_module(monkeypatch, fake)
    _base(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["workspace"] is None
    assert fake.workspaces == []
    ops = [c for c, unused in fake.calls]
    assert "DeleteWorkSpace" in ops


# ---------------------------------------------------------------------------
# creation flows
# ---------------------------------------------------------------------------


def test_create_requires_name(monkeypatch):
    fake = FakeOceanusClient(workspaces=[])
    _make_module(monkeypatch, fake)
    _base(state="present", name=None, workspace_id="ws-unknown")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "name is required to create an Oceanus workspace" in exc.value.args[0]["msg"]


def test_create_workspace(monkeypatch):
    fake = FakeOceanusClient(workspaces=[])
    _make_module(monkeypatch, fake)
    _base(state="present", name="brand-new", description="brand new workspace")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["workspace"]["WorkSpaceName"] == "brand-new"
    assert result["workspace"]["Description"] == "brand new workspace"
    assert result["workspace"]["WorkSpaceId"].startswith("ws-new-")
    assert len(fake.workspaces) == 1
    ops = [c for c, unused in fake.calls]
    assert ops[0] == "DescribeWorkSpaces"
    assert "CreateWorkSpace" in ops


def test_create_check_mode_is_dry_run(monkeypatch):
    fake = FakeOceanusClient(workspaces=[])
    _make_module(monkeypatch, fake)
    _base(_ansible_check_mode=True, state="present", name="brand-new", description="brand new workspace")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["workspace"]["WorkSpaceName"] == "brand-new"
    assert fake.workspaces == []
    assert "CreateWorkSpace" not in [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# existing-workspace flows
# ---------------------------------------------------------------------------


def test_existing_workspace_no_drift_is_idempotent(monkeypatch):
    fake = FakeOceanusClient(workspaces=[_workspace()])
    _make_module(monkeypatch, fake)
    _base(state="present")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["workspace"]["WorkSpaceId"] == "ws-1a2b3c4d"


def test_rename_workspace(monkeypatch):
    fake = FakeOceanusClient(workspaces=[_workspace()])
    _make_module(monkeypatch, fake)
    _base(state="present", workspace_id="ws-1a2b3c4d", name="renamed-streaming")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["workspace"]["WorkSpaceName"] == "renamed-streaming"
    ops = [c for c, unused in fake.calls]
    assert "ModifyWorkSpace" in ops


def test_update_description(monkeypatch):
    fake = FakeOceanusClient(workspaces=[_workspace()])
    _make_module(monkeypatch, fake)
    _base(state="present", workspace_id="ws-1a2b3c4d", name="prod-streaming", description="Updated description")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["workspace"]["Description"] == "Updated description"
    ops = [c for c, unused in fake.calls]
    assert "ModifyWorkSpace" in ops


def test_multiple_matches_fail(monkeypatch):
    fake = FakeOceanusClient(workspaces=[_workspace(), _workspace(WorkSpaceId="ws-dup")])
    _make_module(monkeypatch, fake)
    _base(state="present")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "Multiple Oceanus workspaces matched; specify workspace_id" in exc.value.args[0]["msg"]


# ---------------------------------------------------------------------------
# failure paths
# ---------------------------------------------------------------------------


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeWorkSpaces(self, request):
            raise Boom("connection dropped")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    _base(state="present", name="prod-streaming")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]
