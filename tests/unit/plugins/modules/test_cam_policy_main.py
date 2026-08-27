"""Main-path unit tests for the cam_policy module (run_module level)."""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import json
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import cam_policy
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    FakeModels,
    FakeResource,
    module_args,
    run,
)

POLICY_DOCUMENT = {
    "version": "2.0",
    "statement": [
        {"action": ["name/cos:GetObject"], "effect": "allow", "resource": ["*"]}
    ],
}

POLICY = {
    "PolicyId": 1000001,
    "PolicyName": "app-read-only",
    "Type": 1,
    "Description": "Read-only access",
    "PolicyDocument": json.dumps(POLICY_DOCUMENT),
    "AddTime": "2026-08-26 12:00:00",
    "Tags": [],
}

CAM_MARKER = type("CamClientMarker", (object,), {})
TAG_MARKER = type("TagClientMarker", (object,), {})


class FakeCamClient(object):
    def __init__(self, policies=None):
        self.policies = list(policies or [])
        self.CreatePolicy = MagicMock(side_effect=self._create_policy)
        self.UpdatePolicy = MagicMock(side_effect=self._update_policy)
        self.DeletePolicy = MagicMock(side_effect=self._delete_policy)

    def ListPolicies(self, request):
        matched = self.policies
        if getattr(request, "Keyword", None):
            matched = [p for p in matched if request.Keyword in p["PolicyName"]]
        return SimpleNamespace(
            List=[FakeResource(p) for p in matched], TotalNum=len(matched)
        )

    def GetPolicy(self, request):
        for policy in self.policies:
            if policy["PolicyId"] == request.PolicyId:
                data = dict(policy)
                return FakeResource(data)
        raise _not_found()

    def _create_policy(self, request):
        policy = {
            "PolicyId": 1000002,
            "PolicyName": request.PolicyName,
            "Type": 1,
            "Description": request.Description,
            "PolicyDocument": request.PolicyDocument,
            "AddTime": "2026-08-26 12:00:01",
            "Tags": [{"Key": t.Key, "Value": t.Value} for t in (getattr(request, "Tags", None) or [])],
        }
        self.policies.append(policy)
        return SimpleNamespace(PolicyId=policy["PolicyId"])

    def _update_policy(self, request):
        for policy in self.policies:
            if policy["PolicyId"] == request.PolicyId:
                for field in ("PolicyName", "Description", "PolicyDocument"):
                    value = getattr(request, field, None)
                    if value is not None:
                        policy[field] = value
        return SimpleNamespace(PolicyId=request.PolicyId)

    def _delete_policy(self, request):
        self.policies = [p for p in self.policies if p["PolicyId"] not in request.PolicyId]
        return SimpleNamespace()


def _not_found():
    class NotFound(Exception):
        def get_code(self):
            return "ResourceNotFound.PolicyIdNotExist"

        def get_request_id(self):
            return "req-1"

    return NotFound("policy not found")


class FakeTagClient(object):
    def __init__(self):
        self.AttachResourcesTag = MagicMock()
        self.DetachResourcesTag = MagicMock()


@pytest.fixture
def clients(monkeypatch):
    fake_cam = FakeCamClient()
    fake_tag = FakeTagClient()
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(
        cam_policy, "_load_cam",
        lambda: (FakeModels(), SimpleNamespace(CamClient=CAM_MARKER)),
    )
    monkeypatch.setattr(
        cam_policy, "_load_tag",
        lambda: (FakeModels(), SimpleNamespace(TagClient=TAG_MARKER)),
    )
    monkeypatch.setattr(
        TencentCloudModule, "create_client",
        lambda self, client_class, endpoint: fake_cam if client_class is CAM_MARKER else fake_tag,
    )
    return fake_cam, fake_tag


def test_create_reports_changed(clients):
    fake_cam, fake_tag = clients
    module_args(state="present", policy_name="app-read-only", description="Read-only access",
                policy_document=POLICY_DOCUMENT)
    result = run(cam_policy.run_module)
    assert result["changed"] is True
    assert result["policy"]["PolicyName"] == "app-read-only"
    fake_cam.CreatePolicy.assert_called_once()
    request = fake_cam.CreatePolicy.call_args[0][0]
    assert json.loads(request.PolicyDocument) == POLICY_DOCUMENT
    assert "diff" not in result


def test_create_requires_policy_document(clients):
    fake_cam, fake_tag = clients
    module_args(state="present", policy_name="app-read-only")
    try:
        run(cam_policy.run_module)
        raise AssertionError("expected fail_json")
    except SystemExit as exc:
        assert "policy_document" in str(exc.args[0]["msg"])
    fake_cam.CreatePolicy.assert_not_called()


def test_create_rejects_preset_type(clients):
    fake_cam, fake_tag = clients
    module_args(state="present", policy_name="app-read-only", type="preset",
                policy_document=POLICY_DOCUMENT)
    try:
        run(cam_policy.run_module)
        raise AssertionError("expected fail_json")
    except SystemExit as exc:
        assert "custom" in str(exc.args[0]["msg"])
    fake_cam.CreatePolicy.assert_not_called()


def test_second_run_is_idempotent(clients):
    fake_cam, fake_tag = clients
    fake_cam.policies.append(dict(POLICY))
    module_args(state="present", policy_name="app-read-only", description="Read-only access",
                policy_document=json.dumps(POLICY_DOCUMENT))
    result = run(cam_policy.run_module)
    assert result["changed"] is False
    fake_cam.CreatePolicy.assert_not_called()
    fake_cam.UpdatePolicy.assert_not_called()


def test_update_description_and_document(clients):
    fake_cam, fake_tag = clients
    fake_cam.policies.append(dict(POLICY))
    changed_document = dict(POLICY_DOCUMENT, version="3.0")
    module_args(state="present", policy_name="app-read-only", description="new description",
                policy_document=changed_document)
    result = run(cam_policy.run_module)
    assert result["changed"] is True
    fake_cam.UpdatePolicy.assert_called_once()
    request = fake_cam.UpdatePolicy.call_args[0][0]
    assert request.PolicyId == 1000001
    assert request.Description == "new description"
    assert json.loads(request.PolicyDocument) == changed_document


def test_tag_drift_goes_through_tag_service(clients):
    fake_cam, fake_tag = clients
    policy = dict(POLICY, Tags=[{"Key": "old", "Value": "gone"}, {"Key": "env", "Value": "dev"}])
    fake_cam.policies.append(policy)
    module_args(state="present", policy_name="app-read-only", tags={"env": "prod"})
    result = run(cam_policy.run_module)
    assert result["changed"] is True
    fake_tag.AttachResourcesTag.assert_called_once()
    fake_tag.DetachResourcesTag.assert_called_once()
    request = fake_tag.AttachResourcesTag.call_args[0][0]
    assert request.ServiceType == "cam"
    assert request.ResourcePrefix == "policy"
    assert request.ResourceIds == ["1000001"]


def test_absent_deletes_existing_policy(clients):
    fake_cam, fake_tag = clients
    fake_cam.policies.append(dict(POLICY))
    module_args(state="absent", policy_name="app-read-only")
    result = run(cam_policy.run_module)
    assert result["changed"] is True
    fake_cam.DeletePolicy.assert_called_once()
    request = fake_cam.DeletePolicy.call_args[0][0]
    assert request.PolicyId == [1000001]
    assert fake_cam.policies == []


def test_absent_on_missing_policy_is_unchanged(clients):
    fake_cam, fake_tag = clients
    module_args(state="absent", policy_name="app-read-only")
    result = run(cam_policy.run_module)
    assert result["changed"] is False
    fake_cam.DeletePolicy.assert_not_called()


def test_lookup_by_policy_id_uses_get_policy(clients):
    fake_cam, fake_tag = clients
    fake_cam.policies.append(dict(POLICY))
    module_args(state="absent", policy_id=1000001)
    result = run(cam_policy.run_module)
    assert result["changed"] is True
    fake_cam.DeletePolicy.assert_called_once()


def test_absent_by_unknown_policy_id_is_unchanged(clients):
    fake_cam, fake_tag = clients
    module_args(state="absent", policy_id=9999999)
    result = run(cam_policy.run_module)
    assert result["changed"] is False
    fake_cam.DeletePolicy.assert_not_called()


def test_preset_policy_cannot_be_deleted(clients):
    fake_cam, fake_tag = clients
    fake_cam.policies.append(dict(POLICY, Type=2))
    module_args(state="absent", policy_name="app-read-only", type="preset")
    try:
        run(cam_policy.run_module)
        raise AssertionError("expected fail_json")
    except SystemExit as exc:
        assert "preset" in str(exc.args[0]["msg"])
    fake_cam.DeletePolicy.assert_not_called()


def test_check_mode_create_makes_no_sdk_writes(clients):
    fake_cam, fake_tag = clients
    module_args(state="present", policy_name="app-read-only",
                policy_document=POLICY_DOCUMENT, _ansible_check_mode=True)
    result = run(cam_policy.run_module)
    assert result["changed"] is True
    assert "diff" in result
    fake_cam.CreatePolicy.assert_not_called()
    fake_cam.DeletePolicy.assert_not_called()


def test_diff_mode_create_includes_diff(clients):
    fake_cam, fake_tag = clients
    module_args(state="present", policy_name="app-read-only",
                policy_document=POLICY_DOCUMENT, _ansible_diff=True)
    result = run(cam_policy.run_module)
    assert result["changed"] is True
    assert result["diff"]["before"] is None
    assert result["diff"]["after"]["policy_name"] == "app-read-only"
    fake_cam.CreatePolicy.assert_called_once()
