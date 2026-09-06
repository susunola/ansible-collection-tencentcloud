"""Unit tests for the dbdc_db_custom_cluster write module (helpers + run_module).

Covers the create / destroy / node-membership / tags / deletion-protection
flows of ``plugins/modules/dbdc_db_custom_cluster.py`` with an in-memory
fake DB Custom client, following the collection's module test harness
(see harness.py).
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import time
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import dbdc_db_custom_cluster as dbdc
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

CLUSTER = {
    "ClusterId": "dbcc-123",
    "ClusterName": "prod-dbcc",
    "ClusterDescription": "production db custom",
    "ClusterStatus": "Running",
    "DeletionProtection": True,
    "Tags": [{"Key": "env", "Value": "prod"}],
    "ContainerNetwork": {"VpcId": "vpc-0a1", "SubnetIds": ["subnet-1", "subnet-2"]},
    "ApiServerNetwork": {"VpcId": "vpc-0a1", "SubnetId": "subnet-1"},
    "Nodes": [],
}

NODE = {"NodeId": "dbcn-111"}

WRITE_OPS = (
    "CreateDBCustomCluster",
    "DestroyDBCustomCluster",
    "AddNodesToDBCustomCluster",
    "RemoveNodesFromDBCustomCluster",
    "ModifyDBCustomClusterAttributes",
    "ModifyDBCustomClusterTags",
)


class FakeDbdcClient(object):
    """In-memory DB Custom client that mutates a small cluster store."""

    def __init__(self, clusters=None, page_size=None, task_status="Succeeded"):
        self.clusters = [dict(cluster) for cluster in (clusters or [])]
        self.page_size = page_size
        self.task_status = task_status
        self.calls = []

    def _record(self, name, request):
        self.calls.append((name, request))
        return request

    def _by_id(self, cluster_id):
        return next(cluster for cluster in self.clusters if cluster["ClusterId"] == cluster_id)

    def DescribeDBCustomClusters(self, request):
        self._record("DescribeDBCustomClusters", request)
        return SimpleNamespace(ClusterSet=[FakeResource(cluster) for cluster in self.clusters])

    def DescribeDBCustomClusterDetail(self, request):
        self._record("DescribeDBCustomClusterDetail", request)
        return FakeResource(dict(self._by_id(request.ClusterId)))

    def DescribeDBCustomClusterNodes(self, request):
        self._record("DescribeDBCustomClusterNodes", request)
        nodes = self._by_id(request.ClusterId).get("Nodes") or []
        if self.page_size:
            items = nodes[request.Offset:request.Offset + self.page_size]
        else:
            items = nodes
        return SimpleNamespace(NodeSet=[FakeResource(node) for node in items], TotalCount=len(nodes))

    def DescribeDBCustomTaskStatus(self, request):
        self._record("DescribeDBCustomTaskStatus", request)
        return SimpleNamespace(Status=self.task_status, TaskId=request.TaskId)

    def CreateDBCustomCluster(self, request):
        self._record("CreateDBCustomCluster", request)
        cluster = {
            "ClusterId": "dbcc-new0001",
            "ClusterName": request.ClusterName,
            "ClusterDescription": getattr(request, "ClusterDescription", None),
            "ClusterStatus": "Running",
            "DeletionProtection": getattr(request, "DeletionProtection", True),
            "Tags": [{"Key": tag.Key, "Value": tag.Value} for tag in (getattr(request, "Tags", None) or [])],
            "ContainerNetwork": {
                "VpcId": request.ContainerNetwork.VpcId,
                "SubnetIds": list(request.ContainerNetwork.SubnetIds or []),
            },
            "ApiServerNetwork": {
                "VpcId": request.ApiServerNetwork.VpcId,
                "SubnetId": request.ApiServerNetwork.SubnetId,
            },
            "Nodes": [],
        }
        self.clusters.append(cluster)
        return SimpleNamespace(ClusterId="dbcc-new0001", TaskId="task-create")

    def DestroyDBCustomCluster(self, request):
        self._record("DestroyDBCustomCluster", request)
        self.clusters = [cluster for cluster in self.clusters if cluster["ClusterId"] != request.ClusterId]
        return SimpleNamespace(TaskId="task-destroy")

    def ModifyDBCustomClusterAttributes(self, request):
        self._record("ModifyDBCustomClusterAttributes", request)
        self._by_id(request.ClusterId)["DeletionProtection"] = request.DeletionProtection
        return SimpleNamespace(TaskId="task-attrs")

    def ModifyDBCustomClusterTags(self, request):
        self._record("ModifyDBCustomClusterTags", request)
        cluster = self._by_id(request.ClusterId)
        tags = [dict(tag) for tag in cluster.get("Tags") or []]
        for key in request.DeleteTagKeys:
            tags = [tag for tag in tags if tag["Key"] != key]
        for tag in request.AddTags or []:
            tags = [existing for existing in tags if existing["Key"] != tag.Key]
            tags.append({"Key": tag.Key, "Value": tag.Value})
        cluster["Tags"] = tags
        return SimpleNamespace(TaskId="task-tags")

    def AddNodesToDBCustomCluster(self, request):
        self._record("AddNodesToDBCustomCluster", request)
        cluster = self._by_id(request.ClusterId)
        existing = {node["NodeId"] for node in cluster.get("Nodes") or []}
        for node_id in request.NodeIds:
            if node_id not in existing:
                cluster.setdefault("Nodes", []).append({"NodeId": node_id})
        return SimpleNamespace(TaskId="task-add")

    def RemoveNodesFromDBCustomCluster(self, request):
        self._record("RemoveNodesFromDBCustomCluster", request)
        cluster = self._by_id(request.ClusterId)
        doomed = set(request.NodeIds)
        cluster["Nodes"] = [node for node in cluster.get("Nodes") or [] if node["NodeId"] not in doomed]
        return SimpleNamespace(TaskId="task-remove")


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
    fake = FakeDbdcClient()
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(
        dbdc, "_load",
        lambda: (FakeModels(), SimpleNamespace(DbdcClient=object)),
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


def test_tags_sorts_and_maps_values():
    tags = dbdc._tags(FakeModels(), {"z": "1", "a": "2"})
    assert [(tag.Key, tag.Value) for tag in tags] == [("a", "2"), ("z", "1")]


def test_tags_empty_when_none():
    assert dbdc._tags(FakeModels(), None) == []


def test_login_none_without_credentials():
    assert dbdc._login(FakeModels(), {"login_password": None, "login_key_id": None, "keep_image_login": None}) is None


def test_login_maps_password():
    item = dbdc._login(FakeModels(), {"login_password": "pw", "login_key_id": None, "keep_image_login": None})
    assert item.Password == "pw"
    assert item.KeyIds is None
    assert item.KeepImageLogin is None


def test_login_maps_key_and_keep_image():
    item = dbdc._login(FakeModels(), {"login_password": None, "login_key_id": "skey-1", "keep_image_login": True})
    assert item.KeyIds == ["skey-1"]
    assert item.KeepImageLogin == "true"


def test_labels_sorts_and_maps_values():
    labels = dbdc._labels(FakeModels(), {"zone": "a", "app": "web"})
    assert [(label.Key, label.Value) for label in labels] == [("app", "web"), ("zone", "a")]


def test_taints_maps_key_value_effect():
    taints = dbdc._taints(FakeModels(), [{"key": "dedicated", "value": "db", "effect": "NoSchedule"}])
    assert taints[0].Key == "dedicated"
    assert taints[0].Value == "db"
    assert taints[0].Effect == "NoSchedule"


def test_taints_empty_when_none():
    assert dbdc._taints(FakeModels(), None) == []


def test_describe_request_filters_by_cluster_id():
    request = dbdc.describe_request(FakeModels(), {"cluster_id": "dbcc-123", "name": None})
    assert request.ClusterIds == ["dbcc-123"]
    assert request.Limit == 100
    assert not hasattr(request, "Filters")


def test_describe_request_filters_by_name():
    request = dbdc.describe_request(FakeModels(), {"cluster_id": None, "name": "prod-dbcc"})
    assert request.ClusterIds is None
    assert request.Filters[0].Name == "cluster-name"
    assert request.Filters[0].Values == ["prod-dbcc"]


def test_detail_nodes_and_task_requests():
    models = FakeModels()
    assert dbdc.detail_request(models, "dbcc-1").ClusterId == "dbcc-1"
    nodes = dbdc.nodes_request(models, "dbcc-1", offset=20)
    assert nodes.ClusterId == "dbcc-1"
    assert nodes.Offset == 20
    assert nodes.Limit == 100
    assert dbdc.task_request(models, "task-1").TaskId == "task-1"


def test_create_request_builds_networks_and_defaults():
    request = dbdc.create_request(FakeModels(), {
        "name": "new-dbcc", "description": "d", "container_vpc_id": "vpc-1",
        "container_subnet_ids": ["subnet-1"], "api_server_vpc_id": "vpc-1",
        "api_server_subnet_id": "subnet-1", "tags": {"env": "prod"},
        "client_token": "tok-1", "deletion_protection": None,
    })
    assert request.ClusterName == "new-dbcc"
    assert request.ContainerNetwork.VpcId == "vpc-1"
    assert request.ContainerNetwork.SubnetIds == ["subnet-1"]
    assert request.ApiServerNetwork.SubnetId == "subnet-1"
    assert request.DeletionProtection is True
    assert request.ClientToken == "tok-1"
    assert [(tag.Key, tag.Value) for tag in request.Tags] == [("env", "prod")]


def test_attributes_and_tags_requests():
    models = FakeModels()
    attrs = dbdc.attributes_request(models, "dbcc-1", False)
    assert attrs.ClusterId == "dbcc-1"
    assert attrs.DeletionProtection is False
    tags = dbdc.tags_request(models, "dbcc-1", {"a": "1"}, {"b", "a"})
    assert tags.DeleteTagKeys == ["a", "b"]
    assert [(tag.Key, tag.Value) for tag in tags.AddTags] == [("a", "1")]


def test_add_nodes_request_sorts_and_builds_login():
    request = dbdc.add_nodes_request(FakeModels(), {
        "node_image_id": "img-1", "login_key_id": "skey-1", "login_password": None,
        "keep_image_login": None, "labels": {"app": "web"}, "taints": [],
        "host_name": "node-", "host_name_type": 2,
    }, "dbcc-1", {"dbcn-2", "dbcn-1"})
    assert request.NodeIds == ["dbcn-1", "dbcn-2"]
    assert request.ImageId == "img-1"
    assert request.LoginSettings.KeyIds == ["skey-1"]
    assert request.HostNameType == 2


def test_remove_nodes_request_sets_force():
    request = dbdc.remove_nodes_request(FakeModels(), {
        "force_node_removal": True, "login_password": None, "login_key_id": None,
        "keep_image_login": None,
    }, "dbcc-1", {"dbcn-1"})
    assert request.ClusterId == "dbcc-1"
    assert request.NodeIds == ["dbcn-1"]
    assert request.Force is True
    assert request.LoginSettings is None


def test_destroy_request_sets_cluster_id():
    assert dbdc.destroy_request(FakeModels(), "dbcc-1").ClusterId == "dbcc-1"


def test_tag_dict_maps_list_of_tags():
    assert dbdc._tag_dict([{"Key": "a", "Value": "1"}, {"Key": "b", "Value": "2"}]) == {"a": "1", "b": "2"}
    assert dbdc._tag_dict(None) == {}


def test_node_set_pages_through_nodes():
    module = FakeModule()
    cluster = dict(CLUSTER, Nodes=[{"NodeId": "dbcn-1"}, {"NodeId": "dbcn-2"}, {"NodeId": "dbcn-3"}])
    client = FakeDbdcClient(clusters=[cluster], page_size=1)
    nodes = dbdc._node_set(module, client, FakeModels(), "dbcc-123")
    assert [node["NodeId"] for node in nodes] == ["dbcn-1", "dbcn-2", "dbcn-3"]
    assert client.calls.count(("DescribeDBCustomClusterNodes", None)) == 0
    assert sum(name == "DescribeDBCustomClusterNodes" for name, request in client.calls) == 3


def test_find_by_id_merges_detail_and_nodes():
    module = FakeModule()
    cluster = dict(CLUSTER, Nodes=[dict(NODE)])
    client = FakeDbdcClient(clusters=[cluster])
    found = dbdc.find(module, client, FakeModels(), {"cluster_id": "dbcc-123", "name": None})
    assert found["ClusterName"] == "prod-dbcc"
    assert found["Nodes"] == [{"NodeId": "dbcn-111"}]
    assert "RequestId" not in found
    names = [name for name, request in client.calls]
    assert "DescribeDBCustomClusterDetail" in names
    assert "DescribeDBCustomClusterNodes" in names


def test_find_by_name_matches():
    module = FakeModule()
    client = FakeDbdcClient(clusters=[dict(CLUSTER)])
    found = dbdc.find(module, client, FakeModels(), {"cluster_id": None, "name": "prod-dbcc"})
    assert found["ClusterId"] == "dbcc-123"


def test_find_no_match_returns_none():
    module = FakeModule()
    client = FakeDbdcClient(clusters=[dict(CLUSTER)])
    assert dbdc.find(module, client, FakeModels(), {"cluster_id": None, "name": "nope"}) is None


def test_find_multiple_matches_fails():
    module = FakeModule()
    client = FakeDbdcClient(clusters=[dict(CLUSTER), dict(CLUSTER, ClusterId="dbcc-2")])
    with pytest.raises(AnsibleFailJson) as exc:
        dbdc.find(module, client, FakeModels(), {"cluster_id": None, "name": "prod-dbcc"})
    assert "Multiple DB Custom clusters" in exc.value.args[0]["msg"]


def test_wait_task_returns_on_success():
    module = FakeModule(waiter_timeout=30, waiter_delay=0)
    client = FakeDbdcClient()
    response = dbdc._wait_task(module, client, FakeModels(), "task-1")
    assert response.Status == "Succeeded"


def test_wait_task_fails_on_failure():
    module = FakeModule(waiter_timeout=30, waiter_delay=1)
    client = FakeDbdcClient(task_status="Failed")
    with pytest.raises(AnsibleFailJson) as exc:
        dbdc._wait_task(module, client, FakeModels(), "task-1")
    assert "Asynchronous task failed" in exc.value.args[0]["msg"]


# ---------------------------------------------------------------------------
# run_module main-path tests
# ---------------------------------------------------------------------------


def test_absent_missing_cluster_is_unchanged(client):
    module_args(state="absent", name="nope")
    result = run(dbdc.run_module)
    assert result["changed"] is False
    assert result["cluster"] is None


def test_absent_protection_enabled_fails(client):
    client.clusters = [dict(CLUSTER)]
    module_args(state="absent", cluster_id="dbcc-123")
    with pytest.raises(AnsibleFailJson) as exc:
        run(dbdc.run_module)
    assert "deletion protection is enabled" in exc.value.args[0]["msg"]


def test_absent_with_nodes_requires_removal_flag(client):
    client.clusters = [dict(CLUSTER, DeletionProtection=False, Nodes=[dict(NODE)])]
    module_args(state="absent", cluster_id="dbcc-123", deletion_protection=False)
    with pytest.raises(AnsibleFailJson) as exc:
        run(dbdc.run_module)
    assert "must have no nodes" in exc.value.args[0]["msg"]


def test_absent_node_detach_requires_login(client):
    client.clusters = [dict(CLUSTER, DeletionProtection=False, Nodes=[dict(NODE)])]
    module_args(state="absent", cluster_id="dbcc-123", deletion_protection=False, remove_nodes_on_delete=True)
    with pytest.raises(AnsibleFailJson) as exc:
        run(dbdc.run_module)
    assert "node login settings are required" in exc.value.args[0]["msg"]


def test_absent_destroys_cluster_with_nodes(client):
    client.clusters = [dict(CLUSTER, Nodes=[dict(NODE)])]
    module_args(
        state="absent", cluster_id="dbcc-123", deletion_protection=False,
        remove_nodes_on_delete=True, login_key_id="skey-1",
        waiter_timeout=30, waiter_delay=0,
    )
    result = run(dbdc.run_module)
    assert result["changed"] is True
    names = [name for name, request in client.calls]
    assert "RemoveNodesFromDBCustomCluster" in names
    assert "ModifyDBCustomClusterAttributes" in names
    assert "DestroyDBCustomCluster" in names
    assert client.clusters == []


def test_absent_destroys_cluster_without_nodes_or_protection(client):
    client.clusters = [dict(CLUSTER, DeletionProtection=False)]
    module_args(state="absent", cluster_id="dbcc-123", waiter_timeout=30, waiter_delay=0)
    result = run(dbdc.run_module)
    assert result["changed"] is True
    names = [name for name, request in client.calls]
    assert "RemoveNodesFromDBCustomCluster" not in names
    assert "ModifyDBCustomClusterAttributes" not in names
    assert "DestroyDBCustomCluster" in names
    assert client.clusters == []


def test_check_mode_absent_makes_no_writes(client):
    client.clusters = [dict(CLUSTER, Nodes=[dict(NODE)])]
    module_args(
        state="absent", cluster_id="dbcc-123", deletion_protection=False,
        remove_nodes_on_delete=True, login_key_id="skey-1", _ansible_check_mode=True,
    )
    result = run(dbdc.run_module)
    assert result["changed"] is True
    assert not any(name in WRITE_OPS for name, request in client.calls)


def test_create_requires_creation_parameters(client):
    module_args(state="present", name="new-dbcc")
    with pytest.raises(AnsibleFailJson) as exc:
        run(dbdc.run_module)
    payload = exc.value.args[0]
    assert "required" in payload["msg"]
    assert "container_vpc_id" in payload["missing"]
    assert "api_server_subnet_id" in payload["missing"]


def test_create_reports_changed(client):
    module_args(
        state="present", name="new-dbcc", container_vpc_id="vpc-1",
        container_subnet_ids=["subnet-1", "subnet-2"], api_server_vpc_id="vpc-1",
        api_server_subnet_id="subnet-1", tags={"env": "staging"},
        waiter_timeout=30, waiter_delay=0,
    )
    result = run(dbdc.run_module)
    assert result["changed"] is True
    assert result["cluster"]["ClusterId"] == "dbcc-new0001"
    assert any(name == "CreateDBCustomCluster" for name, request in client.calls)
    assert client.clusters[0]["DeletionProtection"] is True
    assert client.clusters[0]["Tags"] == [{"Key": "env", "Value": "staging"}]


def test_check_mode_create_makes_no_writes(client):
    module_args(
        state="present", name="new-dbcc", container_vpc_id="vpc-1",
        container_subnet_ids=["subnet-1"], api_server_vpc_id="vpc-1",
        api_server_subnet_id="subnet-1", _ansible_check_mode=True,
    )
    result = run(dbdc.run_module)
    assert result["changed"] is True
    assert result["cluster"]["ClusterName"] == "new-dbcc"
    assert not any(name in WRITE_OPS for name, request in client.calls)


def test_present_idempotent_is_unchanged(client):
    client.clusters = [dict(CLUSTER)]
    module_args(state="present", cluster_id="dbcc-123")
    result = run(dbdc.run_module)
    assert result["changed"] is False
    assert not any(name in WRITE_OPS for name, request in client.calls)


def test_immutable_identity_drift_fails(client):
    client.clusters = [dict(CLUSTER)]
    module_args(state="present", cluster_id="dbcc-123", name="other-name")
    with pytest.raises(AnsibleFailJson) as exc:
        run(dbdc.run_module)
    payload = exc.value.args[0]
    assert "immutable" in payload["msg"]
    assert "ClusterName" in payload["immutable_drift"]


def test_network_drift_fails(client):
    client.clusters = [dict(CLUSTER)]
    module_args(state="present", cluster_id="dbcc-123", container_vpc_id="vpc-other")
    with pytest.raises(AnsibleFailJson) as exc:
        run(dbdc.run_module)
    assert "ContainerVpcId" in exc.value.args[0]["immutable_drift"]


def test_add_nodes_requires_image_and_login(client):
    client.clusters = [dict(CLUSTER)]
    module_args(state="present", cluster_id="dbcc-123", node_ids=["dbcn-222"], node_image_id="img-1")
    with pytest.raises(AnsibleFailJson) as exc:
        run(dbdc.run_module)
    assert "required to attach nodes" in exc.value.args[0]["msg"]


def test_add_nodes_reports_changed(client):
    client.clusters = [dict(CLUSTER)]
    module_args(
        state="present", cluster_id="dbcc-123", node_ids=["dbcn-222"],
        node_image_id="img-1", login_key_id="skey-1",
        waiter_timeout=30, waiter_delay=0,
    )
    result = run(dbdc.run_module)
    assert result["changed"] is True
    assert any(name == "AddNodesToDBCustomCluster" for name, request in client.calls)
    assert client.clusters[0]["Nodes"] == [{"NodeId": "dbcn-222"}]


def test_remove_nodes_requires_allowance(client):
    client.clusters = [dict(CLUSTER, Nodes=[dict(NODE)])]
    module_args(state="present", cluster_id="dbcc-123", node_ids=[])
    with pytest.raises(AnsibleFailJson) as exc:
        run(dbdc.run_module)
    assert "allow_node_removal=true" in exc.value.args[0]["msg"]


def test_remove_nodes_reports_changed(client):
    client.clusters = [dict(CLUSTER, Nodes=[dict(NODE)])]
    module_args(
        state="present", cluster_id="dbcc-123", node_ids=[], allow_node_removal=True,
        waiter_timeout=30, waiter_delay=0,
    )
    result = run(dbdc.run_module)
    assert result["changed"] is True
    assert any(name == "RemoveNodesFromDBCustomCluster" for name, request in client.calls)
    assert client.clusters[0]["Nodes"] == []


def test_update_tags_reports_changed(client):
    client.clusters = [dict(CLUSTER)]
    module_args(state="present", cluster_id="dbcc-123", tags={"env": "staging", "team": "infra"})
    result = run(dbdc.run_module)
    assert result["changed"] is True
    assert any(name == "ModifyDBCustomClusterTags" for name, request in client.calls)
    assert sorted(client.clusters[0]["Tags"], key=lambda tag: tag["Key"]) == [
        {"Key": "env", "Value": "staging"},
        {"Key": "team", "Value": "infra"},
    ]


def test_update_deletion_protection_reports_changed(client):
    client.clusters = [dict(CLUSTER)]
    module_args(state="present", cluster_id="dbcc-123", deletion_protection=False)
    result = run(dbdc.run_module)
    assert result["changed"] is True
    assert any(name == "ModifyDBCustomClusterAttributes" for name, request in client.calls)
    assert client.clusters[0]["DeletionProtection"] is False


def test_check_mode_update_makes_no_writes(client):
    client.clusters = [dict(CLUSTER)]
    module_args(
        state="present", cluster_id="dbcc-123", deletion_protection=False,
        tags={"env": "staging"}, node_ids=["dbcn-222"], node_image_id="img-1",
        login_key_id="skey-1", _ansible_check_mode=True,
    )
    result = run(dbdc.run_module)
    assert result["changed"] is True
    assert not any(name in WRITE_OPS for name, request in client.calls)
