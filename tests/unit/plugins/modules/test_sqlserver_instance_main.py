"""Unit tests for the sqlserver_instance write module (run_module flows).

Drives ``run_module()`` end to end against an in-memory fake SQL Server
client whose write operations mutate the instance store so the post-write
``find`` refetch and the ``wait_for_state`` waiter converge immediately.

Scenario matrix:

* absent on a missing instance (idempotent no-op)
* absent with a matching instance (check-mode dry run, real isolation)
* already-isolated no-op and the purge guard/dry-run/delete path
* creation when missing (with/without the mandatory creation parameters,
  check mode, and the post-create waiter/lookup)
* no-op when nothing drifts
* immutable network-placement drift guard
* rename and resize drift updates (with and without check mode)
* multiple-match ambiguity and the blanket ``sdk_error_payload`` failure
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import sqlserver_instance as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

INSTANCE_ID = "mssql-8b0a1c2d"
INSTANCE_NAME = "production-sqlserver"

INSTANCE = {
    "InstanceId": INSTANCE_ID,
    "Name": INSTANCE_NAME,
    "Zone": "ap-guangzhou-3",
    "UniqVpcId": "vpc-abcdef12",
    "UniqSubnetId": "subnet-abcdef12",
    "Memory": 8,
    "Storage": 100,
    "Cpu": 4,
    "Version": "2019",
    "Status": 2,
}


def _instance(**overrides):
    item = dict(INSTANCE)
    item.update(overrides)
    return item


def _base(**overrides):
    params = {}
    params.update(overrides)
    return module_args(**params)


def _id_args(**overrides):
    params = {"instance_id": INSTANCE_ID}
    params.update(overrides)
    return params


def _name_args(**overrides):
    params = {"name": INSTANCE_NAME}
    params.update(overrides)
    return params


class FakeSqlserverClient(object):
    """In-memory SQL Server client mutating a small instance store."""

    def __init__(self, instances=None):
        self.instances = [dict(t) for t in (instances or [])]
        self.calls = []
        self._next = 0
        self._last_name = None

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def DescribeDBInstances(self, request):
        self._record("DescribeDBInstances", request)
        id_set = list(getattr(request, "InstanceIdSet", None) or [])
        name_set = list(getattr(request, "InstanceNameSet", None) or [])
        if name_set:
            self._last_name = name_set[0]
        if id_set:
            rows = [t for t in self.instances if t.get("InstanceId") in id_set]
        elif name_set:
            rows = [t for t in self.instances if t.get("Name") == name_set[0]]
        else:
            rows = list(self.instances)
        return SimpleNamespace(DBInstances=[FakeResource(t) for t in rows], TotalCount=len(rows), RequestId="req-list")

    def CreateDBInstances(self, request):
        self._record("CreateDBInstances", request)
        self._next += 1
        row = {
            "InstanceId": "mssql-new-%03d" % self._next,
            "Name": self._last_name,
            "Zone": getattr(request, "Zone", None),
            "UniqVpcId": getattr(request, "VpcId", None),
            "UniqSubnetId": getattr(request, "SubnetId", None),
            "Memory": getattr(request, "Memory", None),
            "Storage": getattr(request, "Storage", None),
            "Version": getattr(request, "DBVersion", None),
            "Status": 2,
        }
        self.instances.append(row)
        return SimpleNamespace(DealNames=["deal-1"], RequestId="req-create")

    def ModifyDBInstanceName(self, request):
        self._record("ModifyDBInstanceName", request)
        for item in self.instances:
            if item.get("InstanceId") == getattr(request, "InstanceId", None):
                item["Name"] = getattr(request, "InstanceName", None)
        return SimpleNamespace(RequestId="req-rename")

    def UpgradeDBInstance(self, request):
        self._record("UpgradeDBInstance", request)
        for item in self.instances:
            if item.get("InstanceId") == getattr(request, "InstanceId", None):
                for attr in ("Memory", "Storage", "Cpu", "DBVersion"):
                    value = getattr(request, attr, None)
                    if value is not None:
                        item[{"DBVersion": "Version"}.get(attr, attr)] = value
                item["Status"] = 2
        return SimpleNamespace(DealNames=["deal-upgrade"], RequestId="req-upgrade")

    def TerminateDBInstance(self, request):
        self._record("TerminateDBInstance", request)
        id_set = list(getattr(request, "InstanceIdSet", None) or [])
        for item in self.instances:
            if item.get("InstanceId") in id_set:
                item["Status"] = -1
        return SimpleNamespace(RequestId="req-terminate")

    def DeleteDBInstance(self, request):
        self._record("DeleteDBInstance", request)
        instance_id = getattr(request, "InstanceId", None)
        self.instances = [t for t in self.instances if t.get("InstanceId") != instance_id]
        return SimpleNamespace(RequestId="req-delete")


def _make_module(monkeypatch, fake, models=None):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (models or FakeModels(), SimpleNamespace(SqlserverClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)


# ---------------------------------------------------------------------------
# absent flows
# ---------------------------------------------------------------------------


def test_absent_missing_instance_is_idempotent(monkeypatch):
    fake = FakeSqlserverClient()
    _make_module(monkeypatch, fake)
    _base(state="absent", **_id_args())
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["instance"] is None
    assert [c for c, unused in fake.calls] == ["DescribeDBInstances"]


def test_absent_isolates_running_instance(monkeypatch):
    fake = FakeSqlserverClient(instances=[_instance()])
    _make_module(monkeypatch, fake)
    _base(state="absent", **_id_args())
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["instance"]["InstanceId"] == INSTANCE_ID
    ops = [c for c, unused in fake.calls]
    assert "TerminateDBInstance" in ops
    assert "DeleteDBInstance" not in ops


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeSqlserverClient(instances=[_instance()])
    _make_module(monkeypatch, fake)
    _base(_ansible_check_mode=True, state="absent", **_id_args())
    result = run(mod.run_module)
    assert result["changed"] is True
    assert len(fake.instances) == 1
    assert "TerminateDBInstance" not in [c for c, unused in fake.calls]


def test_absent_already_isolated_is_idempotent(monkeypatch):
    fake = FakeSqlserverClient(instances=[_instance(Status=-1)])
    _make_module(monkeypatch, fake)
    _base(state="absent", **_id_args())
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["instance"]["Status"] == -1
    ops = [c for c, unused in fake.calls]
    assert "TerminateDBInstance" not in ops
    assert "DeleteDBInstance" not in ops


def test_purge_requires_isolated_instance(monkeypatch):
    fake = FakeSqlserverClient(instances=[_instance(Status=2)])
    _make_module(monkeypatch, fake)
    _base(state="absent", purge=True, **_id_args())
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "purge requires an already isolated SQL Server instance" in payload["msg"]
    assert payload["current_status"] == 2


def test_purge_isolated_instance_deletes(monkeypatch):
    fake = FakeSqlserverClient(instances=[_instance(Status=-1)])
    _make_module(monkeypatch, fake)
    _base(state="absent", purge=True, **_id_args())
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["instance"] is None
    assert fake.instances == []
    assert "DeleteDBInstance" in [c for c, unused in fake.calls]


def test_purge_check_mode_is_dry_run(monkeypatch):
    fake = FakeSqlserverClient(instances=[_instance(Status=5)])
    _make_module(monkeypatch, fake)
    _base(_ansible_check_mode=True, state="absent", purge=True, **_id_args())
    result = run(mod.run_module)
    assert result["changed"] is True
    assert len(fake.instances) == 1
    assert "DeleteDBInstance" not in [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# creation flows
# ---------------------------------------------------------------------------


def test_create_requires_creation_parameters(monkeypatch):
    fake = FakeSqlserverClient()
    _make_module(monkeypatch, fake)
    _base(state="present", **_name_args())
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "creation parameters are required" in payload["msg"]
    assert set(payload["missing"]) == {"zone", "vpc_id", "subnet_id", "memory", "storage", "db_version"}


def test_create_instance(monkeypatch):
    fake = FakeSqlserverClient()
    _make_module(monkeypatch, fake)
    _base(
        state="present",
        **_name_args(zone="ap-guangzhou-3", vpc_id="vpc-abcdef12", subnet_id="subnet-abcdef12",
                     memory=8, storage=100, db_version="2019"),
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["instance"]["InstanceId"].startswith("mssql-new-")
    assert result["instance"]["Memory"] == 8
    assert result["instance"]["Storage"] == 100
    assert result["instance"]["Status"] == 2
    assert len(fake.instances) == 1
    ops = [c for c, unused in fake.calls]
    assert ops[0] == "DescribeDBInstances"
    assert "CreateDBInstances" in ops


def test_create_check_mode_is_dry_run(monkeypatch):
    fake = FakeSqlserverClient()
    _make_module(monkeypatch, fake)
    _base(
        _ansible_check_mode=True,
        state="present",
        **_name_args(zone="ap-guangzhou-3", vpc_id="vpc-abcdef12", subnet_id="subnet-abcdef12",
                     memory=8, storage=100, db_version="2019"),
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["instance"] == {
        "Name": INSTANCE_NAME,
        "Zone": "ap-guangzhou-3",
        "UniqVpcId": "vpc-abcdef12",
        "UniqSubnetId": "subnet-abcdef12",
        "Memory": 8,
        "Storage": 100,
        "Version": "2019",
    }
    assert fake.instances == []
    assert "CreateDBInstances" not in [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# existing-instance flows
# ---------------------------------------------------------------------------


def test_existing_instance_no_drift_is_idempotent(monkeypatch):
    fake = FakeSqlserverClient(instances=[_instance()])
    _make_module(monkeypatch, fake)
    _base(
        state="present",
        **_id_args(name=INSTANCE_NAME, memory=8, storage=100, cpu=4,
                   db_version="2019", zone="ap-guangzhou-3", vpc_id="vpc-abcdef12", subnet_id="subnet-abcdef12"),
    )
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["instance"]["InstanceId"] == INSTANCE_ID
    ops = [c for c, unused in fake.calls]
    assert "ModifyDBInstanceName" not in ops
    assert "UpgradeDBInstance" not in ops


def test_immutable_placement_drift_fails(monkeypatch):
    fake = FakeSqlserverClient(instances=[_instance()])
    _make_module(monkeypatch, fake)
    _base(state="present", **_id_args(name=INSTANCE_NAME, zone="ap-beijing-1", memory=8, storage=100, cpu=4))
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "network placement is immutable" in payload["msg"]
    assert "Zone" in payload["immutable_drift"]


def test_rename_instance(monkeypatch):
    fake = FakeSqlserverClient(instances=[_instance()])
    _make_module(monkeypatch, fake)
    _base(state="present", **_id_args(name="renamed-sqlserver", memory=8, storage=100, cpu=4))
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["instance"]["Name"] == "renamed-sqlserver"
    ops = [c for c, unused in fake.calls]
    assert "ModifyDBInstanceName" in ops
    assert "UpgradeDBInstance" not in ops


def test_resize_instance(monkeypatch):
    fake = FakeSqlserverClient(instances=[_instance()])
    _make_module(monkeypatch, fake)
    _base(state="present", **_id_args(name=INSTANCE_NAME, memory=16, storage=200, cpu=8))
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["instance"]["Memory"] == 16
    assert result["instance"]["Storage"] == 200
    assert result["instance"]["Cpu"] == 8
    assert result["instance"]["Status"] == 2
    assert "UpgradeDBInstance" in [c for c, unused in fake.calls]


def test_update_check_mode_is_dry_run(monkeypatch):
    fake = FakeSqlserverClient(instances=[_instance()])
    _make_module(monkeypatch, fake)
    _base(_ansible_check_mode=True, state="present", **_id_args(name="renamed-sqlserver", memory=16, cpu=8))
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["instance"]["Memory"] == 8
    ops = [c for c, unused in fake.calls]
    assert "ModifyDBInstanceName" not in ops
    assert "UpgradeDBInstance" not in ops


def test_rename_and_resize_together(monkeypatch):
    fake = FakeSqlserverClient(instances=[_instance()])
    _make_module(monkeypatch, fake)
    _base(state="present", **_id_args(name="renamed-sqlserver", memory=16, storage=200))
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["instance"]["Name"] == "renamed-sqlserver"
    assert result["instance"]["Memory"] == 16
    ops = [c for c, unused in fake.calls]
    assert "ModifyDBInstanceName" in ops
    assert "UpgradeDBInstance" in ops


# ---------------------------------------------------------------------------
# guards / failure paths
# ---------------------------------------------------------------------------


def test_multiple_matching_instances_fail(monkeypatch):
    fake = FakeSqlserverClient(instances=[_instance(), _instance(InstanceId="mssql-dup")])
    _make_module(monkeypatch, fake)
    _base(state="present", **_name_args(memory=8, storage=100, cpu=4))
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "Ambiguous SQL Server instance reference" in payload["msg"]
    assert payload["ambiguous"] is True


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeDBInstances(self, request):
            raise Boom("connection dropped")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    _base(state="present", **_name_args())
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]
