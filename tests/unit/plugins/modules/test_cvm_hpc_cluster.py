"""Unit tests for the cvm_hpc_cluster write module (helpers + run_module).

Creates, updates and deletes CVM high-performance clusters. A cluster is
looked up by HpcClusterId or by name; multiple name matches fail. Zone /
cluster type / business id are immutable — a topology drift fails unless
force_replace is set, and replacing a cluster that still has InstanceIds
always fails. Name and remark drift is applied through ModifyHpcCluster
Attribute and the module re-finds after every mutation.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import cvm_hpc_cluster as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)


class _SdkError(Exception):
    """Stand-in for TencentCloudSDKException carrying a code/request id."""

    def __init__(self, code, message="", request_id=None):
        super(_SdkError, self).__init__(message)
        self._code = code
        self._request_id = request_id

    def get_code(self):
        return self._code

    def get_request_id(self):
        return self._request_id


def _cluster(**overrides):
    """API-shaped HPC cluster dict; fresh copy per call."""
    item = {
        "HpcClusterId": "hpc-101",
        "Name": "rdma-production",
        "Zone": "ap-guangzhou-3",
        "Remark": "managed by Ansible",
        "HpcClusterType": "STANDARD",
        "HpcClusterBusinessId": None,
    }
    item.update(overrides)
    return item


def _params(**overrides):
    """Module parameters pre-filled from the argument spec defaults."""
    params = {
        "state": "present",
        "cluster_id": None,
        "name": "rdma-production",
        "zone": "ap-guangzhou-3",
        "remark": "managed by Ansible",
        "cluster_type": "STANDARD",
        "business_id": None,
        "force_replace": False,
    }
    params.update(overrides)
    return params


def _run_args(**extra):
    """module_args() pre-filled with every non-None module parameter."""
    params = _params(**extra)
    args = {k: v for k, v in params.items() if v is not None}
    for key, value in extra.items():
        if key.startswith("_"):
            args[key] = value
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


class FakeCvmClient(object):
    """In-memory CvmClient stand-in storing HPC cluster dicts.

    DescribeHpcClusters filters by HpcClusterIds when the request carries
    them and otherwise returns every cluster (the module re-filters by
    name client-side). CreateHpcCluster synthesizes hpc-NNNN ids,
    ModifyHpcClusterAttribute rewrites Name/Remark and DeleteHpcClusters
    removes by id.
    """

    def __init__(self, clusters=None):
        self.clusters = [dict(c) for c in (clusters or [])]
        self.calls = []
        self._seq = 2001

    def _record(self, name, request):
        self.calls.append((name, request))
        return request

    def DescribeHpcClusters(self, request):
        self._record("DescribeHpcClusters", request)
        values = self.clusters
        ids = getattr(request, "HpcClusterIds", None)
        if ids:
            values = [c for c in values if c["HpcClusterId"] in ids]
        return SimpleNamespace(
            HpcClusterSet=[FakeResource(dict(c)) for c in values],
            RequestId="req-fake",
        )

    def CreateHpcCluster(self, request):
        self._record("CreateHpcCluster", request)
        cluster_id = "hpc-%d" % self._seq
        self._seq += 1
        stored = {
            "HpcClusterId": cluster_id,
            "Name": request.Name,
            "Zone": request.Zone,
            "Remark": request.Remark,
            "HpcClusterType": request.HpcClusterType,
            "HpcClusterBusinessId": getattr(request, "HpcClusterBusinessId", None),
        }
        self.clusters.append(stored)
        return SimpleNamespace(HpcClusterId=cluster_id, RequestId="req-fake")

    def ModifyHpcClusterAttribute(self, request):
        self._record("ModifyHpcClusterAttribute", request)
        for cluster in self.clusters:
            if cluster["HpcClusterId"] == request.HpcClusterId:
                cluster["Name"] = request.Name
                cluster["Remark"] = request.Remark
        return SimpleNamespace(RequestId="req-fake")

    def DeleteHpcClusters(self, request):
        self._record("DeleteHpcClusters", request)
        ids = request.HpcClusterIds
        self.clusters = [c for c in self.clusters if c["HpcClusterId"] not in ids]
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake):
    """Wire the shared monkeypatches and return the fake client."""
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(
        mod,
        "_load",
        lambda: (FakeModels(), SimpleNamespace(CvmClient=object)),
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
            raise _SdkError("AuthFailure", "auth rejected", request_id="req-err")

        return boom


# ---------------------------------------------------------------------------
# request-builder / helper tests
# ---------------------------------------------------------------------------


def test_describe_request_filters_by_cluster_id():
    request = mod.describe_request(FakeModels(), _params(cluster_id="hpc-101"))
    assert request.Limit == 100
    assert request.HpcClusterIds == ["hpc-101"]
    assert not hasattr(request, "Name")


def test_describe_request_filters_by_name():
    request = mod.describe_request(FakeModels(), _params())
    assert request.Limit == 100
    assert not hasattr(request, "HpcClusterIds")
    assert request.Name == "rdma-production"


def test_describe_request_no_identity_filters():
    request = mod.describe_request(FakeModels(), _params(cluster_id=None, name=None))
    assert request.Limit == 100
    assert not hasattr(request, "HpcClusterIds")
    assert not hasattr(request, "Name")


def test_create_request_carries_fields():
    request = mod.create_request(FakeModels(), _params())
    assert request.Zone == "ap-guangzhou-3"
    assert request.Name == "rdma-production"
    assert request.Remark == "managed by Ansible"
    assert request.HpcClusterType == "STANDARD"
    assert request.HpcClusterBusinessId is None


def test_create_request_cdc_business_id():
    request = mod.create_request(
        FakeModels(), _params(cluster_type="CDC", business_id="biz-1")
    )
    assert request.HpcClusterType == "CDC"
    assert request.HpcClusterBusinessId == "biz-1"


def test_update_request_carries_id_name_remark():
    request = mod.update_request(FakeModels(), _params(remark="tuned"), "hpc-101")
    assert request.HpcClusterId == "hpc-101"
    assert request.Name == "rdma-production"
    assert request.Remark == "tuned"


def test_delete_request_carries_ids():
    request = mod.delete_request(FakeModels(), "hpc-101")
    assert request.HpcClusterIds == ["hpc-101"]


def test_comparable_defaults_standard_type():
    value = mod.comparable({"Name": "n", "Remark": "r", "Zone": "z"})
    assert value == {
        "Name": "n",
        "Remark": "r",
        "Zone": "z",
        "HpcClusterType": "STANDARD",
        "HpcClusterBusinessId": None,
    }


def test_comparable_passthrough():
    value = mod.comparable(_cluster())
    assert value["Name"] == "rdma-production"
    assert value["HpcClusterType"] == "STANDARD"


def test_desired_matches_params():
    assert mod.desired(_params(remark="tuned", cluster_type="CHC", business_id="biz-9")) == {
        "Name": "rdma-production",
        "Remark": "tuned",
        "Zone": "ap-guangzhou-3",
        "HpcClusterType": "CHC",
        "HpcClusterBusinessId": "biz-9",
    }


def test_find_by_cluster_id():
    fake = FakeCvmClient([_cluster(), _cluster(HpcClusterId="hpc-102", Name="other")])
    module = FakeModule(_params(cluster_id="hpc-102"))
    value = mod.find(module, fake, FakeModels(), module.params)
    assert value["HpcClusterId"] == "hpc-102"


def test_find_by_name():
    fake = FakeCvmClient([_cluster(HpcClusterId="hpc-102")])
    module = FakeModule(_params())
    value = mod.find(module, fake, FakeModels(), module.params)
    assert value["HpcClusterId"] == "hpc-102"


def test_find_no_match_returns_none():
    fake = FakeCvmClient([_cluster(Name="other")])
    module = FakeModule(_params())
    assert mod.find(module, fake, FakeModels(), module.params) is None


def test_find_multi_match_fails():
    fake = FakeCvmClient([_cluster(), _cluster(HpcClusterId="hpc-102")])
    module = FakeModule(_params())
    with pytest.raises(AnsibleFailJson) as exc:
        mod.find(module, fake, FakeModels(), module.params)
    assert "Multiple CVM HPC clusters matched" in exc.value.args[0]["msg"]


# ---------------------------------------------------------------------------
# run_module main-path tests
# ---------------------------------------------------------------------------


def test_present_requires_name_and_zone(monkeypatch):
    fake = FakeCvmClient()
    _make_module(monkeypatch, fake)
    _run_args(cluster_id="hpc-101", name=None, zone=None)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "name and zone are required when state=present" in exc.value.args[0]["msg"]


def test_cdc_requires_business_id(monkeypatch):
    fake = FakeCvmClient()
    _make_module(monkeypatch, fake)
    _run_args(cluster_type="CDC")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "business_id is required for CDC clusters" in exc.value.args[0]["msg"]


def test_absent_noop_when_missing(monkeypatch):
    fake = FakeCvmClient()
    _make_module(monkeypatch, fake)
    _run_args(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["hpc_cluster"] is None
    assert [c[0] for c in fake.calls] == ["DescribeHpcClusters"]


def test_absent_check_mode_delete_is_dry_run(monkeypatch):
    fake = FakeCvmClient([_cluster()])
    _make_module(monkeypatch, fake)
    _run_args(state="absent", _ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["hpc_cluster"]["HpcClusterId"] == "hpc-101"
    assert result["diff"]["before"]["Name"] == "rdma-production"
    assert result["diff"]["after"] is None
    assert [c[0] for c in fake.calls] == ["DescribeHpcClusters"]
    assert len(fake.clusters) == 1


def test_absent_deletes_cluster(monkeypatch):
    fake = FakeCvmClient([_cluster()])
    _make_module(monkeypatch, fake)
    _run_args(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["hpc_cluster"] is None
    assert [c[0] for c in fake.calls] == ["DescribeHpcClusters", "DeleteHpcClusters"]
    assert fake.calls[1][1].HpcClusterIds == ["hpc-101"]
    assert fake.clusters == []


def test_present_noop_matching_name(monkeypatch):
    fake = FakeCvmClient([_cluster()])
    _make_module(monkeypatch, fake)
    _run_args()
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["hpc_cluster"]["HpcClusterId"] == "hpc-101"
    assert [c[0] for c in fake.calls] == ["DescribeHpcClusters"]


def test_present_noop_via_cluster_id(monkeypatch):
    fake = FakeCvmClient([_cluster()])
    _make_module(monkeypatch, fake)
    _run_args(cluster_id="hpc-101")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["hpc_cluster"]["HpcClusterId"] == "hpc-101"
    assert [c[0] for c in fake.calls] == ["DescribeHpcClusters"]


def test_present_creates_cluster(monkeypatch):
    fake = FakeCvmClient()
    _make_module(monkeypatch, fake)
    _run_args()
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["hpc_cluster"]["HpcClusterId"] == "hpc-2001"
    assert result["hpc_cluster"]["Zone"] == "ap-guangzhou-3"
    assert [c[0] for c in fake.calls] == [
        "DescribeHpcClusters",
        "CreateHpcCluster",
        "DescribeHpcClusters",
    ]
    created = fake.calls[1][1]
    assert created.Name == "rdma-production"
    assert created.Zone == "ap-guangzhou-3"
    assert created.Remark == "managed by Ansible"
    assert created.HpcClusterType == "STANDARD"
    assert created.HpcClusterBusinessId is None
    assert len(fake.clusters) == 1


def test_present_creates_cdc_cluster(monkeypatch):
    fake = FakeCvmClient()
    _make_module(monkeypatch, fake)
    _run_args(cluster_type="CDC", business_id="biz-1")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["hpc_cluster"]["HpcClusterId"] == "hpc-2001"
    created = fake.calls[1][1]
    assert created.HpcClusterType == "CDC"
    assert created.HpcClusterBusinessId == "biz-1"


def test_present_updates_remark_drift(monkeypatch):
    fake = FakeCvmClient([_cluster()])
    _make_module(monkeypatch, fake)
    _run_args(remark="rebalanced")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["hpc_cluster"]["Remark"] == "rebalanced"
    assert [c[0] for c in fake.calls] == [
        "DescribeHpcClusters",
        "ModifyHpcClusterAttribute",
        "DescribeHpcClusters",
    ]
    updated = fake.calls[1][1]
    assert updated.HpcClusterId == "hpc-101"
    assert updated.Remark == "rebalanced"


def test_present_renames_via_cluster_id(monkeypatch):
    fake = FakeCvmClient([_cluster(Name="legacy-name")])
    _make_module(monkeypatch, fake)
    _run_args(cluster_id="hpc-101", name="new-name")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["hpc_cluster"]["Name"] == "new-name"
    assert fake.calls[1][0] == "ModifyHpcClusterAttribute"
    assert fake.calls[1][1].Name == "new-name"


def test_present_check_mode_update_is_dry_run(monkeypatch):
    fake = FakeCvmClient([_cluster()])
    _make_module(monkeypatch, fake)
    _run_args(remark="rebalanced", _ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["hpc_cluster"]["Remark"] == "managed by Ansible"
    assert result["diff"]["after"]["Remark"] == "rebalanced"
    assert [c[0] for c in fake.calls] == ["DescribeHpcClusters"]


def test_topology_drift_requires_force_replace(monkeypatch):
    fake = FakeCvmClient([_cluster()])
    _make_module(monkeypatch, fake)
    _run_args(zone="ap-guangzhou-6")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "HPC cluster topology is immutable" in payload["msg"]
    assert payload["current"]["Zone"] == "ap-guangzhou-3"
    assert payload["desired"]["Zone"] == "ap-guangzhou-6"
    assert [c[0] for c in fake.calls] == ["DescribeHpcClusters"]


def test_force_replace_refuses_non_empty_cluster(monkeypatch):
    fake = FakeCvmClient([_cluster(InstanceIds=["ins-1"])])
    _make_module(monkeypatch, fake)
    _run_args(zone="ap-guangzhou-6", force_replace=True)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "cannot replace a non-empty HPC cluster" in payload["msg"]
    assert payload["instance_ids"] == ["ins-1"]
    assert [c[0] for c in fake.calls] == ["DescribeHpcClusters"]


def test_force_replace_replaces_empty_cluster(monkeypatch):
    fake = FakeCvmClient([_cluster()])
    _make_module(monkeypatch, fake)
    _run_args(zone="ap-guangzhou-6", force_replace=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["hpc_cluster"]["HpcClusterId"] == "hpc-2001"
    assert result["hpc_cluster"]["Zone"] == "ap-guangzhou-6"
    assert [c[0] for c in fake.calls] == [
        "DescribeHpcClusters",
        "DeleteHpcClusters",
        "CreateHpcCluster",
        "DescribeHpcClusters",
    ]
    assert fake.calls[1][1].HpcClusterIds == ["hpc-101"]
    assert fake.calls[2][1].Zone == "ap-guangzhou-6"
    assert len(fake.clusters) == 1
    assert fake.clusters[0]["HpcClusterId"] == "hpc-2001"


def test_force_replace_check_mode_is_dry_run(monkeypatch):
    fake = FakeCvmClient([_cluster()])
    _make_module(monkeypatch, fake)
    _run_args(zone="ap-guangzhou-6", force_replace=True, _ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["hpc_cluster"]["HpcClusterId"] == "hpc-101"
    assert result["diff"]["before"]["Zone"] == "ap-guangzhou-3"
    assert result["diff"]["after"]["Zone"] == "ap-guangzhou-6"
    assert [c[0] for c in fake.calls] == ["DescribeHpcClusters"]
    assert len(fake.clusters) == 1


def test_multi_match_fails_in_run(monkeypatch):
    fake = FakeCvmClient([_cluster(), _cluster(HpcClusterId="hpc-102")])
    _make_module(monkeypatch, fake)
    _run_args()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "Multiple CVM HPC clusters matched" in exc.value.args[0]["msg"]


def test_sdk_failure_reports_error_payload(monkeypatch):
    fake = _BoomClient()
    _make_module(monkeypatch, fake)
    _run_args(state="absent")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert payload["error"] == "auth rejected"
    assert payload["error_code"] == "AuthFailure"
    assert payload["request_id"] == "req-err"


def test_main_entrypoint_runs_module(monkeypatch):
    fake = FakeCvmClient()
    _make_module(monkeypatch, fake)
    _run_args(state="absent")
    result = run(mod.main)
    assert result["changed"] is False
    assert result["hpc_cluster"] is None
