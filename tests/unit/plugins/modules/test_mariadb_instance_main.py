"""Unit tests for the mariadb_instance write module (run_module flows).

Drives ``run_module()`` end to end against an in-memory fake MariaDB client
whose write operations mutate the instance store so the module's post-write
``find`` refetch and ``wait_for_state`` polls converge immediately.

Scenario matrix:

* absent on a missing instance (idempotent no-op)
* absent with a matching instance (isolate, check-mode dry run, already
  isolated no-op, purge guard, real destroy of an isolated instance)
* creation when missing (missing-parameter guard, hourly and prepaid happy
  paths, check mode)
* no-op when nothing drifts
* drift updates (rename, resize on hourly and prepaid instances)
* immutable network / version / node-count guard
* identity validation guard and the blanket ``sdk_error_payload`` path
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import mariadb_instance as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

INSTANCE = {
    "InstanceId": "tdsql-mariadb-1",
    "InstanceName": "prod-mariadb",
    "Status": 2,
    "Paymode": "postpaid_by_hour",
    "Memory": 8,
    "Storage": 100,
    "Zone": "ap-guangzhou-3",
    "DbVersionId": "10.1",
    "UniqueVpcId": "vpc-aaa111",
    "UniqueSubnetId": "subnet-bbb222",
    "NodeCount": 2,
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
    params = {"instance_id": "tdsql-mariadb-1"}
    params.update(overrides)
    return module_args(**params)


def _name_args(**overrides):
    params = {"name": "prod-mariadb"}
    params.update(overrides)
    return module_args(**params)


class FakeMariadbClient(object):
    """In-memory MariaDB client mutating a small instance store."""

    def __init__(self, instances=None):
        self.instances = [dict(t) for t in (instances or [])]
        self.calls = []
        self._next = 0

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def _find(self, request):
        if getattr(request, "InstanceIds", None):
            return [i for i in self.instances if i.get("InstanceId") in request.InstanceIds]
        if getattr(request, "SearchName", None):
            return [i for i in self.instances if i.get("InstanceName") == request.SearchName]
        return []

    def DescribeDBInstances(self, request):
        self._record("DescribeDBInstances", request)
        rows = self._find(request)
        return SimpleNamespace(Instances=[FakeResource(r) for r in rows], RequestId="req-describe")

    def CreateHourDBInstance(self, request):
        self._record("CreateHourDBInstance", request)
        return self._create(request, "tdsql-mariadb-hour-")

    def CreateDBInstance(self, request):
        self._record("CreateDBInstance", request)
        return self._create(request, "tdsql-mariadb-pre-")

    def _create(self, request, prefix):
        self._next += 1
        instance_id = "%s%d" % (prefix, self._next)
        item = {
            "InstanceId": instance_id,
            "InstanceName": getattr(request, "InstanceName", None),
            "Status": 2,
            "Paymode": "postpaid_by_hour" if "hour" in prefix else "prepaid",
            "Memory": getattr(request, "Memory", None),
            "Storage": getattr(request, "Storage", None),
            "Zone": (getattr(request, "Zones", None) or [None])[0],
            "DbVersionId": getattr(request, "DbVersionId", None),
            "UniqueVpcId": getattr(request, "VpcId", None),
            "UniqueSubnetId": getattr(request, "SubnetId", None),
            "NodeCount": getattr(request, "NodeCount", None) or 2,
        }
        self.instances.append(item)
        return SimpleNamespace(InstanceIds=[instance_id], RequestId="req-create")

    def ModifyDBInstanceName(self, request):
        self._record("ModifyDBInstanceName", request)
        for item in self.instances:
            if item.get("InstanceId") == getattr(request, "InstanceId", None):
                item["InstanceName"] = getattr(request, "InstanceName", None)
        return SimpleNamespace(RequestId="req-rename")

    def UpgradeHourDBInstance(self, request):
        self._record("UpgradeHourDBInstance", request)
        self._upgrade(request)
        return SimpleNamespace(RequestId="req-upgrade")

    def UpgradeDBInstance(self, request):
        self._record("UpgradeDBInstance", request)
        self._upgrade(request)
        return SimpleNamespace(RequestId="req-upgrade")

    def _upgrade(self, request):
        for item in self.instances:
            if item.get("InstanceId") == getattr(request, "InstanceId", None):
                if getattr(request, "Memory", None) is not None:
                    item["Memory"] = request.Memory
                if getattr(request, "Storage", None) is not None:
                    item["Storage"] = request.Storage
                item["Status"] = 2

    def IsolateHourDBInstance(self, request):
        self._record("IsolateHourDBInstance", request)
        self._isolate(request.InstanceIds)
        return SimpleNamespace(RequestId="req-isolate")

    def IsolateDBInstance(self, request):
        self._record("IsolateDBInstance", request)
        self._isolate(request.InstanceIds)
        return SimpleNamespace(RequestId="req-isolate")

    def _isolate(self, instance_ids):
        for item in self.instances:
            if item.get("InstanceId") in list(instance_ids or []):
                item["Status"] = -1

    def DestroyHourDBInstance(self, request):
        self._record("DestroyHourDBInstance", request)
        self._destroy(getattr(request, "InstanceId", None))
        return SimpleNamespace(RequestId="req-destroy")

    def DestroyDBInstance(self, request):
        self._record("DestroyDBInstance", request)
        self._destroy(getattr(request, "InstanceId", None))
        return SimpleNamespace(RequestId="req-destroy")

    def _destroy(self, instance_id):
        self.instances = [i for i in self.instances if i.get("InstanceId") != instance_id]


def _make_module(monkeypatch, fake, models=None):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (models or FakeModels(), SimpleNamespace(MariadbClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)


# ---------------------------------------------------------------------------
# absent flows
# ---------------------------------------------------------------------------


def test_absent_missing_instance_is_idempotent(monkeypatch):
    fake = FakeMariadbClient()
    _make_module(monkeypatch, fake)
    _name_args(state="absent", name="ghost-mariadb")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["instance"] is None
    assert [c for c, unused in fake.calls] == ["DescribeDBInstances"]


def test_absent_isolates_instance(monkeypatch):
    fake = FakeMariadbClient(instances=[_instance()])
    _make_module(monkeypatch, fake)
    _id_args(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["instance"]["Status"] == -1
    assert fake.instances[0]["Status"] == -1
    assert "IsolateHourDBInstance" in [c for c, unused in fake.calls]


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeMariadbClient(instances=[_instance()])
    _make_module(monkeypatch, fake)
    _id_args(_ansible_check_mode=True, state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert fake.instances[0]["Status"] == 2
    assert "IsolateHourDBInstance" not in [c for c, unused in fake.calls]


def test_absent_already_isolated_is_idempotent(monkeypatch):
    fake = FakeMariadbClient(instances=[_instance(Status=-1)])
    _make_module(monkeypatch, fake)
    _id_args(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["instance"]["Status"] == -1


def test_absent_purge_requires_isolated_instance(monkeypatch):
    fake = FakeMariadbClient(instances=[_instance()])
    _make_module(monkeypatch, fake)
    _id_args(state="absent", purge=True)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "purge requires an already isolated" in exc.value.args[0]["msg"]


def test_absent_purge_destroys_hourly_instance(monkeypatch):
    fake = FakeMariadbClient(instances=[_instance(Status=-1)])
    _make_module(monkeypatch, fake)
    _id_args(state="absent", purge=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["instance"] is None
    assert fake.instances == []
    assert "DestroyHourDBInstance" in [c for c, unused in fake.calls]


def test_absent_purge_destroys_prepaid_instance(monkeypatch):
    fake = FakeMariadbClient(instances=[_instance(Paymode="prepaid", Status=-1)])
    _make_module(monkeypatch, fake)
    _id_args(state="absent", purge=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert fake.instances == []
    assert "DestroyDBInstance" in [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# creation flows
# ---------------------------------------------------------------------------


def test_create_requires_creation_parameters(monkeypatch):
    fake = FakeMariadbClient()
    _make_module(monkeypatch, fake)
    _name_args(state="present", name="brand-new")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "creation parameters are required" in payload["msg"]
    assert payload["missing"] == ["zones", "memory", "storage", "db_version", "vpc_id", "subnet_id"]


def test_create_hourly_instance(monkeypatch):
    fake = FakeMariadbClient()
    _make_module(monkeypatch, fake)
    _name_args(
        state="present",
        name="brand-new",
        zones=["ap-guangzhou-3", "ap-guangzhou-4"],
        memory=8,
        storage=100,
        db_version="10.1",
        vpc_id="vpc-aaa111",
        subnet_id="subnet-bbb222",
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["instance"]["InstanceName"] == "brand-new"
    assert result["instance"]["InstanceId"].startswith("tdsql-mariadb-hour-")
    assert len(fake.instances) == 1
    ops = [c for c, unused in fake.calls]
    assert ops[0] == "DescribeDBInstances"
    assert "CreateHourDBInstance" in ops


def test_create_prepaid_instance(monkeypatch):
    fake = FakeMariadbClient()
    _make_module(monkeypatch, fake)
    _base(
        state="present",
        name="brand-new",
        zones=["ap-guangzhou-3"],
        memory=8,
        storage=100,
        db_version="10.1",
        vpc_id="vpc-aaa111",
        subnet_id="subnet-bbb222",
        charge_type="PREPAID",
        period_months=3,
        auto_renew=True,
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["instance"]["InstanceId"].startswith("tdsql-mariadb-pre-")
    assert "CreateDBInstance" in [c for c, unused in fake.calls]
    assert "CreateHourDBInstance" not in [c for c, unused in fake.calls]


def test_create_check_mode_is_dry_run(monkeypatch):
    fake = FakeMariadbClient()
    _make_module(monkeypatch, fake)
    _name_args(
        _ansible_check_mode=True,
        state="present",
        name="brand-new",
        zones=["ap-guangzhou-3"],
        memory=8,
        storage=100,
        db_version="10.1",
        vpc_id="vpc-aaa111",
        subnet_id="subnet-bbb222",
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["instance"]["InstanceName"] == "brand-new"
    assert "InstanceId" not in result["instance"]
    assert fake.instances == []
    assert "CreateHourDBInstance" not in [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# existing-instance flows
# ---------------------------------------------------------------------------


def test_existing_instance_no_drift_is_idempotent(monkeypatch):
    fake = FakeMariadbClient(instances=[_instance()])
    _make_module(monkeypatch, fake)
    _id_args(state="present")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["instance"]["InstanceId"] == "tdsql-mariadb-1"


def test_immutable_version_drift_fails(monkeypatch):
    fake = FakeMariadbClient(instances=[_instance()])
    _make_module(monkeypatch, fake)
    _id_args(state="present", db_version="5.7")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "immutable" in payload["msg"]
    assert "DbVersionId" in payload["immutable_drift"]


def test_immutable_node_count_drift_fails(monkeypatch):
    fake = FakeMariadbClient(instances=[_instance(NodeCount=2)])
    _make_module(monkeypatch, fake)
    _id_args(state="present", node_count=3)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "NodeCount" in payload["immutable_drift"]


def test_rename_instance(monkeypatch):
    fake = FakeMariadbClient(instances=[_instance()])
    _make_module(monkeypatch, fake)
    _id_args(state="present", name="renamed-mariadb")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["instance"]["InstanceName"] == "renamed-mariadb"
    assert fake.instances[0]["InstanceName"] == "renamed-mariadb"
    assert "ModifyDBInstanceName" in [c for c, unused in fake.calls]


def test_resize_hourly_instance(monkeypatch):
    fake = FakeMariadbClient(instances=[_instance()])
    _make_module(monkeypatch, fake)
    _id_args(state="present", memory=32, storage=400)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["instance"]["Memory"] == 32
    assert result["instance"]["Storage"] == 400
    assert "UpgradeHourDBInstance" in [c for c, unused in fake.calls]
    assert "UpgradeDBInstance" not in [c for c, unused in fake.calls]


def test_resize_prepaid_instance(monkeypatch):
    fake = FakeMariadbClient(instances=[_instance(Paymode="prepaid")])
    _make_module(monkeypatch, fake)
    _id_args(state="present", storage=500)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["instance"]["Storage"] == 500
    assert "UpgradeDBInstance" in [c for c, unused in fake.calls]


def test_existing_update_check_mode_is_dry_run(monkeypatch):
    fake = FakeMariadbClient(instances=[_instance()])
    _make_module(monkeypatch, fake)
    _id_args(_ansible_check_mode=True, state="present", name="renamed-mariadb", memory=16)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert fake.instances[0]["InstanceName"] == "prod-mariadb"
    assert "ModifyDBInstanceName" not in [c for c, unused in fake.calls]
    assert "UpgradeHourDBInstance" not in [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# validation / failure paths
# ---------------------------------------------------------------------------


def test_requires_instance_id_or_name(monkeypatch):
    fake = FakeMariadbClient()
    _make_module(monkeypatch, fake)
    _base(state="present")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "instance_id" in exc.value.args[0]["msg"]


def test_invalid_db_version_fails(monkeypatch):
    fake = FakeMariadbClient()
    _make_module(monkeypatch, fake)
    _name_args(state="present", name="brand-new", db_version="6.0")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "6.0" in exc.value.args[0]["msg"]


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
