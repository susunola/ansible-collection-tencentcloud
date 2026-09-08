"""Unit tests for the tdmq_rabbitmq_instance write module (run_module flows).

Drives ``run_module()`` end to end against an in-memory fake TDMQ client
whose write operations mutate the RabbitMQ instance store, so the module's
post-write ``find`` refetch and the cluster-state waiter return immediately.

Scenario matrix:

* absent on a missing instance (idempotent no-op)
* absent with a matching instance (deletion-protection guard, authorized
  disable-then-delete, check-mode dry run, real delete)
* creation when missing (with/without the mandatory creation parameters,
  check mode, running-state wait)
* no-op when nothing drifts
* mutable updates (remark / name / tags / deletion protection)
* the immutable network / version / node-topology guards
* the blanket SDK-failure path
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import tdmq_rabbitmq_instance as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

INSTANCE = {
    "InstanceId": "rabbitmq-prod-1",
    "InstanceName": "production-rabbitmq",
    "InstanceVersion": "3.11.8",
    "ClusterStatus": 1,
    "NodeCount": 3,
    "MaxStorage": 200,
    "EnableDeletionProtection": False,
    "Remark": "production broker",
    "Tags": [{"TagKey": "env", "TagValue": "prod"}],
    "Vpcs": [{"VpcId": "vpc-aaaa1111", "SubnetId": "subnet-bbbb2222"}],
}


def _instance(**overrides):
    item = copy.deepcopy(INSTANCE)
    item.update(overrides)
    return item


def _base(**overrides):
    # instance_id and name are alternatives (required_one_of); start from the
    # id and let creation tests pass a name instead.
    params = {"instance_id": "rabbitmq-prod-1"}
    params.update(overrides)
    return module_args(**params)


def _name_base(**overrides):
    params = {"name": "production-rabbitmq"}
    params.update(overrides)
    return module_args(**params)


class FakeTdmqClient(object):
    """In-memory TDMQ client mutating a RabbitMQ instance store."""

    def __init__(self, instances=None):
        self.instances = [copy.deepcopy(t) for t in (instances or [])]
        self.calls = []
        self._next = 0

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def _tags_from_request(self, request):
        tags = []
        for tag in list(getattr(request, "Tags", None) or []):
            tags.append({
                "TagKey": getattr(tag, "TagKey", None),
                "TagValue": getattr(tag, "TagValue", None),
            })
        if getattr(request, "RemoveAllTags", False) and not tags:
            return []
        return tags

    def DescribeRabbitMQVipInstances(self, request):
        self._record("DescribeRabbitMQVipInstances", request)
        return SimpleNamespace(
            Instances=[FakeResource(dict(t)) for t in self.instances],
            TotalCount=len(self.instances),
        )

    def CreateRabbitMQVipInstance(self, request):
        self._record("CreateRabbitMQVipInstance", request)
        self._next += 1
        self.instances.append({
            "InstanceId": "rabbitmq-new-%03d" % self._next,
            "InstanceName": request.ClusterName,
            "InstanceVersion": request.ClusterVersion,
            "ClusterStatus": 1,
            "NodeCount": request.NodeNum,
            "MaxStorage": request.StorageSize,
            "EnableDeletionProtection": request.EnableDeletionProtection,
            "Remark": None,
            "Tags": [],
            "Vpcs": [{"VpcId": request.VpcId, "SubnetId": request.SubnetId}],
        })
        return SimpleNamespace(InstanceId=self.instances[-1]["InstanceId"], RequestId="req-fake")

    def ModifyRabbitMQVipInstance(self, request):
        self._record("ModifyRabbitMQVipInstance", request)
        for item in self.instances:
            if item.get("InstanceId") != request.InstanceId:
                continue
            for attr in ("ClusterName", "Remark"):
                value = getattr(request, attr, None)
                if value is not None:
                    item["InstanceName" if attr == "ClusterName" else "Remark"] = value
            if getattr(request, "EnableDeletionProtection", None) is not None:
                item["EnableDeletionProtection"] = request.EnableDeletionProtection
            if hasattr(request, "Tags"):
                item["Tags"] = self._tags_from_request(request)
        return SimpleNamespace(RequestId="req-fake")

    def DeleteRabbitMQVipInstance(self, request):
        self._record("DeleteRabbitMQVipInstance", request)
        self.instances = [t for t in self.instances if t.get("InstanceId") != request.InstanceId]
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake, models=None):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (models or FakeModels(), SimpleNamespace(TdmqClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


# ---------------------------------------------------------------------------
# absent flows
# ---------------------------------------------------------------------------


def test_absent_missing_instance_is_idempotent(monkeypatch):
    fake = FakeTdmqClient(instances=[])
    _make_module(monkeypatch, fake)
    _base(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["instance"] is None
    assert [c for c, unused in fake.calls] == ["DescribeRabbitMQVipInstances"]


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeTdmqClient(instances=[_instance()])
    _make_module(monkeypatch, fake)
    _base(_ansible_check_mode=True, state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert len(fake.instances) == 1
    assert "DeleteRabbitMQVipInstance" not in [c for c, unused in fake.calls]


def test_absent_deletes_instance(monkeypatch):
    fake = FakeTdmqClient(instances=[_instance()])
    _make_module(monkeypatch, fake)
    _base(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["instance"] is None
    assert fake.instances == []
    ops = [c for c, unused in fake.calls]
    assert "DeleteRabbitMQVipInstance" in ops


def test_absent_with_deletion_protection_requires_authorization(monkeypatch):
    fake = FakeTdmqClient(instances=[_instance(EnableDeletionProtection=True)])
    _make_module(monkeypatch, fake)
    _base(state="absent")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "set deletion_protection=false to authorize" in exc.value.args[0]["msg"]


def test_absent_disables_protection_before_delete(monkeypatch):
    fake = FakeTdmqClient(instances=[_instance(EnableDeletionProtection=True)])
    _make_module(monkeypatch, fake)
    _base(state="absent", deletion_protection=False)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert fake.instances == []
    ops = [c for c, unused in fake.calls]
    assert "ModifyRabbitMQVipInstance" in ops
    assert "DeleteRabbitMQVipInstance" in ops


# ---------------------------------------------------------------------------
# creation flows
# ---------------------------------------------------------------------------


def test_create_requires_creation_parameters(monkeypatch):
    fake = FakeTdmqClient(instances=[])
    _make_module(monkeypatch, fake)
    _name_base(state="present", name="brand-new")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert exc.value.args[0]["msg"] == "creation parameters are required for a new RabbitMQ instance"


def test_create_instance(monkeypatch):
    fake = FakeTdmqClient(instances=[])
    _make_module(monkeypatch, fake)
    _name_base(
        state="present",
        name="production-rabbitmq",
        zone_ids=[100003, 100004, 100005],
        vpc_id="vpc-aaaa1111",
        subnet_id="subnet-bbbb2222",
        node_spec="rabbit-vip-profession-4c16g",
        node_count=3,
        storage_size=500,
        cluster_version="3.13.7",
        deletion_protection=True,
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    instance = result["instance"]
    assert instance["InstanceName"] == "production-rabbitmq"
    assert instance["InstanceVersion"] == "3.13.7"
    assert instance["NodeCount"] == 3
    assert instance["EnableDeletionProtection"] is True
    assert len(fake.instances) == 1
    ops = [c for c, unused in fake.calls]
    assert ops[0] == "DescribeRabbitMQVipInstances"
    assert "CreateRabbitMQVipInstance" in ops


def test_create_check_mode_is_dry_run(monkeypatch):
    fake = FakeTdmqClient(instances=[])
    _make_module(monkeypatch, fake)
    _name_base(
        _ansible_check_mode=True,
        state="present",
        name="production-rabbitmq",
        zone_ids=[100003],
        vpc_id="vpc-aaaa1111",
        subnet_id="subnet-bbbb2222",
        storage_size=500,
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["instance"]["InstanceName"] == "production-rabbitmq"
    assert result["instance"]["NodeCount"] == 1
    assert fake.instances == []
    assert "CreateRabbitMQVipInstance" not in [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# existing-instance flows
# ---------------------------------------------------------------------------


def test_existing_instance_no_drift_is_idempotent(monkeypatch):
    fake = FakeTdmqClient(instances=[_instance()])
    _make_module(monkeypatch, fake)
    _base(state="present", remark="production broker", tags={"env": "prod"})
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["instance"]["InstanceId"] == "rabbitmq-prod-1"


def test_update_remark_drift(monkeypatch):
    fake = FakeTdmqClient(instances=[_instance()])
    _make_module(monkeypatch, fake)
    _base(state="present", remark="renamed broker")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["instance"]["Remark"] == "renamed broker"
    ops = [c for c, unused in fake.calls]
    assert "ModifyRabbitMQVipInstance" in ops


def test_update_tags_reconciles_full_set(monkeypatch):
    fake = FakeTdmqClient(instances=[_instance()])
    _make_module(monkeypatch, fake)
    _base(state="present", remark="production broker", tags={"env": "staging"})
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["instance"]["Tags"] == [{"TagKey": "env", "TagValue": "staging"}]


def test_update_check_mode_is_dry_run(monkeypatch):
    fake = FakeTdmqClient(instances=[_instance()])
    _make_module(monkeypatch, fake)
    _base(_ansible_check_mode=True, state="present", remark="renamed broker")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["instance"]["Remark"] == "production broker"
    assert "ModifyRabbitMQVipInstance" not in [c for c, unused in fake.calls]


def test_vpc_topology_is_immutable(monkeypatch):
    fake = FakeTdmqClient(instances=[_instance()])
    _make_module(monkeypatch, fake)
    _base(state="present", vpc_id="vpc-other999", subnet_id="subnet-other999")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "topology are immutable" in payload["msg"]
    assert "Vpc" in payload["immutable_drift"]


def test_version_is_immutable(monkeypatch):
    fake = FakeTdmqClient(instances=[_instance()])
    _make_module(monkeypatch, fake)
    _base(state="present", cluster_version="3.8.30")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "InstanceVersion" in payload["immutable_drift"]


def test_node_count_is_immutable(monkeypatch):
    fake = FakeTdmqClient(instances=[_instance()])
    _make_module(monkeypatch, fake)
    _base(state="present", node_count=5)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "NodeCount" in payload["immutable_drift"]


# ---------------------------------------------------------------------------
# guards / failure paths
# ---------------------------------------------------------------------------


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeRabbitMQVipInstances(self, request):
            raise Boom("connection dropped")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    _name_base(state="present", name="production-rabbitmq")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]
