"""Main-path unit tests for the security_group_rule module (run_module level)."""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import security_group_rule
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    FakeModels,
    FakeResource,
    module_args,
    run,
)

RULE = {
    "protocol": "TCP",
    "port": "443",
    "cidr_block": "0.0.0.0/0",
    "action": "ACCEPT",
    "policy_description": "HTTPS from anywhere",
    "direction": "ingress",
}

CURRENT_POLICY = {
    "Protocol": "TCP",
    "Port": "443",
    "CidrBlock": "0.0.0.0/0",
    "Action": "ACCEPT",
    "PolicyDescription": "HTTPS from anywhere",
}


def _dump(policy):
    return {
        "Protocol": policy.Protocol,
        "Port": policy.Port,
        "CidrBlock": policy.CidrBlock,
        "Action": policy.Action,
        "PolicyDescription": getattr(policy, "PolicyDescription", ""),
    }


def _key(policy_dict):
    return (policy_dict["Action"], policy_dict["Protocol"],
            policy_dict["CidrBlock"], policy_dict["Port"])


class FakeVpcClient(object):
    def __init__(self, ingress=None, egress=None):
        self.ingress = list(ingress or [])
        self.egress = list(egress or [])
        self.CreateSecurityGroupPolicies = MagicMock(side_effect=self._create)
        self.DeleteSecurityGroupPolicies = MagicMock(side_effect=self._delete)

    def DescribeSecurityGroupPolicies(self, request):
        policy_set = SimpleNamespace(
            Ingress=[FakeResource(p) for p in self.ingress],
            Egress=[FakeResource(p) for p in self.egress],
        )
        return SimpleNamespace(SecurityGroupPolicySet=policy_set)

    def _create(self, request):
        for policy in request.SecurityGroupPolicySet.Ingress or []:
            self.ingress.append(_dump(policy))
        for policy in request.SecurityGroupPolicySet.Egress or []:
            self.egress.append(_dump(policy))
        return SimpleNamespace()

    def _delete(self, request):
        ingress_victims = {_key(_dump(p)) for p in request.SecurityGroupPolicySet.Ingress or []}
        egress_victims = {_key(_dump(p)) for p in request.SecurityGroupPolicySet.Egress or []}
        self.ingress = [p for p in self.ingress if _key(p) not in ingress_victims]
        self.egress = [p for p in self.egress if _key(p) not in egress_victims]
        return SimpleNamespace()


@pytest.fixture
def client(monkeypatch):
    fake = FakeVpcClient()
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(
        security_group_rule, "_load_vpc",
        lambda: (FakeModels(), SimpleNamespace(VpcClient=object)),
    )
    monkeypatch.setattr(
        TencentCloudModule, "create_client",
        lambda self, client_class, endpoint: fake,
    )
    return fake


def test_create_rules_reports_changed(client):
    module_args(security_group_id="sg-existing1", rules=[RULE])
    result = run(security_group_rule.run_module)
    assert result["changed"] is True
    assert result["rules"][0]["port"] == "443"
    client.CreateSecurityGroupPolicies.assert_called_once()
    assert "diff" not in result


def test_second_run_is_idempotent(client):
    client.ingress.append(dict(CURRENT_POLICY))
    module_args(security_group_id="sg-existing1", rules=[RULE])
    result = run(security_group_rule.run_module)
    assert result["changed"] is False
    assert result["rules"][0]["policy_description"] == "HTTPS from anywhere"
    client.CreateSecurityGroupPolicies.assert_not_called()
    client.DeleteSecurityGroupPolicies.assert_not_called()


def test_purge_deletes_unlisted_rules(client):
    client.ingress.append(dict(CURRENT_POLICY))
    module_args(security_group_id="sg-existing1", rules=[])
    result = run(security_group_rule.run_module)
    assert result["changed"] is True
    client.DeleteSecurityGroupPolicies.assert_called_once()
    assert client.ingress == []


def test_empty_rules_on_empty_group_is_unchanged(client):
    module_args(security_group_id="sg-existing1", rules=[])
    result = run(security_group_rule.run_module)
    assert result["changed"] is False
    client.CreateSecurityGroupPolicies.assert_not_called()
    client.DeleteSecurityGroupPolicies.assert_not_called()


def test_check_mode_makes_no_sdk_writes(client):
    module_args(
        security_group_id="sg-existing1", rules=[RULE],
        _ansible_check_mode=True,
    )
    result = run(security_group_rule.run_module)
    assert result["changed"] is True
    assert "diff" in result
    client.CreateSecurityGroupPolicies.assert_not_called()
    client.DeleteSecurityGroupPolicies.assert_not_called()


def test_diff_mode_includes_diff(client):
    module_args(
        security_group_id="sg-existing1", rules=[RULE],
        _ansible_diff=True,
    )
    result = run(security_group_rule.run_module)
    assert result["changed"] is True
    # build_diff strips empty containers, so an empty rule set is omitted.
    assert result["diff"]["before"] == {"security_group_id": "sg-existing1"}
    assert result["diff"]["after"]["rules"][0]["port"] == "443"
    client.CreateSecurityGroupPolicies.assert_called_once()
