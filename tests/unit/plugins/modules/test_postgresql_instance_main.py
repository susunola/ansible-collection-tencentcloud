"""Unit tests for the postgresql_instance write module (run_module flows).

Drives ``run_module()`` end to end against an in-memory fake Postgres client
whose write operations mutate the instance store, so the post-write describe
refetch and waiters converge immediately.

Scenario matrix:

* absent on a missing instance (idempotent no-op)
* absent with a matching instance (check-mode dry run, real isolate-and-wait,
  already-isolated no-op, and purge guards)
* creation when missing (missing creation parameters, check-mode dry run and
  the happy path with waiting)
* no-op when nothing drifts
* rename / resize / auto-renew drift updates
* the immutable network-placement guard
* the ambiguous-reference guard
* the blanket ``Tencent Cloud API request failed`` failure path
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import postgresql_instance as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

INSTANCE_ID = "postgres-8b0a1c2d"

INSTANCE = {
    "DBInstanceId": INSTANCE_ID,
    "DBInstanceName": "production-postgres",
    "Zone": "ap-guangzhou-3",
    "VpcId": "vpc-abc",
    "SubnetId": "subnet-abc",
    "DBInstanceCpu": 2,
    "DBInstanceMemory": 4,
    "DBInstanceStorage": 100,
    "DBMajorVersion": "15",
    "AutoRenew": 0,
    "DBInstanceStatus": "running",
}


def _instance(**overrides):
    item = copy.deepcopy(INSTANCE)
    item.update(overrides)
    return item


def _base(**overrides):
    # NOTE: keys carrying ``choices`` (state, charset, charge_type,
    # auto_renew) must not be pre-filled with None. instance_id/name are a
    # required_one_of pair so a helper supplies exactly one of them.
    params = {}
    params.update(overrides)
    return module_args(**params)


def _name_args(**overrides):
    params = {"name": "production-postgres"}
    params.update(overrides)
    return module_args(**params)


def _id_args(**overrides):
    params = {"instance_id": INSTANCE_ID}
    params.update(overrides)
    return module_args(**params)


class FakePostgresClient(object):
    """In-memory Postgres client mutating a small instance store."""

    def __init__(self, instances=None):
        self.instances = [copy.deepcopy(t) for t in (instances or [])]
        self.calls = []

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def DescribeDBInstances(self, request):
        self._record("DescribeDBInstances", request)
        filters = {getattr(f, "Name", None): list(getattr(f, "Values", None) or []) for f in (getattr(request, "Filters", None) or [])}
        if filters.get("db-instance-id"):
            wanted = filters["db-instance-id"][0]
            page = [dict(t) for t in self.instances if str(t.get("DBInstanceId")) == str(wanted)]
        elif filters.get("db-instance-name"):
            wanted = filters["db-instance-name"][0]
            page = [dict(t) for t in self.instances if t.get("DBInstanceName") == wanted]
        else:
            page = [dict(t) for t in self.instances]
        return SimpleNamespace(DBInstanceSet=[FakeResource(t) for t in page], TotalCount=len(page))

    def CreateInstances(self, request):
        self._record("CreateInstances", request)
        item = {
            "DBInstanceId": "postgres-new-%d" % (len(self.instances) + 1),
            "DBInstanceName": getattr(request, "Name", None),
            "Zone": getattr(request, "Zone", None),
            "VpcId": getattr(request, "VpcId", None),
            "SubnetId": getattr(request, "SubnetId", None),
            "DBMajorVersion": getattr(request, "DBMajorVersion", None),
            "DBInstanceStorage": getattr(request, "Storage", None),
            "DBInstanceCpu": 2,
            "DBInstanceMemory": 4,
            "DBInstanceStatus": "running",
            "AutoRenew": 0,
        }
        self.instances.append(item)
        return SimpleNamespace(DBInstanceIdSet=[item["DBInstanceId"]], RequestId="req-fake")

    def ModifyDBInstanceName(self, request):
        self._record("ModifyDBInstanceName", request)
        for item in self.instances:
            if item.get("DBInstanceId") == getattr(request, "DBInstanceId", None):
                item["DBInstanceName"] = getattr(request, "InstanceName", None)
        return SimpleNamespace(RequestId="req-fake")

    def ModifyDBInstanceSpec(self, request):
        self._record("ModifyDBInstanceSpec", request)
        for item in self.instances:
            if item.get("DBInstanceId") == getattr(request, "DBInstanceId", None):
                for attr, name in (("Cpu", "DBInstanceCpu"), ("Memory", "DBInstanceMemory"), ("Storage", "DBInstanceStorage")):
                    value = getattr(request, attr, None)
                    if value is not None:
                        item[name] = value
                item["DBInstanceStatus"] = "running"
        return SimpleNamespace(RequestId="req-fake")

    def SetAutoRenewFlag(self, request):
        self._record("SetAutoRenewFlag", request)
        ids = list(getattr(request, "DBInstanceIdSet", None) or [])
        flag = getattr(request, "AutoRenewFlag", None)
        for item in self.instances:
            if item.get("DBInstanceId") in ids:
                item["AutoRenew"] = flag
        return SimpleNamespace(RequestId="req-fake")

    def IsolateDBInstances(self, request):
        self._record("IsolateDBInstances", request)
        ids = list(getattr(request, "DBInstanceIdSet", None) or [])
        for item in self.instances:
            if item.get("DBInstanceId") in ids:
                item["DBInstanceStatus"] = "isolated"
        return SimpleNamespace(RequestId="req-fake")

    def DestroyDBInstance(self, request):
        self._record("DestroyDBInstance", request)
        self.instances = [t for t in self.instances if t.get("DBInstanceId") != getattr(request, "DBInstanceId", None)]
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake, models=None):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (models or FakeModels(), SimpleNamespace(PostgresClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


# ---------------------------------------------------------------------------
# absent flows
# ---------------------------------------------------------------------------


def test_absent_missing_instance_is_idempotent(monkeypatch):
    fake = FakePostgresClient(instances=[])
    _make_module(monkeypatch, fake)
    _name_args(state="absent", name="ghost-db")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["instance"] is None


def test_absent_isolates_running_instance(monkeypatch):
    fake = FakePostgresClient(instances=[_instance()])
    _make_module(monkeypatch, fake)
    _id_args(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["instance"]["DBInstanceStatus"] == "isolated"
    assert fake.instances[0]["DBInstanceStatus"] == "isolated"
    assert "IsolateDBInstances" in [c for c, unused in fake.calls]


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakePostgresClient(instances=[_instance()])
    _make_module(monkeypatch, fake)
    _id_args(_ansible_check_mode=True, state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert fake.instances[0]["DBInstanceStatus"] == "running"
    assert "IsolateDBInstances" not in [c for c, unused in fake.calls]


def test_absent_already_isolated_is_noop(monkeypatch):
    fake = FakePostgresClient(instances=[_instance(DBInstanceStatus="isolated")])
    _make_module(monkeypatch, fake)
    _id_args(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["instance"]["DBInstanceStatus"] == "isolated"
    assert "IsolateDBInstances" not in [c for c, unused in fake.calls]


def test_absent_purge_requires_isolated(monkeypatch):
    fake = FakePostgresClient(instances=[_instance(DBInstanceStatus="running")])
    _make_module(monkeypatch, fake)
    _id_args(state="absent", purge=True)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "purge requires an already isolated PostgreSQL instance" in exc.value.args[0]["msg"]


def test_absent_purge_destroys_isolated(monkeypatch):
    fake = FakePostgresClient(instances=[_instance(DBInstanceStatus="isolated")])
    _make_module(monkeypatch, fake)
    _id_args(state="absent", purge=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["instance"] is None
    assert fake.instances == []
    assert "DestroyDBInstance" in [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# creation flows
# ---------------------------------------------------------------------------


def test_create_requires_creation_parameters(monkeypatch):
    fake = FakePostgresClient(instances=[])
    _make_module(monkeypatch, fake)
    _name_args(state="present", name="new-db")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "creation parameters are required" in payload["msg"]
    assert "spec_code" in payload["missing"]
    assert "admin_password" in payload["missing"]


def test_create_instance(monkeypatch):
    fake = FakePostgresClient(instances=[])
    _make_module(monkeypatch, fake)
    _name_args(
        state="present",
        zone="ap-guangzhou-3",
        vpc_id="vpc-abc",
        subnet_id="subnet-abc",
        spec_code="pg.it.medium2",
        storage=100,
        major_version="15",
        admin_password="hunter2-secret",
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["instance"]["DBInstanceName"] == "production-postgres"
    assert result["instance"]["DBInstanceStatus"] == "running"
    assert len(fake.instances) == 1
    ops = [c for c, unused in fake.calls]
    assert ops[0] == "DescribeDBInstances"
    assert "CreateInstances" in ops


def test_create_check_mode_is_dry_run(monkeypatch):
    fake = FakePostgresClient(instances=[])
    _make_module(monkeypatch, fake)
    _name_args(
        _ansible_check_mode=True,
        state="present",
        zone="ap-guangzhou-3",
        vpc_id="vpc-abc",
        subnet_id="subnet-abc",
        spec_code="pg.it.medium2",
        storage=100,
        major_version="15",
        admin_password="hunter2-secret",
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["instance"]["DBInstanceName"] == "production-postgres"
    assert fake.instances == []
    assert "CreateInstances" not in [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# existing-instance flows
# ---------------------------------------------------------------------------


def test_existing_instance_no_drift_is_idempotent(monkeypatch):
    fake = FakePostgresClient(instances=[_instance()])
    _make_module(monkeypatch, fake)
    _id_args(state="present")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["instance"]["DBInstanceId"] == INSTANCE_ID


def test_rename_instance(monkeypatch):
    fake = FakePostgresClient(instances=[_instance(DBInstanceName="old-db")])
    _make_module(monkeypatch, fake)
    _id_args(state="present", name="renamed-db")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["instance"]["DBInstanceName"] == "renamed-db"
    assert "ModifyDBInstanceName" in [c for c, unused in fake.calls]


def test_resize_instance(monkeypatch):
    fake = FakePostgresClient(instances=[_instance()])
    _make_module(monkeypatch, fake)
    _id_args(state="present", cpu=4, memory=8, storage=200)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["instance"]["DBInstanceCpu"] == 4
    assert result["instance"]["DBInstanceMemory"] == 8
    assert result["instance"]["DBInstanceStorage"] == 200
    assert "ModifyDBInstanceSpec" in [c for c, unused in fake.calls]


def test_auto_renew_drift(monkeypatch):
    fake = FakePostgresClient(instances=[_instance(AutoRenew=0)])
    _make_module(monkeypatch, fake)
    _id_args(state="present", auto_renew=1)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["instance"]["AutoRenew"] == 1
    assert "SetAutoRenewFlag" in [c for c, unused in fake.calls]


def test_update_check_mode_is_dry_run(monkeypatch):
    fake = FakePostgresClient(instances=[_instance(DBInstanceName="old-db")])
    _make_module(monkeypatch, fake)
    _id_args(_ansible_check_mode=True, state="present", name="new-db")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert fake.instances[0]["DBInstanceName"] == "old-db"
    assert "ModifyDBInstanceName" not in [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# guards / validation / failure paths
# ---------------------------------------------------------------------------


def test_immutable_network_placement_fails(monkeypatch):
    fake = FakePostgresClient(instances=[_instance()])
    _make_module(monkeypatch, fake)
    _id_args(state="present", zone="ap-guangzhou-1")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "network placement and major version are immutable" in payload["msg"]
    assert "Zone" in payload["immutable_drift"]


def test_ambiguous_reference_fails(monkeypatch):
    fake = FakePostgresClient(instances=[_instance(), _instance(DBInstanceId="postgres-dup")])
    _make_module(monkeypatch, fake)
    _name_args(state="present")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "Ambiguous PostgreSQL instance reference" in payload["msg"]
    assert payload["ambiguous"] is True


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeDBInstances(self, request):
            raise Boom("connection dropped")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    _id_args(state="present")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]
