"""Unit tests for the oceanus_folder write module (run_module flows).

``run_module()`` is driven end to end against an in-memory fake Oceanus client
whose folder trees are plain nested dicts; create/rename/delete mutate the
store so the module's post-write tree walk converges immediately. The module
walks the whole workspace folder tree (job folders via DescribeTreeJobs,
resource folders via DescribeTreeResources).

Scenario matrix:

* absent on a missing folder (idempotent) / non-empty guard / check-mode dry
  run / real delete
* present on a missing folder (name required, check mode, real create with
  captured request fields)
* idempotent no-op when name+parent already match
* rename/parent drift drives ``ModifyFolder`` (check mode + real)
* the multiple-match guard, argument validation, and the blanket SDK-failure
  path
* legacy helper regression tests (folded from test_oceanus_folder.py)
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import oceanus_folder as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

FOLDER = {"Id": "folder-0001", "Name": "production-jobs", "ParentId": "root", "FolderType": 0, "Children": []}
WORKSPACE = "space-abcdefgh"


def _root(folders=None):
    return {"Id": "root", "Name": "root", "ParentId": None, "FolderType": 0, "Children": [copy.deepcopy(f) for f in (folders or [])]}


def _folder(**overrides):
    item = copy.deepcopy(FOLDER)
    item.update(overrides)
    return item


def _base(**overrides):
    params = {"workspace_id": WORKSPACE, "folder_type": 0, "name": "production-jobs", "parent_id": "root"}
    params.update(overrides)
    return module_args(**params)


class FakeOceanusClient(object):
    """In-memory Oceanus client mutating nested job/resource folder trees."""

    def __init__(self, job_root=None, resource_root=None):
        self.job_root = copy.deepcopy(job_root) if job_root is not None else _root()
        self.resource_root = copy.deepcopy(resource_root) if resource_root is not None else _root()
        self.calls = []
        self._next = 0

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def DescribeTreeJobs(self, request):
        self._record("DescribeTreeJobs", request)
        return FakeResource(self.job_root)

    def DescribeTreeResources(self, request):
        self._record("DescribeTreeResources", request)
        return FakeResource(self.resource_root)

    def CreateFolder(self, request):
        self._record("CreateFolder", request)
        self._next += 1
        folder_id = "folder-new-%04d" % self._next
        node = {
            "Id": folder_id,
            "Name": request.FolderName,
            "ParentId": request.ParentId,
            "FolderType": request.FolderType,
            "Children": [],
        }
        self._attach(request.FolderType, request.ParentId, node)
        return SimpleNamespace(FolderId=folder_id, RequestId="req-fake")

    def ModifyFolder(self, request):
        self._record("ModifyFolder", request)
        self._prune(self.job_root, request.SourceFolderId)
        self._prune(self.resource_root, request.SourceFolderId)
        node = self._detach(request.SourceFolderId)
        node["Name"] = request.FolderName
        self._attach(request.FolderType, request.TargetFolderId, node)
        return SimpleNamespace(RequestId="req-fake")

    def DeleteFolders(self, request):
        self._record("DeleteFolders", request)
        for folder_id in request.FolderIds:
            self._prune(self.job_root, folder_id)
            self._prune(self.resource_root, folder_id)
        return SimpleNamespace(RequestId="req-fake")

    def _root_for(self, folder_type):
        return self.job_root if folder_type == 0 else self.resource_root

    def _prune(self, node, folder_id):
        if not isinstance(node, dict):
            return
        children = node.get("Children") or []
        node["Children"] = [child for child in children if child.get("Id") != folder_id]
        for child in node["Children"]:
            self._prune(child, folder_id)

    def _detach(self, folder_id):
        for node in mod._walk(self.job_root):
            for child in node.get("Children") or []:
                if child.get("Id") == folder_id:
                    return child
        for node in mod._walk(self.resource_root):
            for child in node.get("Children") or []:
                if child.get("Id") == folder_id:
                    return child
        return {"Id": folder_id, "Name": "", "Children": []}

    def _attach(self, folder_type, parent_id, node):
        root = self._root_for(folder_type)
        for candidate in mod._walk(root):
            if candidate.get("Id") == parent_id:
                candidate.setdefault("Children", []).append(node)
                return


def _make_module(monkeypatch, fake, models=None):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (models or FakeModels(), SimpleNamespace(OceanusClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


def _find_call(fake, operation):
    return next(request for name, request in fake.calls if name == operation)


# ---------------------------------------------------------------------------
# absent flows
# ---------------------------------------------------------------------------


def test_absent_missing_folder_is_idempotent(monkeypatch):
    fake = FakeOceanusClient()
    _make_module(monkeypatch, fake)
    _base(state="absent", name="ghost")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["folder"] is None


def test_absent_nonempty_folder_requires_authorization(monkeypatch):
    folder = _folder(Children=[_folder(Id="folder-child", Name="child")])
    fake = FakeOceanusClient(job_root=_root([folder]))
    _make_module(monkeypatch, fake)
    _base(state="absent")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "allow_delete_nonempty=true" in exc.value.args[0]["msg"]


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeOceanusClient(job_root=_root([_folder()]))
    _make_module(monkeypatch, fake)
    _base(_ansible_check_mode=True, state="absent", allow_delete_nonempty=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["folder"] is None
    assert "DeleteFolders" not in [name for name, unused in fake.calls]


def test_absent_deletes_folder(monkeypatch):
    fake = FakeOceanusClient(job_root=_root([_folder()]))
    _make_module(monkeypatch, fake)
    _base(state="absent", allow_delete_nonempty=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["folder"] is None
    assert fake.job_root["Children"] == []
    request = _find_call(fake, "DeleteFolders")
    assert request.FolderIds == ["folder-0001"]
    assert request.FolderType == 0
    assert request.WorkSpaceId == WORKSPACE


# ---------------------------------------------------------------------------
# creation flows
# ---------------------------------------------------------------------------


def test_create_requires_name(monkeypatch):
    fake = FakeOceanusClient()
    _make_module(monkeypatch, fake)
    _base(folder_id="folder-ghost", name=None)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "name is required to create an Oceanus folder" in exc.value.args[0]["msg"]


def test_create_folder(monkeypatch):
    fake = FakeOceanusClient()
    _make_module(monkeypatch, fake)
    _base()
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["folder"]["Name"] == "production-jobs"
    assert result["folder"]["ParentId"] == "root"
    assert result["folder"]["Id"].startswith("folder-new-")
    request = _find_call(fake, "CreateFolder")
    assert request.FolderName == "production-jobs"
    assert request.ParentId == "root"
    assert request.FolderType == 0
    assert request.WorkSpaceId == WORKSPACE
    assert len(fake.job_root["Children"]) == 1


def test_create_check_mode_is_dry_run(monkeypatch):
    fake = FakeOceanusClient()
    _make_module(monkeypatch, fake)
    _base(_ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["folder"] == {"Name": "production-jobs", "ParentId": "root", "FolderType": 0}
    assert fake.job_root["Children"] == []
    assert "CreateFolder" not in [name for name, unused in fake.calls]


# ---------------------------------------------------------------------------
# existing-folder flows
# ---------------------------------------------------------------------------


def test_existing_folder_no_drift_is_idempotent(monkeypatch):
    fake = FakeOceanusClient(job_root=_root([_folder()]))
    _make_module(monkeypatch, fake)
    _base()
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["folder"]["Id"] == "folder-0001"


def test_rename_drift_updates_folder(monkeypatch):
    fake = FakeOceanusClient(job_root=_root([_folder()]))
    _make_module(monkeypatch, fake)
    _base(folder_id="folder-0001", name="archive-jobs")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["folder"]["Name"] == "archive-jobs"
    request = _find_call(fake, "ModifyFolder")
    assert request.SourceFolderId == "folder-0001"
    assert request.TargetFolderId == "root"
    assert request.FolderName == "archive-jobs"


def test_rename_check_mode_is_dry_run(monkeypatch):
    fake = FakeOceanusClient(job_root=_root([_folder()]))
    _make_module(monkeypatch, fake)
    _base(_ansible_check_mode=True, folder_id="folder-0001", name="archive-jobs")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["folder"]["Name"] == "archive-jobs"
    assert fake.job_root["Children"][0]["Name"] == "production-jobs"
    assert "ModifyFolder" not in [name for name, unused in fake.calls]


def test_multiple_matches_fail(monkeypatch):
    fake = FakeOceanusClient(job_root=_root([_folder(), _folder(Id="folder-0002")]))
    _make_module(monkeypatch, fake)
    _base()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "Multiple Oceanus folders matched" in exc.value.args[0]["msg"]


# ---------------------------------------------------------------------------
# argument validation and failure paths
# ---------------------------------------------------------------------------


def test_missing_folder_identity_fails(monkeypatch):
    fake = FakeOceanusClient()
    _make_module(monkeypatch, fake)
    module_args(workspace_id=WORKSPACE, folder_type=0, parent_id="root")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "one of the following is required" in exc.value.args[0]["msg"]
    assert fake.calls == []


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeTreeJobs(self, request):
            raise Boom("connection dropped")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    _base()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]


# ---------------------------------------------------------------------------
# legacy helper regression tests (folded from test_oceanus_folder.py)
# ---------------------------------------------------------------------------


def test_walk_flattens_nested_folder_tree():
    root = {"Id": "root", "Children": [{"Id": "a", "Children": [{"Id": "b"}]}]}
    assert [item["Id"] for item in mod._walk(root)] == ["root", "a", "b"]


def test_walk_ignores_non_dict_nodes():
    assert list(mod._walk("leaf")) == []


def test_nonempty_covers_job_and_resource_folders():
    assert mod.nonempty({"JobSet": [{"JobId": "j"}]}, {})
    assert mod.nonempty({"Items": [{"ResourceId": "r"}]}, {})
    assert mod.nonempty({"Children": [{"Id": "c"}]}, {})
    assert not mod.nonempty({"Children": [], "Items": []}, {})
