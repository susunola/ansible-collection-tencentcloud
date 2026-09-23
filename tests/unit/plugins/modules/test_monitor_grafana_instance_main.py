"""Unit tests for the monitor_grafana_instance write module (run_module flows).

Drives ``run_module()`` against an in-memory fake Monitor client whose
create / modify / delete operations mutate a Grafana-instance store so the
module's post-write ``find`` converges immediately.

Scenario matrix:

* absent on a missing instance (idempotent no-op, by name or by id)
* absent with a matching instance (check-mode dry run, real delete)
* the ``name``-required-when-present guard
* creation when missing (missing vpc/subnet guard, happy path, check mode)
* no-op when the instance name already matches
* rename by ``instance_id`` through Modify
* the ambiguous-name guard and the blanket SDK failure path
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import monitor_grafana_instance as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

INSTANCE = {
    "InstanceId": "grafana-abc123",
    "InstanceName": "production-dashboards",
    "InternetUrl": "https://grafana.example.com",
    "Status": 2,
}


def _instance(**overrides):
    item = copy.deepcopy(INSTANCE)
    item.update(overrides)
    return item


def _name_args(**overrides):
    params = {"name": "production-dashboards"}
    params.update(overrides)
    return module_args(**params)


def _id_args(**overrides):
    params = {"instance_id": "grafana-abc123", "name": "production-dashboards"}
    params.update(overrides)
    return module_args(**params)


class FakeMonitorClient(object):
    """In-memory Monitor client mutating a small Grafana-instance store."""

    def __init__(self, instances=None):
        self.instances = [copy.deepcopy(t) for t in (instances or [])]
        self.calls = []
        self._next = 0

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def DescribeGrafanaInstances(self, request):
        self._record("DescribeGrafanaInstances", request)
        ids = list(getattr(request, "InstanceIds", None) or [])
        name = getattr(request, "InstanceName", None)
        matched = list(self.instances)
        if ids:
            matched = [t for t in matched if t.get("InstanceId") in ids]
        elif name:
            matched = [t for t in matched if t.get("InstanceName") == name]
        # The module reads ``InstanceSet or Instances or []``, so the
        # fallback attribute must exist even when the primary set is empty.
        return SimpleNamespace(InstanceSet=[FakeResource(t) for t in matched], Instances=None)

    def CreateGrafanaInstance(self, request):
        self._record("CreateGrafanaInstance", request)
        self._next += 1
        item = {
            "InstanceId": "grafana-new-%03d" % self._next,
            "InstanceName": getattr(request, "InstanceName", None),
            "VpcId": getattr(request, "VpcId", None),
            "SubnetIds": list(getattr(request, "SubnetIds", None) or []),
            "EnableInternet": getattr(request, "EnableInternet", False),
        }
        self.instances.append(item)
        return SimpleNamespace(InstanceId=item["InstanceId"], RequestId="req-fake")

    def ModifyGrafanaInstance(self, request):
        self._record("ModifyGrafanaInstance", request)
        for item in self.instances:
            if item.get("InstanceId") == getattr(request, "InstanceId", None):
                item["InstanceName"] = getattr(request, "InstanceName", item.get("InstanceName"))
        return SimpleNamespace(RequestId="req-fake")

    def DeleteGrafanaInstance(self, request):
        self._record("DeleteGrafanaInstance", request)
        ids = list(getattr(request, "InstanceIDs", None) or [])
        self.instances = [t for t in self.instances if t.get("InstanceId") not in ids]
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (FakeModels(), SimpleNamespace(MonitorClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


# ---------------------------------------------------------------------------
# guards
# ---------------------------------------------------------------------------


def test_present_requires_name(monkeypatch):
    fake = FakeMonitorClient(instances=[])
    _make_module(monkeypatch, fake)
    module_args(state="present", instance_id="grafana-abc123")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert exc.value.args[0]["msg"] == "name is required when state=present"


def test_create_requires_vpc_and_subnets(monkeypatch):
    fake = FakeMonitorClient(instances=[])
    _make_module(monkeypatch, fake)
    _name_args(state="present")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert exc.value.args[0]["msg"] == "vpc_id and subnet_ids are required when creating"


# ---------------------------------------------------------------------------
# absent flows
# ---------------------------------------------------------------------------


def test_absent_missing_by_name_is_idempotent(monkeypatch):
    fake = FakeMonitorClient(instances=[])
    _make_module(monkeypatch, fake)
    _name_args(state="absent", name="ghost-instance")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["instance"] is None
    assert [c for c, unused in fake.calls] == ["DescribeGrafanaInstances"]


def test_absent_missing_by_id_is_idempotent(monkeypatch):
    fake = FakeMonitorClient(instances=[])
    _make_module(monkeypatch, fake)
    module_args(state="absent", instance_id="grafana-9999")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["instance"] is None


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeMonitorClient(instances=[_instance()])
    _make_module(monkeypatch, fake)
    _name_args(_ansible_check_mode=True, state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["instance"]["InstanceId"] == "grafana-abc123"
    assert len(fake.instances) == 1
    assert "DeleteGrafanaInstance" not in [c for c, unused in fake.calls]


def test_absent_deletes_instance(monkeypatch):
    fake = FakeMonitorClient(instances=[_instance()])
    _make_module(monkeypatch, fake)
    _id_args(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["instance"] is None
    assert fake.instances == []
    ops = [c for c, unused in fake.calls]
    assert "DeleteGrafanaInstance" in ops


# ---------------------------------------------------------------------------
# creation flows
# ---------------------------------------------------------------------------


def test_create_instance(monkeypatch):
    fake = FakeMonitorClient(instances=[])
    _make_module(monkeypatch, fake)
    _name_args(
        state="present",
        vpc_id="vpc-xxxxxx",
        subnet_ids=["subnet-1", "subnet-2"],
        tags={"env": "prod", "team": "sre"},
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["instance"]["InstanceName"] == "production-dashboards"
    assert result["instance"]["InstanceId"].startswith("grafana-new-")
    assert len(fake.instances) == 1
    ops = [c for c, unused in fake.calls]
    assert ops[0] == "DescribeGrafanaInstances"
    assert "CreateGrafanaInstance" in ops


def test_create_check_mode_is_dry_run(monkeypatch):
    fake = FakeMonitorClient(instances=[])
    _make_module(monkeypatch, fake)
    _name_args(_ansible_check_mode=True, state="present", vpc_id="vpc-xxxxxx", subnet_ids=["subnet-1"])
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["instance"] is None
    assert fake.instances == []
    assert "CreateGrafanaInstance" not in [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# existing-instance flows
# ---------------------------------------------------------------------------


def test_existing_instance_no_drift_is_idempotent(monkeypatch):
    fake = FakeMonitorClient(instances=[_instance()])
    _make_module(monkeypatch, fake)
    _name_args(state="present")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["instance"]["InstanceId"] == "grafana-abc123"
    assert "ModifyGrafanaInstance" not in [c for c, unused in fake.calls]


def test_rename_instance_by_id(monkeypatch):
    fake = FakeMonitorClient(instances=[_instance()])
    _make_module(monkeypatch, fake)
    _id_args(state="present", name="renamed-dashboards")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["instance"]["InstanceName"] == "renamed-dashboards"
    assert fake.instances[0]["InstanceName"] == "renamed-dashboards"
    ops = [c for c, unused in fake.calls]
    assert "ModifyGrafanaInstance" in ops


def test_ambiguous_name_match_fails(monkeypatch):
    fake = FakeMonitorClient(instances=[_instance(), _instance(InstanceId="grafana-xyz789")])
    _make_module(monkeypatch, fake)
    _name_args(state="present")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "Multiple Grafana instances have the requested name" in exc.value.args[0]["msg"]


# ---------------------------------------------------------------------------
# failure paths
# ---------------------------------------------------------------------------


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeGrafanaInstances(self, request):
            raise Boom("connection dropped")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    _name_args(state="present")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]
