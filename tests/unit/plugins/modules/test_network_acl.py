"""Tests for network_acl."""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from ansible_collections.susunola.tencentcloud.plugins.modules import network_acl
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import FakeModels


def test_build_requests_and_normalization():
    models = FakeModels()
    params = {"name": "app", "vpc_id": "vpc-1", "acl_type": None, "tags": {"env": "prod"}}
    create = network_acl.build_create_request(models, params)
    assert create.NetworkAclName == "app"
    assert create.Tags[0].Key == "env"
    values = [{"protocol": "TCP", "port": "443", "cidr": "10.0.0.0/8", "action": "ACCEPT", "description": "https", "priority": 1}]
    request = network_acl.build_entries_request(models, "acl-1", values, [])
    assert request.NetworkAclEntrySet.Ingress[0].Port == "443"
    assert network_acl._rules(
        request.NetworkAclEntrySet.Ingress[0].__dict__.get("_data", {}) if hasattr(request.NetworkAclEntrySet.Ingress[0], "_data") else values
    )


def test_rule_and_subnet_canonicalization():
    rules = [{"Protocol": "ALL", "CidrBlock": "0.0.0.0/0", "Action": "ACCEPT", "Priority": 1}]
    assert network_acl._rules(rules)[0]["cidr"] == "0.0.0.0/0"
    assert network_acl._subnets([{"SubnetId": "subnet-b"}, {"SubnetId": "subnet-a"}]) == ["subnet-a", "subnet-b"]
