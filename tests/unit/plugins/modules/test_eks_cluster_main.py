"""Main-path unit tests for the eks_cluster module (run_module level)."""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import eks_cluster
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

CLUSTER_NAME = "eks-prod"


class FakeSdkError(Exception):
    def __init__(self, code, request_id="req-fake"):
        super(FakeSdkError, self).__init__(code)
        self._code = code
        self._request_id = request_id

    def get_code(self):
        return self._code

    def get_request_id(self):
        return self._request_id


class FakeTkeClient(object):
    """In-memory stand-in for the TkeClient EKS cluster operations."""

    def __init__(self, clusters=None):
        self.clusters = list(clusters or [])
        self.describe_offsets = []
        self.DescribeEKSClusters = MagicMock(side_effect=self._describe)
        self.CreateEKSCluster = MagicMock(side_effect=self._create)
        self.UpdateEKSCluster = MagicMock(side_effect=self._update)
        self.DeleteEKSCluster = MagicMock(side_effect=self._delete)

    def _describe(self, request):
        self.describe_offsets.append(request.Offset)
        start = request.Offset or 0
        end = start + (request.Limit or 100)
        items = [FakeResource(c) for c in self.clusters[start:end]]
        return SimpleNamespace(Clusters=items)

    def _create(self, request):
        self.clusters.append({
            "ClusterId": "eks-2222",
            "ClusterName": request.ClusterName,
            "Status": "initializing",
            "ClusterDesc": getattr(request, "ClusterDesc", None),
        })
        return SimpleNamespace(ClusterId="eks-2222")

    def _update(self, request):
        for cluster in self.clusters:
            if cluster["ClusterId"] == request.ClusterId:
                cluster["ClusterDesc"] = request.ClusterDesc
        return SimpleNamespace()

    def _delete(self, request):
        self.clusters = [c for c in self.clusters if c["ClusterId"] != request.ClusterId]
        return SimpleNamespace()


def make_cluster(cluster_id="eks-1111", name=CLUSTER_NAME, status="running", desc="prod cluster"):
    return {
        "ClusterId": cluster_id,
        "ClusterName": name,
        "Status": status,
        "ClusterDesc": desc,
    }


@pytest.fixture
def client(monkeypatch):
    fake = FakeTkeClient()
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(
        eks_cluster, "_load_tke",
        lambda: (FakeModels(), SimpleNamespace(TkeClient=object)),
    )
    monkeypatch.setattr(
        TencentCloudModule, "create_client",
        lambda self, client_class, endpoint: fake,
    )
    return fake


CREATE_ARGS = dict(
    cluster_name=CLUSTER_NAME,
    vpc_id="vpc-abcdef",
    subnet_ids=["subnet-1111", "subnet-2222"],
)


def test_absent_noop_when_cluster_missing(client):
    module_args(cluster_name=CLUSTER_NAME, state="absent")
    result = run(eks_cluster.run_module)
    assert result["changed"] is False
    client.DeleteEKSCluster.assert_not_called()


def test_absent_deletes_existing_cluster(client):
    client.clusters = [make_cluster()]
    module_args(cluster_name=CLUSTER_NAME, state="absent")
    result = run(eks_cluster.run_module)
    assert result["changed"] is True
    request = client.DeleteEKSCluster.call_args[0][0]
    assert request.ClusterId == "eks-1111"


def test_absent_check_mode_does_not_delete(client):
    client.clusters = [make_cluster()]
    module_args(cluster_name=CLUSTER_NAME, state="absent", _ansible_check_mode=True)
    result = run(eks_cluster.run_module)
    assert result["changed"] is True
    assert "diff" in result
    client.DeleteEKSCluster.assert_not_called()


def test_present_noop_when_desc_matches(client):
    client.clusters = [make_cluster(desc="prod cluster")]
    module_args(**dict(CREATE_ARGS, cluster_desc="prod cluster"))
    result = run(eks_cluster.run_module)
    assert result["changed"] is False
    assert result["cluster_id"] == "eks-1111"
    assert result["status"] == "running"
    client.CreateEKSCluster.assert_not_called()
    client.UpdateEKSCluster.assert_not_called()


def test_present_updates_desc_when_changed(client):
    client.clusters = [make_cluster(desc="old desc")]
    module_args(**dict(CREATE_ARGS, cluster_desc="new desc"))
    result = run(eks_cluster.run_module)
    assert result["changed"] is True
    request = client.UpdateEKSCluster.call_args[0][0]
    assert request.ClusterId == "eks-1111"
    assert request.ClusterDesc == "new desc"
    client.CreateEKSCluster.assert_not_called()


def test_present_update_check_mode_no_write(client):
    client.clusters = [make_cluster(desc="old desc")]
    module_args(**dict(CREATE_ARGS, cluster_desc="new desc", _ansible_check_mode=True))
    result = run(eks_cluster.run_module)
    assert result["changed"] is True
    assert "diff" in result
    client.UpdateEKSCluster.assert_not_called()


def test_present_creates_when_absent(client):
    module_args(**CREATE_ARGS)
    result = run(eks_cluster.run_module)
    assert result["changed"] is True
    assert result["cluster_id"] == "eks-2222"
    request = client.CreateEKSCluster.call_args[0][0]
    assert request.ClusterName == CLUSTER_NAME
    assert request.VpcId == "vpc-abcdef"
    assert request.SubnetIds == ["subnet-1111", "subnet-2222"]


def test_present_optional_create_fields_forwarded(client):
    module_args(**dict(CREATE_ARGS, k8s_version="1.28.5", cluster_desc="prod", enable_vpc_coredns=True,
                       service_subnet_id="subnet-svc"))
    run(eks_cluster.run_module)
    request = client.CreateEKSCluster.call_args[0][0]
    assert request.K8SVersion == "1.28.5"
    assert request.ClusterDesc == "prod"
    assert request.EnableVpcCoreDNS is True
    assert request.ServiceSubnetId == "subnet-svc"


def test_present_check_mode_does_not_create(client):
    module_args(**CREATE_ARGS, _ansible_check_mode=True)
    result = run(eks_cluster.run_module)
    assert result["changed"] is True
    assert "diff" in result
    client.CreateEKSCluster.assert_not_called()


def test_present_missing_create_params_fails(client):
    module_args(cluster_name=CLUSTER_NAME)
    with pytest.raises(AnsibleFailJson) as exc:
        run(eks_cluster.run_module)
    assert "vpc_id" in exc.value.args[0]["msg"]
    assert "subnet_ids" in exc.value.args[0]["msg"]
    client.CreateEKSCluster.assert_not_called()


def test_find_cluster_scans_beyond_first_page(client):
    first_page = [make_cluster(cluster_id="eks-{0}".format(i), name="other-{0}".format(i))
                  for i in range(100)]
    client.clusters = first_page + [make_cluster(cluster_id="eks-9999", name=CLUSTER_NAME)]
    module_args(**dict(CREATE_ARGS, cluster_desc="prod cluster"))
    result = run(eks_cluster.run_module)
    assert result["changed"] is False
    assert result["cluster_id"] == "eks-9999"
    # first page offset 0, second page offset 100 (recorded inside the fake
    # client because the module reuses a single request object)
    assert client.describe_offsets == [0, 100]


def test_sdk_error_fails(client, monkeypatch):
    def boom(self, fn, request, **kwargs):
        raise FakeSdkError("InternalError")

    monkeypatch.setattr(TencentCloudModule, "sdk_call", boom)
    module_args(**CREATE_ARGS)
    with pytest.raises(AnsibleFailJson) as exc:
        run(eks_cluster.run_module)
    assert exc.value.args[0]["failed"] is True
