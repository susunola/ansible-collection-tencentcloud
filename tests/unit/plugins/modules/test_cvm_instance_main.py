"""Main-path unit tests for the cvm_instance module (run_module level)."""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import cvm_instance
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    FakeModels,
    FakeResource,
    module_args,
    run,
)

INSTANCE = {
    "InstanceId": "ins-existing1",
    "InstanceName": "web-01",
    "InstanceState": "RUNNING",
    "ImageId": "img-existing1",
    "InstanceType": "S5.MEDIUM2",
    "InstanceChargeType": "POSTPAID_BY_HOUR",
    "SecurityGroupIds": [],
    "Tags": [],
    "VirtualPrivateCloud": {},
}

CREATE_ARGS = dict(
    state="present",
    instance_name="web-01",
    image_id="img-existing1",
    instance_type="S5.MEDIUM2",
)


class FakeCvmClient(object):
    def __init__(self, instances=None):
        self.instances = list(instances or [])
        self.RunInstances = MagicMock(side_effect=self._run)
        self.TerminateInstances = MagicMock(side_effect=self._terminate)
        self.StartInstances = MagicMock()
        self.StopInstances = MagicMock()
        self.ModifyInstancesAttribute = MagicMock()

    def DescribeInstances(self, request):
        matched = self.instances
        ids = getattr(request, "InstanceIds", None)
        filters = getattr(request, "Filters", None)
        if ids:
            matched = [i for i in matched if i["InstanceId"] in ids]
        elif filters:
            name_filter = filters[0]
            if name_filter.Name == "instance-name":
                matched = [i for i in matched if i.get("InstanceName") in name_filter.Values]
        return SimpleNamespace(InstanceSet=[FakeResource(i) for i in matched])

    def _run(self, request):
        instance = {
            "InstanceId": "ins-new000001",
            "InstanceName": getattr(request, "InstanceName", ""),
            "InstanceState": "RUNNING",
            "ImageId": request.ImageId,
            "InstanceType": request.InstanceType,
            "InstanceChargeType": request.InstanceChargeType,
            "SecurityGroupIds": [],
            "Tags": [],
            "VirtualPrivateCloud": {},
        }
        self.instances.append(instance)
        return SimpleNamespace(InstanceIdSet=[instance["InstanceId"]])

    def _terminate(self, request):
        self.instances = [i for i in self.instances if i["InstanceId"] not in request.InstanceIds]
        return SimpleNamespace()


@pytest.fixture
def client(monkeypatch):
    fake = FakeCvmClient()
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(
        cvm_instance, "_load_cvm",
        lambda: (FakeModels(), SimpleNamespace(CvmClient=object)),
    )
    monkeypatch.setattr(
        TencentCloudModule, "create_client",
        lambda self, client_class, endpoint: fake,
    )
    return fake


def test_create_reports_changed(client):
    module_args(**CREATE_ARGS)
    result = run(cvm_instance.run_module)
    assert result["changed"] is True
    assert result["instance"]["InstanceId"] == "ins-new000001"
    assert result["instance"]["InstanceState"] == "RUNNING"
    client.RunInstances.assert_called_once()
    assert "diff" not in result


def test_second_run_is_idempotent(client):
    client.instances.append(dict(INSTANCE))
    module_args(state="present", instance_name="web-01")
    result = run(cvm_instance.run_module)
    assert result["changed"] is False
    assert result["instance"]["InstanceId"] == "ins-existing1"
    client.RunInstances.assert_not_called()
    client.ModifyInstancesAttribute.assert_not_called()


def test_absent_terminates_existing_instance(client):
    client.instances.append(dict(INSTANCE))
    module_args(state="absent", instance_name="web-01")
    result = run(cvm_instance.run_module)
    assert result["changed"] is True
    client.TerminateInstances.assert_called_once()
    assert client.instances == []


def test_absent_on_missing_instance_is_unchanged(client):
    module_args(state="absent", instance_name="web-01")
    result = run(cvm_instance.run_module)
    assert result["changed"] is False
    client.TerminateInstances.assert_not_called()


def test_check_mode_create_makes_no_sdk_writes(client):
    module_args(_ansible_check_mode=True, **CREATE_ARGS)
    result = run(cvm_instance.run_module)
    assert result["changed"] is True
    assert "diff" in result
    client.RunInstances.assert_not_called()
    client.TerminateInstances.assert_not_called()
    client.StartInstances.assert_not_called()
    client.StopInstances.assert_not_called()
    client.ModifyInstancesAttribute.assert_not_called()


def test_diff_mode_create_includes_diff(client):
    module_args(_ansible_diff=True, **CREATE_ARGS)
    result = run(cvm_instance.run_module)
    assert result["changed"] is True
    assert result["diff"]["before"] is None
    assert result["diff"]["after"]["InstanceName"] == "web-01"
    client.RunInstances.assert_called_once()
