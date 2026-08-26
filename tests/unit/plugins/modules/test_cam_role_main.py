"""Main-path unit tests for the cam_role module (run_module level)."""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import json
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from ansible_collections.tencentcloud.cloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.tencentcloud.cloud.plugins.modules import cam_role
from ansible_collections.tencentcloud.cloud.tests.unit.plugins.modules.harness import (
    FakeModels,
    FakeResource,
    module_args,
    run,
)

TRUST_POLICY = {
    "version": "2.0",
    "statement": [
        {"action": "name/sts:AssumeRole", "effect": "allow", "principal": {"service": ["cvm.qcloud.com"]}}
    ],
}

ROLE = {
    "RoleId": "4611686018427904001",
    "RoleName": "app-instance-role",
    "Description": "Role for application CVM instances",
    "PolicyDocument": json.dumps(TRUST_POLICY),
    "AddTime": "2026-08-26 12:00:00",
    "Tags": [],
}


class FakeCamClient(object):
    def __init__(self, roles=None):
        self.roles = list(roles or [])
        self.CreateRole = MagicMock(side_effect=self._create_role)
        self.DeleteRole = MagicMock(side_effect=self._delete_role)
        self.UpdateRoleDescription = MagicMock(side_effect=self._update_description)
        self.UpdateAssumeRolePolicy = MagicMock(side_effect=self._update_policy)
        self.TagRole = MagicMock(side_effect=self._tag_role)
        self.UntagRole = MagicMock(side_effect=self._untag_role)

    def DescribeRoleList(self, request):
        return SimpleNamespace(
            List=[FakeResource(r) for r in self.roles], TotalNum=len(self.roles)
        )

    def _create_role(self, request):
        role = {
            "RoleId": "4611686018427904999",
            "RoleName": request.RoleName,
            "Description": request.Description,
            "PolicyDocument": request.PolicyDocument,
            "AddTime": "2026-08-26 12:00:01",
            "Tags": [{"Key": t.Key, "Value": t.Value} for t in (getattr(request, "Tags", None) or [])],
        }
        self.roles.append(role)
        return SimpleNamespace(RoleId=role["RoleId"])

    def _delete_role(self, request):
        self.roles = [r for r in self.roles if r["RoleId"] != request.RoleId]
        return SimpleNamespace()

    def _update_description(self, request):
        for role in self.roles:
            if role["RoleId"] == request.RoleId:
                role["Description"] = request.Description
        return SimpleNamespace()

    def _update_policy(self, request):
        for role in self.roles:
            if role["RoleId"] == request.RoleId:
                role["PolicyDocument"] = request.PolicyDocument
        return SimpleNamespace()

    def _tag_role(self, request):
        for role in self.roles:
            if role["RoleId"] == request.RoleId:
                tags = {t["Key"]: t["Value"] for t in role["Tags"]}
                tags.update({t.Key: t.Value for t in request.Tags})
                role["Tags"] = [{"Key": k, "Value": v} for k, v in sorted(tags.items())]
        return SimpleNamespace()

    def _untag_role(self, request):
        for role in self.roles:
            if role["RoleId"] == request.RoleId:
                role["Tags"] = [t for t in role["Tags"] if t["Key"] not in request.TagKeys]
        return SimpleNamespace()


@pytest.fixture
def client(monkeypatch):
    fake = FakeCamClient()
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(
        cam_role, "_load_cam",
        lambda: (FakeModels(), SimpleNamespace(CamClient=object)),
    )
    monkeypatch.setattr(
        TencentCloudModule, "create_client",
        lambda self, client_class, endpoint: fake,
    )
    return fake


def test_create_reports_changed(client):
    module_args(state="present", role_name="app-instance-role",
                description="Role for application CVM instances",
                assume_policy_document=TRUST_POLICY)
    result = run(cam_role.run_module)
    assert result["changed"] is True
    assert result["role"]["RoleName"] == "app-instance-role"
    client.CreateRole.assert_called_once()
    request = client.CreateRole.call_args[0][0]
    assert json.loads(request.PolicyDocument) == TRUST_POLICY
    assert "diff" not in result


def test_create_requires_trust_policy(client):
    module_args(state="present", role_name="app-instance-role")
    try:
        run(cam_role.run_module)
        raise AssertionError("expected fail_json")
    except SystemExit as exc:
        assert "assume_policy_document" in str(exc.args[0]["msg"])
    client.CreateRole.assert_not_called()


def test_second_run_is_idempotent(client):
    client.roles.append(dict(ROLE))
    module_args(state="present", role_name="app-instance-role",
                description="Role for application CVM instances",
                assume_policy_document=json.dumps(TRUST_POLICY))
    result = run(cam_role.run_module)
    assert result["changed"] is False
    client.CreateRole.assert_not_called()
    client.UpdateRoleDescription.assert_not_called()
    client.UpdateAssumeRolePolicy.assert_not_called()


def test_update_description(client):
    client.roles.append(dict(ROLE))
    module_args(state="present", role_name="app-instance-role", description="new description")
    result = run(cam_role.run_module)
    assert result["changed"] is True
    client.UpdateRoleDescription.assert_called_once()
    client.UpdateAssumeRolePolicy.assert_not_called()


def test_update_trust_policy_semantic_compare(client):
    client.roles.append(dict(ROLE))
    changed_policy = dict(TRUST_POLICY, version="3.0")
    module_args(state="present", role_name="app-instance-role",
                assume_policy_document=changed_policy)
    result = run(cam_role.run_module)
    assert result["changed"] is True
    client.UpdateAssumeRolePolicy.assert_called_once()


def test_tag_reconciliation_via_native_cam_apis(client):
    role = dict(ROLE, Tags=[{"Key": "old", "Value": "gone"}, {"Key": "env", "Value": "dev"}])
    client.roles.append(role)
    module_args(state="present", role_name="app-instance-role", tags={"env": "prod"})
    result = run(cam_role.run_module)
    assert result["changed"] is True
    client.TagRole.assert_called_once()
    client.UntagRole.assert_called_once()
    assert client.UntagRole.call_args[0][0].TagKeys == ["old"]


def test_absent_deletes_existing_role(client):
    client.roles.append(dict(ROLE))
    module_args(state="absent", role_name="app-instance-role")
    result = run(cam_role.run_module)
    assert result["changed"] is True
    client.DeleteRole.assert_called_once()
    assert client.roles == []


def test_absent_on_missing_role_is_unchanged(client):
    module_args(state="absent", role_name="app-instance-role")
    result = run(cam_role.run_module)
    assert result["changed"] is False
    client.DeleteRole.assert_not_called()


def test_lookup_by_role_id(client):
    client.roles.append(dict(ROLE))
    module_args(state="absent", role_id="4611686018427904001")
    result = run(cam_role.run_module)
    assert result["changed"] is True
    client.DeleteRole.assert_called_once()


def test_missing_identifiers_fail(client):
    module_args(state="present")
    try:
        run(cam_role.run_module)
        raise AssertionError("expected fail_json")
    except SystemExit as exc:
        assert "role_id or role_name" in str(exc.args[0]["msg"])


def test_check_mode_create_makes_no_sdk_writes(client):
    module_args(state="present", role_name="app-instance-role",
                assume_policy_document=TRUST_POLICY, _ansible_check_mode=True)
    result = run(cam_role.run_module)
    assert result["changed"] is True
    assert "diff" in result
    client.CreateRole.assert_not_called()
    client.DeleteRole.assert_not_called()


def test_diff_mode_create_includes_diff(client):
    module_args(state="present", role_name="app-instance-role",
                assume_policy_document=TRUST_POLICY, _ansible_diff=True)
    result = run(cam_role.run_module)
    assert result["changed"] is True
    assert result["diff"]["before"] is None
    assert result["diff"]["after"]["role_name"] == "app-instance-role"
    client.CreateRole.assert_called_once()
