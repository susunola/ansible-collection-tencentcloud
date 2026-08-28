"""Main-path unit tests for the nat_gateway_rule module (run_module level)."""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import nat_gateway_rule
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

DNAT = {
    "IpProtocol": "TCP", "PublicIpAddress": "114.182.81.73", "PublicPort": 8989,
    "PrivateIpAddress": "10.80.80.41", "PrivatePort": 8989, "Description": "web",
}

SNAT = {
    "NatGatewaySnatId": "snat-1", "ResourceType": "CVM", "ResourceId": "cvm-1",
    "PrivateIpAddress": "10.0.0.5", "PublicIpAddresses": ["180.12.59.43"],
    "Description": "prod",
}


class FakeVpcClient(object):
    def __init__(self, gateway=True, dnat=None, snat=None):
        self.gateway_present = gateway
        self.dnat = list(dnat or [])
        self.snat = list(snat or [])
        self.CreateNatGatewayDestinationIpPortTranslationNatRule = MagicMock(
            side_effect=self._create_dnat)
        self.DeleteNatGatewayDestinationIpPortTranslationNatRule = MagicMock(
            side_effect=self._delete_dnat)
        self.CreateNatGatewaySourceIpTranslationNatRule = MagicMock(
            side_effect=self._create_snat)
        self.DeleteNatGatewaySourceIpTranslationNatRule = MagicMock(
            side_effect=self._delete_snat)

    def DescribeNatGateways(self, request):
        if not self.gateway_present:
            return SimpleNamespace(NatGatewaySet=[])
        return SimpleNamespace(NatGatewaySet=[
            FakeResource({"NatGatewayId": request.NatGatewayIds[0],
                          "NatGatewayName": "prod-nat", "State": "AVAILABLE"})
        ])

    def DescribeNatGatewayDestinationIpPortTranslationNatRules(self, request):
        return SimpleNamespace(
            NatGatewayDestinationIpPortTranslationNatRuleSet=[FakeResource(r) for r in self.dnat])

    def DescribeNatGatewaySourceIpTranslationNatRules(self, request):
        return SimpleNamespace(
            SourceIpTranslationNatRuleSet=[FakeResource(r) for r in self.snat])

    def _create_dnat(self, request):
        for rule in request.DestinationIpPortTranslationNatRules:
            self.dnat.append({
                "IpProtocol": rule.IpProtocol, "PublicIpAddress": rule.PublicIpAddress,
                "PublicPort": rule.PublicPort, "PrivateIpAddress": rule.PrivateIpAddress,
                "PrivatePort": rule.PrivatePort, "Description": rule.Description,
            })
        return SimpleNamespace()

    def _delete_dnat(self, request):
        for rule in request.DestinationIpPortTranslationNatRules:
            self.dnat = [r for r in self.dnat
                         if not (r["PublicPort"] == rule.PublicPort
                                 and r["PrivatePort"] == rule.PrivatePort
                                 and r["PublicIpAddress"] == rule.PublicIpAddress
                                 and r["PrivateIpAddress"] == rule.PrivateIpAddress
                                 and r["IpProtocol"] == rule.IpProtocol)]

    def _create_snat(self, request):
        for rule in request.SourceIpTranslationNatRules:
            self.snat.append({
                "NatGatewaySnatId": "snat-%d" % (len(self.snat) + 1),
                "ResourceType": rule.ResourceType, "ResourceId": rule.ResourceId,
                "PrivateIpAddress": rule.PrivateIpAddress,
                "PublicIpAddresses": list(rule.PublicIpAddresses),
                "Description": rule.Description,
            })
        return SimpleNamespace()

    def _delete_snat(self, request):
        ids = set(request.NatGatewaySnatIds or [])
        self.snat = [r for r in self.snat if r["NatGatewaySnatId"] not in ids]


@pytest.fixture
def client(monkeypatch):
    fake = FakeVpcClient()
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(
        nat_gateway_rule, "_load_vpc",
        lambda: (FakeModels(), SimpleNamespace(VpcClient=object)),
    )
    monkeypatch.setattr(
        TencentCloudModule, "create_client",
        lambda self, client_class, endpoint: fake,
    )
    return fake


def test_creates_missing_rules(client):
    module_args(
        nat_gateway_id="nat-1",
        dnat_rules=[{
            "ip_protocol": "tcp", "public_ip_address": "114.182.81.73",
            "public_port": 8989, "private_ip_address": "10.80.80.41",
            "private_port": 8989, "description": "web",
        }],
        snat_rules=[{
            "resource_type": "cvm", "resource_id": "cvm-1",
            "private_ip_address": "10.0.0.5",
            "public_ip_addresses": ["180.12.59.43"], "description": "prod",
        }],
    )
    result = run(nat_gateway_rule.run_module)
    assert result["changed"] is True
    assert result["msg"] == "NAT gateway rules reconciled"
    client.CreateNatGatewayDestinationIpPortTranslationNatRule.assert_called_once()
    client.CreateNatGatewaySourceIpTranslationNatRule.assert_called_once()
    assert len(result["dnat_rules"]) == 1
    assert len(result["snat_rules"]) == 1


def test_second_run_is_idempotent(client):
    client.dnat = [dict(DNAT)]
    client.snat = [dict(SNAT)]
    module_args(
        nat_gateway_id="nat-1",
        dnat_rules=[{
            "ip_protocol": "TCP", "public_ip_address": "114.182.81.73",
            "public_port": 8989, "private_ip_address": "10.80.80.41",
            "private_port": 8989, "description": "web",
        }],
        snat_rules=[{
            "resource_type": "CVM", "resource_id": "cvm-1",
            "private_ip_address": "10.0.0.5",
            "public_ip_addresses": ["180.12.59.43"], "description": "prod",
        }],
    )
    result = run(nat_gateway_rule.run_module)
    assert result["changed"] is False
    assert result["msg"] == "NAT gateway rules are up to date"
    client.CreateNatGatewayDestinationIpPortTranslationNatRule.assert_not_called()
    client.DeleteNatGatewaySourceIpTranslationNatRule.assert_not_called()


def test_purge_deletes_surplus(client):
    client.dnat = [dict(DNAT), dict(DNAT, PublicPort=9999)]
    module_args(
        nat_gateway_id="nat-1",
        dnat_rules=[{
            "ip_protocol": "TCP", "public_ip_address": "114.182.81.73",
            "public_port": 8989, "private_ip_address": "10.80.80.41",
            "private_port": 8989, "description": "web",
        }],
    )
    result = run(nat_gateway_rule.run_module)
    assert result["changed"] is True
    client.DeleteNatGatewayDestinationIpPortTranslationNatRule.assert_called_once()
    request = client.DeleteNatGatewayDestinationIpPortTranslationNatRule.call_args[0][0]
    assert [r.PublicPort for r in request.DestinationIpPortTranslationNatRules] == [9999]
    assert len(result["dnat_rules"]) == 1


def test_purge_false_keeps_surplus(client):
    client.dnat = [dict(DNAT), dict(DNAT, PublicPort=9999)]
    module_args(
        purge=False,
        nat_gateway_id="nat-1",
        dnat_rules=[{
            "ip_protocol": "TCP", "public_ip_address": "114.182.81.73",
            "public_port": 8989, "private_ip_address": "10.80.80.41",
            "private_port": 8989, "description": "web",
        }],
    )
    result = run(nat_gateway_rule.run_module)
    assert result["changed"] is False
    assert len(result["dnat_rules"]) == 2
    client.DeleteNatGatewayDestinationIpPortTranslationNatRule.assert_not_called()


def test_check_mode_reports_changed_without_writes(client):
    module_args(
        _ansible_check_mode=True,
        nat_gateway_id="nat-1",
        dnat_rules=[{
            "ip_protocol": "TCP", "public_ip_address": "114.182.81.73",
            "public_port": 8989, "private_ip_address": "10.80.80.41",
            "private_port": 8989,
        }],
    )
    result = run(nat_gateway_rule.run_module)
    assert result["changed"] is True
    assert result["msg"].startswith("Would reconcile")
    assert "diff" in result
    client.CreateNatGatewayDestinationIpPortTranslationNatRule.assert_not_called()
    client.CreateNatGatewaySourceIpTranslationNatRule.assert_not_called()


def test_fails_when_gateway_missing(client):
    client.gateway_present = False
    module_args(
        nat_gateway_id="nat-9",
        dnat_rules=[{
            "ip_protocol": "TCP", "public_ip_address": "114.182.81.73",
            "public_port": 8989, "private_ip_address": "10.80.80.41",
            "private_port": 8989,
        }],
    )
    with pytest.raises(AnsibleFailJson) as exc:
        run(nat_gateway_rule.run_module)
    assert "not found" in exc.value.args[0]["msg"]


def test_snat_public_ip_change_replaces_rule(client):
    client.snat = [dict(SNAT)]
    module_args(
        nat_gateway_id="nat-1",
        snat_rules=[{
            "resource_type": "CVM", "resource_id": "cvm-1",
            "private_ip_address": "10.0.0.5",
            "public_ip_addresses": ["9.9.9.9"], "description": "prod",
        }],
    )
    result = run(nat_gateway_rule.run_module)
    assert result["changed"] is True
    # Delete the old rule by its snat id, then create the new one
    client.DeleteNatGatewaySourceIpTranslationNatRule.assert_called_once()
    delete_request = client.DeleteNatGatewaySourceIpTranslationNatRule.call_args[0][0]
    assert delete_request.NatGatewaySnatIds == ["snat-1"]
    client.CreateNatGatewaySourceIpTranslationNatRule.assert_called_once()
    create_request = client.CreateNatGatewaySourceIpTranslationNatRule.call_args[0][0]
    assert create_request.SourceIpTranslationNatRules[0].PublicIpAddresses == ["9.9.9.9"]
    assert [r["PublicIpAddresses"] for r in result["snat_rules"]] == [["9.9.9.9"]]


def test_empty_desired_with_purge_removes_everything(client):
    client.dnat = [dict(DNAT)]
    client.snat = [dict(SNAT)]
    module_args(nat_gateway_id="nat-1")
    result = run(nat_gateway_rule.run_module)
    assert result["changed"] is True
    client.DeleteNatGatewayDestinationIpPortTranslationNatRule.assert_called_once()
    client.DeleteNatGatewaySourceIpTranslationNatRule.assert_called_once()
    assert result["dnat_rules"] == []
    assert result["snat_rules"] == []
