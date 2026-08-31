"""Unit tests for the generic resource_id lookup helpers."""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import pytest
from ansible.errors import AnsibleError

from ansible_collections.susunola.tencentcloud.plugins.lookup.resource_id import (
    build_request,
    resolve_resource,
    sdk_error_message,
)


class Object(object):
    def __init__(self, **values):
        self.__dict__.update(values)


class Filter(Object):
    pass


class Request(Object):
    def __init__(self):
        pass


class Models(object):
    Filter = Filter
    DescribeVpcsRequest = Request
    DescribeSubnetsRequest = Request
    DescribeSecurityGroupsRequest = Request
    DescribeInstancesRequest = Request
    DescribeLoadBalancersRequest = Request
    DescribeClustersRequest = Request
    DescribeDBInstancesRequest = Request


class Client(object):
    def __init__(self, response):
        self.response = response
        self.request = None

    def __getattr__(self, name):
        def call(request):
            self.request = request
            return self.response
        return call


def test_vpc_request_uses_exact_name_filter():
    request = build_request("vpc", Models, "production")
    assert request.Limit == "100"
    assert request.Filters[0].Name == "vpc-name"
    assert request.Filters[0].Values == ["production"]


def test_subnet_request_scopes_to_vpc():
    request = build_request("subnet", Models, "app-a", "vpc-1")
    assert [(item.Name, item.Values) for item in request.Filters] == [
        ("subnet-name", ["app-a"]),
        ("vpc-id", ["vpc-1"]),
    ]


def test_cdb_request_uses_instance_names():
    request = build_request("cdb_instance", Models, "orders")
    assert request.InstanceNames == ["orders"]


def test_resolve_resource_returns_exact_match_only():
    response = Object(VpcSet=[
        Object(VpcId="vpc-fuzzy", VpcName="production-old"),
        Object(VpcId="vpc-exact", VpcName="production"),
    ])
    assert resolve_resource(Client(response), Models, "vpc", "production") == "vpc-exact"


def test_resolve_resource_rejects_absent_and_ambiguous_names():
    with pytest.raises(AnsibleError, match="No vpc"):
        resolve_resource(Client(Object(VpcSet=[])), Models, "vpc", "missing")
    response = Object(VpcSet=[
        Object(VpcId="vpc-1", VpcName="duplicate"),
        Object(VpcId="vpc-2", VpcName="duplicate"),
    ])
    with pytest.raises(AnsibleError, match="Multiple vpc"):
        resolve_resource(Client(response), Models, "vpc", "duplicate")


def test_sdk_error_message_keeps_code_and_request_id():
    class Failure(Exception):
        def get_code(self):
            return "UnauthorizedOperation"

        def get_request_id(self):
            return "req-1"

    message = sdk_error_message("vpc", "production", Failure("denied"))
    assert "UnauthorizedOperation" in message
    assert "req-1" in message
