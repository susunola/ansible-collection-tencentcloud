# -*- coding: utf-8 -*-
"""Shared resolution semantics across the rolled-out resource families.

Every ``find_*`` helper listed in ``SPECS`` used to hand back
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
    cdb_instance,
    clb_listener,
    clb_load_balancer,
    clb_rule,
    clb_target_group,
    customer_gateway,
    cynosdb_cluster,
    dc_direct_connect,
    dc_direct_connect_tunnel,
    dcdb_instance,
    elasticsearch_instance,
    mariadb_instance,
    mongodb_instance,
    nat_gateway_rule,
    network_acl,
    network_interface,
    peering_connection,
    postgresql_instance,
    redis_instance,
    sqlserver_instance,
    tdcpg_cluster,
    tke_cluster,
    tke_cluster_upgrade,
    tke_node_pool,
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


class Listener(object):
    """A CLB listener; ``clb_rule`` reads its forwarding rules off it."""

    def __init__(self, rules):
        self.Rules = rules


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
                 call, by_name=True, by_id=True, total_attr="TotalCount", wrap=None, extra_models=()):
        self.key = key
        self.find = find
        self.method = method
        self.set_name = set_name
        self.request_name = request_name
        self.id_field = id_field
        self.name_field = name_field
        self.call = call
        self.by_name = by_name
        self.by_id = by_id
        self.total_attr = total_attr
        # CLB forwarding rules are not a top-level Describe* result set: they
        # hang off the listener, so the records are wrapped in one.
        self.wrap = wrap
        # Products that build their scope with a differently named filter
        # model (CynosDB uses QueryFilter) need it on the fake models.
        self.extra_models = extra_models

    @property
    def models(self):
        namespace = {"Filter": FakeFilter, self.request_name: FakeRequest}
        for name in self.extra_models:
            namespace[name] = FakeFilter
        return type("FakeModels", (), namespace)

    def record(self, resource_id, name, **extra):
        fields = {self.id_field: resource_id, self.name_field: name}
        fields.update(extra)
        return Record(**fields)

    def resolve(self, records, id_value=None, name_value=None):
        page = self.wrap(records) if self.wrap else records
        client = FakeClient(self.method, self.set_name, [page], self.total_attr)
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
    Spec(
        "tke_cluster", tke_cluster.find_cluster, "DescribeClusters", "Clusters",
        "DescribeClustersRequest", "ClusterId", "ClusterName",
        lambda find, module, client, models, id_value, name_value: find(module, client, models, id_value, name_value),
    ),
    Spec(
        "tke_node_pool", tke_node_pool.find_node_pool, "DescribeClusterNodePools", "NodePoolSet",
        "DescribeClusterNodePoolsRequest", "NodePoolId", "Name",
        lambda find, module, client, models, id_value, name_value: find(module, client, models, "cls-1", name_value),
        by_id=False,
    ),
    Spec(
        "tke_cluster_upgrade", tke_cluster_upgrade.find_cluster, "DescribeClusters", "Clusters",
        "DescribeClustersRequest", "ClusterId", "ClusterName",
        lambda find, module, client, models, id_value, name_value: find(module, client, models, id_value),
        by_name=False,
    ),
    Spec(
        "clb_load_balancer", clb_load_balancer.find_load_balancer, "DescribeLoadBalancers", "LoadBalancerSet",
        "DescribeLoadBalancersRequest", "LoadBalancerId", "LoadBalancerName",
        lambda find, module, client, models, id_value, name_value: find(module, client, models, id_value, name_value, None),
    ),
    Spec(
        "clb_target_group", clb_target_group.find_group, "DescribeTargetGroups", "TargetGroupSet",
        "DescribeTargetGroupsRequest", "TargetGroupId", "TargetGroupName",
        lambda find, module, client, models, id_value, name_value: find(module, client, models, id_value, name_value, None),
    ),
    Spec(
        "clb_listener", clb_listener.find_listener, "DescribeListeners", "Listeners",
        "DescribeListenersRequest", "ListenerId", "ListenerName",
        lambda find, module, client, models, id_value, name_value: find(module, client, models, "lb-1", id_value, None, None),
        by_name=False,
    ),
    Spec(
        "clb_rule", clb_rule.find_rule, "DescribeListeners", "Listeners",
        "DescribeListenersRequest", "LocationId", "Url",
        lambda find, module, client, models, id_value, name_value: find(
            module, client, models, "lb-1", "lbl-1", id_value, None, None),
        by_name=False,
        wrap=lambda records: [Listener(records)],
    ),
    # --- database family ------------------------------------------------
    Spec(
        "cdb_instance", cdb_instance.find_instance, "DescribeDBInstances", "Items",
        "DescribeDBInstancesRequest", "InstanceId", "InstanceName",
        lambda find, module, client, models, id_value, name_value: find(module, client, models, id_value, name_value),
    ),
    Spec(
        "redis_instance", redis_instance.find_instance, "DescribeInstances", "InstanceSet",
        "DescribeInstancesRequest", "InstanceId", "InstanceName",
        lambda find, module, client, models, id_value, name_value: find(module, client, models, id_value, name_value),
    ),
    Spec(
        "mongodb_instance", mongodb_instance.find_instance, "DescribeDBInstances", "InstanceDetails",
        "DescribeDBInstancesRequest", "InstanceId", "InstanceName",
        lambda find, module, client, models, id_value, name_value: find(module, client, models, id_value, name_value),
    ),
    Spec(
        "elasticsearch_instance", elasticsearch_instance.find_instance, "DescribeInstances", "InstanceList",
        "DescribeInstancesRequest", "InstanceId", "InstanceName",
        lambda find, module, client, models, id_value, name_value: find(module, client, models, id_value, name_value),
    ),
    Spec(
        "sqlserver_instance", sqlserver_instance.find, "DescribeDBInstances", "DBInstances",
        "DescribeDBInstancesRequest", "InstanceId", "Name",
        lambda find, module, client, models, id_value, name_value: find(
            module, client, models, {"instance_id": id_value, "name": name_value}),
    ),
    Spec(
        "mariadb_instance", mariadb_instance.find, "DescribeDBInstances", "Instances",
        "DescribeDBInstancesRequest", "InstanceId", "InstanceName",
        lambda find, module, client, models, id_value, name_value: find(
            module, client, models, {"instance_id": id_value, "name": name_value}),
    ),
    Spec(
        "dcdb_instance", dcdb_instance.find, "DescribeDCDBInstances", "Instances",
        "DescribeDCDBInstancesRequest", "InstanceId", "InstanceName",
        lambda find, module, client, models, id_value, name_value: find(
            module, client, models, {"instance_id": id_value, "name": name_value}),
    ),
    Spec(
        "postgresql_instance", postgresql_instance.find, "DescribeDBInstances", "DBInstanceSet",
        "DescribeDBInstancesRequest", "DBInstanceId", "DBInstanceName",
        lambda find, module, client, models, id_value, name_value: find(
            module, client, models, {"instance_id": id_value, "name": name_value}),
    ),
    Spec(
        "cynosdb_cluster", cynosdb_cluster.find, "DescribeClusters", "ClusterSet",
        "DescribeClustersRequest", "ClusterId", "ClusterName",
        lambda find, module, client, models, id_value, name_value: find(
            module, client, models, {"cluster_id": id_value, "name": name_value}),
        extra_models=("QueryFilter",),
    ),
    Spec(
        "tdcpg_cluster", tdcpg_cluster.find, "DescribeClusters", "ClusterSet",
        "DescribeClustersRequest", "ClusterId", "ClusterName",
        lambda find, module, client, models, id_value, name_value: find(
            module, client, models, {"cluster_id": id_value, "name": name_value}),
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
    if not spec.by_id:
        pytest.skip("lookup is by name only")
    records = [spec.record("x-1", "prod"), spec.record("x-2", "prod-2")]
    found = spec.resolve(records, id_value="x-2")
    assert found[spec.id_field] == "x-2"


@pytest.mark.parametrize("spec", SPECS, ids=SPEC_IDS)
def test_unknown_id_returns_none(spec):
    if not spec.by_id:
        pytest.skip("lookup is by name only")
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


def _clb_models():
    return type("FakeModels", (), {"Filter": FakeFilter, "DescribeListenersRequest": FakeRequest})


def _find_listener(records, listener_id=None, port=None, protocol=None):
    client = FakeClient("DescribeListeners", "Listeners", [records])
    return clb_listener.find_listener(FakeModule(), client, _clb_models(), "lb-1", listener_id, port, protocol)


def test_find_listener_by_endpoint_picks_the_matching_port():
    records = [
        Record(ListenerId="lbl-1", Port=80, Protocol="TCP"),
        Record(ListenerId="lbl-2", Port=443, Protocol="TCP"),
    ]
    assert _find_listener(records, port=443, protocol="TCP")["ListenerId"] == "lbl-2"


def test_find_listener_same_endpoint_twice_is_ambiguous():
    records = [
        Record(ListenerId="lbl-1", Port=80, Protocol="TCP"),
        Record(ListenerId="lbl-2", Port=80, Protocol="TCP"),
    ]
    with pytest.raises(ResolutionFailed) as exc:
        _find_listener(records, port=80, protocol="TCP")
    assert exc.value.args[0]["match_count"] == 2


def _find_rule(records, location_id=None, domain=None, url=None):
    client = FakeClient("DescribeListeners", "Listeners", [[Listener(records)]])
    return clb_rule.find_rule(FakeModule(), client, _clb_models(), "lb-1", "lbl-1", location_id, domain, url)


def test_find_rule_by_endpoint_picks_the_matching_url():
    records = [
        Record(LocationId="loc-1", Domain="a.example.com", Url="/a"),
        Record(LocationId="loc-2", Domain="a.example.com", Url="/b"),
    ]
    found = _find_rule(records, domain="a.example.com", url="/b")
    assert found["LocationId"] == "loc-2"


def test_find_rule_same_endpoint_twice_is_ambiguous():
    records = [
        Record(LocationId="loc-1", Domain="a.example.com", Url="/a"),
        Record(LocationId="loc-2", Domain="a.example.com", Url="/a"),
    ]
    with pytest.raises(ResolutionFailed) as exc:
        _find_rule(records, domain="a.example.com", url="/a")
    assert exc.value.args[0]["match_count"] == 2
