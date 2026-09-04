"""Unit tests for the nat_gateway_rule write module helpers."""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from ansible_collections.susunola.tencentcloud.plugins.modules.nat_gateway_rule import (
    build_dnat_describe_request,
    build_dnat_rule,
    build_snat_describe_request,
    build_snat_rule,
    find_gateway,
    list_dnat_rules,
    list_snat_rules,
    normalize_dnat,
    normalize_snat,
    reconcile,
    _create_dnat,
    _create_snat,
    _delete_dnat,
    _delete_snat,
    _dnat_key,
    _snat_compare,
    _snat_key,
)


class FakeRequest(object):
    pass


class FakeModels(object):
    DescribeNatGatewaysRequest = FakeRequest
    DescribeNatGatewayDestinationIpPortTranslationNatRulesRequest = FakeRequest
    DescribeNatGatewaySourceIpTranslationNatRulesRequest = FakeRequest
    CreateNatGatewayDestinationIpPortTranslationNatRuleRequest = FakeRequest
    DeleteNatGatewayDestinationIpPortTranslationNatRuleRequest = FakeRequest
    CreateNatGatewaySourceIpTranslationNatRuleRequest = FakeRequest
    DeleteNatGatewaySourceIpTranslationNatRuleRequest = FakeRequest
    DestinationIpPortTranslationNatRule = FakeRequest
    SourceIpTranslationNatRule = FakeRequest


class FakeRule(object):
    def __init__(self, data):
        self._data = dict(data)

    def _serialize(self, allow_none=True):
        return dict(self._data)


class FakeGateway(object):
    def __init__(self, nat_id, name="prod-nat"):
        self.NatGatewayId = nat_id
        self.NatGatewayName = name
        self.State = "AVAILABLE"

    def _serialize(self, allow_none=True):
        return {
            "NatGatewayId": self.NatGatewayId,
            "NatGatewayName": self.NatGatewayName,
            "State": self.State,
        }


class FakeDescribeResponse(object):
    def __init__(self, rules):
        self.NatGatewayDestinationIpPortTranslationNatRuleSet = rules
        self.SourceIpTranslationNatRuleSet = rules


class FakeGatewayResponse(object):
    def __init__(self, gateways):
        self.NatGatewaySet = gateways


class FakeClient(object):
    def __init__(self, gateway_response=None, dnat_rules=None, snat_rules=None):
        self.gateway_response = gateway_response
        self.dnat_rules = dnat_rules or []
        self.snat_rules = snat_rules or []
        self.calls = []

    def DescribeNatGateways(self, request):
        self.calls.append(("DescribeNatGateways", request))
        return self.gateway_response

    def DescribeNatGatewayDestinationIpPortTranslationNatRules(self, request):
        self.calls.append(("DescribeDNAT", request))
        return FakeDescribeResponse(self.dnat_rules)

    def DescribeNatGatewaySourceIpTranslationNatRules(self, request):
        self.calls.append(("DescribeSNAT", request))
        return FakeDescribeResponse(self.snat_rules)

    def CreateNatGatewayDestinationIpPortTranslationNatRule(self, request):
        self.calls.append(("CreateDNAT", request))

    def DeleteNatGatewayDestinationIpPortTranslationNatRule(self, request):
        self.calls.append(("DeleteDNAT", request))

    def CreateNatGatewaySourceIpTranslationNatRule(self, request):
        self.calls.append(("CreateSNAT", request))

    def DeleteNatGatewaySourceIpTranslationNatRule(self, request):
        self.calls.append(("DeleteSNAT", request))


class FakeModule(object):
    def __init__(self):
        self.params = {"retries": 2}

    def sdk_call(self, operation, request):
        return operation(request)

    def fail_json(self, *args, **kwargs):
        if args:
            kwargs["msg"] = args[0]
        kwargs["failed"] = True
        raise SystemExit(kwargs)


DNAT_USER = {
    "ip_protocol": "tcp",
    "public_ip_address": "114.182.81.73",
    "public_port": 8989,
    "private_ip_address": "10.80.80.41",
    "private_port": 8989,
    "description": "web",
}

SNAT_USER = {
    "resource_type": "cvm",
    "resource_id": "cvm-1",
    "private_ip_address": "10.0.0.5",
    "public_ip_addresses": ["180.12.59.43", "180.12.59.44"],
    "description": "prod",
}


def test_normalize_dnat_uppercases_protocol():
    rule = normalize_dnat(DNAT_USER)
    assert rule["IpProtocol"] == "TCP"
    assert rule["PublicPort"] == 8989
    assert rule["Description"] == "web"


def test_normalize_dnat_defaults_empty_description():
    user = dict(DNAT_USER, description=None)
    rule = normalize_dnat(user)
    assert rule["Description"] == ""


def test_normalize_snat_uppercases_type_and_sorts_ips():
    rule = normalize_snat(SNAT_USER)
    assert rule["ResourceType"] == "CVM"
    assert rule["PublicIpAddresses"] == ["180.12.59.43", "180.12.59.44"]
    assert "NatGatewaySnatId" not in rule


def test_dnat_key_is_attribute_tuple():
    key = _dnat_key(normalize_dnat(DNAT_USER))
    assert key == ("TCP", "114.182.81.73", 8989, "10.80.80.41", 8989)


def test_snat_key_ignores_public_ips_and_description():
    base = normalize_snat(SNAT_USER)
    moved = dict(base, PublicIpAddresses=["9.9.9.9"], Description="changed")
    assert _snat_key(base) == _snat_key(moved)


def test_build_dnat_rule_maps_comparison_shape_to_sdk():
    rule = build_dnat_rule(FakeModels, normalize_dnat(DNAT_USER))
    assert rule.IpProtocol == "TCP"
    assert rule.PublicIpAddress == "114.182.81.73"
    assert rule.PublicPort == 8989
    assert rule.PrivateIpAddress == "10.80.80.41"
    assert rule.PrivatePort == 8989
    assert rule.Description == "web"


def test_build_snat_rule_maps_comparison_shape_to_sdk():
    rule = build_snat_rule(FakeModels, normalize_snat(SNAT_USER))
    assert rule.ResourceType == "CVM"
    assert rule.ResourceId == "cvm-1"
    assert rule.PrivateIpAddress == "10.0.0.5"
    assert rule.PublicIpAddresses == ["180.12.59.43", "180.12.59.44"]
    assert rule.Description == "prod"


def test_build_dnat_describe_request_sends_ids_plural():
    request = build_dnat_describe_request(FakeModels, "nat-1")
    assert request.NatGatewayIds == ["nat-1"]
    assert request.Limit == 100


def test_build_snat_describe_request_sends_id_singular():
    request = build_snat_describe_request(FakeModels, "nat-1")
    assert request.NatGatewayId == "nat-1"
    assert request.Limit == 100


def test_find_gateway_returns_gateway():
    client = FakeClient(gateway_response=FakeGatewayResponse([FakeGateway("nat-1")]))
    module = FakeModule()
    gateway = find_gateway(module, client, FakeModels, "nat-1")
    assert gateway["NatGatewayId"] == "nat-1"


def test_find_gateway_returns_none_when_absent():
    client = FakeClient(gateway_response=FakeGatewayResponse([]))
    module = FakeModule()
    assert find_gateway(module, client, FakeModels, "nat-9") is None


def test_list_dnat_rules_returns_comparison_shape():
    current = [{
        "IpProtocol": "TCP", "PublicIpAddress": "1.2.3.4", "PublicPort": 80,
        "PrivateIpAddress": "10.0.0.8", "PrivatePort": 8080, "Description": None,
    }]
    client = FakeClient(dnat_rules=[FakeRule(current[0])])
    module = FakeModule()
    rules = list_dnat_rules(module, client, FakeModels, "nat-1")
    assert rules == [{
        "IpProtocol": "TCP", "PublicIpAddress": "1.2.3.4", "PublicPort": 80,
        "PrivateIpAddress": "10.0.0.8", "PrivatePort": 8080, "Description": "",
    }]


def test_list_snat_rules_keeps_snat_id_drops_output_fields():
    current = {
        "NatGatewaySnatId": "snat-1", "ResourceType": "CVM",
        "ResourceId": "cvm-1", "PrivateIpAddress": "10.0.0.5",
        "PublicIpAddresses": ["180.12.59.44", "180.12.59.43"],
        "Description": "prod", "NatGatewayId": "nat-1", "VpcId": "vpc-1",
        "CreatedTime": "2026-01-01",
    }
    client = FakeClient(snat_rules=[FakeRule(current)])
    module = FakeModule()
    rules = list_snat_rules(module, client, FakeModels, "nat-1")
    assert rules == [{
        "NatGatewaySnatId": "snat-1", "ResourceType": "CVM",
        "ResourceId": "cvm-1", "PrivateIpAddress": "10.0.0.5",
        "PublicIpAddresses": ["180.12.59.43", "180.12.59.44"],
        "Description": "prod",
    }]


def test_reconcile_creates_missing_rules():
    current = []
    desired = [normalize_dnat(DNAT_USER)]
    to_create, to_replace, to_delete = reconcile(current, desired, _dnat_key, lambda rule: rule)
    assert to_create == desired
    assert to_replace == []
    assert to_delete == []


def test_reconcile_noop_when_identical():
    current = [normalize_dnat(DNAT_USER)]
    to_create, to_replace, to_delete = reconcile(current, current, _dnat_key, lambda rule: rule)
    assert to_create == []
    assert to_replace == []
    assert to_delete == []


def test_reconcile_replaces_when_description_drift():
    current = [normalize_dnat(DNAT_USER)]
    changed = [dict(normalize_dnat(DNAT_USER), Description="renamed")]
    to_create, to_replace, to_delete = reconcile(current, changed, _dnat_key, lambda rule: rule)
    assert to_create == []
    assert list(to_replace) == [(current[0], changed[0])]
    assert to_delete == []


def test_reconcile_lists_surplus_for_delete():
    current = [normalize_dnat(DNAT_USER), normalize_dnat(dict(DNAT_USER, public_port=9999))]
    desired = [normalize_dnat(DNAT_USER)]
    to_create, to_replace, to_delete = reconcile(current, desired, _dnat_key, lambda rule: rule)
    assert to_create == []
    assert to_replace == []
    assert [rule["PublicPort"] for rule in to_delete] == [9999]


def test_reconcile_snat_ignores_output_snat_id():
    current = [dict(normalize_snat(SNAT_USER), NatGatewaySnatId="snat-1")]
    desired = [normalize_snat(SNAT_USER)]
    to_create, to_replace, to_delete = reconcile(current, desired, _snat_key, _snat_compare)
    assert to_create == []
    assert to_replace == []
    assert to_delete == []
    assert _snat_compare(current[0]) == _snat_compare(desired[0])


def test_reconcile_snat_replaces_when_public_ip_drift():
    current = [dict(normalize_snat(SNAT_USER), NatGatewaySnatId="snat-1")]
    desired = [dict(normalize_snat(SNAT_USER), PublicIpAddresses=["9.9.9.9"])]
    to_create, to_replace, to_delete = reconcile(current, desired, _snat_key, _snat_compare)
    assert to_create == []
    assert list(to_replace) == [(current[0], desired[0])]
    assert to_delete == []


def test_create_dnat_builds_request_with_rule_objects():
    client = FakeClient()
    module = FakeModule()
    _create_dnat(module, client, FakeModels, "nat-1", [normalize_dnat(DNAT_USER)])
    name, request = client.calls[-1]
    assert name == "CreateDNAT"
    assert request.NatGatewayId == "nat-1"
    assert request.DestinationIpPortTranslationNatRules[0].IpProtocol == "TCP"


def test_delete_dnat_builds_request_with_full_rule_objects():
    client = FakeClient()
    module = FakeModule()
    _delete_dnat(module, client, FakeModels, "nat-1", [normalize_dnat(DNAT_USER)])
    name, request = client.calls[-1]
    assert name == "DeleteDNAT"
    assert request.NatGatewayId == "nat-1"
    assert request.DestinationIpPortTranslationNatRules[0].PrivatePort == 8989


def test_create_snat_builds_request():
    client = FakeClient()
    module = FakeModule()
    _create_snat(module, client, FakeModels, "nat-1", [normalize_snat(SNAT_USER)])
    name, request = client.calls[-1]
    assert name == "CreateSNAT"
    assert request.NatGatewayId == "nat-1"
    assert request.SourceIpTranslationNatRules[0].ResourceId == "cvm-1"


def test_delete_snat_builds_request_with_ids():
    client = FakeClient()
    module = FakeModule()
    _delete_snat(module, client, FakeModels, "nat-1", ["snat-1", "snat-2"])
    name, request = client.calls[-1]
    assert name == "DeleteSNAT"
    assert request.NatGatewayId == "nat-1"
    assert request.NatGatewaySnatIds == ["snat-1", "snat-2"]
