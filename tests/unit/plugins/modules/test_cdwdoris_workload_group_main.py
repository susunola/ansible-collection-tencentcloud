"""Unit tests for the cdwdoris_workload_group write module (run_module flows).

The module reconciles a named Doris workload group (create/update/delete)
and optionally the instance-wide workload-group switch. The fake CDW Doris
client mutates a group store and status so post-write describe calls
converge immediately.

Scenario matrix:

* argument validation (missing instance/name) and multiple-match failure
* no-op when group limits and the instance switch already match
* create flows (real and check-mode dry run)
* limit drift drives ``ModifyWorkloadGroup``
* the instance-wide switch is toggled independently of group limits
* delete flows (present, absent no-op, check-mode dry run)
* the blanket SDK failure path
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import cdwdoris_workload_group as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

INSTANCE_ID = "cdwdoris-xxxxxxxx"


def _args(**overrides):
    params = {"instance_id": INSTANCE_ID, "name": "interactive"}
    params.update(overrides)
    return module_args(**params)


def _group(**overrides):
    item = {"WorkloadGroupName": "interactive", "CpuShare": 800, "MemoryLimit": 40, "MaxConcurrencyNum": 30}
    item.update(overrides)
    return item


class FakeCdwdorisClient(object):
    """In-memory CDW Doris client mutating a workload-group store."""

    def __init__(self, groups=None, status="close"):
        self.groups = [copy.deepcopy(g) for g in (groups or [])]
        self.status = status
        self.calls = []

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def DescribeWorkloadGroup(self, request):
        self._record("DescribeWorkloadGroup", request)
        return SimpleNamespace(WorkloadGroups=[FakeResource(g) for g in self.groups], Status=self.status, ErrorMsg=None)

    def CreateWorkloadGroup(self, request):
        self._record("CreateWorkloadGroup", request)
        self.groups.append(copy.deepcopy(vars(request.WorkloadGroup)))
        return SimpleNamespace(ErrorMsg=None, RequestId="req-fake")

    def ModifyWorkloadGroup(self, request):
        self._record("ModifyWorkloadGroup", request)
        payload = vars(request.WorkloadGroup)
        name = payload.get("WorkloadGroupName")
        for group in self.groups:
            if group.get("WorkloadGroupName") == name:
                group.update(copy.deepcopy(payload))
        return SimpleNamespace(ErrorMsg=None, RequestId="req-fake")

    def DeleteWorkloadGroup(self, request):
        self._record("DeleteWorkloadGroup", request)
        self.groups = [g for g in self.groups if g.get("WorkloadGroupName") != getattr(request, "WorkloadGroupName", None)]
        return SimpleNamespace(ErrorMsg=None, RequestId="req-fake")

    def ModifyWorkloadGroupStatus(self, request):
        self._record("ModifyWorkloadGroupStatus", request)
        self.status = getattr(request, "OperationType", None) or self.status
        return SimpleNamespace(ErrorMsg=None, RequestId="req-fake")


def _make_module(monkeypatch, fake, models=None):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (models or FakeModels(), SimpleNamespace(CdwdorisClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


def test_missing_required_args_fails(monkeypatch):
    fake = FakeCdwdorisClient()
    _make_module(monkeypatch, fake)
    module_args()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "missing required arguments" in exc.value.args[0]["msg"]
    assert fake.calls == []


def test_idempotent_when_group_and_status_match(monkeypatch):
    fake = FakeCdwdorisClient(groups=[_group()], status="open")
    _make_module(monkeypatch, fake)
    _args(cpu_share=800, memory_limit=40, max_concurrency=30, workload_groups_enabled=True)
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["workload_group"]["WorkloadGroupName"] == "interactive"
    assert result["workload_groups_status"] == "open"
    assert [c for c, unused in fake.calls] == ["DescribeWorkloadGroup", "DescribeWorkloadGroup"]


def test_create_workload_group(monkeypatch):
    fake = FakeCdwdorisClient()
    _make_module(monkeypatch, fake)
    _args(cpu_share=800, memory_limit=40)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["workload_group"]["CpuShare"] == 800
    assert result["workload_groups_status"] == "close"
    assert len(fake.groups) == 1
    ops = [c for c, unused in fake.calls]
    assert "CreateWorkloadGroup" in ops
    assert "ModifyWorkloadGroupStatus" not in ops


def test_create_check_mode_is_dry_run(monkeypatch):
    fake = FakeCdwdorisClient()
    _make_module(monkeypatch, fake)
    _args(_ansible_check_mode=True, cpu_share=800)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["workload_group"] == {"WorkloadGroupName": "interactive", "CpuShare": 800}
    assert fake.groups == []
    assert "CreateWorkloadGroup" not in [c for c, unused in fake.calls]


def test_limit_drift_updates_group(monkeypatch):
    fake = FakeCdwdorisClient(groups=[_group()])
    _make_module(monkeypatch, fake)
    _args(cpu_share=900)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["workload_group"]["CpuShare"] == 900
    assert result["workload_group"]["MemoryLimit"] == 40
    modify_call = next((c, r) for c, r in fake.calls if c == "ModifyWorkloadGroup")
    assert vars(getattr(modify_call[1], "WorkloadGroup"))["CpuShare"] == 900
    assert vars(getattr(modify_call[1], "WorkloadGroup"))["MemoryLimit"] == 40


def test_instance_switch_toggled_independently(monkeypatch):
    fake = FakeCdwdorisClient(groups=[_group()], status="close")
    _make_module(monkeypatch, fake)
    _args(cpu_share=800, memory_limit=40, workload_groups_enabled=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["workload_groups_status"] == "open"
    ops = [c for c, unused in fake.calls]
    assert "ModifyWorkloadGroup" not in ops
    assert "ModifyWorkloadGroupStatus" in ops


def test_delete_workload_group(monkeypatch):
    fake = FakeCdwdorisClient(groups=[_group()])
    _make_module(monkeypatch, fake)
    _args(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["workload_group"] is None
    assert fake.groups == []
    delete_call = next((c, r) for c, r in fake.calls if c == "DeleteWorkloadGroup")
    assert getattr(delete_call[1], "WorkloadGroupName") == "interactive"


def test_delete_missing_group_is_idempotent(monkeypatch):
    fake = FakeCdwdorisClient()
    _make_module(monkeypatch, fake)
    _args(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["workload_group"] is None
    assert "DeleteWorkloadGroup" not in [c for c, unused in fake.calls]


def test_delete_check_mode_is_dry_run(monkeypatch):
    fake = FakeCdwdorisClient(groups=[_group()])
    _make_module(monkeypatch, fake)
    _args(_ansible_check_mode=True, state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert len(fake.groups) == 1
    assert "DeleteWorkloadGroup" not in [c for c, unused in fake.calls]


def test_multiple_matches_fail(monkeypatch):
    fake = FakeCdwdorisClient(groups=[_group(), _group(CpuShare=200)])
    _make_module(monkeypatch, fake)
    _args(cpu_share=800)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "Multiple CDW Doris workload groups matched" in exc.value.args[0]["msg"]


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeWorkloadGroup(self, request):
            raise Boom("connection dropped")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    _args(cpu_share=800)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]


# ---------------------------------------------------------------------------
# legacy helper regression tests (folded from test_cdwdoris_workload_group.py)
# ---------------------------------------------------------------------------


def test_desired_only_manages_explicit_limits():
    value = mod.desired(
        {
            "name": "interactive",
            "cpu_share": 800,
            "memory_limit": None,
            "enable_memory_overcommit": None,
            "cpu_hard_limit": None,
            "min_cpu_percent": None,
            "min_memory_percent": None,
            "max_concurrency": 30,
            "max_queue_size": None,
            "queue_timeout": None,
        }
    )
    assert value == {"WorkloadGroupName": "interactive", "CpuShare": 800, "MaxConcurrencyNum": 30}


def test_comparable_ignores_server_computed_fields():
    target = {"WorkloadGroupName": "batch", "MemoryLimit": 60}
    current = {"WorkloadGroupName": "batch", "MemoryLimit": 60, "ServerOnly": "ignored"}
    assert mod.comparable(current, target) == target


def test_update_payload_preserves_unspecified_resource_limits():
    current = {"WorkloadGroupName": "batch", "CpuShare": 200, "MemoryLimit": 60, "ServerOnly": "ignored"}
    assert mod.update_payload(current, {"WorkloadGroupName": "batch", "CpuShare": 300}) == {
        "WorkloadGroupName": "batch",
        "CpuShare": 300,
        "MemoryLimit": 60,
    }
