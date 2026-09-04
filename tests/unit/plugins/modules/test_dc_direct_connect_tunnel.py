"""Unit tests for the dc_direct_connect_tunnel write module (helpers + run_module).

Covers the create / drift-update / delete flows of
``plugins/modules/dc_direct_connect_tunnel.py`` with an in-memory fake DC
client whose write operations mutate the tunnel store, so the module's
post-write ``find`` refetch converges immediately. Tunnels can be matched by
``tunnel_id`` or by ``name`` (+ optional ``direct_connect_id``) — both lookup
paths are exercised, along with the immutable-field guard, the BgpPeer
AuthKey scrub and the route-prefix/tag builders.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
import json
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import dc_direct_connect_tunnel as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

TUNNEL = {
    "DirectConnectTunnelId": "dcx-8b0a1c2d",
    "DirectConnectTunnelName": "tunnel-prod",
    "DirectConnectId": "dc-8b0a1c2d",
    "NetworkType": "VPC",
    "NetworkRegion": "ap-guangzhou",
    "VpcId": "vpc-8b0a1c2d",
    "DirectConnectGatewayId": "dcg-8b0a1c2d",
    "Bandwidth": 500,
    "RouteType": "BGP",
    "BgpPeer": {"Asn": 65001},
    "RouteFilterPrefixes": [{"Cidr": "10.0.0.0/16"}],
    "Vlan": 100,
    "TencentAddress": "192.0.2.1/30",
    "CustomerAddress": "192.0.2.2/30",
    "TencentBackupAddress": "192.0.2.5/30",
    "BfdEnable": 1,
    "NqaEnable": 0,
    "Tags": [{"Key": "env", "Value": "prod"}],
}

WRITE_OPS = (
    "CreateDirectConnectTunnel",
    "ModifyDirectConnectTunnelAttribute",
    "DeleteDirectConnectTunnel",
)


def _tunnel(**overrides):
    """Return a tunnel fixture isolated from the shared constant."""
    tunnel = copy.deepcopy(TUNNEL)
    tunnel.update(overrides)
    return tunnel


def _params(**overrides):
    """Module parameters pre-filled from the argument spec (base params included)."""
    params = {
        "state": "present",
        "tunnel_id": None,
        "name": None,
        "direct_connect_id": None,
        "owner_account": None,
        "network_type": None,
        "network_region": None,
        "vpc_id": None,
        "direct_connect_gateway_id": None,
        "bandwidth": None,
        "bgp_peer": None,
        "route_filter_prefixes": None,
        "vlan": None,
        "tencent_address": None,
        "customer_address": None,
        "tencent_backup_address": None,
        "tags": None,
        "retries": 5,
        "waiter_delay": 5,
        "waiter_timeout": 120,
    }
    # NOTE: bfd_enabled / nqa_enabled / route_type carry choices but no
    # default. Ansible only validates choices for keys the user explicitly
    # passed, so omitted (absent) keys are safe but an explicit None is
    # rejected. Tests therefore never pre-fill them; pass a concrete value
    # (0/1, "BGP"/"STATIC") when a scenario needs them.
    params.update(overrides)
    return params


def _run_args(**extra):
    """module_args() pre-filled with every module parameter."""
    args = dict(_params())
    args.update(extra)
    return module_args(**args)


class FakeModule(object):
    """Minimal stand-in for helpers that need sdk_call / fail_json."""

    def __init__(self, params=None):
        self.params = params or _params()
        self.sdk_calls = []

    def sdk_call(self, operation, request):
        self.sdk_calls.append((operation, request))
        return operation(request)

    def fail_json(self, **kwargs):
        raise AnsibleFailJson(kwargs)


class FakeDcClient(object):
    """In-memory DC client that mutates a small tunnel store."""

    def __init__(self, tunnels=None):
        self.tunnels = [copy.deepcopy(t) for t in (tunnels or [])]
        self.calls = []

    def _record(self, name, request):
        self.calls.append((name, request))
        return request

    def DescribeDirectConnectTunnels(self, request):
        self._record("DescribeDirectConnectTunnels", request)
        ids = getattr(request, "DirectConnectTunnelIds", None)
        items = self.tunnels
        if ids:
            items = [t for t in items if t.get("DirectConnectTunnelId") in ids]
        return SimpleNamespace(DirectConnectTunnelSet=[FakeResource(dict(t)) for t in items])

    def CreateDirectConnectTunnel(self, request):
        self._record("CreateDirectConnectTunnel", request)
        tunnel = {
            "DirectConnectTunnelId": "dcx-fake-001",
            "DirectConnectTunnelName": request.DirectConnectTunnelName,
            "DirectConnectId": request.DirectConnectId,
            "NetworkType": request.NetworkType,
            "NetworkRegion": request.NetworkRegion,
            "DirectConnectGatewayId": request.DirectConnectGatewayId,
            "RouteType": request.RouteType,
            "Bandwidth": getattr(request, "Bandwidth", None),
            "Vlan": getattr(request, "Vlan", None),
            "BgpPeer": getattr(request, "BgpPeer", None),
            "RouteFilterPrefixes": getattr(request, "RouteFilterPrefixes", None),
            "TencentAddress": getattr(request, "TencentAddress", None),
            "CustomerAddress": getattr(request, "CustomerAddress", None),
            "TencentBackupAddress": getattr(request, "TencentBackupAddress", None),
            "BfdEnable": getattr(request, "BfdEnable", None),
            "NqaEnable": getattr(request, "NqaEnable", None),
        }
        if getattr(request, "VpcId", None):
            tunnel["VpcId"] = request.VpcId
        self.tunnels.append(tunnel)
        return SimpleNamespace(DirectConnectTunnelIdSet=["dcx-fake-001"])

    def ModifyDirectConnectTunnelAttribute(self, request):
        self._record("ModifyDirectConnectTunnelAttribute", request)
        for tunnel in self.tunnels:
            if tunnel.get("DirectConnectTunnelId") == request.DirectConnectTunnelId:
                if getattr(request, "DirectConnectTunnelName", None) is not None:
                    tunnel["DirectConnectTunnelName"] = request.DirectConnectTunnelName
                if getattr(request, "Bandwidth", None) is not None:
                    tunnel["Bandwidth"] = request.Bandwidth
                if getattr(request, "BgpPeer", None) is not None:
                    tunnel["BgpPeer"] = request.BgpPeer
                if getattr(request, "RouteFilterPrefixes", None) is not None:
                    tunnel["RouteFilterPrefixes"] = request.RouteFilterPrefixes
                if getattr(request, "TencentAddress", None) is not None:
                    tunnel["TencentAddress"] = request.TencentAddress
                if getattr(request, "CustomerAddress", None) is not None:
                    tunnel["CustomerAddress"] = request.CustomerAddress
                if getattr(request, "TencentBackupAddress", None) is not None:
                    tunnel["TencentBackupAddress"] = request.TencentBackupAddress
        return SimpleNamespace(RequestId="req-fake")

    def DeleteDirectConnectTunnel(self, request):
        self._record("DeleteDirectConnectTunnel", request)
        self.tunnels = [
            t
            for t in self.tunnels
            if t.get("DirectConnectTunnelId") != request.DirectConnectTunnelId
        ]
        return SimpleNamespace(RequestId="req-fake")


class _BgpPeerModel(object):
    """Stand-in for the SDK BgpPeer model with json round-trip.

    ``_model()`` builds ``cls()`` then calls ``from_json_string``, so the fake
    model must implement it (FakeModels' dynamic classes only support free
    attribute assignment).
    """

    def __init__(self):
        self._value = None

    def from_json_string(self, text):
        self._value = json.loads(text)

    def to_json_string(self):
        return json.dumps(self._value)


class FakeBgpModels(FakeModels):
    """FakeModels whose BgpPeer resolves to the round-trippable model."""

    def __getattr__(self, name):
        if name == "BgpPeer":
            return _BgpPeerModel
        return super(FakeBgpModels, self).__getattr__(name)


def _make_module(monkeypatch, fake, params=None):
    """Wire the shared monkeypatches and return the fake client."""
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(
        mod,
        "_load",
        lambda: (FakeBgpModels(), SimpleNamespace(DcClient=object)),
    )
    monkeypatch.setattr(
        TencentCloudModule,
        "create_client",
        lambda self, client_class, endpoint: fake,
    )
    return fake


# ---------------------------------------------------------------------------
# Helper-level tests
# ---------------------------------------------------------------------------


def test_describe_request_with_tunnel_id():
    models = FakeBgpModels()
    request = mod.describe_request(models, _params(tunnel_id="dcx-abc"))
    assert request.Offset == 0
    assert request.Limit == 100
    assert request.DirectConnectTunnelIds == ["dcx-abc"]


def test_describe_request_without_tunnel_id():
    models = FakeBgpModels()
    request = mod.describe_request(models, _params(name="tunnel-prod"))
    assert request.Offset == 0
    assert request.Limit == 100
    assert getattr(request, "DirectConnectTunnelIds", None) is None


def test_routes_builds_prefix_models():
    models = FakeBgpModels()
    prefixes = mod._routes(models, ["10.0.0.0/16", "192.168.0.0/24"])
    assert [p.Cidr for p in prefixes] == ["10.0.0.0/16", "192.168.0.0/24"]


def test_routes_accepts_none():
    models = FakeBgpModels()
    assert mod._routes(models, None) == []


def test_tags_sort_keys():
    models = FakeBgpModels()
    tags = mod._tags(models, {"b": "two", "a": "one"})
    assert [(t.Key, t.Value) for t in tags] == [("a", "one"), ("b", "two")]


def test_tags_accepts_none():
    models = FakeBgpModels()
    assert mod._tags(models, None) == []


def test_fill_sets_mutable_fields():
    models = FakeBgpModels()
    request = SimpleNamespace()
    mod._fill(request, models, _params(
        name="tunnel-new",
        bandwidth=300,
        bgp_peer={"Asn": 65002},
        route_filter_prefixes=["10.1.0.0/16"],
        tencent_address="203.0.113.1/30",
        customer_address="203.0.113.2/30",
        tencent_backup_address="203.0.113.5/30",
    ))
    assert request.DirectConnectTunnelName == "tunnel-new"
    assert request.Bandwidth == 300
    assert request.TencentAddress == "203.0.113.1/30"
    assert request.CustomerAddress == "203.0.113.2/30"
    assert request.TencentBackupAddress == "203.0.113.5/30"


def test_fill_optional_fields_default_none():
    models = FakeBgpModels()
    request = SimpleNamespace()
    mod._fill(request, models, _params(name="tunnel-new", bandwidth=100))
    assert request.BgpPeer is None
    assert request.RouteFilterPrefixes == []
    assert request.TencentAddress is None


def test_model_round_trip():
    value = mod._model(_BgpPeerModel, {"Asn": 65001, "AuthKey": "secret"})
    assert value._value == {"Asn": 65001, "AuthKey": "secret"}


def test_model_none_returns_none():
    assert mod._model(_BgpPeerModel, None) is None


def test_create_request_sets_all_fields():
    models = FakeBgpModels()
    request = mod.create_request(models, _params(
        name="tunnel-new",
        direct_connect_id="dc-abc",
        owner_account="owner-1",
        network_type="VPC",
        network_region="ap-guangzhou",
        vpc_id="vpc-abc",
        direct_connect_gateway_id="dcg-abc",
        bandwidth=500,
        route_type="BGP",
        vlan=100,
        bfd_enabled=1,
        nqa_enabled=0,
        tags={"env": "prod"},
    ))
    assert request.DirectConnectTunnelName == "tunnel-new"
    assert request.DirectConnectId == "dc-abc"
    assert request.DirectConnectOwnerAccount == "owner-1"
    assert request.NetworkType == "VPC"
    assert request.NetworkRegion == "ap-guangzhou"
    assert request.VpcId == "vpc-abc"
    assert request.DirectConnectGatewayId == "dcg-abc"
    assert request.RouteType == "BGP"
    assert request.Vlan == 100
    assert request.BfdEnable == 1
    assert request.NqaEnable == 0
    assert [(t.Key, t.Value) for t in request.Tags] == [("env", "prod")]


def test_update_request_sets_tunnel_id():
    models = FakeBgpModels()
    request = mod.update_request(models, _params(name="tunnel-renamed", bandwidth=800), "dcx-abc")
    assert request.DirectConnectTunnelId == "dcx-abc"
    assert request.DirectConnectTunnelName == "tunnel-renamed"
    assert request.Bandwidth == 800


def test_delete_request_sets_tunnel_id():
    models = FakeBgpModels()
    request = mod.delete_request(models, "dcx-abc")
    assert request.DirectConnectTunnelId == "dcx-abc"


def test_safe_bgp_strips_auth_key():
    assert mod._safe_bgp({"Asn": 65001, "AuthKey": "hunter2"}) == {"Asn": 65001}


def test_safe_bgp_empty_returns_none():
    assert mod._safe_bgp(None) is None
    assert mod._safe_bgp({}) is None
    assert mod._safe_bgp({"AuthKey": "x"}) is None


def test_route_values_sorted():
    value = {"RouteFilterPrefixes": [{"Cidr": "10.2.0.0/16"}, {"Cidr": "10.1.0.0/16"}]}
    assert mod._route_values(value) == ["10.1.0.0/16", "10.2.0.0/16"]


def test_route_values_missing():
    assert mod._route_values({}) == []


def test_comparable_shape():
    value = mod.comparable(_tunnel(BgpPeer={"Asn": 65001, "AuthKey": "hunter2"}))
    assert value["DirectConnectTunnelName"] == "tunnel-prod"
    assert value["DirectConnectId"] == "dc-8b0a1c2d"
    assert value["NetworkType"] == "VPC"
    assert value["NetworkRegion"] == "ap-guangzhou"
    assert value["VpcId"] == "vpc-8b0a1c2d"
    assert value["DirectConnectGatewayId"] == "dcg-8b0a1c2d"
    assert value["Bandwidth"] == 500
    assert value["RouteType"] == "BGP"
    assert value["BgpPeer"] == {"Asn": 65001}  # AuthKey scrubbed
    assert value["RouteFilterPrefixes"] == ["10.0.0.0/16"]
    assert value["Vlan"] == 100
    assert value["TencentAddress"] == "192.0.2.1/30"
    assert value["CustomerAddress"] == "192.0.2.2/30"
    assert value["TencentBackupAddress"] == "192.0.2.5/30"
    assert value["BfdEnable"] == 1


def test_desired_new_resource():
    p = _params(
        name="tunnel-new",
        direct_connect_id="dc-abc",
        network_type="VPC",
        network_region="ap-guangzhou",
        vpc_id="vpc-abc",
        direct_connect_gateway_id="dcg-abc",
        bandwidth=300,
        route_type="STATIC",
        route_filter_prefixes=["10.9.0.0/16", "10.8.0.0/16"],
        vlan=50,
    )
    value = mod.desired(p)
    assert value["DirectConnectTunnelName"] == "tunnel-new"
    assert value["Bandwidth"] == 300
    assert value["RouteFilterPrefixes"] == ["10.8.0.0/16", "10.9.0.0/16"]  # sorted
    assert value["Vlan"] == 50


def test_desired_keeps_current_when_param_omitted():
    # desired() receives the RAW find() dict (not a comparable-shaped one),
    # so passing a pre-comparabled value would double-process BgpPeer /
    # RouteFilterPrefixes and crash in _route_values().
    p = _params(name="tunnel-prod", direct_connect_id="dc-8b0a1c2d", bandwidth=None)
    value = mod.desired(p, _tunnel())
    # Bandwidth omitted -> falls back to the current value.
    assert value["Bandwidth"] == 500
    assert value["NetworkRegion"] == "ap-guangzhou"
    assert value["RouteFilterPrefixes"] == ["10.0.0.0/16"]


# ---------------------------------------------------------------------------
# find() tests
# ---------------------------------------------------------------------------


def test_find_by_tunnel_id(monkeypatch):
    fake = FakeDcClient(tunnels=[_tunnel()])
    module = FakeModule(params=_params())
    found = mod.find(module, fake, FakeBgpModels(), _params(tunnel_id="dcx-8b0a1c2d"))
    assert found["DirectConnectTunnelName"] == "tunnel-prod"
    assert "AuthKey" not in (found.get("BgpPeer") or {})
    assert fake.calls[0][0] == "DescribeDirectConnectTunnels"


def test_find_by_name_and_direct_connect_id(monkeypatch):
    fake = FakeDcClient(tunnels=[_tunnel()])
    module = FakeModule(params=_params())
    found = mod.find(module, fake, FakeBgpModels(), _params(
        name="tunnel-prod", direct_connect_id="dc-8b0a1c2d"
    ))
    assert found["DirectConnectTunnelId"] == "dcx-8b0a1c2d"


def test_find_no_match_returns_none(monkeypatch):
    fake = FakeDcClient(tunnels=[_tunnel()])
    module = FakeModule(params=_params())
    found = mod.find(module, fake, FakeBgpModels(), _params(name="tunnel-other"))
    assert found is None


def test_find_multiple_matches_fails(monkeypatch):
    fake = FakeDcClient(tunnels=[
        _tunnel(DirectConnectTunnelId="dcx-1", DirectConnectTunnelName="dup"),
        _tunnel(DirectConnectTunnelId="dcx-2", DirectConnectTunnelName="dup"),
    ])
    module = FakeModule(params=_params())
    with pytest.raises(AnsibleFailJson) as exc:
        mod.find(module, fake, FakeBgpModels(), _params(name="dup"))
    assert "Multiple Direct Connect tunnels matched" in exc.value.args[0]["msg"]


# ---------------------------------------------------------------------------
# run_module tests
# ---------------------------------------------------------------------------


def test_required_arguments_enforced(monkeypatch):
    _make_module(monkeypatch, FakeDcClient())
    module_args()  # neither tunnel_id nor name given
    with pytest.raises(AnsibleFailJson):
        run(mod.run_module)


def test_absent_no_tunnel_is_noop(monkeypatch):
    fake = FakeDcClient()
    _make_module(monkeypatch, fake)
    _run_args(state="absent", name="tunnel-missing")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["tunnel"] is None
    # no write op was issued
    assert not [c for c in fake.calls if c[0] in WRITE_OPS]


def test_absent_deletes_tunnel(monkeypatch):
    fake = FakeDcClient(tunnels=[_tunnel()])
    _make_module(monkeypatch, fake)
    _run_args(state="absent", tunnel_id="dcx-8b0a1c2d")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["tunnel"] is None
    assert "DeleteDirectConnectTunnel" in [c[0] for c in fake.calls]
    assert fake.tunnels == []


def test_absent_check_mode_reports_change_without_write(monkeypatch):
    fake = FakeDcClient(tunnels=[_tunnel()])
    _make_module(monkeypatch, fake)
    _run_args(state="absent", tunnel_id="dcx-8b0a1c2d", _ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert "diff" in result
    assert not [c for c in fake.calls if c[0] in WRITE_OPS]


def test_present_create_missing_params_fails(monkeypatch):
    fake = FakeDcClient()
    _make_module(monkeypatch, fake)
    _run_args(name="tunnel-new", direct_connect_id="dc-abc")  # missing the rest
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["failed"] is True
    assert "creation parameters are required" in payload["msg"]
    assert "network_type" in payload["missing"]
    assert "bandwidth" in payload["missing"]


def test_present_creates_tunnel(monkeypatch):
    fake = FakeDcClient()
    _make_module(monkeypatch, fake)
    _run_args(
        name="tunnel-new",
        direct_connect_id="dc-abc",
        network_type="VPC",
        network_region="ap-guangzhou",
        vpc_id="vpc-abc",
        direct_connect_gateway_id="dcg-abc",
        bandwidth=500,
        route_type="BGP",
        vlan=100,
        tencent_address="192.0.2.1/30",
        customer_address="192.0.2.2/30",
        bgp_peer={"Asn": 65001},
        route_filter_prefixes=["10.0.0.0/16"],
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert "CreateDirectConnectTunnel" in [c[0] for c in fake.calls]
    assert fake.tunnels[0]["DirectConnectTunnelId"] == "dcx-fake-001"
    assert result["tunnel"]["DirectConnectTunnelName"] == "tunnel-new"


def test_present_up_to_date_is_noop(monkeypatch):
    fake = FakeDcClient(tunnels=[_tunnel()])
    _make_module(monkeypatch, fake)
    _run_args(
        tunnel_id="dcx-8b0a1c2d",
        name="tunnel-prod",
        direct_connect_id="dc-8b0a1c2d",
        network_type="VPC",
        network_region="ap-guangzhou",
        vpc_id="vpc-8b0a1c2d",
        direct_connect_gateway_id="dcg-8b0a1c2d",
        bandwidth=500,
        route_type="BGP",
        vlan=100,
        tencent_address="192.0.2.1/30",
        customer_address="192.0.2.2/30",
        bgp_peer={"Asn": 65001},
        route_filter_prefixes=["10.0.0.0/16"],
        bfd_enabled=1,
    )
    result = run(mod.run_module)
    assert result["changed"] is False
    assert not [c for c in fake.calls if c[0] in WRITE_OPS]


def test_present_updates_drift(monkeypatch):
    fake = FakeDcClient(tunnels=[_tunnel()])
    _make_module(monkeypatch, fake)
    _run_args(
        tunnel_id="dcx-8b0a1c2d",
        name="tunnel-renamed",
        direct_connect_id="dc-8b0a1c2d",
        network_type="VPC",
        network_region="ap-guangzhou",
        vpc_id="vpc-8b0a1c2d",
        direct_connect_gateway_id="dcg-8b0a1c2d",
        bandwidth=800,
        route_type="BGP",
        vlan=100,
        tencent_address="192.0.2.1/30",
        customer_address="192.0.2.2/30",
        bgp_peer={"Asn": 65001},
        route_filter_prefixes=["10.0.0.0/16"],
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert "ModifyDirectConnectTunnelAttribute" in [c[0] for c in fake.calls]
    updated = fake.tunnels[0]
    assert updated["DirectConnectTunnelName"] == "tunnel-renamed"
    assert updated["Bandwidth"] == 800
    assert result["tunnel"]["DirectConnectTunnelName"] == "tunnel-renamed"


def test_present_immutable_change_fails(monkeypatch):
    fake = FakeDcClient(tunnels=[_tunnel()])
    _make_module(monkeypatch, fake)
    _run_args(
        tunnel_id="dcx-8b0a1c2d",
        name="tunnel-prod",
        direct_connect_id="dc-8b0a1c2d",
        network_type="VPC",
        network_region="ap-guangzhou",
        vpc_id="vpc-8b0a1c2d",
        direct_connect_gateway_id="dcg-8b0a1c2d",
        bandwidth=500,
        route_type="STATIC",  # immutable vs existing BGP
        vlan=100,
        tencent_address="192.0.2.1/30",
        customer_address="192.0.2.2/30",
        bgp_peer={"Asn": 65001},
        route_filter_prefixes=["10.0.0.0/16"],
    )
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["failed"] is True
    assert "immutable" in payload["msg"].lower() or "RouteType" in payload["msg"]


def test_present_check_mode_create_no_write(monkeypatch):
    fake = FakeDcClient()
    _make_module(monkeypatch, fake)
    _run_args(
        _ansible_check_mode=True,
        name="tunnel-new",
        direct_connect_id="dc-abc",
        network_type="VPC",
        network_region="ap-guangzhou",
        vpc_id="vpc-abc",
        direct_connect_gateway_id="dcg-abc",
        bandwidth=500,
        route_type="BGP",
        vlan=100,
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert "diff" in result
    assert result["tunnel"]["DirectConnectTunnelName"] == "tunnel-new"  # target preview
    assert not [c for c in fake.calls if c[0] in WRITE_OPS]


def test_present_check_mode_update_no_write(monkeypatch):
    fake = FakeDcClient(tunnels=[_tunnel()])
    _make_module(monkeypatch, fake)
    _run_args(
        _ansible_check_mode=True,
        tunnel_id="dcx-8b0a1c2d",
        name="tunnel-renamed",
        direct_connect_id="dc-8b0a1c2d",
        network_type="VPC",
        network_region="ap-guangzhou",
        vpc_id="vpc-8b0a1c2d",
        direct_connect_gateway_id="dcg-8b0a1c2d",
        bandwidth=800,
        route_type="BGP",
        vlan=100,
        tencent_address="192.0.2.1/30",
        customer_address="192.0.2.2/30",
        bgp_peer={"Asn": 65001},
        route_filter_prefixes=["10.0.0.0/16"],
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert "diff" in result
    assert result["diff"]["before"]["DirectConnectTunnelName"] == "tunnel-prod"
    assert result["diff"]["after"]["DirectConnectTunnelName"] == "tunnel-renamed"
    assert not [c for c in fake.calls if c[0] in WRITE_OPS]


def test_sdk_error_is_reported(monkeypatch):
    class _BoomClient(object):
        def __getattr__(self, name):
            def boom(*args, **kwargs):
                raise RuntimeError("service exploded")
            return boom

    fake = _BoomClient()
    _make_module(monkeypatch, fake)
    _run_args(name="tunnel-new", direct_connect_id="dc-abc")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["failed"] is True
