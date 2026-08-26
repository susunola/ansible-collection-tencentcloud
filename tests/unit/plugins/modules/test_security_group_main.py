"""Main-path unit tests for the security_group module (run_module level)."""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from ansible_collections.tencentcloud.cloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.tencentcloud.cloud.plugins.modules import security_group
from ansible_collections.tencentcloud.cloud.tests.unit.plugins.modules.harness import (
    FakeModels,
    FakeResource,
    module_args,
    run,
)

GROUP = {
    "SecurityGroupId": "sg-existing1",
    "SecurityGroupName": "web-sg",
    "SecurityGroupDesc": "Web tier security group",
    "TagSet": [],
}


class FakeVpcClient(object):
    def __init__(self, groups=None):
        self.groups = list(groups or [])
        self.CreateSecurityGroup = MagicMock(side_effect=self._create)
        self.DeleteSecurityGroup = MagicMock(side_effect=self._delete)
        self.ModifySecurityGroupAttribute = MagicMock()

    def DescribeSecurityGroups(self, request):
        matched = self.groups
        ids = getattr(request, "SecurityGroupIds", None)
        if ids:
            matched = [g for g in matched if g["SecurityGroupId"] in ids]
        return SimpleNamespace(SecurityGroupSet=[FakeResource(g) for g in matched])

    def _create(self, request):
        group = {
            "SecurityGroupId": "sg-new000001",
            "SecurityGroupName": request.GroupName,
            "SecurityGroupDesc": request.GroupDescription,
            "TagSet": [],
        }
        self.groups.append(group)
        return SimpleNamespace(SecurityGroup=FakeResource(group))

    def _delete(self, request):
        self.groups = [g for g in self.groups if g["SecurityGroupId"] != request.SecurityGroupId]
        return SimpleNamespace()


@pytest.fixture
def client(monkeypatch):
    fake = FakeVpcClient()
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(
        security_group, "_load_vpc",
        lambda: (FakeModels(), SimpleNamespace(VpcClient=object)),
    )
    monkeypatch.setattr(
        TencentCloudModule, "create_client",
        lambda self, client_class, endpoint: fake,
    )
    return fake


def test_create_reports_changed(client):
    module_args(state="present", name="web-sg", description="Web tier security group")
    result = run(security_group.run_module)
    assert result["changed"] is True
    assert result["security_group"]["SecurityGroupName"] == "web-sg"
    client.CreateSecurityGroup.assert_called_once()
    assert "diff" not in result


def test_second_run_is_idempotent(client):
    client.groups.append(dict(GROUP))
    module_args(state="present", name="web-sg", description="Web tier security group")
    result = run(security_group.run_module)
    assert result["changed"] is False
    assert result["security_group"]["SecurityGroupId"] == "sg-existing1"
    client.CreateSecurityGroup.assert_not_called()
    client.ModifySecurityGroupAttribute.assert_not_called()


def test_absent_deletes_existing_group(client):
    client.groups.append(dict(GROUP))
    module_args(state="absent", name="web-sg")
    result = run(security_group.run_module)
    assert result["changed"] is True
    client.DeleteSecurityGroup.assert_called_once()
    assert client.groups == []


def test_absent_on_missing_group_is_unchanged(client):
    module_args(state="absent", name="web-sg")
    result = run(security_group.run_module)
    assert result["changed"] is False
    client.DeleteSecurityGroup.assert_not_called()


def test_check_mode_create_makes_no_sdk_writes(client):
    module_args(
        state="present", name="web-sg", description="Web tier security group",
        _ansible_check_mode=True,
    )
    result = run(security_group.run_module)
    assert result["changed"] is True
    assert "diff" in result
    client.CreateSecurityGroup.assert_not_called()
    client.DeleteSecurityGroup.assert_not_called()
    client.ModifySecurityGroupAttribute.assert_not_called()


def test_diff_mode_create_includes_diff(client):
    module_args(
        state="present", name="web-sg", description="Web tier security group",
        _ansible_diff=True,
    )
    result = run(security_group.run_module)
    assert result["changed"] is True
    assert result["diff"]["before"] is None
    assert result["diff"]["after"]["name"] == "web-sg"
    client.CreateSecurityGroup.assert_called_once()
