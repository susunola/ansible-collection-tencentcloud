"""Main-path unit tests for the vpc module (run_module level)."""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from ansible_collections.tencentcloud.cloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.tencentcloud.cloud.plugins.modules import vpc
from ansible_collections.tencentcloud.cloud.tests.unit.plugins.modules.harness import (
    FakeModels,
    FakeResource,
    module_args,
    run,
)

VPC = {
    "VpcId": "vpc-existing1",
    "VpcName": "prod-vpc",
    "CidrBlock": "10.0.0.0/16",
    "DnsServerSet": [],
    "DomainName": "",
    "TagSet": [],
}


class FakeVpcClient(object):
    def __init__(self, vpcs=None):
        self.vpcs = list(vpcs or [])
        self.CreateVpc = MagicMock(side_effect=self._create)
        self.DeleteVpc = MagicMock(side_effect=self._delete)
        self.ModifyVpcAttribute = MagicMock()

    def DescribeVpcs(self, request):
        matched = self.vpcs
        ids = getattr(request, "VpcIds", None)
        if ids:
            matched = [v for v in matched if v["VpcId"] in ids]
        return SimpleNamespace(VpcSet=[FakeResource(v) for v in matched])

    def _create(self, request):
        new_vpc = {
            "VpcId": "vpc-new000001",
            "VpcName": request.VpcName,
            "CidrBlock": request.CidrBlock,
            "DnsServerSet": [],
            "DomainName": "",
            "TagSet": [],
        }
        self.vpcs.append(new_vpc)
        return SimpleNamespace(Vpc=FakeResource(new_vpc))

    def _delete(self, request):
        self.vpcs = [v for v in self.vpcs if v["VpcId"] != request.VpcId]
        return SimpleNamespace()


@pytest.fixture
def client(monkeypatch):
    fake = FakeVpcClient()
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(
        vpc, "_load_vpc",
        lambda: (FakeModels(), SimpleNamespace(VpcClient=object)),
    )
    monkeypatch.setattr(
        TencentCloudModule, "create_client",
        lambda self, client_class, endpoint: fake,
    )
    return fake


def test_create_reports_changed(client):
    module_args(state="present", name="prod-vpc", cidr_block="10.0.0.0/16")
    result = run(vpc.run_module)
    assert result["changed"] is True
    assert result["vpc"]["VpcName"] == "prod-vpc"
    assert result["vpc"]["CidrBlock"] == "10.0.0.0/16"
    client.CreateVpc.assert_called_once()
    assert "diff" not in result


def test_second_run_is_idempotent(client):
    client.vpcs.append(dict(VPC))
    module_args(state="present", name="prod-vpc", cidr_block="10.0.0.0/16")
    result = run(vpc.run_module)
    assert result["changed"] is False
    assert result["vpc"]["VpcId"] == "vpc-existing1"
    client.CreateVpc.assert_not_called()
    client.ModifyVpcAttribute.assert_not_called()


def test_absent_deletes_existing_vpc(client):
    client.vpcs.append(dict(VPC))
    module_args(state="absent", name="prod-vpc")
    result = run(vpc.run_module)
    assert result["changed"] is True
    client.DeleteVpc.assert_called_once()
    assert client.vpcs == []


def test_absent_on_missing_vpc_is_unchanged(client):
    module_args(state="absent", name="prod-vpc")
    result = run(vpc.run_module)
    assert result["changed"] is False
    client.DeleteVpc.assert_not_called()


def test_check_mode_create_makes_no_sdk_writes(client):
    module_args(
        state="present", name="prod-vpc", cidr_block="10.0.0.0/16",
        _ansible_check_mode=True,
    )
    result = run(vpc.run_module)
    assert result["changed"] is True
    assert "diff" in result
    client.CreateVpc.assert_not_called()
    client.DeleteVpc.assert_not_called()
    client.ModifyVpcAttribute.assert_not_called()


def test_diff_mode_create_includes_diff(client):
    module_args(
        state="present", name="prod-vpc", cidr_block="10.0.0.0/16",
        _ansible_diff=True,
    )
    result = run(vpc.run_module)
    assert result["changed"] is True
    assert result["diff"]["before"] is None
    assert result["diff"]["after"]["cidr_block"] == "10.0.0.0/16"
    client.CreateVpc.assert_called_once()
