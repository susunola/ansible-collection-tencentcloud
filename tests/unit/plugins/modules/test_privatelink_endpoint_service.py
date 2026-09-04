"""Tests for privatelink_endpoint_service."""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from ansible_collections.susunola.tencentcloud.plugins.modules import privatelink_endpoint_service
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import FakeModels


def test_request_builders():
    models = FakeModels()
    params = {
        "name": "api",
        "vpc_id": "vpc-1",
        "service_instance_id": "lb-1",
        "service_type": "CLB",
        "auto_accept": True,
        "ip_address_type": "IPv4",
        "tags": {"env": "prod"},
    }
    create = privatelink_endpoint_service.build_create_request(models, params)
    assert create.ServiceInstanceId == "lb-1"
    assert create.Tags[0].Key == "env"
    update = privatelink_endpoint_service.build_update_request(models, "vpcsvc-1", params)
    assert update.EndPointServiceId == "vpcsvc-1"
    assert privatelink_endpoint_service.build_delete_request(models, "vpcsvc-1", "IPv4").EndPointServiceId == "vpcsvc-1"
