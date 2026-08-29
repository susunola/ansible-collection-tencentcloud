"""Tests for privatelink_endpoint."""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from ansible_collections.susunola.tencentcloud.plugins.modules import privatelink_endpoint
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import FakeModels


def test_request_builders():
    models = FakeModels()
    params = {
        "name": "api-client",
        "vpc_id": "vpc-1",
        "subnet_id": "subnet-1",
        "endpoint_service_id": "vpcsvc-1",
        "endpoint_vip": None,
        "security_group_ids": ["sg-1"],
        "ip_address_type": "IPv4",
        "tags": {"env": "prod"},
    }
    create = privatelink_endpoint.build_create_request(models, params)
    assert create.EndPointServiceId == "vpcsvc-1"
    assert create.SecurityGroupId == "sg-1"
    update = privatelink_endpoint.build_update_request(models, "vpce-1", params)
    assert update.SecurityGroupIds == ["sg-1"]
    assert privatelink_endpoint.build_delete_request(models, "vpce-1", "IPv4").EndPointId == "vpce-1"
