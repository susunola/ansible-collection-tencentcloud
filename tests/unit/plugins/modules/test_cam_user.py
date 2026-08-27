"""Unit tests for the cam_user write module helpers."""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from types import SimpleNamespace

from ansible_collections.susunola.tencentcloud.plugins.modules.cam_user import (
    _apply_tags,
    _create,
    _current_tags,
    _delete,
    _update,
    find_user,
)
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    FakeModels,
    FakeResource,
)


class FakeModule(object):
    def __init__(self):
        self.params = {"retries": 2, "region": "ap-guangzhou"}

    def sdk_call(self, operation, request):
        return operation(request)


class FakeCamClient(object):
    def __init__(self, users=None):
        self.users = list(users or [])
        self.calls = []

    def ListUsers(self, request):
        self.calls.append(request)
        return SimpleNamespace(Data=[FakeResource(u) for u in self.users])

    def AddUser(self, request):
        self.calls.append(request)
        return SimpleNamespace(Uin=100000000001, Name=request.Name)

    def UpdateUser(self, request):
        self.calls.append(request)
        return SimpleNamespace()

    def DeleteUser(self, request):
        self.calls.append(request)
        return SimpleNamespace()


class FakeTagClient(object):
    def __init__(self, tags=None):
        self.tags = tags or []
        self.calls = []

    def DescribeResourceTagsByResourceIds(self, request):
        self.calls.append(request)
        return SimpleNamespace(Tags=self.tags)

    def AttachResourcesTag(self, request):
        self.calls.append(request)
        return SimpleNamespace()

    def DetachResourcesTag(self, request):
        self.calls.append(request)
        return SimpleNamespace()


USER = {"Uin": 100000000001, "Name": "deploy-bot", "Remark": "ci", "ConsoleLogin": 1}


def test_find_user_matches_by_name():
    client = FakeCamClient([USER, {"Uin": 2, "Name": "other"}])
    found = find_user(FakeModule(), client, FakeModels(), "deploy-bot")
    assert found["Uin"] == 100000000001
    assert len(client.calls) == 1


def test_find_user_returns_none_when_absent():
    client = FakeCamClient([{"Uin": 2, "Name": "other"}])
    assert find_user(FakeModule(), client, FakeModels(), "deploy-bot") is None


def test_find_user_handles_none_data():
    client = FakeCamClient([])
    client.ListUsers = lambda request: SimpleNamespace(Data=None)
    assert find_user(FakeModule(), client, FakeModels(), "deploy-bot") is None


def test_create_disables_api_keys_and_maps_console_login():
    client = FakeCamClient()
    uin = _create(FakeModule(), client, FakeModels(), "deploy-bot", "ci", True, "S3cret!")
    request = client.calls[-1]
    assert uin == 100000000001
    assert request.Name == "deploy-bot"
    assert request.Remark == "ci"
    assert request.ConsoleLogin == 1
    assert request.UseApi == 0
    assert request.Password == "S3cret!"


def test_create_without_console_login_sends_no_password():
    client = FakeCamClient()
    _create(FakeModule(), client, FakeModels(), "deploy-bot", None, False, "S3cret!")
    request = client.calls[-1]
    assert request.ConsoleLogin == 0
    assert request.Remark == ""
    assert not hasattr(request, "Password") or request.Password is None


def test_update_sets_console_login_only_when_given():
    client = FakeCamClient()
    _update(FakeModule(), client, FakeModels(), "deploy-bot", "new", None)
    request = client.calls[-1]
    assert request.Remark == "new"
    assert not hasattr(request, "ConsoleLogin") or request.ConsoleLogin is None

    _update(FakeModule(), client, FakeModels(), "deploy-bot", "new", True)
    assert client.calls[-1].ConsoleLogin == 1


def test_delete_sends_name():
    client = FakeCamClient()
    _delete(FakeModule(), client, FakeModels(), "deploy-bot")
    assert client.calls[-1].Name == "deploy-bot"


def test_current_tags_normalizes_tag_service_shape():
    resource_tag = SimpleNamespace(Tags=[SimpleNamespace(TagKey="env", TagValue="prod")])
    client = FakeTagClient(tags=[resource_tag])
    tags = _current_tags(FakeModule(), client, FakeModels(), "100000000001", "uin")
    assert tags == [{"Key": "env", "Value": "prod"}]
    request = client.calls[-1]
    assert request.ServiceType == "cam"
    assert request.ResourcePrefix == "uin"
    assert request.ResourceIds == ["100000000001"]


def test_apply_tags_uses_cam_uin_prefix():
    client = FakeTagClient()
    module = FakeModule()
    _apply_tags(module, client, FakeModels(), "100000000001", "uin", {"env": "prod"}, ["old"])
    attach, detach = client.calls
    assert attach.ServiceType == "cam"
    assert attach.ResourcePrefix == "uin"
    assert attach.ResourceIds == ["100000000001"]
    assert attach.ResourceRegion == "ap-guangzhou"
    assert attach.TagKey == "env"
    assert attach.TagValue == "prod"
    assert detach.TagKey == "old"
    assert detach.ResourcePrefix == "uin"
