"""Main-path unit tests for the elasticsearch_instance module (run_module level)."""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import elasticsearch_instance
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

INSTANCE = {
    "InstanceId": "es-xxxxxxxx",
    "InstanceName": "logs-es",
    "Status": 1,
    "EsVersion": "7.10.1",
    "EsDomain": "es-xxxxxxxx.ap-guangzhou.es.tencentcloudcs.com",
}


class FakeEsClient(object):
    def __init__(self, instance=None):
        self.instance = dict(instance) if instance else None
        self.CreateInstance = MagicMock(side_effect=self._create)
        self.UpdateInstance = MagicMock(side_effect=self._rename)
        self.DeleteInstance = MagicMock(side_effect=self._destroy)

    def DescribeInstances(self, request):
        items = []
        if self.instance:
            if getattr(request, "InstanceIds", None):
                if self.instance["InstanceId"] in request.InstanceIds:
                    items = [self.instance]
            elif getattr(request, "InstanceNames", None):
                if self.instance["InstanceName"] in request.InstanceNames:
                    items = [self.instance]
            else:
                items = [self.instance]
        return SimpleNamespace(InstanceList=[FakeResource(s) for s in items])

    def _create(self, request):
        self.instance = {
            "InstanceId": "es-new",
            "InstanceName": request.InstanceName,
            "Status": 0,
            "EsVersion": request.EsVersion,
        }
        return SimpleNamespace()

    def _rename(self, request):
        self.instance["InstanceName"] = request.InstanceName
        return SimpleNamespace()

    def _destroy(self, request):
        self.instance = None
        return SimpleNamespace()


@pytest.fixture
def client(monkeypatch):
    fake = FakeEsClient()
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(
        elasticsearch_instance, "_load_es",
        lambda: (FakeModels(), SimpleNamespace(EsClient=object)),
    )
    monkeypatch.setattr(
        TencentCloudModule, "create_client",
        lambda self, client_class, endpoint: fake,
    )
    return fake


def _create_args():
    return dict(name="logs-es", zone="ap-guangzhou-3", es_version="7.10.1",
                vpc_id="vpc-xxxxxxxx", subnet_id="subnet-xxxxxxxx",
                password="secret-pass-1", node_type="ES.S1.MEDIUM8",
                node_num=3, disk_type="CLOUD_SSD", disk_size=200)


def test_creates_cluster(client, monkeypatch):
    # Creation is asynchronous: the create call leaves Status 0 and the
    # waiter polls DescribeInstances until the cluster reaches Status 1.
    original_describe = FakeEsClient.DescribeInstances

    def describe_with_transition(self, request):
        response = original_describe(self, request)
        if self.instance:
            self.instance["Status"] = 1
        return response

    monkeypatch.setattr(FakeEsClient, "DescribeInstances", describe_with_transition)
    module_args(**_create_args())
    result = run(elasticsearch_instance.run_module)
    assert result["changed"] is True
    assert result["msg"] == "Elasticsearch cluster created"
    client.CreateInstance.assert_called_once()
    request = client.CreateInstance.call_args[0][0]
    assert request.Zone == "ap-guangzhou-3"
    assert request.EsVersion == "7.10.1"
    assert request.VpcId == "vpc-xxxxxxxx"
    assert request.Password == "secret-pass-1"
    node_info = request.NodeInfoList[0]
    assert node_info.Type == "hotData"
    assert node_info.NodeNum == 3
    assert node_info.NodeType == "ES.S1.MEDIUM8"
    assert node_info.DiskType == "CLOUD_SSD"
    assert node_info.DiskSize == 200
    assert result["instance"]["InstanceId"] == "es-new"


def test_second_run_is_idempotent(client):
    client.instance = dict(INSTANCE)
    module_args(**_create_args())
    result = run(elasticsearch_instance.run_module)
    assert result["changed"] is False
    assert result["msg"] == "Elasticsearch cluster is up to date"
    client.CreateInstance.assert_not_called()
    client.UpdateInstance.assert_not_called()


def test_rename_triggers_update(client):
    client.instance = dict(INSTANCE)
    # Renaming is driven by the stable identity (instance_id) plus the
    # desired name; the cluster cannot be looked up by its future name.
    module_args(instance_id="es-xxxxxxxx", name="logs-es-v2")
    result = run(elasticsearch_instance.run_module)
    assert result["changed"] is True
    assert result["msg"] == "Elasticsearch cluster renamed"
    request = client.UpdateInstance.call_args[0][0]
    assert request.InstanceId == "es-xxxxxxxx"
    assert request.InstanceName == "logs-es-v2"
    assert result["instance"]["InstanceName"] == "logs-es-v2"


def test_absent_destroys(client):
    client.instance = dict(INSTANCE)
    module_args(name="logs-es", state="absent")
    result = run(elasticsearch_instance.run_module)
    assert result["changed"] is True
    assert result["msg"] == "Elasticsearch cluster destroyed"
    assert result["instance"] is None
    request = client.DeleteInstance.call_args[0][0]
    assert request.InstanceId == "es-xxxxxxxx"


def test_absent_already_absent(client):
    module_args(name="logs-es", state="absent")
    result = run(elasticsearch_instance.run_module)
    assert result["changed"] is False
    assert result["msg"] == "Elasticsearch cluster already absent"
    client.DeleteInstance.assert_not_called()


def test_check_mode_create_does_not_write(client):
    module_args(_ansible_check_mode=True, **_create_args())
    result = run(elasticsearch_instance.run_module)
    assert result["changed"] is True
    assert result["msg"] == "Would create Elasticsearch cluster"
    client.CreateInstance.assert_not_called()


def test_check_mode_rename_does_not_write(client):
    client.instance = dict(INSTANCE)
    module_args(_ansible_check_mode=True, instance_id="es-xxxxxxxx", name="logs-es-v2")
    result = run(elasticsearch_instance.run_module)
    assert result["changed"] is True
    assert result["msg"] == "Would rename Elasticsearch cluster"
    client.UpdateInstance.assert_not_called()


def test_fails_without_identifier(client):
    module_args()
    with pytest.raises(AnsibleFailJson) as exc:
        run(elasticsearch_instance.run_module)
    assert "required" in exc.value.args[0]["msg"]


def test_fails_creating_without_required(client):
    module_args(name="logs-es")
    with pytest.raises(AnsibleFailJson) as exc:
        run(elasticsearch_instance.run_module)
    assert "zone" in exc.value.args[0]["msg"]
    assert "es_version" in exc.value.args[0]["msg"]
    assert "node_num" in exc.value.args[0]["msg"]
