"""Unit tests for the cam_role write module helpers."""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from types import SimpleNamespace

from ansible_collections.tencentcloud.cloud.plugins.modules.cam_role import (
    _create,
    _delete,
    _documents_equal,
    _tag_role,
    _untag_role,
    _update_description,
    _update_policy_document,
    build_role_tags,
    find_role,
    normalize_document,
)
from ansible_collections.tencentcloud.cloud.tests.unit.plugins.modules.harness import (
    FakeModels,
    FakeResource,
)


class FakeModule(object):
    def __init__(self):
        self.params = {"retries": 2, "region": "ap-guangzhou"}

    def sdk_call(self, operation, request):
        return operation(request)


class FakeRoleTags(object):
    """Mimics the SDK RoleTags model: zero-arg constructor with Key/Value."""

    def __init__(self):
        self.Key = None
        self.Value = None


class FakeCamModels(FakeModels):
    RoleTags = FakeRoleTags


class FakeCamClient(object):
    def __init__(self, pages=None):
        self.pages = list(pages or [])
        self.calls = []

    def DescribeRoleList(self, request):
        self.calls.append(request)
        page = request.Page
        items = self.pages[page - 1] if page <= len(self.pages) else []
        total = sum(len(p) for p in self.pages)
        return SimpleNamespace(List=[FakeResource(r) for r in items], TotalNum=total)

    def CreateRole(self, request):
        self.calls.append(request)
        return SimpleNamespace(RoleId="4611686018427904001")

    def UpdateRoleDescription(self, request):
        self.calls.append(request)
        return SimpleNamespace()

    def UpdateAssumeRolePolicy(self, request):
        self.calls.append(request)
        return SimpleNamespace()

    def DeleteRole(self, request):
        self.calls.append(request)
        return SimpleNamespace()

    def TagRole(self, request):
        self.calls.append(request)
        return SimpleNamespace()

    def UntagRole(self, request):
        self.calls.append(request)
        return SimpleNamespace()


ROLE = {
    "RoleId": "4611686018427904001",
    "RoleName": "app-instance-role",
    "Description": "app role",
    "PolicyDocument": '{"version":"2.0","statement":[]}',
    "Tags": [],
}


def test_find_role_matches_by_name():
    client = FakeCamClient([[ROLE]])
    found = find_role(FakeModule(), client, FakeCamModels(), None, "app-instance-role")
    assert found["RoleId"] == "4611686018427904001"
    assert client.calls[0].Page == 1


def test_find_role_matches_by_id_across_pages():
    other = dict(ROLE, RoleId="4611686018427904002", RoleName="other")
    client = FakeCamClient([[other] * 100, [ROLE]])
    found = find_role(FakeModule(), client, FakeCamModels(), ROLE["RoleId"], None)
    assert found["RoleName"] == "app-instance-role"
    assert len(client.calls) == 2


def test_find_role_returns_none_when_absent():
    client = FakeCamClient([[dict(ROLE, RoleName="other")]])
    assert find_role(FakeModule(), client, FakeCamModels(), None, "app-instance-role") is None


def test_normalize_document_accepts_dict_and_string():
    document = {"version": "2.0", "statement": []}
    assert normalize_document(document) == document
    assert normalize_document('{"version": "2.0", "statement": []}') == document
    assert normalize_document(None) is None


def test_documents_equal_ignores_formatting():
    desired = {"version": "2.0", "statement": [{"effect": "allow"}]}
    assert _documents_equal('{"version":"2.0","statement":[{"effect":"allow"}]}', desired)
    assert not _documents_equal('{"version":"2.0","statement":[]}', desired)


def test_build_role_tags_uses_role_tags_model():
    tags = build_role_tags(FakeCamModels(), {"env": "prod"})
    assert isinstance(tags[0], FakeRoleTags)
    assert tags[0].Key == "env"
    assert tags[0].Value == "prod"
    assert build_role_tags(FakeCamModels(), {}) is None


def test_create_serializes_policy_document():
    client = FakeCamClient()
    role_id = _create(FakeModule(), client, FakeCamModels(), "app-instance-role", "app role",
                      {"version": "2.0"}, {"env": "prod"})
    request = client.calls[-1]
    assert role_id == "4611686018427904001"
    assert request.RoleName == "app-instance-role"
    assert request.PolicyDocument == '{"version": "2.0"}'
    assert request.Tags[0].Key == "env"


def test_update_helpers_send_role_id():
    client = FakeCamClient()
    module = FakeModule()
    _update_description(module, client, FakeCamModels(), "4611686018427904001", "new")
    assert client.calls[-1].RoleId == "4611686018427904001"
    assert client.calls[-1].Description == "new"
    _update_policy_document(module, client, FakeCamModels(), "4611686018427904001", {"version": "2.0"})
    assert client.calls[-1].PolicyDocument == '{"version": "2.0"}'


def test_delete_prefers_role_id():
    client = FakeCamClient()
    module = FakeModule()
    _delete(module, client, FakeCamModels(), "4611686018427904001", None)
    assert client.calls[-1].RoleId == "4611686018427904001"
    assert not hasattr(client.calls[-1], "RoleName") or client.calls[-1].RoleName is None
    _delete(module, client, FakeCamModels(), None, "app-instance-role")
    assert client.calls[-1].RoleName == "app-instance-role"


def test_tag_and_untag_role():
    client = FakeCamClient()
    module = FakeModule()
    _tag_role(module, client, FakeCamModels(), "4611686018427904001", {"env": "prod"})
    request = client.calls[-1]
    assert request.RoleId == "4611686018427904001"
    assert request.Tags[0].Key == "env"
    _untag_role(module, client, FakeCamModels(), "4611686018427904001", ["old"])
    assert client.calls[-1].TagKeys == ["old"]
