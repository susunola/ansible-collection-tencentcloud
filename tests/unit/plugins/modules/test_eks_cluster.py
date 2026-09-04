"""Unit tests for the eks_cluster write module (helpers + run_module).

Covers the create / description-drift / delete flows of
``plugins/modules/eks_cluster.py`` with an in-memory fake TKE client whose
write operations mutate the cluster store, so post-write state converges.
Clusters are matched by name across the paged DescribeEKSClusters list;
only the cluster description can be updated in place (UpdateEKSCluster) —
VPC, subnets and Kubernetes version are create-only.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import eks_cluster as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

CLUSTER = {
    "ClusterId": "eks-abcdefg",
    "ClusterName": "eks-prod",
    "ClusterDesc": "",
    "Status": "running",
}


def _cluster(**overrides):
    """API-shaped cluster dict isolated from the shared constant."""
    item = copy.deepcopy(CLUSTER)
    item.update(overrides)
    return item


def _params(**overrides):
    """Module parameters pre-filled from the argument spec (base included)."""
    params = {
        "cluster_name": "eks-prod",
        "state": "present",
        "vpc_id": None,
        "subnet_ids": None,
        "k8s_version": None,
        "cluster_desc": None,
        "enable_vpc_coredns": None,
        "service_subnet_id": None,
        "retries": 5,
        "waiter_delay": 5,
        "waiter_timeout": 120,
    }
    params.update(overrides)
    return params


def _run_args(**extra):
    """module_args() pre-filled with every module parameter."""
    args = dict(_params())
    args.update(extra)
    return module_args(**args)


class FakeModule(object):
    """Minimal stand-in for helpers that need sdk_call / fail_json."""

    def __init__(self, params=None):
        self.params = params or _params()
        self.sdk_calls = []

    def sdk_call(self, operation, request):
        self.sdk_calls.append((operation, request))
        return operation(request)

    def fail_json(self, **kwargs):
        raise AnsibleFailJson(kwargs)


class FakeTkeClient(object):
    """In-memory TkeClient stand-in.

    Stores API-shaped cluster dicts. DescribeEKSClusters pages over the
    store honouring Offset/Limit so find pagination is exercised; the write
    operations mutate the store so post-write refetches converge.
    """

    def __init__(self, clusters=None):
        self.clusters = [copy.deepcopy(c) for c in (clusters or [])]
        self.calls = []

    def _record(self, name, request):
        self.calls.append((name, request))
        return request

    def DescribeEKSClusters(self, request):
        self._record("DescribeEKSClusters", request)
        page = self.clusters[request.Offset : request.Offset + request.Limit]
        return SimpleNamespace(
            Clusters=[FakeResource(dict(c)) for c in page],
            TotalCount=len(self.clusters),
            RequestId="req-fake",
        )

    def CreateEKSCluster(self, request):
        self._record("CreateEKSCluster", request)
        entry = {
            "ClusterId": "eks-fake-%04d" % (len(self.clusters) + 1),
            "ClusterName": request.ClusterName,
            "ClusterDesc": getattr(request, "ClusterDesc", "") or "",
            "Status": "creating",
        }
        self.clusters.append(entry)
        return SimpleNamespace(ClusterId=entry["ClusterId"], RequestId="req-fake")

    def UpdateEKSCluster(self, request):
        self._record("UpdateEKSCluster", request)
        for stored in self.clusters:
            if stored.get("ClusterId") == request.ClusterId:
                stored["ClusterDesc"] = request.ClusterDesc or ""
        return SimpleNamespace(RequestId="req-fake")

    def DeleteEKSCluster(self, request):
        self._record("DeleteEKSCluster", request)
        self.clusters = [c for c in self.clusters if c.get("ClusterId") != request.ClusterId]
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake):
    """Wire the shared monkeypatches and return the fake client."""
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(
        mod,
        "_load_tke",
        lambda: (FakeModels(), SimpleNamespace(TkeClient=object)),
    )
    monkeypatch.setattr(
        TencentCloudModule,
        "create_client",
        lambda self, client_class, endpoint: fake,
    )
    return fake


class _BoomClient(object):
    """Every SDK call raises, so the module's wrapped error path is hit."""

    def __getattr__(self, name):
        def boom(*args, **kwargs):
            raise RuntimeError("service exploded")

        return boom


# ---------------------------------------------------------------------------
# find helper tests
# ---------------------------------------------------------------------------


def test_find_cluster_matches_by_name(monkeypatch):
    fake = FakeTkeClient([_cluster(ClusterName="other"), _cluster()])
    _make_module(monkeypatch, fake)
    module = FakeModule()
    value = mod.find_cluster(module, fake, FakeModels(), "eks-prod")
    assert value["ClusterId"] == "eks-abcdefg"


def test_find_cluster_no_match_returns_none(monkeypatch):
    fake = FakeTkeClient([_cluster(ClusterName="other")])
    _make_module(monkeypatch, fake)
    module = FakeModule()
    assert mod.find_cluster(module, fake, FakeModels(), "ghost") is None


def test_find_cluster_paginates_until_match(monkeypatch):
    clusters = [_cluster(ClusterId="eks-bulk-%04d" % i, ClusterName="bulk-%04d" % i) for i in range(250)]
    clusters.append(_cluster())
    fake = FakeTkeClient(clusters)
    _make_module(monkeypatch, fake)
    module = FakeModule()
    value = mod.find_cluster(module, fake, FakeModels(), "eks-prod")
    assert value["ClusterId"] == "eks-abcdefg"
    assert len([c for c in fake.calls if c[0] == "DescribeEKSClusters"]) == 3  # pages of 100


# ---------------------------------------------------------------------------
# run_module main-path tests
# ---------------------------------------------------------------------------


def test_cluster_name_required():
    module_args(state="present")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "cluster_name" in exc.value.args[0]["msg"]


def test_sdk_error_is_reported(monkeypatch):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(
        mod,
        "_load_tke",
        lambda: (FakeModels(), SimpleNamespace(TkeClient=object)),
    )
    monkeypatch.setattr(
        TencentCloudModule,
        "create_client",
        lambda self, client_class, endpoint: _BoomClient(),
    )
    _run_args()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert payload["error"] == "service exploded"


def test_present_missing_create_params_fails(monkeypatch):
    fake = FakeTkeClient()
    _make_module(monkeypatch, fake)
    _run_args()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "vpc_id" in payload["msg"]
    assert "subnet_ids" in payload["msg"]
    assert "Parameters required to create" in payload["msg"]
    assert not any("CreateEKSCluster" == c[0] for c in fake.calls)


def test_present_creates_cluster(monkeypatch):
    fake = FakeTkeClient()
    _make_module(monkeypatch, fake)
    _run_args(vpc_id="vpc-abc", subnet_ids=["subnet-a", "subnet-b"])
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["cluster_id"] == "eks-fake-0001"
    assert result["cluster_name"] == "eks-prod"
    assert "creation submitted" in result["msg"]
    create = [c for c in fake.calls if c[0] == "CreateEKSCluster"][0][1]
    assert create.ClusterName == "eks-prod"
    assert create.VpcId == "vpc-abc"
    assert create.SubnetIds == ["subnet-a", "subnet-b"]
    assert not hasattr(create, "K8SVersion")
    assert not hasattr(create, "ClusterDesc")


def test_present_creates_with_optional_fields(monkeypatch):
    fake = FakeTkeClient()
    _make_module(monkeypatch, fake)
    _run_args(
        vpc_id="vpc-abc",
        subnet_ids=["subnet-a"],
        k8s_version="1.28.5",
        cluster_desc="prod eks",
        enable_vpc_coredns=True,
        service_subnet_id="subnet-svc",
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    create = [c for c in fake.calls if c[0] == "CreateEKSCluster"][0][1]
    assert create.K8SVersion == "1.28.5"
    assert create.ClusterDesc == "prod eks"
    assert create.EnableVpcCoreDNS is True
    assert create.ServiceSubnetId == "subnet-svc"


def test_present_check_mode_create_is_dry_run(monkeypatch):
    fake = FakeTkeClient()
    _make_module(monkeypatch, fake)
    module_args(_ansible_check_mode=True, **_params(vpc_id="vpc-abc", subnet_ids=["subnet-a"]))
    result = run(mod.run_module)
    assert result["changed"] is True
    assert "Would create" in result["msg"]
    assert not any("CreateEKSCluster" == c[0] for c in fake.calls)


def test_present_noop_is_unchanged(monkeypatch):
    fake = FakeTkeClient([_cluster()])
    _make_module(monkeypatch, fake)
    _run_args()
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["cluster_id"] == "eks-abcdefg"
    assert result["status"] == "running"
    assert "already present" in result["msg"]
    assert not any("UpdateEKSCluster" == c[0] for c in fake.calls)


def test_present_desc_drift_triggers_update(monkeypatch):
    fake = FakeTkeClient([_cluster()])
    _make_module(monkeypatch, fake)
    _run_args(cluster_desc="new description")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert "Updated description" in result["msg"]
    update = [c for c in fake.calls if c[0] == "UpdateEKSCluster"][0][1]
    assert update.ClusterId == "eks-abcdefg"
    assert update.ClusterDesc == "new description"
    assert fake.clusters[0]["ClusterDesc"] == "new description"


def test_present_check_mode_update_is_dry_run(monkeypatch):
    fake = FakeTkeClient([_cluster()])
    _make_module(monkeypatch, fake)
    module_args(_ansible_check_mode=True, **_params(cluster_desc="draft"))
    result = run(mod.run_module)
    assert result["changed"] is True
    assert "Would update description" in result["msg"]
    assert not any("UpdateEKSCluster" == c[0] for c in fake.calls)


def test_present_desc_cleared_to_empty_triggers_update(monkeypatch):
    fake = FakeTkeClient([_cluster(ClusterDesc="old desc")])
    _make_module(monkeypatch, fake)
    _run_args(cluster_desc="")
    result = run(mod.run_module)
    assert result["changed"] is True
    update = [c for c in fake.calls if c[0] == "UpdateEKSCluster"][0][1]
    assert update.ClusterDesc == ""
    assert fake.clusters[0]["ClusterDesc"] == ""


def test_absent_not_found_is_noop(monkeypatch):
    fake = FakeTkeClient([_cluster(ClusterName="other")])
    _make_module(monkeypatch, fake)
    _run_args(state="absent", cluster_name="ghost")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert "not present" in result["msg"]
    assert not any("DeleteEKSCluster" == c[0] for c in fake.calls)


def test_absent_deletes_cluster(monkeypatch):
    fake = FakeTkeClient([_cluster()])
    _make_module(monkeypatch, fake)
    _run_args(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert "Deleted EKS cluster eks-abcdefg" in result["msg"]
    delete = [c for c in fake.calls if c[0] == "DeleteEKSCluster"][0][1]
    assert delete.ClusterId == "eks-abcdefg"
    assert fake.clusters == []


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeTkeClient([_cluster()])
    _make_module(monkeypatch, fake)
    module_args(_ansible_check_mode=True, **_params(state="absent"))
    result = run(mod.run_module)
    assert result["changed"] is True
    assert "Would delete EKS cluster eks-abcdefg" in result["msg"]
    assert not any("DeleteEKSCluster" == c[0] for c in fake.calls)
    assert len(fake.clusters) == 1
