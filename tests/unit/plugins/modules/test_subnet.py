"""Unit tests for the subnet write module helpers."""

from __future__ import absolute_import, division, print_function
__metaclass__ = type
from ansible_collections.tencentcloud.cloud.plugins.modules.subnet import (
    _create,
    _delete,
    _update,
    build_describe_request,
    find_subnet,
)


class FakeFilter(object):
    pass


class FakeTag(object):
    pass


class FakeRequest(object):
    pass


class FakeModels(object):
    Filter = FakeFilter
    Tag = FakeTag
    DescribeSubnetsRequest = FakeRequest
    CreateSubnetRequest = FakeRequest
    ModifySubnetAttributeRequest = FakeRequest
    DeleteSubnetRequest = FakeRequest


class FakeSubnet(object):
    def __init__(self, subnet_id, name, vpc_id="vpc-1", cidr="10.0.1.0/24",
                 zone="ap-guangzhou-1", broadcast=False, tags=None):
        self.SubnetId = subnet_id
        self.SubnetName = name
        self.VpcId = vpc_id
        self.CidrBlock = cidr
        self.Zone = zone
        self.EnableBroadcast = broadcast
        self.TagSet = tags or []

    def _serialize(self, allow_none=True):
        return {
            "SubnetId": self.SubnetId,
            "SubnetName": self.SubnetName,
            "VpcId": self.VpcId,
            "CidrBlock": self.CidrBlock,
            "Zone": self.Zone,
            "EnableBroadcast": self.EnableBroadcast,
            "TagSet": [{"Key": t.Key, "Value": t.Value} for t in self.TagSet],
        }


class FakeDescribeResponse(object):
    def __init__(self, subnets):
        self.SubnetSet = subnets


class FakeCreateResponse(object):
    def __init__(self, subnet):
        self.Subnet = subnet


class FakeClient(object):
    def __init__(self, response=None, exc=None):
        self.response = response
        self.exc = exc
        self.calls = []

    def DescribeSubnets(self, request):
        self.calls.append(request)
        if self.exc:
            raise self.exc
        return self.response

    def CreateSubnet(self, request):
        self.calls.append(request)
        return self.response

    def ModifySubnetAttribute(self, request):
        self.calls.append(request)
        return None

    def DeleteSubnet(self, request):
        self.calls.append(request)
        return None


class FakeModule(object):
    def __init__(self):
        self.params = {"retries": 2, "region": "ap-guangzhou"}

    def sdk_call(self, operation, request):
        return operation(request)


def test_build_describe_request_by_id():
    request = build_describe_request(FakeModels, "subnet-123", None, None)
    assert request.SubnetIds == ["subnet-123"]
    assert request.Limit == 100
    assert not hasattr(request, "Filters")


def test_build_describe_request_by_vpc_and_name():
    request = build_describe_request(FakeModels, None, "vpc-1", "web")
    assert not hasattr(request, "SubnetIds")
    assert [(f.Name, f.Values) for f in request.Filters] == [
        ("vpc-id", ["vpc-1"]), ("subnet-name", ["web"]),
    ]


def test_build_describe_request_by_name_only():
    request = build_describe_request(FakeModels, None, None, "web")
    assert [(f.Name, f.Values) for f in request.Filters] == [("subnet-name", ["web"])]


def test_find_subnet_returns_first_match():
    client = FakeClient(FakeDescribeResponse([FakeSubnet("subnet-1", "web")]))
    module = FakeModule()
    subnet = find_subnet(module, client, FakeModels, None, "vpc-1", "web")
    assert subnet["SubnetId"] == "subnet-1"
    assert len(client.calls) == 1


def test_find_subnet_returns_none_when_absent():
    client = FakeClient(FakeDescribeResponse([]))
    module = FakeModule()
    assert find_subnet(module, client, FakeModels, None, None, "web") is None


def test_find_subnet_handles_none_set():
    client = FakeClient(FakeDescribeResponse(None))
    module = FakeModule()
    assert find_subnet(module, client, FakeModels, None, None, "web") is None


def test_find_subnet_surfaces_sdk_exceptions():
    class Boom(Exception):
        def get_code(self):
            return "ResourceNotFound"

    client = FakeClient(exc=Boom("gone"))
    module = FakeModule()
    try:
        find_subnet(module, client, FakeModels, None, None, "web")
        raise AssertionError("expected exception")
    except Boom:
        pass


def test_create_builds_full_request():
    client = FakeClient(FakeCreateResponse(FakeSubnet("subnet-1", "web")))
    module = FakeModule()
    created = _create(module, client, FakeModels, "vpc-1", "web", "10.0.1.0/24",
                      "ap-guangzhou-1", {"env": "prod"})
    request = client.calls[0]
    assert request.VpcId == "vpc-1"
    assert request.SubnetName == "web"
    assert request.CidrBlock == "10.0.1.0/24"
    assert request.Zone == "ap-guangzhou-1"
    assert [(t.Key, t.Value) for t in request.Tags] == [("env", "prod")]
    assert created["SubnetId"] == "subnet-1"


def test_create_omits_tags_when_empty():
    client = FakeClient(FakeCreateResponse(FakeSubnet("subnet-1", "web")))
    module = FakeModule()
    _create(module, client, FakeModels, "vpc-1", "web", "10.0.1.0/24",
            "ap-guangzhou-1", {})
    assert not hasattr(client.calls[0], "Tags")


def test_update_serializes_broadcast_as_string():
    client = FakeClient()
    module = FakeModule()
    _update(module, client, FakeModels, "subnet-1", "web", True)
    request = client.calls[0]
    assert request.SubnetId == "subnet-1"
    assert request.SubnetName == "web"
    assert request.EnableBroadcast == "true"


def test_update_omits_broadcast_when_unspecified():
    client = FakeClient()
    module = FakeModule()
    _update(module, client, FakeModels, "subnet-1", "web", None)
    assert not hasattr(client.calls[0], "EnableBroadcast")


def test_delete_builds_request():
    client = FakeClient()
    module = FakeModule()
    _delete(module, client, FakeModels, "subnet-1")
    assert client.calls[0].SubnetId == "subnet-1"
