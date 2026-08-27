"""Unit tests for the cam_policy write module helpers."""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from types import SimpleNamespace

from ansible_collections.susunola.tencentcloud.plugins.modules.cam_policy import (
    _apply_tags,
    _create,
    _delete,
    _documents_equal,
    _update,
    find_policy,
    normalize_document,
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
    def __init__(self, pages=None, get_response=None, get_exc=None):
        self.pages = list(pages or [])
        self.get_response = get_response
        self.get_exc = get_exc
        self.calls = []

    def ListPolicies(self, request):
        self.calls.append(request)
        page = request.Page
        items = self.pages[page - 1] if page <= len(self.pages) else []
        total = sum(len(p) for p in self.pages)
        return SimpleNamespace(List=[FakeResource(p) for p in items], TotalNum=total)

    def GetPolicy(self, request):
        self.calls.append(request)
        if self.get_exc:
            raise self.get_exc
        return FakeResource(self.get_response)

    def CreatePolicy(self, request):
        self.calls.append(request)
        return SimpleNamespace(PolicyId=1000001)

    def UpdatePolicy(self, request):
        self.calls.append(request)
        return SimpleNamespace(PolicyId=request.PolicyId)

    def DeletePolicy(self, request):
        self.calls.append(request)
        return SimpleNamespace()


POLICY = {
    "PolicyId": 1000001,
    "PolicyName": "app-read-only",
    "Type": 1,
    "Description": "app policy",
    "PolicyDocument": '{"version":"2.0","statement":[]}',
    "Tags": [],
}


def test_find_policy_by_name_uses_scope_and_keyword():
    client = FakeCamClient(pages=[[POLICY]])
    found = find_policy(FakeModule(), client, FakeModels(), None, "app-read-only", "Local")
    request = client.calls[0]
    assert request.Scope == "Local"
    assert request.Keyword == "app-read-only"
    assert request.Page == 1
    assert found["PolicyId"] == 1000001


def test_find_policy_by_name_exact_match_only():
    other = dict(POLICY, PolicyId=1000002, PolicyName="app-read-only-extended")
    client = FakeCamClient(pages=[[other]])
    assert find_policy(FakeModule(), client, FakeModels(), None, "app-read-only", "Local") is None


def test_find_policy_by_id_uses_get_policy():
    response = dict(POLICY)
    response.pop("PolicyId")
    client = FakeCamClient(get_response=response)
    found = find_policy(FakeModule(), client, FakeModels(), 1000001, None, "Local")
    assert found["PolicyId"] == 1000001
    assert found["PolicyName"] == "app-read-only"


def test_find_policy_by_id_maps_not_found_to_none():
    class NotFound(Exception):
        def get_code(self):
            return "ResourceNotFound.PolicyIdNotExist"

    client = FakeCamClient(get_exc=NotFound("gone"))
    assert find_policy(FakeModule(), client, FakeModels(), 1000001, None, "Local") is None


def test_find_policy_by_id_reraises_other_errors():
    class Boom(Exception):
        def get_code(self):
            return "InternalError"

    client = FakeCamClient(get_exc=Boom("boom"))
    try:
        find_policy(FakeModule(), client, FakeModels(), 1000001, None, "Local")
        raise AssertionError("expected exception")
    except Boom:
        pass


def test_normalize_document_accepts_dict_and_string():
    document = {"version": "2.0", "statement": []}
    assert normalize_document(document) == document
    assert normalize_document('{"version": "2.0", "statement": []}') == document
    assert normalize_document(None) is None


def test_documents_equal_ignores_formatting():
    desired = {"version": "2.0", "statement": [{"effect": "allow"}]}
    assert _documents_equal('{"version":"2.0","statement":[{"effect":"allow"}]}', desired)
    assert not _documents_equal('{"version":"2.0","statement":[]}', desired)


def test_create_serializes_document_and_tags():
    client = FakeCamClient()
    policy_id = _create(FakeModule(), client, FakeModels(), "app-read-only", "app policy",
                        {"version": "2.0"}, {"env": "prod"})
    request = client.calls[-1]
    assert policy_id == 1000001
    assert request.PolicyName == "app-read-only"
    assert request.PolicyDocument == '{"version": "2.0"}'
    assert request.Tags[0].Key == "env"


def test_update_sends_only_changed_fields():
    client = FakeCamClient()
    module = FakeModule()
    _update(module, client, FakeModels(), 1000001, "app-read-only", "new", None, ["description"])
    request = client.calls[-1]
    assert request.PolicyId == 1000001
    assert request.Description == "new"
    assert not hasattr(request, "PolicyDocument") or request.PolicyDocument is None
    assert not hasattr(request, "PolicyName") or request.PolicyName is None


def test_delete_sends_policy_id_list():
    client = FakeCamClient()
    _delete(FakeModule(), client, FakeModels(), 1000001)
    assert client.calls[-1].PolicyId == [1000001]


def test_apply_tags_uses_cam_policy_prefix():
    attached = []
    detached = []

    class FakeTagClient(object):
        def AttachResourcesTag(self, request):
            attached.append(request)
            return SimpleNamespace()

        def DetachResourcesTag(self, request):
            detached.append(request)
            return SimpleNamespace()

    _apply_tags(FakeModule(), FakeTagClient(), FakeModels(), "1000001", {"env": "prod"}, ["old"])
    assert attached[0].ServiceType == "cam"
    assert attached[0].ResourcePrefix == "policy"
    assert attached[0].ResourceIds == ["1000001"]
    assert attached[0].ResourceRegion == "ap-guangzhou"
    assert attached[0].TagKey == "env"
    assert detached[0].TagKey == "old"
    assert detached[0].ResourcePrefix == "policy"
