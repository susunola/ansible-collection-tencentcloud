"""Unit tests for the tione_notebook write module (run_module flows).

Drives ``run_module()`` end to end against an in-memory fake TIONE client
whose write operations mutate the notebook store, so the post-write detail
refetches and waiters converge immediately.

Scenario matrix:

* argument validation (missing name/notebook_id, too many code repos,
  absent without notebook_id)
* absent on a missing notebook (idempotent) / allow_delete guard / wait
  guard / check-mode dry run / real delete (running and stopped)
* creation when missing (missing creation params, by-ID not found, running
  and stopped, check mode)
* no-op when nothing drifts
* drift updates (description on a stopped notebook) with wait and in
  check mode, plus the wait-required guard when running
* immutable drift failure and the multiple-match guard
* the blanket ``sdk_error_payload`` failure path
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import tione_notebook as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

WRITE_KEYS = [
    "Name", "ChargeType", "ResourceConf", "LogEnable", "RootAccess", "AutoStopping",
    "DirectInternetAccess", "ResourceGroupId", "VpcId", "SubnetId", "VolumeSourceType",
    "VolumeSizeInGB", "VolumeSourceCFS", "VolumeSourceGooseFS", "LogConfig",
    "LifecycleScriptId", "DefaultCodeRepoId", "AdditionalCodeRepoIds", "AutomaticStopTime",
    "Tags", "DataConfigs", "ImageInfo", "ImageType", "SSHConfig", "Description",
]

NOTEBOOK = {
    "Id": "nb-8b0a1c2d",
    "Name": "llm-finetuning",
    "Status": "running",
    "ChargeType": "POSTPAID_BY_HOUR",
    "Description": "production",
}


class NotFoundError(Exception):
    def get_code(self):
        return "ResourceNotFound.Notebook"

    def get_request_id(self):
        return "req-404"


def _notebook(**overrides):
    item = copy.deepcopy(NOTEBOOK)
    item.update(overrides)
    return item


def _base(**overrides):
    params = {"name": "llm-finetuning"}
    params.update(overrides)
    return module_args(**params)


class FakeTioneClient(object):
    """In-memory TIONE notebook client mutating a small notebook store."""

    def __init__(self, notebooks=None):
        self.notebooks = [copy.deepcopy(t) for t in (notebooks or [])]
        self.calls = []
        self._next = 0

    def _find(self, notebook_id):
        for item in self.notebooks:
            if item.get("Id") == notebook_id:
                return item
        raise NotFoundError("notebook %s not found" % notebook_id)

    def _apply(self, request, item):
        for key in WRITE_KEYS:
            value = getattr(request, key, None)
            if value is not None:
                item[key] = value

    def DescribeNotebook(self, request):
        self.calls.append("DescribeNotebook")
        return SimpleNamespace(NotebookDetail=FakeResource(dict(self._find(request.Id))), RequestId="req-fake")

    def DescribeNotebooks(self, request):
        self.calls.append("DescribeNotebooks")
        name = request.Filters[0].Values[0]
        matches = [t for t in self.notebooks if t.get("Name") == name]
        return SimpleNamespace(NotebookSet=[FakeResource(t) for t in matches], TotalCount=len(matches), RequestId="req-fake")

    def CreateNotebook(self, request):
        self.calls.append("CreateNotebook")
        self._next += 1
        item = {"Id": "nb-new-%03d" % self._next, "Status": "running"}
        self._apply(request, item)
        item.setdefault("Name", getattr(request, "Name", None))
        self.notebooks.append(item)
        return SimpleNamespace(Id=item["Id"], RequestId="req-fake")

    def StopNotebook(self, request):
        self.calls.append("StopNotebook")
        self._find(request.Id)["Status"] = "stopped"
        return SimpleNamespace(RequestId="req-fake")

    def StartNotebook(self, request):
        self.calls.append("StartNotebook")
        self._find(request.Id)["Status"] = "running"
        return SimpleNamespace(RequestId="req-fake")

    def ModifyNotebook(self, request):
        self.calls.append("ModifyNotebook")
        self._apply(request, self._find(request.Id))
        return SimpleNamespace(RequestId="req-fake")

    def DeleteNotebook(self, request):
        self.calls.append("DeleteNotebook")
        self.notebooks = [t for t in self.notebooks if t.get("Id") != request.Id]
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake, models=None):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (models or FakeModels(), SimpleNamespace(TioneClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


# ---------------------------------------------------------------------------
# argument validation (before any SDK call)
# ---------------------------------------------------------------------------


def test_present_requires_name_or_notebook_id(monkeypatch):
    fake = FakeTioneClient()
    _make_module(monkeypatch, fake)
    module_args()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "name or notebook_id is required" in exc.value.args[0]["msg"]


def test_too_many_code_repos_fails(monkeypatch):
    fake = FakeTioneClient()
    _make_module(monkeypatch, fake)
    _base(additional_code_repo_ids=["r1", "r2", "r3", "r4"])
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "at most three repositories" in exc.value.args[0]["msg"]


def test_absent_requires_notebook_id(monkeypatch):
    fake = FakeTioneClient()
    _make_module(monkeypatch, fake)
    _base(state="absent")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "notebook_id is required for safe deletion" in exc.value.args[0]["msg"]


# ---------------------------------------------------------------------------
# absent flows
# ---------------------------------------------------------------------------


def test_absent_missing_notebook_is_idempotent(monkeypatch):
    fake = FakeTioneClient()
    _make_module(monkeypatch, fake)
    _base(state="absent", notebook_id="nb-ghost")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["notebook"] is None
    assert result["notebook_id"] == "nb-ghost"


def test_absent_requires_allow_delete(monkeypatch):
    fake = FakeTioneClient(notebooks=[_notebook()])
    _make_module(monkeypatch, fake)
    _base(state="absent", notebook_id="nb-8b0a1c2d")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "allow_delete=true" in exc.value.args[0]["msg"]


def test_absent_running_requires_wait(monkeypatch):
    fake = FakeTioneClient(notebooks=[_notebook()])
    _make_module(monkeypatch, fake)
    _base(state="absent", notebook_id="nb-8b0a1c2d", allow_delete=True, wait=False)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "wait=true is required to stop a TIONE notebook before deletion" in exc.value.args[0]["msg"]


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeTioneClient(notebooks=[_notebook()])
    _make_module(monkeypatch, fake)
    _base(_ansible_check_mode=True, state="absent", notebook_id="nb-8b0a1c2d", allow_delete=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert len(fake.notebooks) == 1
    ops = list(fake.calls)
    assert "DeleteNotebook" not in ops


def test_absent_stopped_deletes_notebook(monkeypatch):
    fake = FakeTioneClient(notebooks=[_notebook(Status="stopped")])
    _make_module(monkeypatch, fake)
    _base(state="absent", notebook_id="nb-8b0a1c2d", allow_delete=True, wait=False)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["notebook"] is None
    assert fake.notebooks == []
    ops = list(fake.calls)
    assert "DeleteNotebook" in ops
    assert "StopNotebook" not in ops


def test_absent_running_deletes_notebook(monkeypatch):
    fake = FakeTioneClient(notebooks=[_notebook()])
    _make_module(monkeypatch, fake)
    _base(state="absent", notebook_id="nb-8b0a1c2d", allow_delete=True, wait=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert fake.notebooks == []
    ops = list(fake.calls)
    assert "StopNotebook" in ops
    assert "DeleteNotebook" in ops


# ---------------------------------------------------------------------------
# creation flows
# ---------------------------------------------------------------------------


def test_create_requires_creation_parameters(monkeypatch):
    fake = FakeTioneClient()
    _make_module(monkeypatch, fake)
    _base(state="running", name="brand-new")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "creation parameters are required" in exc.value.args[0]["msg"]


def test_create_with_unknown_notebook_id_fails(monkeypatch):
    fake = FakeTioneClient()
    _make_module(monkeypatch, fake)
    _base(state="running", notebook_id="nb-ghost")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "does not exist" in exc.value.args[0]["msg"]


def test_create_running_notebook(monkeypatch):
    fake = FakeTioneClient()
    _make_module(monkeypatch, fake)
    _base(
        state="running",
        name="llm-finetuning",
        charge_type="POSTPAID_BY_HOUR",
        resource_conf={"Cpu": 8, "Memory": 32},
        volume_source_type="CLOUD_PREMIUM",
        volume_size_gb=100,
        auto_stopping=True,
        automatic_stop_time=4,
        direct_internet_access=False,
        description="production",
        wait=True,
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["notebook_id"].startswith("nb-new-")
    assert result["notebook"]["Name"] == "llm-finetuning"
    assert len(fake.notebooks) == 1
    ops = list(fake.calls)
    assert ops[0] == "DescribeNotebooks"
    assert "CreateNotebook" in ops


def test_create_stopped_notebook(monkeypatch):
    fake = FakeTioneClient()
    _make_module(monkeypatch, fake)
    _base(
        state="stopped",
        name="batch-prep",
        charge_type="POSTPAID_BY_HOUR",
        resource_conf={"Cpu": 4, "Memory": 16},
        wait=True,
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["notebook"]["Status"] == "stopped"
    ops = list(fake.calls)
    assert "CreateNotebook" in ops
    assert "StopNotebook" in ops


def test_create_check_mode_is_dry_run(monkeypatch):
    fake = FakeTioneClient()
    _make_module(monkeypatch, fake)
    _base(
        _ansible_check_mode=True,
        state="running",
        name="llm-finetuning",
        charge_type="POSTPAID_BY_HOUR",
        resource_conf={"Cpu": 8, "Memory": 32},
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["notebook_id"] is None
    assert result["notebook"]["Name"] == "llm-finetuning"
    assert result["notebook"]["Status"] == "Running"
    assert fake.notebooks == []
    assert "CreateNotebook" not in fake.calls


# ---------------------------------------------------------------------------
# existing-notebook flows
# ---------------------------------------------------------------------------


def test_existing_notebook_no_drift_is_idempotent(monkeypatch):
    fake = FakeTioneClient(notebooks=[_notebook()])
    _make_module(monkeypatch, fake)
    _base(state="running", description="production")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["notebook"]["Id"] == "nb-8b0a1c2d"
    ops = list(fake.calls)
    assert "ModifyNotebook" not in ops
    assert "StopNotebook" not in ops


def test_immutable_drift_fails(monkeypatch):
    fake = FakeTioneClient(notebooks=[_notebook()])
    _make_module(monkeypatch, fake)
    _base(state="running", charge_type="PREPAID")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "immutable configuration drift" in payload["msg"]
    assert "ChargeType" in payload["immutable_drift"]


def test_update_description_on_stopped_notebook(monkeypatch):
    fake = FakeTioneClient(notebooks=[_notebook(Status="stopped")])
    _make_module(monkeypatch, fake)
    _base(state="stopped", description="renamed", wait=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["notebook"]["Description"] == "renamed"
    ops = list(fake.calls)
    assert "ModifyNotebook" in ops
    assert "StopNotebook" not in ops
    assert "StartNotebook" not in ops


def test_update_description_check_mode(monkeypatch):
    fake = FakeTioneClient(notebooks=[_notebook(Status="stopped")])
    _make_module(monkeypatch, fake)
    _base(_ansible_check_mode=True, state="stopped", description="renamed")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["notebook"]["Description"] == "renamed"
    assert "ModifyNotebook" not in fake.calls


def test_modify_running_requires_wait(monkeypatch):
    fake = FakeTioneClient(notebooks=[_notebook()])
    _make_module(monkeypatch, fake)
    _base(state="running", description="renamed", wait=False)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "wait=true is required to stop a TIONE notebook before modifying it" in exc.value.args[0]["msg"]


def test_update_running_notebook_stops_modifies_restarts(monkeypatch):
    fake = FakeTioneClient(notebooks=[_notebook()])
    _make_module(monkeypatch, fake)
    _base(state="running", description="renamed", wait=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["notebook"]["Description"] == "renamed"
    assert result["notebook"]["Status"] == "running"
    ops = list(fake.calls)
    assert "StopNotebook" in ops
    assert "ModifyNotebook" in ops
    assert "StartNotebook" in ops


def test_start_stopped_notebook(monkeypatch):
    fake = FakeTioneClient(notebooks=[_notebook(Status="stopped")])
    _make_module(monkeypatch, fake)
    _base(state="running", description="production")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["notebook"]["Status"] == "running"
    ops = list(fake.calls)
    assert "StartNotebook" in ops
    assert "ModifyNotebook" not in ops


def test_stop_running_notebook(monkeypatch):
    fake = FakeTioneClient(notebooks=[_notebook()])
    _make_module(monkeypatch, fake)
    _base(state="stopped", description="production")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["notebook"]["Status"] == "stopped"
    ops = list(fake.calls)
    assert "StopNotebook" in ops


def test_multiple_matches_fail(monkeypatch):
    fake = FakeTioneClient(notebooks=[_notebook(), _notebook(Id="nb-dup")])
    _make_module(monkeypatch, fake)
    _base(state="running")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "Multiple TIONE notebooks matched" in exc.value.args[0]["msg"]


# ---------------------------------------------------------------------------
# failure paths
# ---------------------------------------------------------------------------


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeNotebooks(self, request):
            raise Boom("connection dropped")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    _base(state="running", name="llm-finetuning")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]


# ---------------------------------------------------------------------------
# legacy helper regression tests (folded from test_tione_notebook.py)
# ---------------------------------------------------------------------------


class LegacyObject(object):
    def from_json_string(self, value):
        self.value = value


class LegacyModels(object):
    CreateNotebookRequest = ModifyNotebookRequest = ResourceConf = CFSConfig = GooseFS = LogConfig = Tag = DataConfig = ImageInfo = SSHConfig = LegacyObject


def legacy_params():
    return {
        "name": "nb",
        "charge_type": "POSTPAID_BY_HOUR",
        "resource_conf": {"Cpu": 4},
        "log_enable": True,
        "root_access": False,
        "auto_stopping": True,
        "direct_internet_access": False,
        "resource_group_id": None,
        "vpc_id": "vpc-1",
        "subnet_id": "subnet-1",
        "volume_source_type": "CLOUD_PREMIUM",
        "volume_size_gb": 100,
        "volume_source_cfs": None,
        "volume_source_goosefs": None,
        "log_config": None,
        "lifecycle_script_id": None,
        "default_code_repo_id": None,
        "additional_code_repo_ids": ["r2", "r1"],
        "automatic_stop_time": 4,
        "tags": [{"TagKey": "b", "TagValue": "2"}],
        "data_configs": None,
        "image_info": {"ImageId": "img-1"},
        "image_type": "SYSTEM",
        "ssh_config": None,
        "description": "workbench",
    }


def test_create_maps_full_notebook_configuration():
    request = mod.create_request(LegacyModels, legacy_params())
    assert request.Name == "nb" and request.ChargeType == "POSTPAID_BY_HOUR" and request.VolumeSizeInGB == 100
    assert request.ResourceConf is not None and request.ImageInfo is not None and len(request.Tags) == 1


def test_modify_excludes_unmodifiable_goosefs_but_maps_mutable_fields():
    p = legacy_params()
    p["volume_source_goosefs"] = {"Id": "g1"}
    request = mod.modify_request(LegacyModels, "nb-1", p)
    assert request.Id == "nb-1" and request.Name == "nb" and request.AutoStopping is True
    assert not hasattr(request, "VolumeSourceGooseFS")


def test_drift_separates_mutable_and_immutable_fields_and_normalizes_tags():
    p = legacy_params()
    current = dict(mod.normalize({"Name": "nb", "ChargeType": "PREPAID", "ResourceConf": {"Cpu": 2}, "Tags": p["tags"]}))
    mutable, immutable = mod.drift(p, current)
    assert "ResourceConf" in mutable and "ChargeType" in immutable and "Tags" not in mutable


def test_status_is_case_insensitive_and_null_safe():
    assert mod.status({"Status": "Running"}) == "running" and mod.status(None) == ""


class LegacyFailingModule(object):
    def fail_json(self, **kwargs):
        raise RuntimeError(kwargs["msg"])


def test_converge_rejects_unknown_operational_state():
    with pytest.raises(RuntimeError, match="unsupported operational state"):
        mod.converge_stopped(LegacyFailingModule(), object(), object(), {"notebook_id": "nb-1", "project_id": None, "wait": True}, {"Status": "Unknown"})
