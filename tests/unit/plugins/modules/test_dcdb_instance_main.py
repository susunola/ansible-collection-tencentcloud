"""Unit tests for the dcdb_instance write module (run_module flows).

Drives ``run_module()`` end to end against an in-memory fake DCDB client
whose write operations mutate the instance store so the post-write ``find``
and ``wait_for_state`` converge immediately.

Scenario matrix:

* absent on a missing instance (idempotent no-op)
* absent on a matching instance (isolate; prepaid and postpaid paths)
* absent on an already isolated instance (no-op, or purge with destroy)
* the ``purge`` guard (refuses running instances)
* creation when missing (postpaid and prepaid, missing-parameter guard,
  check-mode dry run, waiting)
* no-op when nothing drifts
* drift updates (rename, shard expansion, shard add)
* immutable network/version drift and scale-down guards
* the blanket ``sdk_error_payload`` failure path
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import dcdb_instance as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

INSTANCE = {
    "InstanceId": "dcdb-1a2b3c4d",
    "InstanceName": "prod-dcdb",
    "Status": 2,
    "Paymode": 0,
    "Region": "ap-guangzhou",
    "VpcId": "vpc-1111",
    "SubnetId": "subnet-2222",
    "DbVersionId": "8.0",
    "Memory": 16,
    "Storage": 100,
    "ShardCount": 2,
    "NodeCount": 2,
    "ShardDetail": [
        {"ShardInstanceId": "shard-1", "Memory": 16, "Storage": 100, "NodeCount": 2},
        {"ShardInstanceId": "shard-2", "Memory": 16, "Storage": 100, "NodeCount": 2},
    ],
}


def _instance(**overrides):
    item = copy.deepcopy(INSTANCE)
    item.update(overrides)
    return item


def _base(**overrides):
    params = {"name": "prod-dcdb"}
    params.update(overrides)
    return module_args(**params)


class FakeDcdbClient(object):
    """In-memory DCDB client mutating a small instance store."""

    def __init__(self, instances=None):
        self.instances = [copy.deepcopy(t) for t in (instances or [])]
        self.calls = []
        self._next = 0

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def _find(self, instance_id):
        for item in self.instances:
            if item.get("InstanceId") == instance_id:
                return item
        return None

    def DescribeDCDBInstances(self, request):
        self._record("DescribeDCDBInstances", request)
        matched = list(self.instances)
        ids = getattr(request, "InstanceIds", None)
        if ids:
            matched = [t for t in matched if t.get("InstanceId") in ids]
        else:
            search = getattr(request, "SearchName", None)
            if search:
                matched = [t for t in matched if t.get("InstanceName") == search]
        return SimpleNamespace(Instances=[FakeResource(t) for t in matched], TotalCount=len(matched))

    def _store_created(self, request, new_id):
        item = {
            "InstanceId": new_id,
            "InstanceName": getattr(request, "InstanceName", None),
            "Status": 2,
            "Paymode": 0,
            "VpcId": getattr(request, "VpcId", None),
            "SubnetId": getattr(request, "SubnetId", None),
            "DbVersionId": getattr(request, "DbVersionId", None),
            "Memory": getattr(request, "ShardMemory", None),
            "Storage": getattr(request, "ShardStorage", None),
            "ShardCount": getattr(request, "ShardCount", None) or 1,
            "NodeCount": getattr(request, "ShardNodeCount", None) or 2,
        }
        memory, storage = item["Memory"], item["Storage"]
        node_count = item["NodeCount"]
        item["ShardDetail"] = [
            {"ShardInstanceId": "shard-%s-%d" % (new_id, i), "Memory": memory, "Storage": storage, "NodeCount": node_count}
            for i in range(1, item["ShardCount"] + 1)
        ]
        return item

    def CreateHourDCDBInstance(self, request):
        self._record("CreateHourDCDBInstance", request)
        self._next += 1
        new_id = "dcdb-hour-%03d" % self._next
        self.instances.append(self._store_created(request, new_id))
        return SimpleNamespace(InstanceIds=[new_id], RequestId="req-fake")

    def CreateDCDBInstance(self, request):
        self._record("CreateDCDBInstance", request)
        self._next += 1
        new_id = "dcdb-pre-%03d" % self._next
        item = self._store_created(request, new_id)
        item["Paymode"] = 1
        self.instances.append(item)
        return SimpleNamespace(InstanceIds=[new_id], RequestId="req-fake")

    def ModifyDBInstanceName(self, request):
        self._record("ModifyDBInstanceName", request)
        item = self._find(getattr(request, "InstanceId", None))
        if item is not None:
            item["InstanceName"] = getattr(request, "InstanceName", item.get("InstanceName"))
        return SimpleNamespace(RequestId="req-fake")

    def UpgradeHourDCDBInstance(self, request):
        self._record("UpgradeHourDCDBInstance", request)
        item = self._find(getattr(request, "InstanceId", None))
        if item is None:
            return SimpleNamespace(RequestId="req-fake")
        if getattr(request, "UpgradeType", None) == "ADD":
            cfg = getattr(request, "AddShardConfig", None)
            item["ShardCount"] = item.get("ShardCount", 0) + getattr(cfg, "ShardCount", 0)
        else:
            cfg = getattr(request, "ExpandShardConfig", None)
            if getattr(cfg, "ShardMemory", None) is not None:
                item["Memory"] = cfg.ShardMemory
            if getattr(cfg, "ShardStorage", None) is not None:
                item["Storage"] = cfg.ShardStorage
            if getattr(cfg, "ShardNodeCount", None) is not None:
                item["NodeCount"] = cfg.ShardNodeCount
        return SimpleNamespace(RequestId="req-fake")

    def UpgradeDCDBInstance(self, request):
        self._record("UpgradeDCDBInstance", request)
        item = self._find(getattr(request, "InstanceId", None))
        if item is not None:
            cfg = getattr(request, "ExpandShardConfig", None)
            if getattr(cfg, "ShardMemory", None) is not None:
                item["Memory"] = cfg.ShardMemory
            if getattr(cfg, "ShardStorage", None) is not None:
                item["Storage"] = cfg.ShardStorage
        return SimpleNamespace(RequestId="req-fake")

    def IsolateHourDCDBInstance(self, request):
        self._record("IsolateHourDCDBInstance", request)
        for instance_id in getattr(request, "InstanceIds", None) or []:
            item = self._find(instance_id)
            if item is not None:
                item["Status"] = 5
        return SimpleNamespace(RequestId="req-fake")

    def IsolateDCDBInstance(self, request):
        self._record("IsolateDCDBInstance", request)
        for instance_id in getattr(request, "InstanceIds", None) or []:
            item = self._find(instance_id)
            if item is not None:
                item["Status"] = 5
        return SimpleNamespace(RequestId="req-fake")

    def DestroyHourDCDBInstance(self, request):
        self._record("DestroyHourDCDBInstance", request)
        instance_id = getattr(request, "InstanceId", None)
        self.instances = [t for t in self.instances if t.get("InstanceId") != instance_id]
        return SimpleNamespace(RequestId="req-fake")

    def DestroyDCDBInstance(self, request):
        self._record("DestroyDCDBInstance", request)
        instance_id = getattr(request, "InstanceId", None)
        self.instances = [t for t in self.instances if t.get("InstanceId") != instance_id]
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake, models=None):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (models or FakeModels(), SimpleNamespace(DcdbClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


# ---------------------------------------------------------------------------
# absent flows
# ---------------------------------------------------------------------------


def test_absent_missing_instance_is_idempotent(monkeypatch):
    fake = FakeDcdbClient(instances=[])
    _make_module(monkeypatch, fake)
    _base(state="absent", name="ghost-dcdb")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["instance"] is None


def test_absent_isolates_postpaid_instance(monkeypatch):
    fake = FakeDcdbClient(instances=[_instance()])
    _make_module(monkeypatch, fake)
    _base(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert fake.instances[0]["Status"] == 5
    ops = [c for c, unused in fake.calls]
    assert "IsolateHourDCDBInstance" in ops


def test_absent_isolates_prepaid_instance(monkeypatch):
    fake = FakeDcdbClient(instances=[_instance(Paymode=1)])
    _make_module(monkeypatch, fake)
    _base(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    ops = [c for c, unused in fake.calls]
    assert "IsolateDCDBInstance" in ops


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeDcdbClient(instances=[_instance()])
    _make_module(monkeypatch, fake)
    _base(_ansible_check_mode=True, state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert fake.instances[0]["Status"] == 2
    assert "IsolateHourDCDBInstance" not in [c for c, unused in fake.calls]


def test_absent_already_isolated_is_noop(monkeypatch):
    fake = FakeDcdbClient(instances=[_instance(Status=5)])
    _make_module(monkeypatch, fake)
    _base(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["instance"]["Status"] == 5
    ops = [c for c, unused in fake.calls]
    assert "IsolateHourDCDBInstance" not in ops


def test_purge_requires_isolated_instance(monkeypatch):
    fake = FakeDcdbClient(instances=[_instance(Status=2)])
    _make_module(monkeypatch, fake)
    _base(state="absent", purge=True)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "purge requires an already isolated DCDB instance" in exc.value.args[0]["msg"]


def test_absent_purges_isolated_instance(monkeypatch):
    fake = FakeDcdbClient(instances=[_instance(Status=5)])
    _make_module(monkeypatch, fake)
    _base(state="absent", purge=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert fake.instances == []
    ops = [c for c, unused in fake.calls]
    assert "DestroyHourDCDBInstance" in ops


# ---------------------------------------------------------------------------
# creation flows
# ---------------------------------------------------------------------------

CREATE_PARAMS = {
    "state": "present",
    "name": "brand-new",
    "zones": ["ap-guangzhou-3"],
    "vpc_id": "vpc-1111",
    "subnet_id": "subnet-2222",
    "db_version": "8.0",
    "shard_memory": 8,
    "shard_storage": 100,
}


def test_create_requires_creation_parameters(monkeypatch):
    fake = FakeDcdbClient(instances=[])
    _make_module(monkeypatch, fake)
    _base(state="present", name="brand-new")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "creation parameters are required for a new DCDB instance" in payload["msg"]
    assert payload["missing"] == ["zones", "vpc_id", "subnet_id", "db_version", "shard_memory", "shard_storage"]


def test_create_postpaid_instance(monkeypatch):
    fake = FakeDcdbClient(instances=[])
    _make_module(monkeypatch, fake)
    _base(**CREATE_PARAMS)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["instance"]["InstanceName"] == "brand-new"
    assert result["instance"]["Memory"] == 8
    assert result["instance"]["ShardCount"] == 2
    assert len(fake.instances) == 1
    ops = [c for c, unused in fake.calls]
    assert "CreateHourDCDBInstance" in ops
    assert "DescribeDCDBInstances" in ops


def test_create_prepaid_instance(monkeypatch):
    fake = FakeDcdbClient(instances=[])
    _make_module(monkeypatch, fake)
    _base(**dict(CREATE_PARAMS, charge_type="PREPAID", period_months=3, auto_renew=True))
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["instance"]["InstanceName"] == "brand-new"
    ops = [c for c, unused in fake.calls]
    assert "CreateDCDBInstance" in ops
    assert "CreateHourDCDBInstance" not in ops


def test_create_check_mode_is_dry_run(monkeypatch):
    fake = FakeDcdbClient(instances=[])
    _make_module(monkeypatch, fake)
    _base(_ansible_check_mode=True, **CREATE_PARAMS)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["instance"]["InstanceName"] == "brand-new"
    assert fake.instances == []
    assert "CreateHourDCDBInstance" not in [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# existing-instance flows
# ---------------------------------------------------------------------------


def test_existing_instance_no_drift_is_idempotent(monkeypatch):
    fake = FakeDcdbClient(instances=[_instance()])
    _make_module(monkeypatch, fake)
    _base(state="present", name="prod-dcdb")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["instance"]["InstanceId"] == "dcdb-1a2b3c4d"


def test_rename_existing_instance(monkeypatch):
    fake = FakeDcdbClient(instances=[_instance()])
    _make_module(monkeypatch, fake)
    _base(state="present", instance_id="dcdb-1a2b3c4d", name="renamed-dcdb")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["instance"]["InstanceName"] == "renamed-dcdb"
    ops = [c for c, unused in fake.calls]
    assert "ModifyDBInstanceName" in ops


def test_expand_memory(monkeypatch):
    fake = FakeDcdbClient(instances=[_instance()])
    _make_module(monkeypatch, fake)
    _base(state="present", instance_id="dcdb-1a2b3c4d", name="prod-dcdb", shard_memory=32, shard_storage=200)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["instance"]["Memory"] == 32
    assert result["instance"]["Storage"] == 200
    ops = [c for c, unused in fake.calls]
    assert "UpgradeHourDCDBInstance" in ops


def test_add_shard(monkeypatch):
    fake = FakeDcdbClient(instances=[_instance()])
    _make_module(monkeypatch, fake)
    _base(state="present", instance_id="dcdb-1a2b3c4d", name="prod-dcdb", shard_count=4)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["instance"]["ShardCount"] == 4
    ops = [c for c, unused in fake.calls]
    assert "UpgradeHourDCDBInstance" in ops


def test_immutable_drift_fails(monkeypatch):
    fake = FakeDcdbClient(instances=[_instance()])
    _make_module(monkeypatch, fake)
    _base(state="present", instance_id="dcdb-1a2b3c4d", name="prod-dcdb", vpc_id="vpc-other")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "DCDB network placement and database version are immutable"
    assert "VpcId" in payload["immutable_drift"]


def test_shrink_fails(monkeypatch):
    fake = FakeDcdbClient(instances=[_instance(Memory=16, Storage=100)])
    _make_module(monkeypatch, fake)
    _base(state="present", instance_id="dcdb-1a2b3c4d", name="prod-dcdb", shard_memory=8)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "cannot be reduced" in exc.value.args[0]["msg"]


# ---------------------------------------------------------------------------
# failure paths
# ---------------------------------------------------------------------------


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeDCDBInstances(self, request):
            raise Boom("connection dropped")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    _base(state="present", name="prod-dcdb")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]
