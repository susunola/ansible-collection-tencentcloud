# -*- coding: utf-8 -*-
"""Shared resolution semantics for the VPC resource family.

Every ``find_*`` helper in this family used to hand back
``response.XxxSet[0]`` after a **fuzzy** server-side name filter, so a task
that said ``name: prod`` could silently manage ``prod-old``. These tests pin
the contract the shared resolver now gives every one of them:

* an exact name wins over a fuzzy neighbour;
* an explicit ID ignores unrelated rows the fuzzy filter dragged in;
* a single fuzzy candidate is still accepted, so existing playbooks keep
  working;
* two or more candidates fail with ``ambiguous=true`` and the candidate list.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type
import pytest
from ansible_collections.susunola.tencentcloud.plugins.modules import (
    customer_gateway,
    dc_direct_connect,
    dc_direct_connect_tunnel,
    nat_gateway_rule,
    network_acl,
    network_interface,
    peering_connection,
    vpc_flow_log,
    vpn_connection,
    vpn_gateway,
)


class ResolutionFailed(Exception):
    """Raised by ``FakeModule.fail_json`` so tests can inspect the payload."""


class FakeFilter(object):
    def __init__(self):
        self.Name = None
        self.Values = None


class FakeRequest(object):
    pass


class Record(object):
    """Mimics an SDK model object; ``find_*`` only ever calls ``_serialize``."""

    def __init__(self, **fields):
        self._fields = fields

    def _serialize(self, allow_none=True):
        return dict(self._fields)


class FakeModule(object):
    def __init__(self):
        self.params = {"retries": 2, "waiter_timeout": 1}

    def sdk_call(self, operation, request):
        return operation(request)

    def fail_json(self, **kwargs):
        raise ResolutionFailed(kwargs)


def _response(set_name, items, total_attr, total):
    return type("Response", (), {set_name: items, total_attr: total})()


class FakeClient(object):
    """Answers a single Describe* method with a fixed list of pages."""

    def __init__(self, method, set_name, pages, total_attr="TotalCount"):
        self.calls = []
        self._empty = _response(set_name, [], total_attr, 0)
        self._pages = [_response(set_name, page, total_attr, len(page)) for page in pages]
        setattr(self, method, self._describe)

    def _describe(self, request):
        self.calls.append(request)
        return self._pages.pop(0) if self._pages else self._empty


class Spec(object):
    """One member of the VPC family, wired up for the shared assertions."""

    def __init__(self, key, find, method, set_name, request_name, id_field, name_field,
                 call, by_name=True, total_attr="TotalCount"):
        self.key = key
        self.find = find
        self.method = method
        self.set_name = set_name
        self.request_name = request_name
        self.id_field = id_field
        self.name_field = name_field
        self.call = call
        self.by_name = by_name
        self.total_attr = total_attr

    @property
    def models(self):
        return type("FakeModels", (), {"Filter": FakeFilter, self.request_name: FakeRequest})

    def record(self, resource_id, name, **extra):
        fields = {self.id_field: resource_id, self.name_field: name}
        fields.update(extra)
        return Record(**fields)

    def resolve(self, records, id_value=None, name_value=None):
        client = FakeClient(self.method, self.set_name, [records], self.total_attr)
        module = FakeModule()
        return self.call(self.find, module, client, self.models, id_value, name_value)


SPECS = [
    Spec(
        "vpn_gateway", vpn_gateway.find_gateway, "DescribeVpnGateways", "VpnGatewaySet",
        "DescribeVpnGatewaysRequest", "VpnGatewayId", "VpnGatewayName",
        lambda find, module, client, models, id_value, name_value: find(module, client, models, id_value, name_value, None),
    ),
    Spec(
        "peering_connection", peering_connection.find_connection, "DescribeVpcPeeringConnections",
        "PeerConnectionSet", "DescribeVpcPeeringConnectionsRequest", "PeeringConnectionId", "PeeringConnectionName",
        lambda find, module, client, models, id_value, name_value: find(module, client, models, id_value, name_value, None),
    ),
    Spec(
        "customer_gateway", customer_gateway.find_gateway, "DescribeCustomerGateways", "CustomerGatewaySet",
        "DescribeCustomerGatewaysRequest", "CustomerGatewayId", "CustomerGatewayName",
        lambda find, module, client, models, id_value, name_value: find(module, client, models, id_value, name_value),
    ),
    Spec(
        "network_interface", network_interface.find_interface, "DescribeNetworkInterfaces", "NetworkInterfaceSet",
        "DescribeNetworkInterfacesRequest", "NetworkInterfaceId", "NetworkInterfaceName",
        lambda find, module, client, models, id_value, name_value: find(module, client, models, id_value, None, name_value),
    ),
    Spec(
        "nat_gateway_rule", nat_gateway_rule.find_gateway, "DescribeNatGateways", "NatGatewaySet",
        "DescribeNatGatewaysRequest", "NatGatewayId", "NatGatewayName",
        lambda find, module, client, models, id_value, name_value: find(module, client, models, id_value),
        by_name=False,
    ),
    Spec(
        "network_acl", network_acl.find_acl, "DescribeNetworkAcls", "NetworkAclSet",
        "DescribeNetworkAclsRequest", "NetworkAclId", "NetworkAclName",
        lambda find, module, client, models, id_value, name_value: find(module, client, models, id_value, name_value, None),
    ),
    Spec(
        "vpc_flow_log", vpc_flow_log.find_flow_log, "DescribeFlowLogs", "FlowLog",
        "DescribeFlowLogsRequest", "FlowLogId", "FlowLogName",
        lambda find, module, client, models, id_value, name_value: find(module, client, models, "vpc-1", id_value, name_value),
        total_attr="TotalNum",
    ),
    Spec(
        "vpn_connection", vpn_connection.find_connection, "DescribeVpnConnections", "VpnConnectionSet",
        "DescribeVpnConnectionsRequest", "VpnConnectionId", "VpnConnectionName",
        lambda find, module, client, models, id_value, name_value: find(module, client, models, id_value, name_value, None),
    ),
    Spec(
        "dc_direct_connect", dc_direct_connect.find, "DescribeDirectConnects", "DirectConnectSet",
        "DescribeDirectConnectsRequest", "DirectConnectId", "DirectConnectName",
        lambda find, module, client, models, id_value, name_value: find(
            module, client, models, {"direct_connect_id": id_value, "name": name_value}),
    ),
    Spec(
        "dc_direct_connect_tunnel", dc_direct_connect_tunnel.find, "DescribeDirectConnectTunnels",
        "DirectConnectTunnelSet", "DescribeDirectConnectTunnelsRequest", "DirectConnectTunnelId",
        "DirectConnectTunnelName",
        lambda find, module, client, models, id_value, name_value: find(
            module, client, models, {"tunnel_id": id_value, "name": name_value}),
    ),
]

SPEC_IDS = [spec.key for spec in SPECS]


@pytest.mark.parametrize("spec", SPECS, ids=SPEC_IDS)
def test_exact_name_wins_over_fuzzy_neighbour(spec):
    # "prod" is listed second: the old first-match helper picked "prod-old".
    if not spec.by_name:
        pytest.skip("lookup is by id only")
    found = spec.resolve([spec.record("x-1", "prod-old"), spec.record("x-2", "prod")], name_value="prod")
    assert found[spec.id_field] == "x-2"


@pytest.mark.parametrize("spec", SPECS, ids=SPEC_IDS)
def test_single_fuzzy_candidate_is_still_accepted(spec):
    if not spec.by_name:
        pytest.skip("lookup is by id only")
    found = spec.resolve([spec.record("x-1", "prod-east")], name_value="prod")
    assert found[spec.id_field] == "x-1"


@pytest.mark.parametrize("spec", SPECS, ids=SPEC_IDS)
def test_ambiguous_name_fails_with_candidates(spec):
    if not spec.by_name:
        pytest.skip("lookup is by id only")
    records = [spec.record("x-1", "prod-a"), spec.record("x-2", "prod-b")]
    with pytest.raises(ResolutionFailed) as exc:
        spec.resolve(records, name_value="prod")
    payload = exc.value.args[0]
    assert payload["ambiguous"] is True
    assert payload["match_count"] == 2
    assert {item["id"] for item in payload["matches"]} == {"x-1", "x-2"}


@pytest.mark.parametrize("spec", SPECS, ids=SPEC_IDS)
def test_id_lookup_ignores_unrelated_rows(spec):
    records = [spec.record("x-1", "prod"), spec.record("x-2", "prod-2")]
    found = spec.resolve(records, id_value="x-2")
    assert found[spec.id_field] == "x-2"


@pytest.mark.parametrize("spec", SPECS, ids=SPEC_IDS)
def test_unknown_id_returns_none(spec):
    assert spec.resolve([spec.record("x-1", "prod")], id_value="x-9") is None


# ---------------------------------------------------------------------------
# module-specific scopes that are not an ID, a name or a tag
# ---------------------------------------------------------------------------
def _resolve_interface(records, subnet_id=None, name=None, interface_id=None):
    client = FakeClient("DescribeNetworkInterfaces", "NetworkInterfaceSet", [records])
    models = type("FakeModels", (), {"Filter": FakeFilter, "DescribeNetworkInterfacesRequest": FakeRequest})
    return network_interface.find_interface(FakeModule(), client, models, interface_id, subnet_id, name)


def _eni(interface_id, name, subnet_id):
    return Record(NetworkInterfaceId=interface_id, NetworkInterfaceName=name, SubnetId=subnet_id)


def test_find_interface_subnet_scope_narrows_the_candidate_set():
    records = [_eni("eni-1", "app", "subnet-1"), _eni("eni-2", "app", "subnet-2")]
    # Without a subnet the two same-named ENIs are genuinely ambiguous.
    with pytest.raises(ResolutionFailed) as exc:
        _resolve_interface(records, name="app")
    assert exc.value.args[0]["ambiguous"] is True

    found = _resolve_interface(records, subnet_id="subnet-2", name="app")
    assert found["NetworkInterfaceId"] == "eni-2"


def test_find_tunnel_strips_bgp_auth_key():
    records = [
        Record(
            DirectConnectTunnelId="dcx-1", DirectConnectTunnelName="tunnel-1",
            BgpPeer={"Asn": 65001, "AuthKey": "secret"},
        ),
    ]
    found = _tunnel_find(records, name="tunnel-1")
    assert "AuthKey" not in found["BgpPeer"]


def _tunnel_find(records, name=None, tunnel_id=None, direct_connect_id=None):
    client = FakeClient("DescribeDirectConnectTunnels", "DirectConnectTunnelSet", [records])
    models = type("FakeModels", (), {"Filter": FakeFilter, "DescribeDirectConnectTunnelsRequest": FakeRequest})
    params = {"tunnel_id": tunnel_id, "name": name, "direct_connect_id": direct_connect_id}
    return dc_direct_connect_tunnel.find(FakeModule(), client, models, params)


def test_find_tunnel_scopes_to_direct_connect_id():
    records = [
        Record(DirectConnectTunnelId="dcx-1", DirectConnectTunnelName="shared", DirectConnectId="dc-1"),
        Record(DirectConnectTunnelId="dcx-2", DirectConnectTunnelName="shared", DirectConnectId="dc-2"),
    ]
    found = _tunnel_find(records, name="shared", direct_connect_id="dc-2")
    assert found["DirectConnectTunnelId"] == "dcx-2"
