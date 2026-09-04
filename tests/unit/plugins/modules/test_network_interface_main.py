"""Main-path unit tests for the network_interface module (run_module level)."""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import network_interface
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

ENI = {
    "NetworkInterfaceId": "eni-xxxxxxxx",
    "NetworkInterfaceName": "web-eni",
    "VpcId": "vpc-xxxxxxxx",
    "SubnetId": "subnet-xxxxxxxx",
    "NetworkInterfaceDescription": "Web tier interface",
    "GroupSet": ["sg-xxxxxxxx"],
    "PrivateIpAddressSet": [{"PrivateIpAddress": "10.0.0.10"}],
}


class FakeVpcClient(object):
    def __init__(self, eni=None):
        self.eni = dict(eni) if eni else None
        self.CreateNetworkInterface = MagicMock(side_effect=self._create)
        self.ModifyNetworkInterfaceAttribute = MagicMock(side_effect=self._modify)
        self.DeleteNetworkInterface = MagicMock(side_effect=self._delete)

    def DescribeNetworkInterfaces(self, request):
        items = []
        if self.eni:
            if getattr(request, "NetworkInterfaceIds", None):
                if self.eni["NetworkInterfaceId"] in request.NetworkInterfaceIds:
                    items = [self.eni]
            else:
                items = [self.eni]
        return SimpleNamespace(NetworkInterfaceSet=[FakeResource(s) for s in items])

    def _create(self, request):
        self.eni = {
            "NetworkInterfaceId": "eni-new",
            "NetworkInterfaceName": request.NetworkInterfaceName,
            "VpcId": request.VpcId,
            "SubnetId": request.SubnetId,
            "NetworkInterfaceDescription": getattr(request, "NetworkInterfaceDescription", None),
            "GroupSet": list(getattr(request, "SecurityGroupIds", []) or []),
        }
        return SimpleNamespace(NetworkInterface=SimpleNamespace(
            NetworkInterfaceId="eni-new"))

    def _modify(self, request):
        if getattr(request, "NetworkInterfaceName", None):
            self.eni["NetworkInterfaceName"] = request.NetworkInterfaceName
        if getattr(request, "NetworkInterfaceDescription", None) is not None:
            self.eni["NetworkInterfaceDescription"] = request.NetworkInterfaceDescription
        if getattr(request, "SecurityGroupIds", None) is not None:
            self.eni["GroupSet"] = list(request.SecurityGroupIds)
        return SimpleNamespace()

    def _delete(self, request):
        self.eni = None
        return SimpleNamespace()


@pytest.fixture
def client(monkeypatch):
    fake = FakeVpcClient()
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(
        network_interface, "_load_vpc",
        lambda: (FakeModels(), SimpleNamespace(VpcClient=object)),
    )
    monkeypatch.setattr(
        TencentCloudModule, "create_client",
        lambda self, client_class, endpoint: fake,
    )
    return fake


def test_creates_interface(client):
    module_args(name="web-eni", vpc_id="vpc-xxxxxxxx", subnet_id="subnet-xxxxxxxx",
                description="Web tier interface", security_group_ids=["sg-xxxxxxxx"])
    result = run(network_interface.run_module)
    assert result["changed"] is True
    assert result["msg"] == "Network interface created"
    client.CreateNetworkInterface.assert_called_once()
    request = client.CreateNetworkInterface.call_args[0][0]
    assert request.VpcId == "vpc-xxxxxxxx"
    assert request.SubnetId == "subnet-xxxxxxxx"
    assert request.NetworkInterfaceName == "web-eni"
    assert request.SecurityGroupIds == ["sg-xxxxxxxx"]
    assert result["network_interface"]["NetworkInterfaceId"] == "eni-new"


def test_second_run_is_idempotent(client):
    client.eni = dict(ENI)
    module_args(name="web-eni", subnet_id="subnet-xxxxxxxx",
                security_group_ids=["sg-xxxxxxxx"])
    result = run(network_interface.run_module)
    assert result["changed"] is False
    assert result["msg"] == "Network interface is up to date"
    client.CreateNetworkInterface.assert_not_called()
    client.ModifyNetworkInterfaceAttribute.assert_not_called()


def test_security_group_drift_triggers_update(client):
    client.eni = dict(ENI)
    module_args(name="web-eni", subnet_id="subnet-xxxxxxxx",
                security_group_ids=["sg-yyyyyyyy"])
    result = run(network_interface.run_module)
    assert result["changed"] is True
    assert result["msg"] == "Network interface updated"
    request = client.ModifyNetworkInterfaceAttribute.call_args[0][0]
    assert request.NetworkInterfaceId == "eni-xxxxxxxx"
    assert request.SecurityGroupIds == ["sg-yyyyyyyy"]
    assert result["network_interface"]["GroupSet"] == ["sg-yyyyyyyy"]


def test_rename_triggers_update(client):
    client.eni = dict(ENI)
    # Renaming is driven by a stable identity (network_interface_id) plus the
    # desired name; the interface cannot be looked up by its future name.
    module_args(network_interface_id="eni-xxxxxxxx", name="web-eni-v2")
    result = run(network_interface.run_module)
    assert result["changed"] is True
    request = client.ModifyNetworkInterfaceAttribute.call_args[0][0]
    assert request.NetworkInterfaceId == "eni-xxxxxxxx"
    assert request.NetworkInterfaceName == "web-eni-v2"


def test_absent_deletes(client):
    client.eni = dict(ENI)
    module_args(name="web-eni", subnet_id="subnet-xxxxxxxx", state="absent")
    result = run(network_interface.run_module)
    assert result["changed"] is True
    assert result["msg"] == "Network interface deleted"
    assert result["network_interface"] is None
    request = client.DeleteNetworkInterface.call_args[0][0]
    assert request.NetworkInterfaceId == "eni-xxxxxxxx"


def test_absent_by_id(client):
    client.eni = dict(ENI)
    module_args(network_interface_id="eni-xxxxxxxx", state="absent")
    result = run(network_interface.run_module)
    assert result["changed"] is True
    client.DeleteNetworkInterface.assert_called_once()


def test_absent_already_absent(client):
    module_args(name="web-eni", subnet_id="subnet-xxxxxxxx", state="absent")
    result = run(network_interface.run_module)
    assert result["changed"] is False
    assert result["msg"] == "Network interface already absent"
    client.DeleteNetworkInterface.assert_not_called()


def test_check_mode_create_does_not_write(client):
    module_args(_ansible_check_mode=True, name="web-eni",
                vpc_id="vpc-xxxxxxxx", subnet_id="subnet-xxxxxxxx")
    result = run(network_interface.run_module)
    assert result["changed"] is True
    assert result["msg"] == "Would create network interface"
    client.CreateNetworkInterface.assert_not_called()


def test_check_mode_update_does_not_write(client):
    client.eni = dict(ENI)
    module_args(_ansible_check_mode=True, name="web-eni", subnet_id="subnet-xxxxxxxx",
                security_group_ids=["sg-yyyyyyyy"])
    result = run(network_interface.run_module)
    assert result["changed"] is True
    assert result["msg"] == "Would update network interface"
    client.ModifyNetworkInterfaceAttribute.assert_not_called()


def test_fails_without_identifier(client):
    module_args()
    with pytest.raises(AnsibleFailJson) as exc:
        run(network_interface.run_module)
    assert "required" in exc.value.args[0]["msg"]


def test_fails_creating_without_vpc_and_subnet(client):
    module_args(name="web-eni")
    with pytest.raises(AnsibleFailJson) as exc:
        run(network_interface.run_module)
    assert "vpc_id" in exc.value.args[0]["msg"]
    assert "subnet_id" in exc.value.args[0]["msg"]
