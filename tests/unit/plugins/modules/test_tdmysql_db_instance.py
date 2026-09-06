"""Unit tests for the tdmysql_db_instance write module (helpers + run_module).

Covers the create / absent / recover / purge / update / check-mode flows of
``plugins/modules/tdmysql_db_instance.py`` with an in-memory fake TDMysql
client, following the collection's module test harness (see harness.py).
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import time
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import tdmysql_db_instance as tdmysql
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

INSTANCE = {
    "InstanceId": "tdsql-8b0a1c2d",
    "InstanceName": "prod-tdmysql",
    "Status": "running",
    "Zone": "ap-guangzhou-3",
    "VpcId": "vpc-0a1b2c3d",
    "SubnetId": "subnet-4e5f6a7b",
    "Disk": 200,
    "StorageNodeNum": 3,
    "Replications": 3,
    "StorageNodeCpu": 4,
    "StorageNodeMem": 16,
    "StorageType": "CLOUD_HSSD",
    "InstanceType": "separate",
    "InstanceMode": "basic",
    "SQLMode": "MySQL",
    "CreateVersion": "MySQL-8.0",
    "PayMode": "0",
    "RenewFlag": 1,
    "SecurityGroupIds": ["sg-0aa1", "sg-0bb2"],
}

WRITE_OPS = (
    "CreateDBInstances",
    "IsolateDBInstance",
    "DestroyInstances",
    "CancelIsolateDBInstances",
    "ExpandInstance",
    "UpgradeInstance",
    "ModifyInstanceName",
    "ModifyAutoRenewFlag",
    "ModifyDBInstanceSecurityGroups",
)

_TRANSITIONAL = ("creating", "initializing", "modifying")


class FakeTdmysqlClient(object):
    """In-memory TDMysql client that mutates a small instance store."""

    def __init__(self, instances=None, page_size=None, auto_advance=False):
        self.instances = [dict(instance) for instance in (instances or [])]
        self.page_size = page_size
        self.auto_advance = auto_advance
        self.describe_count = 0
        self.calls = []
        self._next_id = 1000

    def _record(self, name, request):
        self.calls.append((name, request))
        return request

    def _by_id(self, instance_id):
        return next(instance for instance in self.instances if instance["InstanceId"] == instance_id)

    def _visible(self):
        """Advance transitional statuses to running once reads pass the first.

        The module's ``find`` merges a ``DescribeDBInstanceDetail`` response
        over the list entry, so the transition must mutate the store itself
        (not just the copy returned by ``DescribeDBInstances``) for the
        detail call to observe the new state.
        """
        if self.auto_advance and self.describe_count >= 2:
            for instance in self.instances:
                if str(instance.get("Status", "")).lower() in _TRANSITIONAL:
                    instance["Status"] = "running"
        return [dict(instance) for instance in self.instances]

    def DescribeDBInstances(self, request):
        self._record("DescribeDBInstances", request)
        self.describe_count += 1
        store = self._visible()
        if self.page_size:
            items = store[request.Offset:request.Offset + self.page_size]
        else:
            items = store
        return SimpleNamespace(
            Instances=[FakeResource(item) for item in items],
            TotalCount=len(store),
        )

    def DescribeDBInstanceDetail(self, request):
        self._record("DescribeDBInstanceDetail", request)
        instance = dict(self._by_id(request.InstanceId))
        instance.setdefault("RequestId", "req-detail-1")
        return FakeResource(instance)

    def DescribeDBSecurityGroups(self, request):
        self._record("DescribeDBSecurityGroups", request)
        groups = self._by_id(request.InstanceId).get("SecurityGroupIds") or []
        return SimpleNamespace(Groups=[FakeResource({"SecurityGroupId": group}) for group in groups])

    def CreateDBInstances(self, request):
        self._record("CreateDBInstances", request)
        instance_id = "tdsql-new%04d" % self._next_id
        self._next_id += 1
        instance = {
            "InstanceId": instance_id,
            "InstanceName": request.InstanceName,
            "Status": "running",
            "Zone": request.Zone,
            "VpcId": request.VpcId,
            "SubnetId": request.SubnetId,
            "Disk": request.Disk,
            "StorageNodeNum": request.StorageNodeNum,
            "Replications": request.Replications,
            "StorageNodeCpu": request.StorageNodeCpu,
            "StorageNodeMem": request.StorageNodeMem,
            "StorageType": getattr(request, "StorageType", None),
            "InstanceType": getattr(request, "InstanceType", None),
            "InstanceMode": getattr(request, "InstanceMode", None),
            "SQLMode": getattr(request, "SQLMode", None),
            "CreateVersion": getattr(request, "CreateVersion", None),
            "PayMode": request.PayMode,
            "RenewFlag": 1,
            "SecurityGroupIds": list(getattr(request, "SecurityGroupIds", None) or []),
        }
        self.instances.append(instance)
        return SimpleNamespace(InstanceIds=[instance_id])

    def IsolateDBInstance(self, request):
        self._record("IsolateDBInstance", request)
        for instance_id in request.InstanceIds:
            self._by_id(instance_id)["Status"] = "isolated"
        return SimpleNamespace()

    def CancelIsolateDBInstances(self, request):
        self._record("CancelIsolateDBInstances", request)
        for instance_id in request.InstanceIds:
            self._by_id(instance_id)["Status"] = "running"
        return SimpleNamespace()

    def DestroyInstances(self, request):
        self._record("DestroyInstances", request)
        doomed = set(request.InstanceIds)
        self.instances = [instance for instance in self.instances if instance["InstanceId"] not in doomed]
        return SimpleNamespace()

    def ExpandInstance(self, request):
        self._record("ExpandInstance", request)
        instance = self._by_id(request.InstanceId)
        instance["StorageNodeNum"] = request.StorageNodeNum
        instance["Status"] = "running"
        return SimpleNamespace()

    def UpgradeInstance(self, request):
        self._record("UpgradeInstance", request)
        instance = self._by_id(request.InstanceId)
        for key in ("SpecCode", "Disk", "StorageNodeCpu", "StorageNodeMem", "StorageType"):
            value = getattr(request, key, None)
            if value is not None:
                instance[key] = value
        instance["Status"] = "running"
        return SimpleNamespace()

    def ModifyInstanceName(self, request):
        self._record("ModifyInstanceName", request)
        self._by_id(request.InstanceId)["InstanceName"] = request.InstanceName
        return SimpleNamespace()

    def ModifyAutoRenewFlag(self, request):
        self._record("ModifyAutoRenewFlag", request)
        for instance_id in request.InstanceIds:
            self._by_id(instance_id)["RenewFlag"] = request.AutoRenewFlag
        return SimpleNamespace()

    def ModifyDBInstanceSecurityGroups(self, request):
        self._record("ModifyDBInstanceSecurityGroups", request)
        self._by_id(request.InstanceId)["SecurityGroupIds"] = list(request.SecurityGroupIds)
        return SimpleNamespace()


class FakeModule(object):
    """Minimal stand-in for helper functions that only need params/sdk_call."""

    def __init__(self, **params):
        self.params = dict(params)
        self.check_mode = False
        self.sdk_calls = []

    def sdk_call(self, operation, request):
        self.sdk_calls.append((operation, request))
        return operation(request)

    def fail_json(self, **kwargs):
        raise AnsibleFailJson(kwargs)


@pytest.fixture
def client(monkeypatch):
    fake = FakeTdmysqlClient()
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(
        tdmysql, "_load",
        lambda: (FakeModels(), SimpleNamespace(TdmysqlClient=object)),
    )
    monkeypatch.setattr(
        TencentCloudModule, "create_client",
        lambda self, client_class, endpoint: fake,
    )
    monkeypatch.setattr(time, "sleep", lambda _seconds: None)
    return fake


# ---------------------------------------------------------------------------
# Helper-level tests
# ---------------------------------------------------------------------------


def test_describe_request_sets_paging():
    request = tdmysql.describe_request(FakeModels(), {}, offset=40)
    assert request.Offset == 40
    assert request.Limit == 100


def test_detail_request_sets_instance_id():
    request = tdmysql.detail_request(FakeModels(), "tdsql-abc")
    assert request.InstanceId == "tdsql-abc"


def test_security_groups_describe_request_sets_instance_id():
    request = tdmysql.security_groups_describe_request(FakeModels(), "tdsql-abc")
    assert request.InstanceId == "tdsql-abc"


def test_tags_sorts_and_maps_values():
    tags = tdmysql._tags(FakeModels(), {"z": "1", "a": "2"})
    assert [(tag.TagKey, tag.TagValue) for tag in tags] == [("a", "2"), ("z", "1")]


def test_tags_empty_when_none():
    assert tdmysql._tags(FakeModels(), None) == []


def test_params_sorts_and_stringifies_values():
    params = tdmysql._params(FakeModels(), {"b": 2, "a": 1})
    assert [(item.Param, item.Value) for item in params] == [("a", "1"), ("b", "2")]


def test_params_empty_when_none():
    assert tdmysql._params(FakeModels(), None) == []


def test_create_request_sets_required_and_optionals():
    request = tdmysql.create_request(FakeModels(), {
        "zone": "ap-guangzhou-3", "vpc_id": "vpc-1", "subnet_id": "subnet-1",
        "spec_code": "tdsql.mysql.x4.medium", "disk": 200,
        "storage_node_count": 3, "replications": 3, "instance_count": 1,
        "full_replications": 3, "create_version": "MySQL-8.0", "name": "new-db",
        "tags": {"env": "prod"}, "init_params": {"charset": "utf8mb4"},
        "period_months": 1, "pay_mode": "1", "storage_node_cpu": 4,
        "storage_node_memory": 16, "port": 3306, "zones": ["ap-guangzhou-3"],
        "instance_type": "separate", "storage_type": "CLOUD_HSSD",
        "az_mode": 1, "instance_mode": "basic", "template_id": "tpl-1",
        "sql_mode": "MySQL", "security_group_ids": ["sg-1"],
        "username": "root", "password": "pw", "encryption": True,
        "auto_scale_min": 0.5, "auto_scale_max": 2.0,
    })
    assert request.Zone == "ap-guangzhou-3"
    assert request.SpecCode == "tdsql.mysql.x4.medium"
    assert request.InstanceCount == 1
    assert request.InstanceName == "new-db"
    assert request.PayMode == "1"
    assert request.EncryptionEnable == 1
    assert request.AutoScaleConfig.RangeMin == 0.5
    assert request.AutoScaleConfig.RangeMax == 2.0
    assert [(tag.TagKey, tag.TagValue) for tag in request.ResourceTags] == [("env", "prod")]
    assert request.SecurityGroupIds == ["sg-1"]
    assert request.UserName == "root"
    assert request.Vport == 3306


def test_create_request_encryption_zero_when_disabled():
    params = {
        "zone": "ap-guangzhou-3", "vpc_id": "vpc-1", "subnet_id": "subnet-1",
        "spec_code": "x", "disk": 100, "storage_node_count": 3, "replications": 3,
        "instance_count": 1, "name": "db", "period_months": 1, "pay_mode": "0",
        "storage_node_cpu": 2, "storage_node_memory": 8, "encryption": False,
    }
    request = tdmysql.create_request(FakeModels(), params)
    assert request.EncryptionEnable == 0
    assert not hasattr(request, "AutoScaleConfig")


def test_expand_request_fields():
    request = tdmysql.expand_request(FakeModels(), {
        "zones": ["ap-guangzhou-3"], "az_mode": 2, "primary_zone": "ap-guangzhou-3",
        "full_replications": 3,
    }, "tdsql-abc", 5)
    assert request.InstanceId == "tdsql-abc"
    assert request.StorageNodeNum == 5
    assert request.AZMode == 2
    assert request.FullReplications == 3


def test_upgrade_request_falls_back_to_current():
    current = {
        "SpecCode": "tdsql.mysql.x4.medium", "Disk": 200,
        "StorageNodeCpu": 4, "StorageNodeMem": 16, "StorageType": "CLOUD_HSSD",
    }
    request = tdmysql.upgrade_request(FakeModels(), {"disk": 400}, "tdsql-abc", current)
    assert request.InstanceId == "tdsql-abc"
    assert request.Disk == 400
    assert request.SpecCode == "tdsql.mysql.x4.medium"
    assert request.StorageNodeCpu == 4
    assert request.StorageType == "CLOUD_HSSD"


def test_lifecycle_request_builders():
    models = FakeModels()
    rename = tdmysql.rename_request(models, "tdsql-abc", "renamed")
    assert rename.InstanceName == "renamed"
    assert tdmysql.isolate_request(models, "tdsql-abc").InstanceIds == ["tdsql-abc"]
    assert tdmysql.recover_request(models, "tdsql-abc").InstanceIds == ["tdsql-abc"]
    assert tdmysql.destroy_request(models, "tdsql-abc").InstanceIds == ["tdsql-abc"]
    assert tdmysql.renew_request(models, "tdsql-abc", False).AutoRenewFlag == 0
    assert tdmysql.renew_request(models, "tdsql-abc", True).AutoRenewFlag == 1
    groups = tdmysql.security_groups_request(models, "tdsql-abc", ["sg-1"])
    assert groups.SecurityGroupIds == ["sg-1"]


def test_find_by_id_enriches_detail_and_security_groups():
    module = FakeModule()
    client = FakeTdmysqlClient(instances=[INSTANCE])
    found = tdmysql.find(module, client, FakeModels(), {"instance_id": "tdsql-8b0a1c2d"})
    assert found["InstanceName"] == "prod-tdmysql"
    assert "RequestId" not in found
    assert found["SecurityGroupIds"] == ["sg-0aa1", "sg-0bb2"]
    names = [name for name, request in client.calls]
    assert "DescribeDBInstanceDetail" in names
    assert "DescribeDBSecurityGroups" not in names


def test_find_by_id_with_security_groups_option_enriches():
    module = FakeModule()
    client = FakeTdmysqlClient(instances=[INSTANCE])
    found = tdmysql.find(module, client, FakeModels(), {
        "instance_id": "tdsql-8b0a1c2d", "security_group_ids": ["sg-0aa1"],
    })
    assert found["SecurityGroupIds"] == ["sg-0aa1", "sg-0bb2"]
    names = [name for name, request in client.calls]
    assert "DescribeDBSecurityGroups" in names


def test_find_by_name_matches():
    module = FakeModule()
    client = FakeTdmysqlClient(instances=[INSTANCE])
    found = tdmysql.find(module, client, FakeModels(), {"name": "prod-tdmysql"})
    assert found["InstanceId"] == "tdsql-8b0a1c2d"


def test_find_no_match_returns_none():
    module = FakeModule()
    client = FakeTdmysqlClient(instances=[INSTANCE])
    assert tdmysql.find(module, client, FakeModels(), {"name": "nope"}) is None


def test_find_pages_beyond_first_page():
    module = FakeModule()
    extra = dict(INSTANCE, InstanceId="tdsql-0002", InstanceName="other-db")
    client = FakeTdmysqlClient(instances=[dict(INSTANCE, InstanceId="tdsql-0001", InstanceName="first"), extra], page_size=1)
    found = tdmysql.find(module, client, FakeModels(), {"name": "other-db"})
    assert found["InstanceId"] == "tdsql-0002"
    assert client.describe_count >= 2


def test_find_multiple_matches_fails():
    module = FakeModule()
    client = FakeTdmysqlClient(instances=[INSTANCE, dict(INSTANCE, InstanceId="tdsql-0002")])
    with pytest.raises(AnsibleFailJson) as exc:
        tdmysql.find(module, client, FakeModels(), {"name": "prod-tdmysql"})
    assert "Multiple TDMysql instances" in exc.value.args[0]["msg"]


def test_wait_helper_returns_when_state_reached():
    module = FakeModule(waiter_timeout=30, waiter_delay=0)
    client = FakeTdmysqlClient(instances=[INSTANCE])
    # Running instance -> first poll matches; must not raise or sleep.
    tdmysql._wait(module, client, FakeModels(), {"instance_id": "tdsql-8b0a1c2d"}, ["running"])


def test_wait_helper_times_out(monkeypatch):
    monkeypatch.setattr(time, "sleep", lambda _seconds: None)
    module = FakeModule(waiter_timeout=1, waiter_delay=1)
    client = FakeTdmysqlClient(instances=[dict(INSTANCE, Status="isolated")])
    with pytest.raises(AnsibleFailJson) as exc:
        tdmysql._wait(module, client, FakeModels(), {"instance_id": "tdsql-8b0a1c2d"}, ["running"])
    assert "Timed out" in exc.value.args[0]["msg"]


# ---------------------------------------------------------------------------
# run_module main-path tests
# ---------------------------------------------------------------------------


def test_absent_missing_instance_is_unchanged(client):
    module_args(state="absent", name="nope")
    result = run(tdmysql.run_module)
    assert result["changed"] is False
    assert result["instance"] is None


def test_absent_isolates_running_instance(client):
    client.instances = [dict(INSTANCE)]
    module_args(state="absent", instance_id="tdsql-8b0a1c2d", waiter_timeout=30, waiter_delay=0)
    result = run(tdmysql.run_module)
    assert result["changed"] is True
    assert any(name == "IsolateDBInstance" for name, request in client.calls)
    assert client.instances[0]["Status"] == "isolated"


def test_absent_already_isolated_is_unchanged(client):
    client.instances = [dict(INSTANCE, Status="isolated")]
    module_args(state="absent", instance_id="tdsql-8b0a1c2d")
    result = run(tdmysql.run_module)
    assert result["changed"] is False
    assert not any(name == "DestroyInstances" for name, request in client.calls)


def test_absent_isolating_is_unchanged(client):
    client.instances = [dict(INSTANCE, Status="isolating")]
    module_args(state="absent", instance_id="tdsql-8b0a1c2d")
    result = run(tdmysql.run_module)
    assert result["changed"] is False


def test_purge_requires_isolated_instance(client):
    client.instances = [dict(INSTANCE)]
    module_args(state="absent", instance_id="tdsql-8b0a1c2d", purge=True)
    with pytest.raises(AnsibleFailJson) as exc:
        run(tdmysql.run_module)
    assert "purge requires an already isolated" in exc.value.args[0]["msg"]


def test_purge_destroys_isolated_instance(client):
    client.instances = [dict(INSTANCE, Status="isolated")]
    module_args(state="absent", instance_id="tdsql-8b0a1c2d", purge=True, waiter_timeout=30, waiter_delay=0)
    result = run(tdmysql.run_module)
    assert result["changed"] is True
    assert any(name == "DestroyInstances" for name, request in client.calls)
    assert client.instances == []


def test_check_mode_absent_makes_no_writes(client):
    client.instances = [dict(INSTANCE)]
    module_args(state="absent", instance_id="tdsql-8b0a1c2d", _ansible_check_mode=True)
    result = run(tdmysql.run_module)
    assert result["changed"] is True
    assert not any(name in WRITE_OPS for name, request in client.calls)


def test_create_requires_creation_parameters(client):
    module_args(state="present", name="new-db")
    with pytest.raises(AnsibleFailJson) as exc:
        run(tdmysql.run_module)
    payload = exc.value.args[0]
    assert "required" in payload["msg"]
    assert "zone" in payload["missing"]
    assert "password" in payload["missing"]


def test_create_reports_changed(client):
    module_args(
        state="present", name="new-db", zone="ap-guangzhou-3", vpc_id="vpc-x",
        subnet_id="subnet-y", spec_code="tdsql.mysql.x4.medium", disk=200,
        storage_node_count=3, replications=3, storage_node_cpu=4,
        storage_node_memory=16, password="secret-pass",
        waiter_timeout=30, waiter_delay=0,
    )
    result = run(tdmysql.run_module)
    assert result["changed"] is True
    assert result["instance"]["InstanceId"] == "tdsql-new1000"
    assert any(name == "CreateDBInstances" for name, request in client.calls)
    assert len(client.instances) == 1


def test_check_mode_create_makes_no_writes(client):
    module_args(
        state="present", name="new-db", zone="ap-guangzhou-3", vpc_id="vpc-x",
        subnet_id="subnet-y", spec_code="tdsql.mysql.x4.medium", disk=200,
        storage_node_count=3, replications=3, storage_node_cpu=4,
        storage_node_memory=16, password="secret-pass", _ansible_check_mode=True,
    )
    result = run(tdmysql.run_module)
    assert result["changed"] is True
    assert result["instance"]["InstanceName"] == "new-db"
    assert not any(name in WRITE_OPS for name, request in client.calls)


def test_present_idempotent_is_unchanged(client):
    client.instances = [dict(INSTANCE)]
    module_args(state="present", instance_id="tdsql-8b0a1c2d")
    result = run(tdmysql.run_module)
    assert result["changed"] is False
    assert not any(name in WRITE_OPS for name, request in client.calls)


def test_present_waits_for_transitional_status(client):
    client.instances = [dict(INSTANCE, Status="creating")]
    client.auto_advance = True
    module_args(state="present", instance_id="tdsql-8b0a1c2d", waiter_timeout=30, waiter_delay=1)
    result = run(tdmysql.run_module)
    assert result["changed"] is False
    assert client.describe_count >= 2


def test_present_isolated_requires_recover(client):
    client.instances = [dict(INSTANCE, Status="isolated")]
    module_args(state="present", instance_id="tdsql-8b0a1c2d")
    with pytest.raises(AnsibleFailJson) as exc:
        run(tdmysql.run_module)
    assert "recover=true" in exc.value.args[0]["msg"]


def test_present_recover_isolated_instance(client):
    client.instances = [dict(INSTANCE, Status="isolated")]
    module_args(state="present", instance_id="tdsql-8b0a1c2d", recover=True, waiter_timeout=30, waiter_delay=0)
    result = run(tdmysql.run_module)
    assert result["changed"] is True
    assert any(name == "CancelIsolateDBInstances" for name, request in client.calls)
    assert client.instances[0]["Status"] == "running"


def test_immutable_drift_fails(client):
    client.instances = [dict(INSTANCE)]
    module_args(state="present", instance_id="tdsql-8b0a1c2d", zone="ap-guangzhou-1")
    with pytest.raises(AnsibleFailJson) as exc:
        run(tdmysql.run_module)
    payload = exc.value.args[0]
    assert "immutable" in payload["msg"]
    assert "Zone" in payload["immutable_drift"]


def test_storage_shrink_fails(client):
    client.instances = [dict(INSTANCE)]
    module_args(state="present", instance_id="tdsql-8b0a1c2d", disk=100)
    with pytest.raises(AnsibleFailJson) as exc:
        run(tdmysql.run_module)
    assert "cannot be reduced" in exc.value.args[0]["msg"]


def test_update_renames_instance(client):
    client.instances = [dict(INSTANCE)]
    module_args(state="present", instance_id="tdsql-8b0a1c2d", name="renamed-db", waiter_timeout=30, waiter_delay=0)
    result = run(tdmysql.run_module)
    assert result["changed"] is True
    assert any(name == "ModifyInstanceName" for name, request in client.calls)
    assert client.instances[0]["InstanceName"] == "renamed-db"


def test_update_expands_storage_node_count(client):
    client.instances = [dict(INSTANCE)]
    module_args(state="present", instance_id="tdsql-8b0a1c2d", storage_node_count=5, waiter_timeout=30, waiter_delay=0)
    result = run(tdmysql.run_module)
    assert result["changed"] is True
    assert any(name == "ExpandInstance" for name, request in client.calls)
    assert client.instances[0]["StorageNodeNum"] == 5


def test_update_upgrades_disk(client):
    client.instances = [dict(INSTANCE)]
    module_args(state="present", instance_id="tdsql-8b0a1c2d", disk=400, waiter_timeout=30, waiter_delay=0)
    result = run(tdmysql.run_module)
    assert result["changed"] is True
    assert any(name == "UpgradeInstance" for name, request in client.calls)
    assert client.instances[0]["Disk"] == 400


def test_update_toggles_auto_renew(client):
    client.instances = [dict(INSTANCE)]
    module_args(state="present", instance_id="tdsql-8b0a1c2d", auto_renew=False)
    result = run(tdmysql.run_module)
    assert result["changed"] is True
    renew_calls = [(name, request) for name, request in client.calls if name == "ModifyAutoRenewFlag"]
    assert len(renew_calls) == 1
    assert renew_calls[0][1].AutoRenewFlag == 0


def test_update_reconciles_security_groups(client):
    client.instances = [dict(INSTANCE)]
    module_args(state="present", instance_id="tdsql-8b0a1c2d", security_group_ids=["sg-0aa1", "sg-0cc3"])
    result = run(tdmysql.run_module)
    assert result["changed"] is True
    assert any(name == "ModifyDBInstanceSecurityGroups" for name, request in client.calls)
    assert sorted(client.instances[0]["SecurityGroupIds"]) == ["sg-0aa1", "sg-0cc3"]


def test_check_mode_update_makes_no_writes(client):
    client.instances = [dict(INSTANCE)]
    module_args(state="present", instance_id="tdsql-8b0a1c2d", name="renamed-db", disk=400, _ansible_check_mode=True)
    result = run(tdmysql.run_module)
    assert result["changed"] is True
    assert not any(name in WRITE_OPS for name, request in client.calls)
