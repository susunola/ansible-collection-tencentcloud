"""Unit tests for the vpc write module helpers."""

from __future__ import absolute_import, division, print_function
__metaclass__ = type
from ansible_collections.tencentcloud.cloud.plugins.modules.vpc import (
    build_describe_request,
    find_vpc,
)


class FakeFilter(object):
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)


class FakeRequest(object):
    pass


class FakeModels(object):
    Filter = FakeFilter
    DescribeVpcsRequest = FakeRequest


class FakeVpc(object):
    def __init__(self, vpc_id, name, cidr="10.0.0.0/16", dns=None, domain="", tags=None):
        self.VpcId = vpc_id
        self.VpcName = name
        self.CidrBlock = cidr
        self.DnsServerSet = dns or []
        self.DomainName = domain
        self.TagSet = tags or []

    def _serialize(self, allow_none=True):
        return {
            "VpcId": self.VpcId,
            "VpcName": self.VpcName,
            "CidrBlock": self.CidrBlock,
            "DnsServerSet": list(self.DnsServerSet),
            "DomainName": self.DomainName,
            "TagSet": [{"Key": t.Key, "Value": t.Value} for t in self.TagSet],
        }


class FakeResponse(object):
    def __init__(self, vpcs):
        self.VpcSet = vpcs


class FakeClient(object):
    def __init__(self, response=None, exc=None):
        self.response = response
        self.exc = exc
        self.calls = []

    def DescribeVpcs(self, request):
        self.calls.append(request)
        if self.exc:
            raise self.exc
        return self.response


class FakeModule(object):
    def __init__(self):
        self.params = {"retries": 2}

    def sdk_call(self, operation, request):
        return operation(request)


def test_build_describe_request_by_id():
    request = build_describe_request(FakeModels, None, "vpc-123")
    assert request.VpcIds == ["vpc-123"]
    assert request.Limit == "100"
    assert request.Offset == "0"
    assert not hasattr(request, "Filters") or request.Filters is None


def test_build_describe_request_by_name():
    request = build_describe_request(FakeModels, "prod", None)
    assert request.Filters[0].Name == "vpc-name"
    assert request.Filters[0].Values == ["prod"]
    assert not hasattr(request, "VpcIds") or request.VpcIds is None


def test_find_vpc_returns_first_match():
    client = FakeClient(FakeResponse([FakeVpc("vpc-1", "prod")]))
    module = FakeModule()
    vpc = find_vpc(module, client, FakeModels, None, "vpc-1")
    assert vpc["VpcId"] == "vpc-1"
    assert len(client.calls) == 1


def test_find_vpc_prefers_exact_name_match():
    # The vpc-name filter matches fuzzily; an exact match must win.
    vpcs = [FakeVpc("vpc-1", "prod-extra"), FakeVpc("vpc-2", "prod")]
    client = FakeClient(FakeResponse(vpcs))
    module = FakeModule()
    vpc = find_vpc(module, client, FakeModels, "prod", None)
    assert vpc["VpcId"] == "vpc-2"


def test_find_vpc_falls_back_to_first_fuzzy_match():
    client = FakeClient(FakeResponse([FakeVpc("vpc-1", "prod-extra")]))
    module = FakeModule()
    vpc = find_vpc(module, client, FakeModels, "prod", None)
    assert vpc["VpcId"] == "vpc-1"


def test_find_vpc_returns_none_when_absent():
    client = FakeClient(FakeResponse([]))
    module = FakeModule()
    assert find_vpc(module, client, FakeModels, "prod", None) is None


def test_find_vpc_handles_none_set():
    client = FakeClient(FakeResponse(None))
    module = FakeModule()
    assert find_vpc(module, client, FakeModels, "prod", None) is None


def test_find_vpc_surfaces_sdk_exceptions():
    class Boom(Exception):
        def get_code(self):
            return "ResourceNotFound"

    client = FakeClient(exc=Boom("gone"))
    module = FakeModule()
    try:
        find_vpc(module, client, FakeModels, "prod", None)
        raise AssertionError("expected exception")
    except Boom:
        pass
