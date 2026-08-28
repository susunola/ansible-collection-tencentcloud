"""Main-path unit tests for the tke_node_pool module (run_module level)."""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import tke_node_pool
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

POOL = {
    "NodePoolId": "np-xxxxxxxx",
    "Name": "workers",
    "LifeState": "normal",
    "EnableAutoscale": True,
    "MaxNodesNum": 10,
    "MinNodesNum": 2,
    "Labels": [{"Name": "app", "Value": "workers"}],
    "Taints": [{"Key": "dedicated", "Value": "true", "Effect": "NoSchedule"}],
    "DeletionProtection": False,
}


class FakeTkeClient(object):
    def __init__(self, pool=None):
        self.pool = dict(pool) if pool else None
        self.CreateClusterNodePool = MagicMock(side_effect=self._create)
        self.ModifyClusterNodePool = MagicMock(side_effect=self._modify)
        self.DeleteClusterNodePool = MagicMock(side_effect=self._delete)

    def DescribeClusterNodePools(self, request):
        items = []
        if self.pool:
            items = [self.pool]
        return SimpleNamespace(NodePoolSet=[FakeResource(s) for s in items],
                               TotalCount=len(items))

    def _create(self, request):
        self.pool = {
            "NodePoolId": "np-new",
            "Name": request.Name,
            "LifeState": "creating",
            "EnableAutoscale": getattr(request, "EnableAutoscale", None),
            "MaxNodesNum": None,
            "MinNodesNum": None,
            "Labels": [],
            "Taints": [],
            "DeletionProtection": getattr(request, "DeletionProtection", None),
        }
        return SimpleNamespace()

    def _modify(self, request):
        if getattr(request, "Name", None):
            self.pool["Name"] = request.Name
        if getattr(request, "EnableAutoscale", None) is not None:
            self.pool["EnableAutoscale"] = request.EnableAutoscale
        if getattr(request, "MaxNodesNum", None) is not None:
            self.pool["MaxNodesNum"] = request.MaxNodesNum
        if getattr(request, "MinNodesNum", None) is not None:
            self.pool["MinNodesNum"] = request.MinNodesNum
        if getattr(request, "Labels", None):
            self.pool["Labels"] = [
                {"Name": label.Name, "Value": label.Value}
                for label in request.Labels
            ]
        if getattr(request, "DeletionProtection", None) is not None:
            self.pool["DeletionProtection"] = request.DeletionProtection
        return SimpleNamespace()

    def _delete(self, request):
        self.pool = None
        return SimpleNamespace()


@pytest.fixture
def client(monkeypatch):
    fake = FakeTkeClient()
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(
        tke_node_pool, "_load_tke",
        lambda: (FakeModels(), SimpleNamespace(TkeClient=object)),
    )
    monkeypatch.setattr(
        TencentCloudModule, "create_client",
        lambda self, client_class, endpoint: fake,
    )
    return fake


LAUNCH_JSON = '{"InstanceTypes":["S5.LARGE8"]}'


def test_creates_node_pool(client):
    module_args(cluster_id="cls-xxxxxxxx", name="workers",
                launch_configuration_json=LAUNCH_JSON,
                enable_autoscale=True)
    result = run(tke_node_pool.run_module)
    assert result["changed"] is True
    assert result["msg"] == "TKE node pool created"
    client.CreateClusterNodePool.assert_called_once()
    request = client.CreateClusterNodePool.call_args[0][0]
    assert request.ClusterId == "cls-xxxxxxxx"
    assert request.Name == "workers"
    assert request.LaunchConfigurePara == LAUNCH_JSON
    assert request.EnableAutoscale is True


def test_creates_with_labels_taints_tags(client):
    module_args(cluster_id="cls-xxxxxxxx", name="workers",
                launch_configuration_json=LAUNCH_JSON,
                labels={"app": "workers"},
                taints=[{"key": "dedicated", "value": "true", "effect": "NoSchedule"}],
                tags={"env": "prod"})
    run(tke_node_pool.run_module)
    request = client.CreateClusterNodePool.call_args[0][0]
    assert request.Labels[0].Name == "app"
    assert request.Labels[0].Value == "workers"
    assert request.Taints[0].Key == "dedicated"
    assert request.Taints[0].Effect == "NoSchedule"
    assert request.Tags[0].Key == "env"
    assert request.Tags[0].Value == "prod"


def test_second_run_is_idempotent(client):
    client.pool = dict(POOL)
    module_args(cluster_id="cls-xxxxxxxx", name="workers",
                launch_configuration_json=LAUNCH_JSON,
                enable_autoscale=True, max_nodes_num=10, min_nodes_num=2,
                labels={"app": "workers"},
                taints=[{"key": "dedicated", "value": "true", "effect": "NoSchedule"}])
    result = run(tke_node_pool.run_module)
    assert result["changed"] is False
    assert result["msg"] == "TKE node pool is up to date"
    client.CreateClusterNodePool.assert_not_called()
    client.ModifyClusterNodePool.assert_not_called()


def test_scale_drift_triggers_update(client):
    client.pool = dict(POOL)
    module_args(cluster_id="cls-xxxxxxxx", name="workers",
                launch_configuration_json=LAUNCH_JSON,
                max_nodes_num=20)
    result = run(tke_node_pool.run_module)
    assert result["changed"] is True
    assert result["msg"] == "TKE node pool updated"
    request = client.ModifyClusterNodePool.call_args[0][0]
    assert request.NodePoolId == "np-xxxxxxxx"
    assert request.MaxNodesNum == 20
    assert result["node_pool"]["MaxNodesNum"] == 20


def test_deletion_protection_drift_triggers_update(client):
    client.pool = dict(POOL)
    module_args(cluster_id="cls-xxxxxxxx", name="workers",
                launch_configuration_json=LAUNCH_JSON,
                deletion_protection=True)
    run(tke_node_pool.run_module)
    request = client.ModifyClusterNodePool.call_args[0][0]
    assert request.DeletionProtection is True


def test_absent_deletes(client):
    client.pool = dict(POOL)
    module_args(cluster_id="cls-xxxxxxxx", name="workers", state="absent")
    result = run(tke_node_pool.run_module)
    assert result["changed"] is True
    assert result["msg"] == "TKE node pool deleted"
    assert result["node_pool"] is None
    request = client.DeleteClusterNodePool.call_args[0][0]
    assert request.ClusterId == "cls-xxxxxxxx"
    assert request.NodePoolIds == ["np-xxxxxxxx"]
    assert not hasattr(request, "KeepInstance") or request.KeepInstance is None


def test_absent_keep_instance_sets_flag(client):
    client.pool = dict(POOL)
    module_args(cluster_id="cls-xxxxxxxx", name="workers", state="absent",
                keep_instance=True)
    run(tke_node_pool.run_module)
    request = client.DeleteClusterNodePool.call_args[0][0]
    assert request.KeepInstance is True


def test_absent_already_absent(client):
    module_args(cluster_id="cls-xxxxxxxx", name="workers", state="absent")
    result = run(tke_node_pool.run_module)
    assert result["changed"] is False
    assert result["msg"] == "TKE node pool already absent"
    client.DeleteClusterNodePool.assert_not_called()


def test_check_mode_create_does_not_write(client):
    module_args(_ansible_check_mode=True, cluster_id="cls-xxxxxxxx", name="workers",
                launch_configuration_json=LAUNCH_JSON)
    result = run(tke_node_pool.run_module)
    assert result["changed"] is True
    assert result["msg"] == "Would create TKE node pool"
    client.CreateClusterNodePool.assert_not_called()


def test_fails_without_name(client):
    module_args(cluster_id="cls-xxxxxxxx")
    with pytest.raises(AnsibleFailJson) as exc:
        run(tke_node_pool.run_module)
    assert "name" in exc.value.args[0]["msg"]


def test_fails_creating_without_launch_config(client):
    module_args(cluster_id="cls-xxxxxxxx", name="workers")
    with pytest.raises(AnsibleFailJson) as exc:
        run(tke_node_pool.run_module)
    assert "launch_configuration_json" in exc.value.args[0]["msg"]
