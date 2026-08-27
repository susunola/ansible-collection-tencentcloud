"""Unit tests for the security_group write module helpers."""

from __future__ import absolute_import, division, print_function

__metaclass__ = type
from ansible_collections.susunola.tencentcloud.plugins.modules.security_group import (
    _create,
    build_describe_request,
    find_security_group,
)


class FakeFilter(object):
    """Mimics the Tencent SDK model: zero-arg constructor, attribute assignment.

    The real ``models.Filter.__init__`` accepts no keyword arguments; passing
    ``Name=...`` at construction time raises TypeError. Keeping this fake
    strict guards against the module regressing to kwargs construction.
    """

    def __init__(self):
        pass


class FakeRequest(object):
    pass


class FakeTag(object):
    """Mimics the SDK Tag model: zero-arg constructor with Key/Value."""

    def __init__(self):
        self.Key = None
        self.Value = None


class FakeModels(object):
    Filter = FakeFilter
    Tag = FakeTag
    DescribeSecurityGroupsRequest = FakeRequest
    CreateSecurityGroupRequest = FakeRequest


class FakeGroup(object):
    def __init__(self, group_id, name, desc, tags=None):
        self.SecurityGroupId = group_id
        self.SecurityGroupName = name
        self.SecurityGroupDesc = desc
        self.TagSet = tags or []

    def _serialize(self, allow_none=True):
        return {
            "SecurityGroupId": self.SecurityGroupId,
            "SecurityGroupName": self.SecurityGroupName,
            "SecurityGroupDesc": self.SecurityGroupDesc,
            "TagSet": [{"Key": t.Key, "Value": t.Value} for t in self.TagSet],
        }


class FakeResponse(object):
    def __init__(self, groups):
        self.SecurityGroupSet = groups


class FakeClient(object):
    def __init__(self, response=None, exc=None):
        self.response = response
        self.exc = exc
        self.calls = []

    def DescribeSecurityGroups(self, request):
        self.calls.append(request)
        if self.exc:
            raise self.exc
        return self.response

    def CreateSecurityGroup(self, request):
        self.calls.append(request)
        if self.exc:
            raise self.exc
        return self.response


class FakeCreatedGroup(object):
    def _serialize(self, allow_none=True):
        return {"SecurityGroupId": "sg-new", "SecurityGroupName": "web"}


class FakeCreateResponse(object):
    def __init__(self):
        self.SecurityGroup = FakeCreatedGroup()


class FakeModule(object):
    def __init__(self):
        self.params = {"retries": 2}

    def sdk_call(self, operation, request):
        return operation(request)


def test_build_describe_request_by_id():
    request = build_describe_request(FakeModels, None, "sg-123")
    assert request.SecurityGroupIds == ["sg-123"]
    assert request.Limit == "100"
    assert not hasattr(request, "Filters") or request.Filters is None


def test_build_describe_request_by_name():
    request = build_describe_request(FakeModels, "web", None)
    assert request.Filters[0].Name == "security-group-name"
    assert request.Filters[0].Values == ["web"]
    assert not hasattr(request, "SecurityGroupIds") or request.SecurityGroupIds is None


def test_find_security_group_returns_first_match():
    client = FakeClient(FakeResponse([FakeGroup("sg-1", "web", "desc")]))
    module = FakeModule()
    group = find_security_group(module, client, FakeModels, "web", None)
    assert group["SecurityGroupId"] == "sg-1"
    assert len(client.calls) == 1


def test_find_security_group_returns_none_when_absent():
    client = FakeClient(FakeResponse([]))
    module = FakeModule()
    assert find_security_group(module, client, FakeModels, "web", None) is None


def test_find_security_group_handles_none_set():
    client = FakeClient(FakeResponse(None))
    module = FakeModule()
    assert find_security_group(module, client, FakeModels, "web", None) is None


def test_create_sends_string_project_id():
    """The VPC API only accepts ProjectId as a string."""
    client = FakeClient(FakeCreateResponse())
    module = FakeModule()
    created = _create(module, client, FakeModels, "web", "desc", 0, {"env": "prod"})
    assert created["SecurityGroupId"] == "sg-new"
    request = client.calls[-1]
    assert request.ProjectId == "0"
    assert request.Tags[0].Key == "env"
    assert request.Tags[0].Value == "prod"


def test_find_security_group_surfaces_sdk_exceptions():
    class Boom(Exception):
        def get_code(self):
            return "ResourceNotFound"

    client = FakeClient(exc=Boom("gone"))
    module = FakeModule()
    try:
        find_security_group(module, client, FakeModels, "web", None)
        raise AssertionError("expected exception")
    except Boom:
        pass
