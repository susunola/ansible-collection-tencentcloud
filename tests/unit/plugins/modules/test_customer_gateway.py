"""Tests for the customer_gateway write module."""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from types import SimpleNamespace
from unittest.mock import MagicMock

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import customer_gateway
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    FakeModels,
    module_args,
    run,
)


def test_request_builders():
    models = FakeModels()
    params = {"name": "office", "ip_address": "203.0.113.10", "bgp_asn": 65001, "tags": {"env": "prod"}}
    create = customer_gateway.build_create_request(models, params)
    assert create.CustomerGatewayName == "office"
    assert create.IpAddress == "203.0.113.10"
    assert create.BgpAsn == 65001
    assert create.Tags[0].Key == "env"
    update = customer_gateway.build_update_request(models, "cgw-1", "office-v2", 65002)
    assert update.CustomerGatewayId == "cgw-1"
    assert update.CustomerGatewayName == "office-v2"
    assert customer_gateway.build_delete_request(models, "cgw-1").CustomerGatewayId == "cgw-1"


def test_create_main_path(monkeypatch):
    models = FakeModels()
    client = SimpleNamespace(CreateCustomerGateway=MagicMock(return_value=SimpleNamespace(CustomerGateway=SimpleNamespace(CustomerGatewayId="cgw-1"))))
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(customer_gateway, "_load_vpc", lambda: (models, SimpleNamespace(VpcClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, cls, endpoint: client)
    monkeypatch.setattr(customer_gateway, "find_gateway", lambda *args: None)
    expected = {"CustomerGatewayId": "cgw-1", "CustomerGatewayName": "office", "IpAddress": "203.0.113.10"}
    waiter = MagicMock(return_value=expected)
    monkeypatch.setattr(customer_gateway, "wait_for_gateway", waiter)

    module_args(name="office", ip_address="203.0.113.10", state="present")
    result = run(customer_gateway.run_module)

    assert result["changed"] is True
    assert result["customer_gateway"]["CustomerGatewayId"] == "cgw-1"
    client.CreateCustomerGateway.assert_called_once()
    waiter.assert_called_once()


def test_existing_gateway_is_idempotent(monkeypatch):
    models = FakeModels()
    client = SimpleNamespace()
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(customer_gateway, "_load_vpc", lambda: (models, SimpleNamespace(VpcClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, cls, endpoint: client)
    current = {"CustomerGatewayId": "cgw-1", "CustomerGatewayName": "office", "IpAddress": "203.0.113.10"}
    monkeypatch.setattr(customer_gateway, "find_gateway", lambda *args: current)

    module_args(name="office", state="present")
    result = run(customer_gateway.run_module)

    assert result["changed"] is False
    assert result["customer_gateway"] == current


def test_check_mode_create_does_not_write(monkeypatch):
    models = FakeModels()
    client = SimpleNamespace(CreateCustomerGateway=MagicMock())
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(customer_gateway, "_load_vpc", lambda: (models, SimpleNamespace(VpcClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, cls, endpoint: client)
    monkeypatch.setattr(customer_gateway, "find_gateway", lambda *args: None)

    module_args(name="office", ip_address="203.0.113.10", state="present", _ansible_check_mode=True)
    result = run(customer_gateway.run_module)

    assert result["changed"] is True
    assert "diff" in result
    client.CreateCustomerGateway.assert_not_called()
