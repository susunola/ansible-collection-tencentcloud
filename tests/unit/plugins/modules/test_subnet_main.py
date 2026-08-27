"""Main-path unit tests for the subnet module (run_module level)."""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import subnet
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    FakeModels,
    FakeResource,
    module_args,
    run,
)

SUBNET = {
    "SubnetId": "subnet-existing1",
    "SubnetName": "web-subnet",
    "VpcId": "vpc-existing1",
    "CidrBlock": "10.0.1.0/24",
    "Zone": "ap-guangzhou-1",
    "EnableBroadcast": False,
    "TagSet": [],
}

CREATE_ARGS = dict(
    state="present",
    name="web-subnet",
    vpc_id="vpc-existing1",
    cidr_block="10.0.1.0/24",
    zone="ap-guangzhou-1",
)


class FakeVpcClient(object):
    def __init__(self, subnets=None):
        self.subnets = list(subnets or [])
        self.CreateSubnet = MagicMock(side_effect=self._create)
        self.DeleteSubnet = MagicMock(side_effect=self._delete)
        self.ModifySubnetAttribute = MagicMock()

    def DescribeSubnets(self, request):
        matched = self.subnets
        ids = getattr(request, "SubnetIds", None)
        if ids:
            matched = [s for s in matched if s["SubnetId"] in ids]
        return SimpleNamespace(SubnetSet=[FakeResource(s) for s in matched])

    def _create(self, request):
        new_subnet = {
            "SubnetId": "subnet-new0001",
            "SubnetName": request.SubnetName,
            "VpcId": request.VpcId,
            "CidrBlock": request.CidrBlock,
            "Zone": request.Zone,
            "EnableBroadcast": False,
            "TagSet": [],
        }
        self.subnets.append(new_subnet)
        return SimpleNamespace(Subnet=FakeResource(new_subnet))

    def _delete(self, request):
        self.subnets = [s for s in self.subnets if s["SubnetId"] != request.SubnetId]
        return SimpleNamespace()


@pytest.fixture
def client(monkeypatch):
    fake = FakeVpcClient()
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(
        subnet, "_load_vpc",
        lambda: (FakeModels(), SimpleNamespace(VpcClient=object)),
    )
    monkeypatch.setattr(
        TencentCloudModule, "create_client",
        lambda self, client_class, endpoint: fake,
    )
    return fake


def test_create_reports_changed(client):
    module_args(**CREATE_ARGS)
    result = run(subnet.run_module)
    assert result["changed"] is True
    assert result["subnet"]["SubnetName"] == "web-subnet"
    assert result["subnet"]["Zone"] == "ap-guangzhou-1"
    client.CreateSubnet.assert_called_once()
    assert "diff" not in result


def test_second_run_is_idempotent(client):
    client.subnets.append(dict(SUBNET))
    module_args(**CREATE_ARGS)
    result = run(subnet.run_module)
    assert result["changed"] is False
    assert result["subnet"]["SubnetId"] == "subnet-existing1"
    client.CreateSubnet.assert_not_called()
    client.ModifySubnetAttribute.assert_not_called()


def test_absent_deletes_existing_subnet(client):
    client.subnets.append(dict(SUBNET))
    module_args(state="absent", name="web-subnet")
    result = run(subnet.run_module)
    assert result["changed"] is True
    client.DeleteSubnet.assert_called_once()
    assert client.subnets == []


def test_absent_on_missing_subnet_is_unchanged(client):
    module_args(state="absent", name="web-subnet")
    result = run(subnet.run_module)
    assert result["changed"] is False
    client.DeleteSubnet.assert_not_called()


def test_check_mode_create_makes_no_sdk_writes(client):
    module_args(_ansible_check_mode=True, **CREATE_ARGS)
    result = run(subnet.run_module)
    assert result["changed"] is True
    assert "diff" in result
    client.CreateSubnet.assert_not_called()
    client.DeleteSubnet.assert_not_called()
    client.ModifySubnetAttribute.assert_not_called()


def test_diff_mode_create_includes_diff(client):
    module_args(_ansible_diff=True, **CREATE_ARGS)
    result = run(subnet.run_module)
    assert result["changed"] is True
    assert result["diff"]["before"] is None
    assert result["diff"]["after"]["cidr_block"] == "10.0.1.0/24"
    client.CreateSubnet.assert_called_once()
