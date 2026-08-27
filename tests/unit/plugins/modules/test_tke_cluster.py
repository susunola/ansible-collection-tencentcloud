"""Unit tests for the tke_cluster write module helpers."""

from __future__ import absolute_import, division, print_function

__metaclass__ = type
from ansible_collections.susunola.tencentcloud.plugins.modules.tke_cluster import (
    build_describe_request,
    find_cluster,
    _create,
    _update,
    _set_deletion_protection,
    _delete,
)


class FakeRequest(object):
    pass


class FakeFilter(object):
    def __init__(self):
        pass


class FakeBasicSettings(object):
    def __init__(self):
        pass


class FakeCIDRSettings(object):
    def __init__(self):
        pass


class FakeAdvancedSettings(object):
    def __init__(self):
        pass


class FakeTag(object):
    def __init__(self):
        self.Key = None
        self.Value = None


class FakeTagSpecification(object):
    def __init__(self):
        pass


class FakeModels(object):
    DescribeClustersRequest = FakeRequest
    CreateClusterRequest = FakeRequest
    ModifyClusterAttributeRequest = FakeRequest
    DeleteClusterRequest = FakeRequest
    Filter = FakeFilter
    ClusterBasicSettings = FakeBasicSettings
    ClusterCIDRSettings = FakeCIDRSettings
    ClusterAdvancedSettings = FakeAdvancedSettings
    Tag = FakeTag
    TagSpecification = FakeTagSpecification


class FakeCluster(object):
    def __init__(self, cluster_id, name, status="Running", deletion_protection=False):
        self.ClusterId = cluster_id
        self.ClusterName = name
        self.ClusterStatus = status
        self.ClusterVersion = "1.28"
        self.ClusterDescription = ""
        self.ProjectId = 0
        self.DeletionProtection = deletion_protection

    def _serialize(self, allow_none=True):
        return {
            "ClusterId": self.ClusterId,
            "ClusterName": self.ClusterName,
            "ClusterStatus": self.ClusterStatus,
            "ClusterVersion": self.ClusterVersion,
            "ClusterDescription": self.ClusterDescription,
            "ProjectId": self.ProjectId,
            "DeletionProtection": self.DeletionProtection,
        }


class FakeDescribeResponse(object):
    def __init__(self, clusters):
        self.Clusters = clusters


class FakeCreateResponse(object):
    def __init__(self, cluster_id):
        self.ClusterId = cluster_id


class FakeClient(object):
    def __init__(self, describe_response=None, create_response=None, exc=None):
        self.describe_response = describe_response
        self.create_response = create_response
        self.exc = exc
        self.calls = []

    def DescribeClusters(self, request):
        self.calls.append(("DescribeClusters", request))
        if self.exc:
            raise self.exc
        return self.describe_response

    def CreateCluster(self, request):
        self.calls.append(("CreateCluster", request))
        return self.create_response

    def ModifyClusterAttribute(self, request):
        self.calls.append(("ModifyClusterAttribute", request))

    def DeleteCluster(self, request):
        self.calls.append(("DeleteCluster", request))


class FakeModule(object):
    def __init__(self):
        self.params = {"retries": 2}

    def sdk_call(self, operation, request):
        return operation(request)


def test_build_describe_request_by_id():
    request = build_describe_request(FakeModels, "cls-1", None)
    assert request.ClusterIds == ["cls-1"]
    assert not hasattr(request, "Filters") or request.Filters is None


def test_build_describe_request_by_name():
    request = build_describe_request(FakeModels, None, "prod-k8s")
    assert request.Filters[0].Name == "cluster-name"
    assert request.Filters[0].Values == ["prod-k8s"]
    assert not hasattr(request, "ClusterIds") or request.ClusterIds is None


def test_find_cluster_by_id():
    client = FakeClient(FakeDescribeResponse([FakeCluster("cls-1", "prod-k8s")]))
    module = FakeModule()
    cluster = find_cluster(module, client, FakeModels, "cls-1", None)
    assert cluster["ClusterId"] == "cls-1"
    assert len(client.calls) == 1


def test_find_cluster_by_exact_name():
    client = FakeClient(FakeDescribeResponse([
        FakeCluster("cls-1", "prod-k8s"),
        FakeCluster("cls-2", "prod-k8s-2"),
    ]))
    module = FakeModule()
    cluster = find_cluster(module, client, FakeModels, None, "prod-k8s")
    assert cluster["ClusterId"] == "cls-1"


def test_find_cluster_returns_none_when_absent():
    client = FakeClient(FakeDescribeResponse([]))
    module = FakeModule()
    assert find_cluster(module, client, FakeModels, "cls-9", None) is None


def test_create_sends_basic_and_network_settings():
    client = FakeClient(create_response=FakeCreateResponse("cls-9"))
    module = FakeModule()
    created_id = _create(module, client, FakeModels, {
        "name": "prod-k8s",
        "vpc_id": "vpc-1",
        "subnet_id": "subnet-1",
        "cluster_version": "1.28",
        "cluster_desc": "prod cluster",
        "project_id": 5,
        "cluster_type": "MANAGED_CLUSTER",
        "cluster_cidr": "10.42.0.0/16",
        "service_cidr": "10.43.0.0/16",
        "max_node_pod_num": 32,
        "deletion_protection": False,
        "tags": {"env": "prod"},
    })
    assert created_id == "cls-9"
    request = client.calls[-1][1]
    assert request.ClusterType == "MANAGED_CLUSTER"
    basic = request.ClusterBasicSettings
    assert basic.ClusterName == "prod-k8s"
    assert basic.VpcId == "vpc-1"
    assert basic.SubnetId == "subnet-1"
    assert basic.ClusterVersion == "1.28"
    assert basic.ClusterDescription == "prod cluster"
    assert basic.ProjectId == 5
    spec = basic.TagSpecification[0]
    assert spec.ResourceType == "cluster"
    assert [(t.Key, t.Value) for t in spec.Tags] == [("env", "prod")]
    cidr = request.ClusterCIDRSettings
    assert cidr.ClusterCIDR == "10.42.0.0/16"
    assert cidr.ServiceCIDR == "10.43.0.0/16"
    assert cidr.MaxNodePodNum == 32
    assert not hasattr(request, "ClusterAdvancedSettings")


def test_create_with_deletion_protection():
    client = FakeClient(create_response=FakeCreateResponse("cls-9"))
    module = FakeModule()
    _create(module, client, FakeModels, {
        "name": "prod-k8s",
        "vpc_id": "vpc-1",
        "subnet_id": None,
        "cluster_version": None,
        "cluster_desc": None,
        "project_id": None,
        "cluster_type": "MANAGED_CLUSTER",
        "cluster_cidr": None,
        "service_cidr": None,
        "max_node_pod_num": None,
        "deletion_protection": True,
        "tags": {},
    })
    request = client.calls[-1][1]
    assert request.ClusterAdvancedSettings.DeletionProtection is True
    assert not hasattr(request, "ClusterCIDRSettings")
    basic = request.ClusterBasicSettings
    assert not hasattr(basic, "SubnetId")
    assert not hasattr(basic, "TagSpecification")


def test_update_sets_changed_fields_only():
    client = FakeClient()
    module = FakeModule()
    _update(module, client, FakeModels, "cls-1", "renamed", "new desc", 9)
    request = client.calls[-1][1]
    assert request.ClusterId == "cls-1"
    assert request.ClusterName == "renamed"
    assert request.ClusterDesc == "new desc"
    assert request.ProjectId == 9


def test_update_skips_none_fields():
    client = FakeClient()
    module = FakeModule()
    _update(module, client, FakeModels, "cls-1", None, None, None)
    request = client.calls[-1][1]
    assert request.ClusterId == "cls-1"
    assert not hasattr(request, "ClusterName")
    assert not hasattr(request, "ClusterDesc")
    assert not hasattr(request, "ProjectId")


def test_set_deletion_protection():
    client = FakeClient()
    module = FakeModule()
    _set_deletion_protection(module, client, FakeModels, "cls-1", True)
    request = client.calls[-1][1]
    assert request.ClusterId == "cls-1"
    assert request.ClusterProperty.DeletionProtection is True


def test_delete_sends_cluster_id_and_mode():
    client = FakeClient()
    module = FakeModule()
    _delete(module, client, FakeModels, "cls-1", "retain")
    request = client.calls[-1][1]
    assert request.ClusterId == "cls-1"
    assert request.InstanceDeleteMode == "retain"


def test_delete_omits_mode_when_none():
    client = FakeClient()
    module = FakeModule()
    _delete(module, client, FakeModels, "cls-1", None)
    request = client.calls[-1][1]
    assert request.ClusterId == "cls-1"
    assert not hasattr(request, "InstanceDeleteMode")
