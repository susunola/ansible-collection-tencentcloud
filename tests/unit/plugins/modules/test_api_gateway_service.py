"""Tests for api_gateway_service."""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from ansible_collections.susunola.tencentcloud.plugins.modules import api_gateway_service
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import FakeModels


def test_request_builders():
    models = FakeModels()
    params = {
        "name": "orders",
        "description": "order APIs",
        "protocol": "http&https",
        "network_types": ["OUTER"],
        "ip_version": "IPv4",
        "vpc_id": None,
        "instance_id": None,
        "tags": {"env": "prod"},
    }
    create = api_gateway_service.build_create_request(models, params)
    assert create.ServiceName == "orders"
    assert create.NetTypes == ["OUTER"]
    update = api_gateway_service.build_update_request(models, "service-1", params)
    assert update.ServiceId == "service-1"
    assert api_gateway_service.build_delete_request(models, "service-1").ServiceId == "service-1"
