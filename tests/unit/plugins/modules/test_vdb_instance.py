"""Unit tests for the vdb_instance write module (helpers + run_module).

Manages Tencent Cloud VectorDB instances through their full lifecycle:
create (with required-parameter validation and a running-state wait),
expand (decomposed ScaleUpInstance / ScaleOutInstance /
ModifyDBInstanceSecurityGroups reconciles keyed on per-field drift with a
cannot-reduce guard), and terminate (isolate then purge, purge requiring an
already isolated instance). Lookup matches by instance_id or exact name and
fails on multiple matches. Identity, network and engine fields are immutable
on existing instances; isolated instances require recover=true to restore.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import vdb_instance as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

_ORIG_LOAD = mod._load  # captured before any monkeypatching


def _load_real_or_fake():
    """Exercise the real lazy SDK import body when the SDK is installed.

    The coverage gate runs with the SDK present (see ci.yml "SDK contract
    tests"), so the real import executes and the ``_load`` body is covered;
    in SDK-less environments (``ansible-test units``) the import falls back
    to fake models so the same test file stays portable.
    """
    try:
        return _ORIG_LOAD()
    except ImportError:
        return FakeModels(), SimpleNamespace(VdbClient=object)


class FakeModule(object):
    """Minimal stand-in for helpers that need sdk_call / fail_json."""

    def __init__(self, params=None):
        self.params = params or {}

    def sdk_call(self, operation, request):
        return operation(request)

    def fail_json(self, **kwargs):
        raise AnsibleFailJson(kwargs)


def _instance(instance_id="vdb-1", name="prod-vdb", **overrides):
    """A serialized VectorDB instance record (Status running by default)."""
    record = {
        "InstanceId": instance_id,
        "Name": name,
        "Status": "running",
        "Zone": "ap-guangzhou-3",
        "ProductType": 1,
        "InstanceType": "NORMAL",
        "EngineName": "VectorDB",
        "EngineVersion": "1.0",
        "NodeType": "nvme",
        "Networks": [{"VpcId": "vpc-1", "SubnetId": "subnet-1"}],
        "Cpu": 4,
        "Memory": 16,
        "Disk": 500,
        "ReplicaNum": 3,
        "SecurityGroupIds": ["sg-1"],
    }
    record.update(overrides)
    return record


class FakeVdbClient(object):
    """In-memory VdbClient stand-in storing VectorDB instance records.

    DescribeInstances returns every record (the module filters by id/name);
    mutating operations address records by InstanceId and apply the request
    fields so a post-wait re-find shows the converged state. CreateInstance
    assigns a fresh id and starts the record in Status running so the
    module's wait converges on its first poll.
    """

    def __init__(self, instances=None):
        self.instances = [dict(x) for x in (instances or [])]
        self.calls = []
        self._next_id = 1

    def _record(self, name, request):
        self.calls.append((name, request))

    def _by_id(self, instance_id):
        for record in self.instances:
            if record["InstanceId"] == instance_id:
                return record
        return None

    def DescribeInstances(self, request):
        self._record("DescribeInstances", request)
        return SimpleNamespace(Items=[FakeResource(dict(x)) for x in self.instances])

    def CreateInstance(self, request):
        self._record("CreateInstance", request)
        instance_id = "vdb-%d" % self._next_id
        self._next_id += 1
        self.instances.append(
            {
                "InstanceId": instance_id,
                "Name": request.InstanceName,
                "Status": "running",
                "Zone": request.Zone,
                "ProductType": request.ProductType,
                "InstanceType": request.InstanceType,
                "EngineName": request.EngineName,
                "EngineVersion": request.EngineVersion,
                "NodeType": request.NodeType,
                "Networks": [{"VpcId": request.VpcId, "SubnetId": request.SubnetId}],
                "Cpu": request.Cpu,
                "Memory": request.Memory,
                "Disk": request.DiskSize,
                "ReplicaNum": 1,
                "SecurityGroupIds": list(request.SecurityGroupIds or []),
            }
        )
        return SimpleNamespace(InstanceIds=[instance_id])

    def ScaleUpInstance(self, request):
        self._record("ScaleUpInstance", request)
        record = self._by_id(request.InstanceId)
        record["Cpu"] = request.Cpu
        record["Memory"] = request.Memory
        record["Disk"] = request.StorageSize
        return SimpleNamespace()

    def ScaleOutInstance(self, request):
        self._record("ScaleOutInstance", request)
        self._by_id(request.InstanceId)["ReplicaNum"] = request.ReplicaNum
        return SimpleNamespace()

    def ModifyDBInstanceSecurityGroups(self, request):
        self._record("ModifyDBInstanceSecurityGroups", request)
        self._by_id(request.InstanceIds[0])["SecurityGroupIds"] = list(request.SecurityGroupIds)
        return SimpleNamespace()

    def IsolateInstance(self, request):
        self._record("IsolateInstance", request)
        self._by_id(request.InstanceId)["Status"] = "isolated"
        return SimpleNamespace()

    def RecoverInstance(self, request):
        self._record("RecoverInstance", request)
        self._by_id(request.InstanceId)["Status"] = "running"
        return SimpleNamespace()

    def DestroyInstances(self, request):
        self._record("DestroyInstances", request)
        self.instances = [x for x in self.instances if x["InstanceId"] not in request.InstanceIds]
        return SimpleNamespace()


# Creation parameters covering every required field for a new instance.
_CREATE_ARGS = {
    "name": "prod-vdb",
    "zone": "ap-guangzhou-3",
    "vpc_id": "vpc-1",
    "subnet_id": "subnet-1",
    "product_type": 1,
    "instance_type": "NORMAL",
    "mode": "CLUSTER",
    "network_type": "VPC",
    "engine_name": "VectorDB",
    "engine_version": "1.0",
    "node_type": "nvme",
    "cpu": 4,
    "memory": 16,
    "disk_size": 500,
    "replica_count": 3,
    "worker_node_count": 2,
    "security_group_ids": ["sg-1"],
    "tags": {"team": "pay", "env": "prod"},
    "project": "p-1",
    "brief": "production vectors",
    "chief": "wang",
    "dba": "dba@example.com",
    "pay_period": 3,
    "auto_renew": 1,
    "pay_mode": 0,
}


def _make_module(monkeypatch, fake):
    """Wire the shared monkeypatches and return the fake client."""
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", _load_real_or_fake)
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


class _BoomClient(object):
    """Every SDK call raises, so the module's wrapped error path is hit."""

    def __getattr__(self, name):
        def boom(*args, **kwargs):
            raise RuntimeError("service exploded")

        return boom


def _call_names(fake):
    return [name for name, request in fake.calls]


# ---------------------------------------------------------------------------
# request-builder and mapping helper tests
# ---------------------------------------------------------------------------


def test_describe_request_by_instance_id():
    request = mod.describe_request(FakeModels(), {"instance_id": "vdb-1", "name": "prod-vdb"})
    assert type(request).__name__ == "DescribeInstancesRequest"
    assert request.Offset == 0
    assert request.Limit == 100
    assert request.InstanceIds == ["vdb-1"]
    assert request.InstanceNames is None  # never sent alongside InstanceIds


def test_describe_request_by_name_and_offset():
    request = mod.describe_request(FakeModels(), {"name": "prod-vdb"}, offset=42)
    assert request.InstanceIds is None
    assert request.InstanceNames == ["prod-vdb"]
    assert request.Offset == 42


def test_describe_request_without_identifier():
    request = mod.describe_request(FakeModels(), {})
    assert request.InstanceIds is None
    assert request.InstanceNames is None


def test_tags_sorted_keys_with_verbatim_values():
    items = mod._tags(FakeModels(), {"b": 2, "a": "x", "c": None})
    assert [i.TagKey for i in items] == ["a", "b", "c"]
    assert [i.TagValue for i in items] == ["x", 2, None]


def test_tags_empty_or_none_returns_empty_list():
    assert mod._tags(FakeModels(), {}) == []
    assert mod._tags(FakeModels(), None) == []


def test_create_request_full_payload():
    params = dict(_CREATE_ARGS)
    request = mod.create_request(FakeModels(), params)
    assert type(request).__name__ == "CreateInstanceRequest"
    assert request.InstanceName == "prod-vdb"
    assert request.VpcId == "vpc-1"
    assert request.SubnetId == "subnet-1"
    assert request.PayMode == 0
    assert request.PayPeriod == 3
    assert request.AutoRenew == 1
    assert request.SecurityGroupIds == ["sg-1"]
    assert request.Project == "p-1"
    assert request.ProductType == 1
    assert request.InstanceType == "NORMAL"
    assert request.Mode == "CLUSTER"
    assert request.NetworkType == "VPC"
    assert request.Zone == "ap-guangzhou-3"
    assert request.EngineName == "VectorDB"
    assert request.EngineVersion == "1.0"
    assert request.NodeType == "nvme"
    assert request.Brief == "production vectors"
    assert request.Chief == "wang"
    assert request.DBA == "dba@example.com"
    assert request.Cpu == 4
    assert request.Memory == 16
    assert request.DiskSize == 500
    assert request.WorkerNodeNum == 2
    assert request.GoodsNum == 1
    assert [t.TagKey for t in request.ResourceTags] == ["env", "team"]  # sorted by key
    assert [t.TagValue for t in request.ResourceTags] == ["prod", "pay"]


def test_create_request_optionals_stay_none_when_unset():
    params = {k: _CREATE_ARGS[k] for k in ("name", "zone", "vpc_id", "subnet_id", "product_type", "instance_type", "mode", "network_type", "engine_name", "engine_version", "cpu", "memory", "disk_size", "pay_period", "auto_renew", "pay_mode")}
    request = mod.create_request(FakeModels(), params)
    assert request.SecurityGroupIds is None
    assert request.SlaveZones is None
    assert request.ResourceTags == []  # no tags requested
    assert request.Project is None
    assert request.Brief is None
    assert request.Chief is None
    assert request.DBA is None
    assert request.NodeType is None
    assert request.WorkerNodeNum is None
    assert request.GoodsNum == 1


def test_scale_out_request_fields():
    request = mod.scale_out_request(FakeModels(), "vdb-1", 5)
    assert type(request).__name__ == "ScaleOutInstanceRequest"
    assert request.InstanceId == "vdb-1"
    assert request.ReplicaNum == 5
    assert request.RunNow is True  # parameter default
    deferred = mod.scale_out_request(FakeModels(), "vdb-1", 5, run_now=False)
    assert deferred.RunNow is False


def test_scale_up_request_fields():
    params = {"cpu": 8, "memory": 32, "disk_size": 1000, "run_now": False}
    request = mod.scale_up_request(FakeModels(), params, "vdb-1")
    assert type(request).__name__ == "ScaleUpInstanceRequest"
    assert request.InstanceId == "vdb-1"
    assert request.Cpu == 8
    assert request.Memory == 32
    assert request.StorageSize == 1000
    assert request.RunNow is False


def test_security_groups_request_fields():
    request = mod.security_groups_request(FakeModels(), "vdb-1", ["sg-1", "sg-2"])
    assert type(request).__name__ == "ModifyDBInstanceSecurityGroupsRequest"
    assert request.InstanceIds == ["vdb-1"]
    assert request.SecurityGroupIds == ["sg-1", "sg-2"]


def test_isolate_request_fields():
    request = mod.isolate_request(FakeModels(), "vdb-1")
    assert type(request).__name__ == "IsolateInstanceRequest"
    assert request.InstanceId == "vdb-1"


def test_recover_request_fields():
    request = mod.recover_request(FakeModels(), "vdb-1", 3)
    assert type(request).__name__ == "RecoverInstanceRequest"
    assert request.InstanceId == "vdb-1"
    assert request.PayPeriod == 3


def test_destroy_request_fields():
    request = mod.destroy_request(FakeModels(), "vdb-1")
    assert type(request).__name__ == "DestroyInstancesRequest"
    assert request.InstanceIds == ["vdb-1"]


# ---------------------------------------------------------------------------
# find helper tests
# ---------------------------------------------------------------------------


def test_find_matches_by_instance_id():
    fake = FakeVdbClient([_instance(), _instance("vdb-2", "other")])
    found = mod.find(FakeModule(), fake, FakeModels(), {"instance_id": "vdb-1"})
    assert found["InstanceId"] == "vdb-1"
    assert found["Name"] == "prod-vdb"


def test_find_matches_by_name():
    fake = FakeVdbClient([_instance(), _instance("vdb-2", "other")])
    found = mod.find(FakeModule(), fake, FakeModels(), {"name": "other"})
    assert found["InstanceId"] == "vdb-2"


def test_find_no_match_returns_none():
    fake = FakeVdbClient([_instance()])
    assert mod.find(FakeModule(), fake, FakeModels(), {"instance_id": "vdb-9"}) is None
    assert mod.find(FakeModule(), fake, FakeModels(), {"name": "missing"}) is None


def test_find_empty_response_returns_none():
    fake = FakeVdbClient()
    assert mod.find(FakeModule(), fake, FakeModels(), {"name": "prod-vdb"}) is None


def test_find_multiple_name_matches_fail():
    fake = FakeVdbClient([_instance("vdb-1", "dup"), _instance("vdb-2", "dup")])
    with pytest.raises(AnsibleFailJson) as exc:
        mod.find(FakeModule(), fake, FakeModels(), {"name": "dup"})
    payload = exc.value.args[0]
    assert payload["msg"] == "Multiple VectorDB instances matched; specify instance_id"


def test_find_multiple_id_matches_fail():
    fake = FakeVdbClient([_instance("vdb-1", "a"), _instance("vdb-1", "b")])
    with pytest.raises(AnsibleFailJson) as exc:
        mod.find(FakeModule(), fake, FakeModels(), {"instance_id": "vdb-1"})
    assert exc.value.args[0]["msg"] == "Multiple VectorDB instances matched; specify instance_id"


# ---------------------------------------------------------------------------
# argument validation
# ---------------------------------------------------------------------------


def test_requires_instance_id_or_name(monkeypatch):
    _make_module(monkeypatch, FakeVdbClient())
    module_args(zone="ap-guangzhou-3")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    msg = exc.value.args[0]["msg"]
    assert "one of the following is required" in msg
    assert "instance_id" in msg and "name" in msg


def test_cpu_requires_memory_and_disk_together(monkeypatch):
    _make_module(monkeypatch, FakeVdbClient())
    module_args(name="prod-vdb", cpu=4)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    msg = exc.value.args[0]["msg"]
    assert "required together" in msg
    assert "cpu" in msg


# ---------------------------------------------------------------------------
# absent main-path tests
# ---------------------------------------------------------------------------


def test_absent_not_found_is_noop(monkeypatch):
    fake = FakeVdbClient()
    _make_module(monkeypatch, fake)
    module_args(state="absent", instance_id="vdb-9")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["instance"] is None
    assert _call_names(fake) == ["DescribeInstances"]


def test_absent_running_instance_isolates(monkeypatch):
    fake = FakeVdbClient([_instance()])
    _make_module(monkeypatch, fake)
    module_args(state="absent", instance_id="vdb-1")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["instance"]["Status"] == "running"  # pre-isolate snapshot
    assert _call_names(fake) == ["DescribeInstances", "IsolateInstance"]
    isolate = [req for name, req in fake.calls if name == "IsolateInstance"][0]
    assert isolate.InstanceId == "vdb-1"
    assert fake.instances[0]["Status"] == "isolated"  # remote now isolated


def test_absent_purge_requires_isolated(monkeypatch):
    fake = FakeVdbClient([_instance()])
    _make_module(monkeypatch, fake)
    module_args(state="absent", instance_id="vdb-1", purge=True)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "purge requires an already isolated VectorDB instance"
    assert payload["current_status"] == "running"
    assert not any(name == "DestroyInstances" for name, request in fake.calls)


def test_absent_already_isolated_is_noop(monkeypatch):
    fake = FakeVdbClient([_instance(Status="isolated")])
    _make_module(monkeypatch, fake)
    module_args(state="absent", instance_id="vdb-1")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["instance"]["Status"] == "isolated"
    assert _call_names(fake) == ["DescribeInstances"]


def test_absent_isolating_instance_is_noop(monkeypatch):
    fake = FakeVdbClient([_instance(Status="isolating")])
    _make_module(monkeypatch, fake)
    module_args(state="absent", instance_id="vdb-1")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["instance"]["Status"] == "isolating"
    assert not any(name == "IsolateInstance" for name, request in fake.calls)


def test_absent_isolated_with_purge_destroys(monkeypatch):
    fake = FakeVdbClient([_instance(Status="isolated")])
    _make_module(monkeypatch, fake)
    module_args(state="absent", instance_id="vdb-1", purge=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["instance"] is None
    assert _call_names(fake) == ["DescribeInstances", "DestroyInstances"]
    destroy = [req for name, req in fake.calls if name == "DestroyInstances"][0]
    assert destroy.InstanceIds == ["vdb-1"]
    assert fake.instances == []  # record destroyed


def test_absent_check_mode_isolate_is_dry_run(monkeypatch):
    fake = FakeVdbClient([_instance()])
    _make_module(monkeypatch, fake)
    module_args(_ansible_check_mode=True, state="absent", instance_id="vdb-1")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["instance"]["Status"] == "running"  # current kept for preview
    assert result["diff"]["before"]["Status"] == "running"
    assert result["diff"]["after"] is None
    assert not any(name == "IsolateInstance" for name, request in fake.calls)
    assert fake.instances[0]["Status"] == "running"  # remote untouched


def test_absent_check_mode_purge_is_dry_run(monkeypatch):
    fake = FakeVdbClient([_instance(Status="isolated")])
    _make_module(monkeypatch, fake)
    module_args(_ansible_check_mode=True, state="absent", instance_id="vdb-1", purge=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["instance"] is None
    assert result["diff"]["before"]["InstanceId"] == "vdb-1"
    assert result["diff"]["after"] is None
    assert not any(name == "DestroyInstances" for name, request in fake.calls)
    assert len(fake.instances) == 1  # remote untouched


# ---------------------------------------------------------------------------
# present main-path tests: creation
# ---------------------------------------------------------------------------


def test_present_missing_creation_params_fails(monkeypatch):
    fake = FakeVdbClient()
    _make_module(monkeypatch, fake)
    module_args(name="prod-vdb")  # satisfies required_one_of but nothing else
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "creation parameters are required for a new VectorDB instance"
    assert payload["missing"] == [
        "zone",
        "vpc_id",
        "subnet_id",
        "product_type",
        "instance_type",
        "mode",
        "network_type",
        "engine_name",
        "engine_version",
        "cpu",
        "memory",
        "disk_size",
    ]
    assert not any(name == "CreateInstance" for name, request in fake.calls)


def test_present_creates_instance_and_refinds(monkeypatch):
    fake = FakeVdbClient()
    _make_module(monkeypatch, fake)
    module_args(**_CREATE_ARGS)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["instance"]["InstanceId"] == "vdb-1"
    assert result["instance"]["Name"] == "prod-vdb"
    assert result["instance"]["Status"] == "running"
    # initial find, create, wait poll, re-find
    assert _call_names(fake) == ["DescribeInstances", "CreateInstance", "DescribeInstances", "DescribeInstances"]
    create = [req for name, req in fake.calls if name == "CreateInstance"][0]
    assert create.InstanceName == "prod-vdb"
    assert create.VpcId == "vpc-1"
    assert create.SubnetId == "subnet-1"
    assert create.PayMode == 0
    assert create.PayPeriod == 3
    assert create.AutoRenew == 1
    assert create.SecurityGroupIds == ["sg-1"]
    assert create.Project == "p-1"
    assert create.ProductType == 1
    assert create.InstanceType == "NORMAL"
    assert create.Mode == "CLUSTER"
    assert create.NetworkType == "VPC"
    assert create.Zone == "ap-guangzhou-3"
    assert create.EngineName == "VectorDB"
    assert create.EngineVersion == "1.0"
    assert create.NodeType == "nvme"
    assert create.Cpu == 4
    assert create.Memory == 16
    assert create.DiskSize == 500
    assert create.WorkerNodeNum == 2
    assert create.GoodsNum == 1
    assert [t.TagKey for t in create.ResourceTags] == ["env", "team"]  # sorted by key
    assert [t.TagValue for t in create.ResourceTags] == ["prod", "pay"]


def test_present_check_mode_create_is_dry_run(monkeypatch):
    fake = FakeVdbClient()
    _make_module(monkeypatch, fake)
    module_args(_ansible_check_mode=True, **_CREATE_ARGS)
    result = run(mod.run_module)
    target = {
        "Name": "prod-vdb",
        "Zone": "ap-guangzhou-3",
        "ProductType": 1,
        "InstanceType": "NORMAL",
        "EngineName": "VectorDB",
        "EngineVersion": "1.0",
        "Cpu": 4,
        "Memory": 16,
        "Disk": 500,
    }
    assert result["changed"] is True
    assert result["instance"] == target
    assert result["diff"]["before"] is None
    assert result["diff"]["after"] == target
    assert _call_names(fake) == ["DescribeInstances"]  # no write
    assert fake.instances == []


# ---------------------------------------------------------------------------
# present main-path tests: isolated instance recovery
# ---------------------------------------------------------------------------


def test_present_isolated_requires_recover(monkeypatch):
    fake = FakeVdbClient([_instance(Status="isolated")])
    _make_module(monkeypatch, fake)
    module_args(instance_id="vdb-1")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "set recover=true to recover an isolated VectorDB instance"
    assert not any(name == "RecoverInstance" for name, request in fake.calls)


def test_present_isolated_recovers_and_refinds(monkeypatch):
    fake = FakeVdbClient([_instance(Status="isolated")])
    _make_module(monkeypatch, fake)
    module_args(instance_id="vdb-1", recover=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["instance"]["Status"] == "running"  # re-found after recover
    assert _call_names(fake) == ["DescribeInstances", "RecoverInstance", "DescribeInstances", "DescribeInstances"]
    recover = [req for name, req in fake.calls if name == "RecoverInstance"][0]
    assert recover.InstanceId == "vdb-1"
    assert recover.PayPeriod == 1  # default pay_period


def test_present_isolated_check_mode_recover_is_dry_run(monkeypatch):
    fake = FakeVdbClient([_instance(Status="isolated")])
    _make_module(monkeypatch, fake)
    module_args(_ansible_check_mode=True, instance_id="vdb-1", recover=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["instance"]["Status"] == "isolated"  # pre-recover snapshot
    assert result["diff"]["before"] == {"Status": "isolated"}
    assert result["diff"]["after"] == {"Status": "running"}
    assert not any(name == "RecoverInstance" for name, request in fake.calls)


# ---------------------------------------------------------------------------
# present main-path tests: immutability drift on a running instance
# ---------------------------------------------------------------------------


def test_present_identity_drift_fails_immutable(monkeypatch):
    fake = FakeVdbClient([_instance()])
    _make_module(monkeypatch, fake)
    module_args(instance_id="vdb-1", name="renamed", zone="ap-guangzhou-9")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "VectorDB identity, network and engine fields are immutable"
    assert payload["immutable_drift"] == {
        "Name": ("prod-vdb", "renamed"),
        "Zone": ("ap-guangzhou-3", "ap-guangzhou-9"),
    }
    assert not any(name != "DescribeInstances" for name, request in fake.calls)


def test_present_network_drift_fails_immutable(monkeypatch):
    fake = FakeVdbClient([_instance()])
    _make_module(monkeypatch, fake)
    module_args(instance_id="vdb-1", vpc_id="vpc-9", subnet_id="subnet-9")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "VectorDB identity, network and engine fields are immutable"
    assert payload["immutable_drift"] == {
        "Network": ([("vpc-1", "subnet-1")], ("vpc-9", "subnet-9"))
    }
    assert not any(name != "DescribeInstances" for name, request in fake.calls)


def test_present_identity_drift_fails_even_in_check_mode(monkeypatch):
    fake = FakeVdbClient([_instance()])
    _make_module(monkeypatch, fake)
    module_args(_ansible_check_mode=True, instance_id="vdb-1", name="renamed")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert exc.value.args[0]["msg"] == "VectorDB identity, network and engine fields are immutable"


# ---------------------------------------------------------------------------
# present main-path tests: scale reconciliation on a running instance
# ---------------------------------------------------------------------------


def test_present_unchanged_is_noop(monkeypatch):
    fake = FakeVdbClient([_instance()])
    _make_module(monkeypatch, fake)
    module_args(
        instance_id="vdb-1",
        cpu=4,
        memory=16,
        disk_size=500,
        replica_count=3,
        security_group_ids=["sg-1"],
        vpc_id="vpc-1",  # matches the current network, so no drift
        subnet_id="subnet-1",
    )
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["instance"]["Cpu"] == 4
    assert _call_names(fake) == ["DescribeInstances"]
    assert fake.instances[0]["Status"] == "running"


def test_present_scale_up_real(monkeypatch):
    fake = FakeVdbClient([_instance()])
    _make_module(monkeypatch, fake)
    module_args(instance_id="vdb-1", cpu=8, memory=16, disk_size=500, run_now=False)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["instance"]["Cpu"] == 8
    assert result["instance"]["Disk"] == 500
    assert _call_names(fake) == ["DescribeInstances", "ScaleUpInstance", "DescribeInstances", "DescribeInstances"]
    up = [req for name, req in fake.calls if name == "ScaleUpInstance"][0]
    assert up.InstanceId == "vdb-1"
    assert up.Cpu == 8
    assert up.Memory == 16
    assert up.StorageSize == 500
    assert up.RunNow is False  # run_now=False propagated
    assert not any(name == "ScaleOutInstance" for name, request in fake.calls)


def test_present_scale_out_real(monkeypatch):
    fake = FakeVdbClient([_instance()])
    _make_module(monkeypatch, fake)
    module_args(instance_id="vdb-1", replica_count=5)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["instance"]["ReplicaNum"] == 5
    out = [req for name, req in fake.calls if name == "ScaleOutInstance"][0]
    assert out.InstanceId == "vdb-1"
    assert out.ReplicaNum == 5
    assert out.RunNow is True  # default run_now
    assert not any(name == "ScaleUpInstance" for name, request in fake.calls)


def test_present_security_group_drift_modifies(monkeypatch):
    fake = FakeVdbClient([_instance(SecurityGroupIds=[])])
    _make_module(monkeypatch, fake)
    module_args(instance_id="vdb-1", security_group_ids=["sg-2", "sg-1"])
    result = run(mod.run_module)
    assert result["changed"] is True
    assert sorted(result["instance"]["SecurityGroupIds"]) == ["sg-1", "sg-2"]
    modify = [req for name, req in fake.calls if name == "ModifyDBInstanceSecurityGroups"][0]
    assert modify.InstanceIds == ["vdb-1"]
    assert modify.SecurityGroupIds == ["sg-1", "sg-2"]  # sorted before sending
    assert not any(name in ("ScaleUpInstance", "ScaleOutInstance") for name, request in fake.calls)


def test_present_combined_scale_applies_all_mutations(monkeypatch):
    fake = FakeVdbClient([_instance()])
    _make_module(monkeypatch, fake)
    module_args(instance_id="vdb-1", cpu=8, memory=16, disk_size=500, replica_count=5, security_group_ids=["sg-2", "sg-1"])
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["instance"]["Cpu"] == 8
    assert result["instance"]["ReplicaNum"] == 5
    assert sorted(result["instance"]["SecurityGroupIds"]) == ["sg-1", "sg-2"]
    assert _call_names(fake) == [
        "DescribeInstances",
        "ScaleUpInstance",
        "ScaleOutInstance",
        "ModifyDBInstanceSecurityGroups",
        "DescribeInstances",
        "DescribeInstances",
    ]
    up = [req for name, req in fake.calls if name == "ScaleUpInstance"][0]
    assert up.Cpu == 8 and up.RunNow is True
    out = [req for name, req in fake.calls if name == "ScaleOutInstance"][0]
    assert out.ReplicaNum == 5 and out.RunNow is True
    modify = [req for name, req in fake.calls if name == "ModifyDBInstanceSecurityGroups"][0]
    assert modify.SecurityGroupIds == ["sg-1", "sg-2"]


def test_present_scale_check_mode_is_dry_run(monkeypatch):
    fake = FakeVdbClient([_instance()])
    _make_module(monkeypatch, fake)
    module_args(_ansible_check_mode=True, instance_id="vdb-1", cpu=8, memory=16, disk_size=500)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["instance"]["Cpu"] == 4  # pre-scale snapshot
    assert result["instance"]["Status"] == "running"
    assert result["diff"]["before"]["Cpu"] == 4
    assert result["diff"]["after"]["Cpu"] == 8
    assert _call_names(fake) == ["DescribeInstances"]
    assert fake.instances[0]["Cpu"] == 4  # remote untouched


def test_present_cannot_reduce_cpu(monkeypatch):
    fake = FakeVdbClient([_instance()])
    _make_module(monkeypatch, fake)
    module_args(instance_id="vdb-1", cpu=2, memory=16, disk_size=500)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "VectorDB compute, storage and replicas cannot be reduced"
    assert payload["field"] == "Cpu"
    assert not any(name != "DescribeInstances" for name, request in fake.calls)


def test_present_cannot_reduce_replicas(monkeypatch):
    fake = FakeVdbClient([_instance()])
    _make_module(monkeypatch, fake)
    module_args(instance_id="vdb-1", replica_count=1)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "VectorDB compute, storage and replicas cannot be reduced"
    assert payload["field"] == "ReplicaNum"


# ---------------------------------------------------------------------------
# error path and entry point
# ---------------------------------------------------------------------------


def test_sdk_error_is_reported(monkeypatch):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (FakeModels(), SimpleNamespace(VdbClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: _BoomClient())
    module_args(name="prod-vdb")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert payload["error"] == "service exploded"


def test_main_entrypoint_runs_module(monkeypatch):
    fake = FakeVdbClient([_instance()])
    _make_module(monkeypatch, fake)
    module_args(instance_id="vdb-1")
    result = run(mod.main)
    assert result["changed"] is False
    assert result["instance"]["InstanceId"] == "vdb-1"
