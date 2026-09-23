"""Unit tests for the nat_gateway write module (run_module flows).

Drives ``run_module()`` end to end against an in-memory fake VPC client
whose write operations mutate the gateway store so the post-write
``find_gateway`` refetch converges immediately.

Scenario matrix:

* identity guard (neither ``nat_gateway_id`` nor ``name``)
* absent on a missing gateway (idempotent no-op)
* absent with a matching gateway (check-mode dry run, real delete, the
  ``ignore_operation_risk`` flag, and the protection-disable-before-delete
  path)
* creation when missing (vpc_id/name guards, check mode, happy path)
* no-op when nothing drifts
* name/bandwidth/deletion-protection drift updates (with and without check
  mode)
* multiple-match ambiguity and both ``fail_from_sdk_error`` envelope paths
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import nat_gateway as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

NAT_ID = "nat-aaaaaaaa"
NAT_NAME = "prod-nat"
VPC_ID = "vpc-aaaaaaaa"

GATEWAY = {
    "NatGatewayId": NAT_ID,
    "NatGatewayName": NAT_NAME,
    "VpcId": VPC_ID,
    "State": "AVAILABLE",
    "InternetMaxBandwidthOut": 100,
    "DeletionProtectionEnabled": False,
}


def _gateway(**overrides):
    item = dict(GATEWAY)
    item.update(overrides)
    return item


def _base(**overrides):
    params = {}
    params.update(overrides)
    return module_args(**params)


def _id_args(**overrides):
    params = {"nat_gateway_id": NAT_ID}
    params.update(overrides)
    return params


def _name_args(**overrides):
    params = {"name": NAT_NAME, "vpc_id": VPC_ID}
    params.update(overrides)
    return params


class FakeVpcClient(object):
    """In-memory VPC client mutating a small NAT-gateway store."""

    def __init__(self, gateways=None):
        self.gateways = [dict(t) for t in (gateways or [])]
        self.calls = []
        self._next = 0

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def _rows(self, request):
        ids = list(getattr(request, "NatGatewayIds", None) or [])
        if ids:
            # An ID is the authoritative identity; the resolver re-checks it
            # client-side, so name filters must not hide the id-addressed row
            # (a rename task sends the new name alongside the id).
            return [r for r in self.gateways if r.get("NatGatewayId") in ids]
        rows = list(self.gateways)
        for item in getattr(request, "Filters", None) or []:
            values = list(getattr(item, "Values", None) or [])
            if item.Name == "nat-gateway-name":
                rows = [r for r in rows if any(v in r.get("NatGatewayName", "") for v in values)]
            elif item.Name == "vpc-id":
                rows = [r for r in rows if r.get("VpcId") in values]
        return rows

    def DescribeNatGateways(self, request):
        self._record("DescribeNatGateways", request)
        rows = self._rows(request)
        return SimpleNamespace(NatGatewaySet=[FakeResource(r) for r in rows], TotalCount=len(rows), RequestId="req-list")

    def CreateNatGateway(self, request):
        self._record("CreateNatGateway", request)
        self._next += 1
        row = {
            "NatGatewayId": "nat-new-%03d" % self._next,
            "NatGatewayName": getattr(request, "NatGatewayName", None),
            "VpcId": getattr(request, "VpcId", None),
            "State": "AVAILABLE",
            "DeletionProtectionEnabled": False,
            "InternetMaxBandwidthOut": getattr(request, "InternetMaxBandwidthOut", None),
        }
        self.gateways.append(row)
        return SimpleNamespace(NatGatewayId=row["NatGatewayId"], RequestId="req-create")

    def ModifyNatGatewayAttribute(self, request):
        self._record("ModifyNatGatewayAttribute", request)
        nat_id = getattr(request, "NatGatewayId", None)
        for row in self.gateways:
            if row.get("NatGatewayId") == nat_id:
                for attr in ("NatGatewayName", "InternetMaxBandwidthOut", "DeletionProtectionEnabled"):
                    value = getattr(request, attr, None)
                    if value is not None:
                        row[attr] = value
        return SimpleNamespace(RequestId="req-modify")

    def DeleteNatGateway(self, request):
        self._record("DeleteNatGateway", request)
        nat_id = getattr(request, "NatGatewayId", None)
        self.gateways = [r for r in self.gateways if r.get("NatGatewayId") != nat_id]
        return SimpleNamespace(RequestId="req-delete")


def _make_module(monkeypatch, fake, models=None):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load_vpc", lambda: (models or FakeModels(), SimpleNamespace(VpcClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)


# ---------------------------------------------------------------------------
# identity guard / absent flows
# ---------------------------------------------------------------------------


def test_identity_requires_id_or_name(monkeypatch):
    fake = FakeVpcClient()
    _make_module(monkeypatch, fake)
    _base(state="present")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "nat_gateway_id or name is required to identify the gateway" in exc.value.args[0]["msg"]


def test_absent_missing_gateway_is_idempotent(monkeypatch):
    fake = FakeVpcClient()
    _make_module(monkeypatch, fake)
    _base(state="absent", **_id_args())
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["msg"] == "NAT gateway already absent"
    assert [c for c, unused in fake.calls] == ["DescribeNatGateways"]


def test_absent_deletes_gateway(monkeypatch):
    fake = FakeVpcClient(gateways=[_gateway()])
    _make_module(monkeypatch, fake)
    _base(state="absent", **_id_args())
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["nat_gateway"] is None
    assert result["msg"] == "NAT gateway deleted"
    assert fake.gateways == []
    assert "DeleteNatGateway" in [c for c, unused in fake.calls]


def test_absent_delete_passes_ignore_operation_risk(monkeypatch):
    fake = FakeVpcClient(gateways=[_gateway()])
    _make_module(monkeypatch, fake)
    _base(state="absent", ignore_operation_risk=True, **_id_args())
    result = run(mod.run_module)
    assert result["changed"] is True
    deletes = [req for name, req in fake.calls if name == "DeleteNatGateway"]
    assert deletes and deletes[0].IgnoreOperationRisk is True


def test_absent_disables_deletion_protection_first(monkeypatch):
    fake = FakeVpcClient(gateways=[_gateway(DeletionProtectionEnabled=True)])
    _make_module(monkeypatch, fake)
    _base(state="absent", **_id_args())
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["nat_gateway"] is None
    ops = [c for c, unused in fake.calls]
    assert "ModifyNatGatewayAttribute" in ops
    assert "DeleteNatGateway" in ops
    modifies = [req for name, req in fake.calls if name == "ModifyNatGatewayAttribute"]
    assert modifies[0].DeletionProtectionEnabled is False


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeVpcClient(gateways=[_gateway()])
    _make_module(monkeypatch, fake)
    _base(_ansible_check_mode=True, state="absent", **_id_args())
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["msg"] == "Would delete NAT gateway"
    assert len(fake.gateways) == 1
    ops = [c for c, unused in fake.calls]
    assert "ModifyNatGatewayAttribute" not in ops
    assert "DeleteNatGateway" not in ops


# ---------------------------------------------------------------------------
# creation flows
# ---------------------------------------------------------------------------


def test_create_requires_vpc_id(monkeypatch):
    fake = FakeVpcClient()
    _make_module(monkeypatch, fake)
    _base(state="present", name=NAT_NAME)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "vpc_id is required when creating a NAT gateway" in exc.value.args[0]["msg"]


def test_create_requires_name(monkeypatch):
    fake = FakeVpcClient()
    _make_module(monkeypatch, fake)
    # An id-addressed create attempt that finds no gateway and provides a
    # vpc_id still needs a name before the module can build the request.
    _base(state="present", nat_gateway_id="nat-missing", vpc_id=VPC_ID)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "name is required when creating a NAT gateway" in exc.value.args[0]["msg"]


def test_create_gateway(monkeypatch):
    fake = FakeVpcClient()
    _make_module(monkeypatch, fake)
    _base(state="present", name=NAT_NAME, vpc_id=VPC_ID, internet_max_bandwidth_out=100)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["msg"] == "NAT gateway created"
    assert result["nat_gateway"]["NatGatewayId"].startswith("nat-new-")
    assert result["nat_gateway"]["NatGatewayName"] == NAT_NAME
    assert len(fake.gateways) == 1
    ops = [c for c, unused in fake.calls]
    assert ops[0] == "DescribeNatGateways"
    assert "CreateNatGateway" in ops
    creates = [req for name, req in fake.calls if name == "CreateNatGateway"]
    assert creates[0].VpcId == VPC_ID
    assert creates[0].InternetMaxBandwidthOut == 100


def test_create_check_mode_is_dry_run(monkeypatch):
    fake = FakeVpcClient()
    _make_module(monkeypatch, fake)
    _base(_ansible_check_mode=True, state="present", name=NAT_NAME, vpc_id=VPC_ID)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["msg"] == "Would create NAT gateway"
    assert fake.gateways == []
    assert "CreateNatGateway" not in [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# existing-gateway flows
# ---------------------------------------------------------------------------


def test_existing_gateway_no_drift_is_idempotent(monkeypatch):
    fake = FakeVpcClient(gateways=[_gateway()])
    _make_module(monkeypatch, fake)
    _base(state="present", **_id_args(name=NAT_NAME, internet_max_bandwidth_out=100))
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["nat_gateway"]["NatGatewayId"] == NAT_ID
    assert result["msg"] == "NAT gateway is up to date"
    ops = [c for c, unused in fake.calls]
    assert "ModifyNatGatewayAttribute" not in ops


def test_update_gateway_name_and_bandwidth(monkeypatch):
    fake = FakeVpcClient(gateways=[_gateway()])
    _make_module(monkeypatch, fake)
    _base(state="present", **_id_args(name="renamed-nat", internet_max_bandwidth_out=200))
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["msg"] == "NAT gateway updated"
    assert result["nat_gateway"]["NatGatewayName"] == "renamed-nat"
    assert result["nat_gateway"]["InternetMaxBandwidthOut"] == 200
    ops = [c for c, unused in fake.calls]
    assert "ModifyNatGatewayAttribute" in ops


def test_update_enables_deletion_protection(monkeypatch):
    fake = FakeVpcClient(gateways=[_gateway()])
    _make_module(monkeypatch, fake)
    _base(state="present", **_id_args(name=NAT_NAME, deletion_protection_enabled=True))
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["nat_gateway"]["DeletionProtectionEnabled"] is True
    modifies = [req for name, req in fake.calls if name == "ModifyNatGatewayAttribute"]
    assert modifies and modifies[-1].DeletionProtectionEnabled is True


def test_update_check_mode_is_dry_run(monkeypatch):
    fake = FakeVpcClient(gateways=[_gateway()])
    _make_module(monkeypatch, fake)
    _base(_ansible_check_mode=True, state="present", **_id_args(name="renamed-nat"))
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["msg"] == "Would update NAT gateway"
    assert fake.gateways[0]["NatGatewayName"] == NAT_NAME
    assert "ModifyNatGatewayAttribute" not in [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# guards / failure paths
# ---------------------------------------------------------------------------


def test_multiple_matching_gateways_fail(monkeypatch):
    fake = FakeVpcClient(gateways=[_gateway(), _gateway(NatGatewayId="nat-bbbbbbbb")])
    _make_module(monkeypatch, fake)
    _base(state="present", name="prod")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "Ambiguous NAT gateway reference" in payload["msg"]
    assert payload["ambiguous"] is True


def test_describe_failure_maps_to_envelope(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeNatGateways(self, request):
            raise Boom("connection dropped")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    _base(state="present", **_name_args())
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed during DescribeNatGateways"
    assert "connection dropped" in payload["error"]


def test_delete_failure_maps_to_envelope(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingDeleteClient(object):
        def __init__(self):
            self.calls = []

        def DescribeNatGateways(self, request):
            self.calls.append("DescribeNatGateways")
            return SimpleNamespace(
                NatGatewaySet=[FakeResource(_gateway())], TotalCount=1, RequestId="req-list"
            )

        def DeleteNatGateway(self, request):
            self.calls.append("DeleteNatGateway")
            raise Boom("connection dropped")

    fake = ExplodingDeleteClient()
    _make_module(monkeypatch, fake)
    _base(state="absent", **_id_args())
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed during DeleteNatGateway"
    assert "connection dropped" in payload["error"]
