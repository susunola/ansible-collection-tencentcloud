"""Unit tests for the thpc_cluster write module (helpers + run_module).

Creates and deletes Tencent Cloud THPC clusters and reconciles deletion
protection. Cluster topology (node/image/network/scheduler counts, VPC,
auto-scaling) is immutable once created and any drift fails. absent deletes
the cluster, refusing to delete while deletion protection is ON unless the
caller explicitly sets deletion_protection=false (which then disables
protection before deletion). Lookup pages DescribeClusters matching by
cluster_id (single page) or exact name (across pages), failing on multiple
name matches.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import thpc_cluster as mod
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
        return FakeModels(), SimpleNamespace(ThpcClient=object)


class FakeModule(object):
    """Minimal stand-in for helpers that need sdk_call / fail_json."""

    def __init__(self, params=None):
        self.params = params or {}
        self.check_mode = False

    def sdk_call(self, operation, request):
        return operation(request)

    def fail_json(self, **kwargs):
        raise AnsibleFailJson(kwargs)


def _cluster(cluster_id="hpc-1", name="prod-hpc", **overrides):
    """A serialized THPC cluster overview record (RUNNING by default)."""
    record = {
        "ClusterId": cluster_id,
        "ClusterName": name,
        "ClusterStatus": "RUNNING",
        "DeletionProtection": "OFF",
        "Placement": {"Zone": "ap-guangzhou-3"},
        "VpcId": "vpc-1",
        "SchedulerType": "SLURM",
        "SchedulerVersion": "latest",
        "ManagerNodeCount": 1,
        "ComputeNodeCount": 2,
        "LoginNodeCount": 0,
        "AutoScalingType": "THPC_AS",
    }
    record.update(overrides)
    return record


class FakeThpcClient(object):
    """In-memory ThpcClient stand-in storing THPC cluster records.

    DescribeClusters returns records from the request offset, optionally
    sliced to ``page_size`` so paging loops can be exercised; mutating
    operations address records by ClusterId. CreateCluster assigns a fresh
    id and starts the record RUNNING so the module's wait converges on its
    first poll; DeleteCluster removes the record so the absent wait sees
    ABSENT immediately.
    """

    def __init__(self, clusters=None, page_size=None):
        self.clusters = [dict(x) for x in (clusters or [])]
        self.calls = []
        self.page_size = page_size
        self._next_id = 1

    def _record(self, name, request):
        self.calls.append((name, request))

    def _by_id(self, cluster_id):
        for record in self.clusters:
            if record["ClusterId"] == cluster_id:
                return record
        return None

    def DescribeClusters(self, request):
        self._record("DescribeClusters", request)
        items = self.clusters[request.Offset :]
        if self.page_size:
            items = items[: self.page_size]
        return SimpleNamespace(ClusterSet=[FakeResource(dict(x)) for x in items], TotalCount=len(self.clusters))

    def CreateCluster(self, request):
        self._record("CreateCluster", request)
        cluster_id = "hpc-%d" % self._next_id
        self._next_id += 1
        self.clusters.append(
            {
                "ClusterId": cluster_id,
                "ClusterName": request.ClusterName,
                "ClusterStatus": "RUNNING",
                "DeletionProtection": "OFF",
                "Placement": {"Zone": request.Placement.Zone},
                "VpcId": request.VirtualPrivateCloud.VpcId,
                "SchedulerType": request.SchedulerType,
                "SchedulerVersion": request.SchedulerVersion,
                "ManagerNodeCount": request.ManagerNodeCount,
                "ComputeNodeCount": request.ComputeNodeCount,
                "LoginNodeCount": request.LoginNodeCount,
                "AutoScalingType": request.AutoScalingType,
            }
        )
        return SimpleNamespace(ClusterId=cluster_id)

    def ModifyClusterDeletionProtection(self, request):
        self._record("ModifyClusterDeletionProtection", request)
        self._by_id(request.ClusterId)["DeletionProtection"] = request.DeletionProtection
        return SimpleNamespace()

    def DeleteCluster(self, request):
        self._record("DeleteCluster", request)
        self.clusters = [x for x in self.clusters if x["ClusterId"] != request.ClusterId]
        return SimpleNamespace()


# Creation parameters covering every required field for a new cluster.
_CREATE_ARGS = {
    "name": "prod-hpc",
    "zone": "ap-guangzhou-3",
    "manager_node": {"instance_type": "S5.LARGE8"},
    "manager_node_count": 2,
    "compute_node": {"instance_type": "S5.LARGE8", "instance_charge_type": "POSTPAID_BY_HOUR"},
    "compute_node_count": 3,
    "login_node": {"instance_type": "S5.LARGE8"},
    "login_node_count": 1,
    "scheduler_type": "SLURM",
    "scheduler_version": "2025.1",
    "image_id": "img-1",
    "vpc_id": "vpc-1",
    "subnet_id": "subnet-1",
    "login_password": "s3cret",
    "login_key_ids": ["skey-1"],
    "security_group_ids": ["sg-1"],
    "client_token": "tok-1",
    "account_type": "NIS",
    "storage_option": {"cos": {"bucket": "bucket-1", "path": "/data"}},
    "tags": {"team": "pay", "env": "prod"},
    "auto_scaling_type": "THPC_AS",
    "init_node_scripts": [{"script_path": "cos://scripts/init.sh", "timeout": 600}],
    "hpc_cluster_id": "hpc-9",
    "deletion_protection": True,
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
    return [name for name, _ in fake.calls]


# ---------------------------------------------------------------------------
# naming/value conversion and request-builder helper tests
# ---------------------------------------------------------------------------


def test_api_key_acronym_mapping():
    assert mod._api_key("instance_type") == "InstanceType"
    assert mod._api_key("security_group_ids") == "SecurityGroupIds"
    assert mod._api_key("vpc_id") == "VpcId"
    assert mod._api_key("subnet_id") == "SubnetId"
    assert mod._api_key("system_disk") == "SystemDisk"
    assert mod._api_key("scheduler_type") == "SchedulerType"
    assert mod._api_key("init_node_scripts") == "InitNodeScripts"
    assert mod._api_key("script_path") == "ScriptPath"
    assert mod._api_key("login_key_ids") == "LoginKeyIds"
    assert mod._api_key("manager_node") == "ManagerNode"


def test_api_key_single_part_acronyms():
    assert mod._api_key("id") == "Id"
    assert mod._api_key("ids") == "Ids"
    assert mod._api_key("ip") == "Ip"
    assert mod._api_key("ipv6") == "Ipv6"
    assert mod._api_key("cfs") == "CFS"
    assert mod._api_key("cos") == "Cos"
    assert mod._api_key("fs") == "FS"
    assert mod._api_key("hpc") == "Hpc"
    assert mod._api_key("name") == "Name"


def test_api_value_maps_nested_dicts_and_lists():
    converted = mod._api_value(
        {
            "node": {"disk_type": "CLOUD_PREMIUM", "count": 2},
            "scripts": [{"script_path": "cos://s/init.sh", "enabled": True}],
            "raw": "keep",
            "flag": None,
        }
    )
    assert converted == {
        "Node": {"DiskType": "CLOUD_PREMIUM", "Count": 2},
        "Scripts": [{"ScriptPath": "cos://s/init.sh", "Enabled": True}],
        "Raw": "keep",
        "Flag": None,
    }


def test_model_none_returns_none():
    assert mod._model(FakeModels(), "StorageOption", None) is None


def test_model_deserializes_camel_case_dict():
    instance = mod._model(FakeModels(), "StorageOption", {"cos": {"bucket": "b-1"}})
    assert type(instance).__name__ == "StorageOption"
    assert instance.Cos == {"Bucket": "b-1"}


def test_tags_sorted_by_key():
    items = mod._tags(FakeModels(), {"b": 2, "a": "x"})
    assert [i.Key for i in items] == ["a", "b"]
    assert [i.Value for i in items] == ["x", 2]


def test_tags_empty_returns_empty_list():
    assert mod._tags(FakeModels(), {}) == []
    assert mod._tags(FakeModels(), None) == []


def test_describe_request_fields():
    request = mod.describe_request(FakeModels(), {"cluster_id": "hpc-1"})
    assert type(request).__name__ == "DescribeClustersRequest"
    assert request.Offset == 0
    assert request.Limit == 100
    assert request.ClusterIds == ["hpc-1"]
    unnamed = mod.describe_request(FakeModels(), {}, offset=42)
    assert unnamed.ClusterIds is None
    assert unnamed.Offset == 42


def test_create_request_full_payload():
    params = dict(_CREATE_ARGS)
    request = mod.create_request(FakeModels(), params)
    assert type(request).__name__ == "CreateClusterRequest"
    assert request.ClusterName == "prod-hpc"
    assert request.Placement.Zone == "ap-guangzhou-3"
    assert request.ManagerNode.InstanceType == "S5.LARGE8"
    assert request.ManagerNodeCount == 2
    assert request.ComputeNode.InstanceType == "S5.LARGE8"
    assert request.ComputeNode.InstanceChargeType == "POSTPAID_BY_HOUR"
    assert request.ComputeNodeCount == 3
    assert request.LoginNode.InstanceType == "S5.LARGE8"
    assert request.LoginNodeCount == 1
    assert request.SchedulerType == "SLURM"
    assert request.SchedulerVersion == "2025.1"
    assert request.ImageId == "img-1"
    assert request.VirtualPrivateCloud.VpcId == "vpc-1"
    assert request.VirtualPrivateCloud.SubnetId == "subnet-1"
    assert request.LoginSettings.Password == "s3cret"
    assert request.LoginSettings.KeyIds == ["skey-1"]
    assert request.SecurityGroupIds == ["sg-1"]
    assert request.ClientToken == "tok-1"
    assert request.AccountType == "NIS"
    assert request.StorageOption.Cos == {"Bucket": "bucket-1", "Path": "/data"}
    assert [t.Key for t in request.Tags] == ["env", "team"]  # sorted by key
    assert [t.Value for t in request.Tags] == ["prod", "pay"]
    assert request.AutoScalingType == "THPC_AS"
    assert len(request.InitNodeScripts) == 1
    assert request.InitNodeScripts[0].ScriptPath == "cos://scripts/init.sh"
    assert request.HpcClusterId == "hpc-9"


def test_create_request_defaults_when_unset():
    params = {
        "name": "prod-hpc",
        "zone": "ap-guangzhou-3",
        "manager_node": {"instance_type": "S5.LARGE8"},
        "compute_node": {"instance_type": "S5.LARGE8"},
        "image_id": "img-1",
        "vpc_id": "vpc-1",
        "subnet_id": "subnet-1",
    }
    request = mod.create_request(FakeModels(), params)
    assert request.ManagerNodeCount == 1  # default when not given
    assert request.ComputeNodeCount == 0
    assert request.LoginNodeCount == 0
    assert request.SchedulerType == "SLURM"
    assert request.SchedulerVersion == "latest"
    assert request.AccountType == "NIS"
    assert request.AutoScalingType == "THPC_AS"
    assert request.LoginSettings is None  # neither password nor key ids
    assert request.StorageOption is None
    assert request.LoginNode is None
    assert request.Tags == []
    assert request.InitNodeScripts == []
    assert request.SecurityGroupIds is None
    assert request.ClientToken is None
    assert request.HpcClusterId is None


def test_deletion_protection_request_on_and_off():
    enabled = mod.deletion_protection_request(FakeModels(), "hpc-1", True)
    assert type(enabled).__name__ == "ModifyClusterDeletionProtectionRequest"
    assert enabled.ClusterId == "hpc-1"
    assert enabled.DeletionProtection == "ON"
    disabled = mod.deletion_protection_request(FakeModels(), "hpc-1", False)
    assert disabled.DeletionProtection == "OFF"


def test_delete_request_fields():
    request = mod.delete_request(FakeModels(), "hpc-1")
    assert type(request).__name__ == "DeleteClusterRequest"
    assert request.ClusterId == "hpc-1"


# ---------------------------------------------------------------------------
# find helper tests (paged DescribeClusters)
# ---------------------------------------------------------------------------


def test_find_matches_by_cluster_id_single_page():
    fake = FakeThpcClient([_cluster(), _cluster("hpc-2", "other")])
    found = mod.find(FakeModule(), fake, FakeModels(), {"cluster_id": "hpc-2"})
    assert found["ClusterId"] == "hpc-2"
    assert [req.Offset for req in (r for _, r in fake.calls)] == [0]


def test_find_id_mode_stops_after_first_page():
    # id lookups only scan the first page: a record on a later page is missed
    fake = FakeThpcClient([_cluster("hpc-1", "a"), _cluster("hpc-2", "b")], page_size=1)
    found = mod.find(FakeModule(), fake, FakeModels(), {"cluster_id": "hpc-2"})
    assert found is None
    assert len(fake.calls) == 1  # single DescribeClusters call


def test_find_pages_until_name_matches():
    fake = FakeThpcClient([_cluster("hpc-1", "a"), _cluster("hpc-2", "b")], page_size=1)
    found = mod.find(FakeModule(), fake, FakeModels(), {"name": "b"})
    assert found["ClusterId"] == "hpc-2"
    assert [req.Offset for _, req in fake.calls] == [0, 1]


def test_find_name_no_match_exhausts_pages():
    fake = FakeThpcClient([_cluster("hpc-1", "a"), _cluster("hpc-2", "b")], page_size=1)
    assert mod.find(FakeModule(), fake, FakeModels(), {"name": "zzz"}) is None
    assert [req.Offset for _, req in fake.calls] == [0, 1]


def test_find_empty_response_returns_none():
    fake = FakeThpcClient()
    assert mod.find(FakeModule(), fake, FakeModels(), {"name": "prod-hpc"}) is None


def test_find_multiple_name_matches_fail():
    fake = FakeThpcClient([_cluster("hpc-1", "dup"), _cluster("hpc-2", "dup")])
    with pytest.raises(AnsibleFailJson) as exc:
        mod.find(FakeModule(), fake, FakeModels(), {"name": "dup"})
    payload = exc.value.args[0]
    assert payload["msg"] == "Multiple THPC clusters matched; specify cluster_id"


# ---------------------------------------------------------------------------
# waiter tests
# ---------------------------------------------------------------------------


def test_wait_fails_when_cluster_initialization_failed():
    fake = FakeThpcClient([_cluster(ClusterStatus="INIT_FAILED")])
    waiter = FakeModule({"waiter_timeout": 120, "waiter_delay": 5})
    with pytest.raises(AnsibleFailJson) as exc:
        mod._wait(waiter, fake, FakeModels(), {"cluster_id": "hpc-1"}, ["RUNNING"])
    payload = exc.value.args[0]
    assert payload["msg"] == "THPC cluster initialization failed"
    assert payload["cluster"]["ClusterId"] == "hpc-1"


# ---------------------------------------------------------------------------
# argument validation
# ---------------------------------------------------------------------------


def test_requires_cluster_id_or_name(monkeypatch):
    _make_module(monkeypatch, FakeThpcClient())
    module_args(zone="ap-guangzhou-3")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    msg = exc.value.args[0]["msg"]
    assert "one of the following is required" in msg
    assert "cluster_id" in msg and "name" in msg


# ---------------------------------------------------------------------------
# absent main-path tests
# ---------------------------------------------------------------------------


def test_absent_not_found_is_noop(monkeypatch):
    fake = FakeThpcClient()
    _make_module(monkeypatch, fake)
    module_args(state="absent", cluster_id="hpc-9")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["cluster"] is None
    assert not any(name == "DeleteCluster" for name, _ in fake.calls)


def test_absent_deletes_unprotected_cluster(monkeypatch):
    fake = FakeThpcClient([_cluster()])
    _make_module(monkeypatch, fake)
    module_args(state="absent", cluster_id="hpc-1")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["cluster"] is None
    # describe, delete, then the ABSENT wait poll
    assert _call_names(fake) == ["DescribeClusters", "DeleteCluster", "DescribeClusters"]
    delete = [req for name, req in fake.calls if name == "DeleteCluster"][0]
    assert delete.ClusterId == "hpc-1"
    assert fake.clusters == []  # record removed


def test_absent_protected_requires_explicit_false(monkeypatch):
    fake = FakeThpcClient([_cluster(DeletionProtection="ON")])
    _make_module(monkeypatch, fake)
    module_args(state="absent", cluster_id="hpc-1")  # deletion_protection not set
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "THPC cluster deletion protection is enabled; set deletion_protection=false to authorize disabling it before deletion"
    assert not any(name in ("DeleteCluster", "ModifyClusterDeletionProtection") for name, _ in fake.calls)


def test_absent_protected_with_false_disables_then_deletes(monkeypatch):
    fake = FakeThpcClient([_cluster(DeletionProtection="ON")])
    _make_module(monkeypatch, fake)
    module_args(state="absent", cluster_id="hpc-1", deletion_protection=False)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["cluster"] is None
    assert _call_names(fake) == ["DescribeClusters", "ModifyClusterDeletionProtection", "DeleteCluster", "DescribeClusters"]
    modify = [req for name, req in fake.calls if name == "ModifyClusterDeletionProtection"][0]
    assert modify.ClusterId == "hpc-1"
    assert modify.DeletionProtection == "OFF"
    assert fake.clusters == []


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeThpcClient([_cluster(DeletionProtection="ON")])
    _make_module(monkeypatch, fake)
    module_args(_ansible_check_mode=True, state="absent", cluster_id="hpc-1", deletion_protection=False)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["cluster"] is None
    assert result["diff"]["before"]["ClusterId"] == "hpc-1"
    assert result["diff"]["after"] is None
    assert not any(name in ("DeleteCluster", "ModifyClusterDeletionProtection") for name, _ in fake.calls)
    assert len(fake.clusters) == 1  # remote untouched


# ---------------------------------------------------------------------------
# present main-path tests: creation
# ---------------------------------------------------------------------------


def test_present_missing_creation_params_fails(monkeypatch):
    fake = FakeThpcClient()
    _make_module(monkeypatch, fake)
    module_args(name="prod-hpc")  # satisfies required_one_of but nothing else
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "creation parameters are required for a new THPC cluster"
    assert payload["missing"] == ["zone", "manager_node", "compute_node", "image_id", "vpc_id", "subnet_id"]
    assert not any(name == "CreateCluster" for name, _ in fake.calls)


def test_present_creates_cluster_and_refinds(monkeypatch):
    fake = FakeThpcClient()
    _make_module(monkeypatch, fake)
    module_args(**_CREATE_ARGS)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["cluster"]["ClusterId"] == "hpc-1"
    assert result["cluster"]["ClusterName"] == "prod-hpc"
    assert result["cluster"]["ClusterStatus"] == "RUNNING"
    assert result["cluster"]["DeletionProtection"] == "ON"  # enabled after create
    # find, create, RUNNING wait poll, enable protection, re-find
    assert _call_names(fake) == [
        "DescribeClusters",
        "CreateCluster",
        "DescribeClusters",
        "ModifyClusterDeletionProtection",
        "DescribeClusters",
    ]
    create = [req for name, req in fake.calls if name == "CreateCluster"][0]
    assert create.ClusterName == "prod-hpc"
    assert create.Placement.Zone == "ap-guangzhou-3"
    assert create.ManagerNode.InstanceType == "S5.LARGE8"
    assert create.ManagerNodeCount == 2
    assert create.ComputeNode.InstanceType == "S5.LARGE8"
    assert create.ComputeNodeCount == 3
    assert create.LoginNodeCount == 1
    assert create.SchedulerType == "SLURM"
    assert create.SchedulerVersion == "2025.1"
    assert create.ImageId == "img-1"
    assert create.VirtualPrivateCloud.VpcId == "vpc-1"
    assert create.VirtualPrivateCloud.SubnetId == "subnet-1"
    assert create.LoginSettings.KeyIds == ["skey-1"]
    assert create.SecurityGroupIds == ["sg-1"]
    assert [t.Key for t in create.Tags] == ["env", "team"]
    modify = [req for name, req in fake.calls if name == "ModifyClusterDeletionProtection"][0]
    assert modify.ClusterId == "hpc-1"
    assert modify.DeletionProtection == "ON"


def test_present_create_without_deletion_protection(monkeypatch):
    args = {k: v for k, v in _CREATE_ARGS.items() if k != "deletion_protection"}
    fake = FakeThpcClient()
    _make_module(monkeypatch, fake)
    module_args(**args)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["cluster"]["DeletionProtection"] == "OFF"
    assert not any(name == "ModifyClusterDeletionProtection" for name, _ in fake.calls)
    # find, create, RUNNING wait poll, re-find (no protection enable step)
    assert _call_names(fake) == ["DescribeClusters", "CreateCluster", "DescribeClusters", "DescribeClusters"]


def test_present_check_mode_create_is_dry_run(monkeypatch):
    fake = FakeThpcClient()
    _make_module(monkeypatch, fake)
    module_args(_ansible_check_mode=True, **_CREATE_ARGS)
    result = run(mod.run_module)
    target = {
        "ClusterName": "prod-hpc",
        "Placement": {"Zone": "ap-guangzhou-3"},
        "SchedulerType": "SLURM",
        "SchedulerVersion": "2025.1",
        "ManagerNodeCount": 2,
        "ComputeNodeCount": 3,
        "LoginNodeCount": 1,
        "VpcId": "vpc-1",
        "AutoScalingType": "THPC_AS",
        "DeletionProtection": "ON",  # deletion_protection=true requested
    }
    assert result["changed"] is True
    assert result["cluster"] == target
    assert result["diff"]["before"] is None
    assert result["diff"]["after"] == target
    assert _call_names(fake) == ["DescribeClusters"]  # no write
    assert fake.clusters == []


# ---------------------------------------------------------------------------
# present main-path tests: immutable topology drift
# ---------------------------------------------------------------------------


def test_present_cluster_name_drift_fails_immutable(monkeypatch):
    fake = FakeThpcClient([_cluster()])
    _make_module(monkeypatch, fake)
    module_args(cluster_id="hpc-1", name="renamed")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "THPC cluster topology fields are immutable"
    assert payload["immutable_drift"] == {"ClusterName": ("prod-hpc", "renamed")}
    assert not any(name != "DescribeClusters" for name, _ in fake.calls)


def test_present_zone_drift_reads_placement(monkeypatch):
    fake = FakeThpcClient([_cluster()])
    _make_module(monkeypatch, fake)
    module_args(cluster_id="hpc-1", zone="ap-guangzhou-9")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "THPC cluster topology fields are immutable"
    assert payload["immutable_drift"] == {"Zone": ("ap-guangzhou-3", "ap-guangzhou-9")}


def test_present_count_drift_fails_immutable(monkeypatch):
    fake = FakeThpcClient([_cluster()])
    _make_module(monkeypatch, fake)
    module_args(cluster_id="hpc-1", manager_node_count=3, compute_node_count=5)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "THPC cluster topology fields are immutable"
    assert payload["immutable_drift"] == {"ManagerNodeCount": (1, 3), "ComputeNodeCount": (2, 5)}


def test_present_topology_drift_fails_even_in_check_mode(monkeypatch):
    fake = FakeThpcClient([_cluster()])
    _make_module(monkeypatch, fake)
    module_args(_ansible_check_mode=True, cluster_id="hpc-1", vpc_id="vpc-9")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "THPC cluster topology fields are immutable"
    assert payload["immutable_drift"] == {"VpcId": ("vpc-1", "vpc-9")}


# ---------------------------------------------------------------------------
# present main-path tests: deletion-protection reconciliation
# ---------------------------------------------------------------------------


def test_present_unchanged_is_noop(monkeypatch):
    fake = FakeThpcClient([_cluster(DeletionProtection="ON")])
    _make_module(monkeypatch, fake)
    module_args(cluster_id="hpc-1")  # deletion_protection unset -> leave as-is
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["cluster"]["DeletionProtection"] == "ON"
    assert _call_names(fake) == ["DescribeClusters"]


def test_present_protection_already_desired_is_noop(monkeypatch):
    fake = FakeThpcClient([_cluster(DeletionProtection="ON")])
    _make_module(monkeypatch, fake)
    module_args(cluster_id="hpc-1", deletion_protection=True)
    result = run(mod.run_module)
    assert result["changed"] is False
    assert not any(name == "ModifyClusterDeletionProtection" for name, _ in fake.calls)


def test_present_enables_deletion_protection(monkeypatch):
    fake = FakeThpcClient([_cluster()])
    _make_module(monkeypatch, fake)
    module_args(cluster_id="hpc-1", deletion_protection=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["cluster"]["DeletionProtection"] == "ON"
    assert _call_names(fake) == ["DescribeClusters", "ModifyClusterDeletionProtection"]
    modify = [req for name, req in fake.calls if name == "ModifyClusterDeletionProtection"][0]
    assert modify.ClusterId == "hpc-1"
    assert modify.DeletionProtection == "ON"


def test_present_disables_deletion_protection(monkeypatch):
    fake = FakeThpcClient([_cluster(DeletionProtection="ON")])
    _make_module(monkeypatch, fake)
    module_args(cluster_id="hpc-1", deletion_protection=False)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["cluster"]["DeletionProtection"] == "OFF"
    modify = [req for name, req in fake.calls if name == "ModifyClusterDeletionProtection"][0]
    assert modify.DeletionProtection == "OFF"


def test_present_check_mode_protection_is_dry_run(monkeypatch):
    fake = FakeThpcClient([_cluster()])
    _make_module(monkeypatch, fake)
    module_args(_ansible_check_mode=True, cluster_id="hpc-1", deletion_protection=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["cluster"]["DeletionProtection"] == "OFF"  # pre-change snapshot
    assert result["diff"]["before"] == {"DeletionProtection": False}
    assert result["diff"]["after"] == {"DeletionProtection": True}
    assert not any(name == "ModifyClusterDeletionProtection" for name, _ in fake.calls)


# ---------------------------------------------------------------------------
# error path and entry point
# ---------------------------------------------------------------------------


def test_sdk_error_is_reported(monkeypatch):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (FakeModels(), SimpleNamespace(ThpcClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: _BoomClient())
    module_args(name="prod-hpc")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert payload["error"] == "service exploded"


def test_main_entrypoint_runs_module(monkeypatch):
    fake = FakeThpcClient([_cluster()])
    _make_module(monkeypatch, fake)
    module_args(cluster_id="hpc-1")
    result = run(mod.main)
    assert result["changed"] is False
    assert result["cluster"]["ClusterId"] == "hpc-1"
