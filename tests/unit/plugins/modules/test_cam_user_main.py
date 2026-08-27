"""Main-path unit tests for the cam_user module (run_module level)."""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import cam_user
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    FakeModels,
    FakeResource,
    module_args,
    run,
)

USER = {
    "Uin": 100000000001,
    "Name": "deploy-bot",
    "Uid": 2000001,
    "Remark": "CI deployment account",
    "ConsoleLogin": 1,
    "CreateTime": "2026-08-26 12:00:00",
}

CAM_MARKER = type("CamClientMarker", (object,), {})
TAG_MARKER = type("TagClientMarker", (object,), {})


class FakeCamClient(object):
    def __init__(self, users=None):
        self.users = list(users or [])
        self.AddUser = MagicMock(side_effect=self._add_user)
        self.UpdateUser = MagicMock()
        self.DeleteUser = MagicMock(side_effect=self._delete_user)

    def ListUsers(self, request):
        return SimpleNamespace(Data=[FakeResource(u) for u in self.users])

    def _add_user(self, request):
        user = {
            "Uin": 100000000002,
            "Name": request.Name,
            "Uid": 2000002,
            "Remark": request.Remark,
            "ConsoleLogin": request.ConsoleLogin,
            "CreateTime": "2026-08-26 12:00:01",
        }
        self.users.append(user)
        return SimpleNamespace(Uin=user["Uin"], Name=user["Name"])

    def _delete_user(self, request):
        self.users = [u for u in self.users if u["Name"] != request.Name]
        return SimpleNamespace()


class FakeTagClient(object):
    def __init__(self):
        self.tags = {}
        self.AttachResourcesTag = MagicMock(side_effect=self._attach)
        self.DetachResourcesTag = MagicMock(side_effect=self._detach)

    def DescribeResourceTagsByResourceIds(self, request):
        resource_tags = [
            SimpleNamespace(Tags=[SimpleNamespace(TagKey=k, TagValue=v) for k, v in sorted(self.tags.items())])
        ]
        return SimpleNamespace(Tags=resource_tags)

    def _attach(self, request):
        self.tags[request.TagKey] = request.TagValue
        return SimpleNamespace()

    def _detach(self, request):
        self.tags.pop(request.TagKey, None)
        return SimpleNamespace()


@pytest.fixture
def clients(monkeypatch):
    fake_cam = FakeCamClient()
    fake_tag = FakeTagClient()
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(
        cam_user, "_load_cam",
        lambda: (FakeModels(), SimpleNamespace(CamClient=CAM_MARKER)),
    )
    monkeypatch.setattr(
        cam_user, "_load_tag",
        lambda: (FakeModels(), SimpleNamespace(TagClient=TAG_MARKER)),
    )
    monkeypatch.setattr(
        TencentCloudModule, "create_client",
        lambda self, client_class, endpoint: fake_cam if client_class is CAM_MARKER else fake_tag,
    )
    return fake_cam, fake_tag


def test_create_reports_changed(clients):
    fake_cam, fake_tag = clients
    module_args(state="present", name="deploy-bot", remark="CI deployment account", console_login=True)
    result = run(cam_user.run_module)
    assert result["changed"] is True
    assert result["user"]["Name"] == "deploy-bot"
    fake_cam.AddUser.assert_called_once()
    assert "diff" not in result


def test_create_with_tags_attaches_via_tag_service(clients):
    fake_cam, fake_tag = clients
    module_args(state="present", name="deploy-bot", tags={"env": "prod"})
    result = run(cam_user.run_module)
    assert result["changed"] is True
    fake_tag.AttachResourcesTag.assert_called_once()
    request = fake_tag.AttachResourcesTag.call_args[0][0]
    assert request.ServiceType == "cam"
    assert request.ResourcePrefix == "uin"
    assert request.ResourceIds == ["100000000002"]


def test_second_run_is_idempotent(clients):
    fake_cam, fake_tag = clients
    fake_cam.users.append(dict(USER))
    module_args(state="present", name="deploy-bot", remark="CI deployment account", console_login=True)
    result = run(cam_user.run_module)
    assert result["changed"] is False
    fake_cam.AddUser.assert_not_called()
    fake_cam.UpdateUser.assert_not_called()
    fake_tag.AttachResourcesTag.assert_not_called()


def test_update_remark_and_console_login(clients):
    fake_cam, fake_tag = clients
    fake_cam.users.append(dict(USER))
    module_args(state="present", name="deploy-bot", remark="new remark", console_login=False)
    result = run(cam_user.run_module)
    assert result["changed"] is True
    fake_cam.UpdateUser.assert_called_once()
    request = fake_cam.UpdateUser.call_args[0][0]
    assert request.Remark == "new remark"
    assert request.ConsoleLogin == 0


def test_tag_drift_is_reconciled(clients):
    fake_cam, fake_tag = clients
    fake_cam.users.append(dict(USER))
    fake_tag.tags = {"old": "gone", "env": "dev"}
    module_args(state="present", name="deploy-bot", remark="CI deployment account",
                console_login=True, tags={"env": "prod"})
    result = run(cam_user.run_module)
    assert result["changed"] is True
    fake_tag.AttachResourcesTag.assert_called_once()
    fake_tag.DetachResourcesTag.assert_called_once()
    assert fake_tag.DetachResourcesTag.call_args[0][0].TagKey == "old"


def test_absent_deletes_existing_user(clients):
    fake_cam, fake_tag = clients
    fake_cam.users.append(dict(USER))
    module_args(state="absent", name="deploy-bot")
    result = run(cam_user.run_module)
    assert result["changed"] is True
    fake_cam.DeleteUser.assert_called_once()
    assert fake_cam.users == []


def test_absent_on_missing_user_is_unchanged(clients):
    fake_cam, fake_tag = clients
    module_args(state="absent", name="deploy-bot")
    result = run(cam_user.run_module)
    assert result["changed"] is False
    fake_cam.DeleteUser.assert_not_called()


def test_check_mode_create_makes_no_sdk_writes(clients):
    fake_cam, fake_tag = clients
    module_args(state="present", name="deploy-bot", _ansible_check_mode=True)
    result = run(cam_user.run_module)
    assert result["changed"] is True
    assert "diff" in result
    fake_cam.AddUser.assert_not_called()
    fake_cam.UpdateUser.assert_not_called()
    fake_cam.DeleteUser.assert_not_called()


def test_check_mode_update_makes_no_sdk_writes(clients):
    fake_cam, fake_tag = clients
    fake_cam.users.append(dict(USER))
    module_args(state="present", name="deploy-bot", remark="changed", _ansible_check_mode=True)
    result = run(cam_user.run_module)
    assert result["changed"] is True
    fake_cam.UpdateUser.assert_not_called()


def test_diff_mode_create_includes_diff(clients):
    fake_cam, fake_tag = clients
    module_args(state="present", name="deploy-bot", _ansible_diff=True)
    result = run(cam_user.run_module)
    assert result["changed"] is True
    assert result["diff"]["before"] is None
    assert result["diff"]["after"]["name"] == "deploy-bot"
    fake_cam.AddUser.assert_called_once()
