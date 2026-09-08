"""Unit tests for the vpn_gateway write module (run_module flows).

Drives ``run_module()`` end to end against an in-memory fake VPC client whose
create/modify/delete operations mutate a gateway store so the post-write
``find_gateway`` call observes the write. Name lookups go through the shared
resolver, which re-checks the fuzzy server-side filter client-side.

Scenario matrix:

* absent on a missing gateway (idempotent) and the identify guard
* absent with a live gateway (check-mode dry run and the real delete)
* creation when missing (vpc_id/name guards, check mode, request fields)
* no-op when the gateway already matches
* drift updates (rename, max_connection, bgp_asn)
* ambiguous-name resolution and the inline SDK-error envelope path
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import vpn_gateway as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

GW_ID = "vpngw-1a2b3c4d"


def _gw(**overrides):
    item = {
        "VpnGatewayId": GW_ID,
        "VpnGatewayName": "office-vpn",
        "VpcId": "vpc-aaaaaaaa",
        "Type": "IPSEC",
        "InstanceChargeType": "POSTPAID_BY_HOUR",
        "State": "AVAILABLE",
        "InternetMaxBandwidthOut": 10,
        "MaxConnection": 5000,
        "BgpAsn": 64512,
    }
    item.update(overrides)
    return item


def _base(**overrides):
    return module_args(**overrides)


class FakeVpcClient(object):
    """In-memory VPC (vpc.v20170312) VPN-gateway client."""

    def __init__(self, entries=None):
        self.entries = [copy.deepcopy(t) for t in (entries or [])]
        self.calls = []
        self._next = 0

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def DescribeVpnGateways(self, request):
        self._record("DescribeVpnGateways", request)
        # The shared resolver re-checks matches client-side, so returning the
        # whole store is enough; the fake never widens the candidate set.
        return SimpleNamespace(VpnGatewaySet=[FakeResource(e) for e in self.entries])

    def CreateVpnGateway(self, request):
        self._record("CreateVpnGateway", request)
        self._next += 1
        data = request.__dict__
        entry = {
            "VpnGatewayId": "vpngw-new-%03d" % self._next,
            "VpnGatewayName": data.get("VpnGatewayName"),
            "VpcId": data.get("VpcId"),
            "Type": data.get("Type"),
            "InstanceChargeType": data.get("InstanceChargeType"),
            "State": "AVAILABLE",
            "InternetMaxBandwidthOut": data.get("InternetMaxBandwidthOut"),
        }
        for key in ("MaxConnection", "Zone", "BgpAsn"):
            if data.get(key) is not None:
                entry[key] = data[key]
        self.entries.append(entry)
        return SimpleNamespace(VpnGatewayId=entry["VpnGatewayId"])

    def ModifyVpnGatewayAttribute(self, request):
        self._record("ModifyVpnGatewayAttribute", request)
        data = request.__dict__
        for entry in self.entries:
            if entry.get("VpnGatewayId") == data.get("VpnGatewayId"):
                for key in ("VpnGatewayName", "MaxConnection", "BgpAsn"):
                    if data.get(key) is not None:
                        entry[key] = data[key]

    def DeleteVpnGateway(self, request):
        self._record("DeleteVpnGateway", request)
        self.entries = [e for e in self.entries if e.get("VpnGatewayId") != request.VpnGatewayId]
        return SimpleNamespace()


def _make_module(monkeypatch, fake):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load_vpc", lambda: (FakeModels(), SimpleNamespace(VpcClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


def _ops(fake):
    return [c for c, unused in fake.calls]


def _request(fake, op_name):
    for op, request in fake.calls:
        if op == op_name:
            return request
    return None


# ---------------------------------------------------------------------------
# absent flows
# ---------------------------------------------------------------------------


def test_absent_missing_gateway_is_idempotent(monkeypatch):
    fake = FakeVpcClient()
    _make_module(monkeypatch, fake)
    _base(state="absent", name="office-vpn")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["msg"] == "VPN gateway already absent"
    assert _ops(fake) == ["DescribeVpnGateways"]


def test_identify_guard_requires_id_or_name(monkeypatch):
    fake = FakeVpcClient()
    _make_module(monkeypatch, fake)
    _base(state="absent")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "vpn_gateway_id or name is required to identify the gateway" in exc.value.args[0]["msg"]


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeVpcClient(entries=[_gw()])
    _make_module(monkeypatch, fake)
    _base(_ansible_check_mode=True, state="absent", vpn_gateway_id=GW_ID)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["msg"] == "Would delete VPN gateway"
    assert len(fake.entries) == 1
    assert "DeleteVpnGateway" not in _ops(fake)


def test_absent_deletes_gateway(monkeypatch):
    fake = FakeVpcClient(entries=[_gw()])
    _make_module(monkeypatch, fake)
    _base(state="absent", vpn_gateway_id=GW_ID)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["vpn_gateway"] is None
    assert fake.entries == []
    assert "DeleteVpnGateway" in _ops(fake)
    assert _request(fake, "DeleteVpnGateway").VpnGatewayId == GW_ID


# ---------------------------------------------------------------------------
# creation flows
# ---------------------------------------------------------------------------


def test_create_requires_vpc_id(monkeypatch):
    fake = FakeVpcClient()
    _make_module(monkeypatch, fake)
    _base(state="present", name="office-vpn")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "vpc_id is required when creating a VPN gateway" in exc.value.args[0]["msg"]


def test_create_requires_name(monkeypatch):
    fake = FakeVpcClient()
    _make_module(monkeypatch, fake)
    _base(state="present", vpn_gateway_id="vpngw-ghost", vpc_id="vpc-aaaaaaaa")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "name is required when creating a VPN gateway" in exc.value.args[0]["msg"]


def test_present_missing_creates_gateway(monkeypatch):
    fake = FakeVpcClient()
    _make_module(monkeypatch, fake)
    _base(state="present", name="office-vpn", vpc_id="vpc-aaaaaaaa")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["msg"] == "VPN gateway created"
    created = result["vpn_gateway"]
    assert created["VpnGatewayName"] == "office-vpn"
    assert created["VpcId"] == "vpc-aaaaaaaa"
    assert created["VpnGatewayId"].startswith("vpngw-new-")
    assert len(fake.entries) == 1
    assert "CreateVpnGateway" in _ops(fake)


def test_create_request_carries_all_fields(monkeypatch):
    fake = FakeVpcClient()
    _make_module(monkeypatch, fake)
    _base(
        state="present",
        name="office-vpn",
        vpc_id="vpc-aaaaaaaa",
        internet_max_bandwidth_out=20,
        instance_charge_type="PREPAID_BY_MONTH",
        type="SSL",
        max_connection=10000,
        zone="ap-guangzhou-3",
        bgp_asn=64520,
    )
    run(mod.run_module)
    request = _request(fake, "CreateVpnGateway")
    assert request.VpcId == "vpc-aaaaaaaa"
    assert request.VpnGatewayName == "office-vpn"
    assert request.InstanceChargeType == "PREPAID_BY_MONTH"
    assert request.Type == "SSL"
    assert request.InternetMaxBandwidthOut == 20
    assert request.MaxConnection == 10000
    assert request.Zone == "ap-guangzhou-3"
    assert request.BgpAsn == 64520


def test_create_omits_unset_optional_fields(monkeypatch):
    fake = FakeVpcClient()
    _make_module(monkeypatch, fake)
    _base(state="present", name="office-vpn", vpc_id="vpc-aaaaaaaa")
    run(mod.run_module)
    request = _request(fake, "CreateVpnGateway")
    assert getattr(request, "InternetMaxBandwidthOut", None) is None
    assert getattr(request, "MaxConnection", None) is None
    assert getattr(request, "Zone", None) is None
    assert getattr(request, "BgpAsn", None) is None


def test_create_check_mode_is_dry_run(monkeypatch):
    fake = FakeVpcClient()
    _make_module(monkeypatch, fake)
    _base(_ansible_check_mode=True, state="present", name="office-vpn", vpc_id="vpc-aaaaaaaa")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["msg"] == "Would create VPN gateway"
    assert fake.entries == []
    assert "CreateVpnGateway" not in _ops(fake)


# ---------------------------------------------------------------------------
# existing-gateway flows
# ---------------------------------------------------------------------------


def test_present_no_drift_is_noop(monkeypatch):
    fake = FakeVpcClient(entries=[_gw()])
    _make_module(monkeypatch, fake)
    _base(
        state="present",
        vpn_gateway_id=GW_ID,
        name="office-vpn",
        max_connection=5000,
        bgp_asn=64512,
    )
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["msg"] == "VPN gateway is up to date"
    assert result["vpn_gateway"]["VpnGatewayId"] == GW_ID
    assert "ModifyVpnGatewayAttribute" not in _ops(fake)


def test_rename_gateway(monkeypatch):
    fake = FakeVpcClient(entries=[_gw()])
    _make_module(monkeypatch, fake)
    _base(state="present", vpn_gateway_id=GW_ID, name="office-vpn-prod")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["vpn_gateway"]["VpnGatewayName"] == "office-vpn-prod"
    assert _request(fake, "ModifyVpnGatewayAttribute").VpnGatewayName == "office-vpn-prod"


def test_update_max_connection(monkeypatch):
    fake = FakeVpcClient(entries=[_gw()])
    _make_module(monkeypatch, fake)
    _base(state="present", vpn_gateway_id=GW_ID, max_connection=10000)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["vpn_gateway"]["MaxConnection"] == 10000
    assert _request(fake, "ModifyVpnGatewayAttribute").MaxConnection == 10000


def test_update_bgp_asn(monkeypatch):
    fake = FakeVpcClient(entries=[_gw()])
    _make_module(monkeypatch, fake)
    _base(state="present", vpn_gateway_id=GW_ID, bgp_asn=64530)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["vpn_gateway"]["BgpAsn"] == 64530
    assert _request(fake, "ModifyVpnGatewayAttribute").BgpAsn == 64530


def test_update_combines_all_drift_changes(monkeypatch):
    fake = FakeVpcClient(entries=[_gw()])
    _make_module(monkeypatch, fake)
    _base(state="present", vpn_gateway_id=GW_ID, name="office-vpn-prod", max_connection=20000, bgp_asn=64540)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["vpn_gateway"]["VpnGatewayName"] == "office-vpn-prod"
    assert result["vpn_gateway"]["MaxConnection"] == 20000
    assert result["vpn_gateway"]["BgpAsn"] == 64540


def test_update_check_mode_is_dry_run(monkeypatch):
    fake = FakeVpcClient(entries=[_gw()])
    _make_module(monkeypatch, fake)
    _base(_ansible_check_mode=True, state="present", vpn_gateway_id=GW_ID, name="office-vpn-prod")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["msg"] == "Would update VPN gateway"
    assert fake.entries[0]["VpnGatewayName"] == "office-vpn"
    assert "ModifyVpnGatewayAttribute" not in _ops(fake)


# ---------------------------------------------------------------------------
# guards / failure paths
# ---------------------------------------------------------------------------


def test_ambiguous_name_fails(monkeypatch):
    fake = FakeVpcClient(entries=[_gw(), _gw(VpnGatewayId="vpngw-dup", VpcId="vpc-bbbbbbbb")])
    _make_module(monkeypatch, fake)
    _base(state="present", name="office-vpn", vpc_id="vpc-aaaaaaaa")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "Ambiguous VPN gateway reference" in payload["msg"]
    assert payload["ambiguous"] is True


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        def get_code(self):
            return "UnsupportedOperation"

        def get_request_id(self):
            return "req-xyz"

    class ExplodingClient(object):
        def DescribeVpnGateways(self, request):
            raise Boom("connection dropped")

    _make_module(monkeypatch, ExplodingClient())
    _base(state="present", name="office-vpn")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]
    assert payload["error_code"] == "UnsupportedOperation"
    assert payload["request_id"] == "req-xyz"
