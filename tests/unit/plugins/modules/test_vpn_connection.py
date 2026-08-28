"""Tests for vpn_connection."""

from types import SimpleNamespace
from unittest.mock import MagicMock

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import vpn_connection
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import FakeModels, module_args, run


def params():
    return {
        "name": "office", "vpn_gateway_id": "vpngw-1", "customer_gateway_id": "cgw-1",
        "vpc_id": "vpc-1", "pre_shared_key": "secret", "rotate_pre_shared_key": False,
        "security_policy_databases": [{"local_cidr": "10.0.0.0/16", "remote_cidr": "192.168.0.0/16"}],
        "route_type": "Policy", "tags": {},
    }


def test_builders():
    models = FakeModels()
    request = vpn_connection.build_create_request(models, params())
    assert request.VpnGatewayId == "vpngw-1"
    assert request.SecurityPolicyDatabases[0].RemoteCidrBlock == ["192.168.0.0/16"]
    assert vpn_connection.build_delete_request(models, "vpngw-1", "vpnx-1").VpnConnectionId == "vpnx-1"


def test_create_main_path(monkeypatch):
    models = FakeModels()
    response = SimpleNamespace(VpnConnection=SimpleNamespace(VpnConnectionId="vpnx-1"))
    client = SimpleNamespace(CreateVpnConnection=MagicMock(return_value=response))
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(vpn_connection, "_load_vpc", lambda: (models, SimpleNamespace(VpcClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, cls, endpoint: client)
    monkeypatch.setattr(vpn_connection, "find_connection", lambda *args: None)
    expected = {"VpnConnectionId": "vpnx-1", "VpnConnectionName": "office"}
    monkeypatch.setattr(vpn_connection, "wait_for_connection", MagicMock(return_value=expected))
    module_args(state="present", **params())
    result = run(vpn_connection.run_module)
    assert result["changed"] is True
    assert result["vpn_connection"]["VpnConnectionId"] == "vpnx-1"
    client.CreateVpnConnection.assert_called_once()


def test_check_mode_does_not_create(monkeypatch):
    models = FakeModels()
    client = SimpleNamespace(CreateVpnConnection=MagicMock())
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(vpn_connection, "_load_vpc", lambda: (models, SimpleNamespace(VpcClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, cls, endpoint: client)
    monkeypatch.setattr(vpn_connection, "find_connection", lambda *args: None)
    module_args(state="present", _ansible_check_mode=True, **params())
    result = run(vpn_connection.run_module)
    assert result["changed"] is True
    assert "diff" in result
    client.CreateVpnConnection.assert_not_called()
