"""Unit tests for the network_acl write module (run_module flows).

Drives ``run_module()`` against an in-memory fake VPC client whose create /
entries / subnet / delete operations mutate an ACL store, so the module's
post-write refetches converge immediately.

Scenario matrix:

* absent on a missing ACL, identified by name or by id (idempotent no-op)
* absent with a matching ACL (check-mode dry run, real delete)
* creation when missing (name/vpc_id required guard, happy path with
  ingress/egress/subnet reconciliation, check mode)
* no-op when nothing drifts
* rename by ``network_acl_id``
* ingress/subnet drift reconciliation on an existing ACL
* the ambiguous-name guard and the blanket SDK failure path
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import network_acl as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

VPC_ID = "vpc-8b0a1c2d"
SUBNET_A = "subnet-aaaa"
SUBNET_B = "subnet-bbbb"

INGRESS_443 = {
    "Protocol": "TCP",
    "Port": "443",
    "CidrBlock": "10.0.0.0/8",
    "Action": "ACCEPT",
    "Priority": 1,
    "Description": "",
}
EGRESS_ALL = {
    "Protocol": "ALL",
    "CidrBlock": "0.0.0.0/0",
    "Action": "ACCEPT",
    "Priority": 1,
    "Description": "",
}

ACL = {
    "NetworkAclId": "acl-8b0a1c2d",
    "NetworkAclName": "app-acl",
    "VpcId": VPC_ID,
    "IngressEntries": [],
    "EgressEntries": [],
    "SubnetSet": [],
}


def _acl(**overrides):
    item = copy.deepcopy(ACL)
    item.update(overrides)
    return item


def _name_args(**overrides):
    params = {"name": "app-acl", "vpc_id": VPC_ID}
    params.update(overrides)
    return module_args(**params)


def _id_args(**overrides):
    params = {"network_acl_id": "acl-8b0a1c2d"}
    params.update(overrides)
    return module_args(**params)


def _api_entry(obj):
    result = {
        "Protocol": getattr(obj, "Protocol", None),
        "Action": getattr(obj, "Action", None),
        "Priority": getattr(obj, "Priority", None),
        "Description": getattr(obj, "Description", ""),
    }
    for key in ("Port", "CidrBlock", "Ipv6CidrBlock"):
        value = getattr(obj, key, None)
        if value is not None:
            result[key] = value
    return result


class FakeVpcClient(object):
    """In-memory VPC client mutating a small network-ACL store."""

    def __init__(self, acls=None):
        self.acls = [copy.deepcopy(t) for t in (acls or [])]
        self.calls = []
        self._next = 0

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def _by_id(self, acl_id):
        for item in self.acls:
            if item.get("NetworkAclId") == acl_id:
                return item
        return None

    def DescribeNetworkAcls(self, request):
        self._record("DescribeNetworkAcls", request)
        ids = list(getattr(request, "NetworkAclIds", None) or [])
        if ids:
            matches = [t for t in self.acls if t.get("NetworkAclId") in ids]
        else:
            matches = list(self.acls)
        return SimpleNamespace(
            NetworkAclSet=[FakeResource(t) for t in matches],
            TotalCount=len(matches),
        )

    def CreateNetworkAcl(self, request):
        self._record("CreateNetworkAcl", request)
        self._next += 1
        item = {
            "NetworkAclId": "acl-new-%03d" % self._next,
            "NetworkAclName": getattr(request, "NetworkAclName", None),
            "VpcId": getattr(request, "VpcId", None),
            "IngressEntries": [],
            "EgressEntries": [],
            "SubnetSet": [],
        }
        self.acls.append(item)
        return SimpleNamespace(NetworkAcl=SimpleNamespace(NetworkAclId=item["NetworkAclId"]), RequestId="req-fake")

    def ModifyNetworkAclAttribute(self, request):
        self._record("ModifyNetworkAclAttribute", request)
        item = self._by_id(getattr(request, "NetworkAclId", None))
        if item is not None and getattr(request, "NetworkAclName", None) is not None:
            item["NetworkAclName"] = request.NetworkAclName
        return SimpleNamespace(RequestId="req-fake")

    def ModifyNetworkAclEntries(self, request):
        self._record("ModifyNetworkAclEntries", request)
        item = self._by_id(getattr(request, "NetworkAclId", None))
        entry_set = getattr(request, "NetworkAclEntrySet", None)
        if item is not None and entry_set is not None:
            item["IngressEntries"] = [_api_entry(e) for e in (entry_set.Ingress or [])]
            item["EgressEntries"] = [_api_entry(e) for e in (entry_set.Egress or [])]
        return SimpleNamespace(RequestId="req-fake")

    def AssociateNetworkAclSubnets(self, request):
        self._record("AssociateNetworkAclSubnets", request)
        item = self._by_id(getattr(request, "NetworkAclId", None))
        if item is not None:
            existing = {s.get("SubnetId") for s in item.get("SubnetSet") or []}
            for subnet_id in getattr(request, "SubnetIds", None) or []:
                if subnet_id not in existing:
                    item.setdefault("SubnetSet", []).append({"SubnetId": subnet_id})
        return SimpleNamespace(RequestId="req-fake")

    def DisassociateNetworkAclSubnets(self, request):
        self._record("DisassociateNetworkAclSubnets", request)
        item = self._by_id(getattr(request, "NetworkAclId", None))
        if item is not None:
            removed = set(getattr(request, "SubnetIds", None) or [])
            item["SubnetSet"] = [s for s in item.get("SubnetSet") or [] if s.get("SubnetId") not in removed]
        return SimpleNamespace(RequestId="req-fake")

    def DeleteNetworkAcl(self, request):
        self._record("DeleteNetworkAcl", request)
        self.acls = [t for t in self.acls if t.get("NetworkAclId") != getattr(request, "NetworkAclId", None)]
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake, models=None):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load_vpc", lambda: (models or FakeModels(), SimpleNamespace(VpcClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


def _ingress_rule(**overrides):
    rule = {"protocol": "TCP", "port": "443", "cidr": "10.0.0.0/8", "action": "ACCEPT", "priority": 1}
    rule.update(overrides)
    return rule


def _egress_rule(**overrides):
    rule = {"protocol": "ALL", "cidr": "0.0.0.0/0", "action": "ACCEPT", "priority": 1}
    rule.update(overrides)
    return rule


# ---------------------------------------------------------------------------
# absent flows
# ---------------------------------------------------------------------------


def test_absent_missing_by_name_is_idempotent(monkeypatch):
    fake = FakeVpcClient(acls=[])
    _make_module(monkeypatch, fake)
    _name_args(state="absent", name="ghost-acl")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["network_acl"] is None
    assert [c for c, unused in fake.calls] == ["DescribeNetworkAcls"]


def test_absent_missing_by_id_is_idempotent(monkeypatch):
    fake = FakeVpcClient(acls=[])
    _make_module(monkeypatch, fake)
    _id_args(state="absent", network_acl_id="acl-ghost")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["network_acl"] is None


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeVpcClient(acls=[_acl()])
    _make_module(monkeypatch, fake)
    _name_args(_ansible_check_mode=True, state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["msg"] == "Would delete network ACL"
    assert result["network_acl"]["NetworkAclId"] == ACL["NetworkAclId"]
    assert len(fake.acls) == 1
    assert "DeleteNetworkAcl" not in [c for c, unused in fake.calls]


def test_absent_deletes_acl(monkeypatch):
    fake = FakeVpcClient(acls=[_acl()])
    _make_module(monkeypatch, fake)
    _id_args(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["network_acl"] is None
    assert fake.acls == []
    ops = [c for c, unused in fake.calls]
    assert "DeleteNetworkAcl" in ops


# ---------------------------------------------------------------------------
# creation flows
# ---------------------------------------------------------------------------


def test_create_requires_name_and_vpc_id(monkeypatch):
    fake = FakeVpcClient(acls=[])
    _make_module(monkeypatch, fake)
    _id_args(state="present", network_acl_id="acl-ghost")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert exc.value.args[0]["msg"] == "name and vpc_id are required when creating a network ACL"


def test_create_acl_with_rules_and_subnets(monkeypatch):
    fake = FakeVpcClient(acls=[])
    _make_module(monkeypatch, fake)
    _name_args(
        state="present",
        ingress=[_ingress_rule()],
        egress=[_egress_rule()],
        subnet_ids=[SUBNET_A],
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["network_acl"]["NetworkAclName"] == "app-acl"
    assert result["network_acl"]["IngressEntries"][0]["Protocol"] == "TCP"
    assert result["network_acl"]["EgressEntries"][0]["Protocol"] == "ALL"
    assert [s["SubnetId"] for s in result["network_acl"]["SubnetSet"]] == [SUBNET_A]
    ops = [c for c, unused in fake.calls]
    assert "CreateNetworkAcl" in ops
    assert "ModifyNetworkAclEntries" in ops
    assert "AssociateNetworkAclSubnets" in ops


def test_create_check_mode_is_dry_run(monkeypatch):
    fake = FakeVpcClient(acls=[])
    _make_module(monkeypatch, fake)
    _name_args(
        _ansible_check_mode=True,
        state="present",
        ingress=[_ingress_rule()],
        subnet_ids=[SUBNET_A],
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["msg"] == "Would create network ACL"
    assert result["network_acl"] is None
    assert fake.acls == []
    assert "CreateNetworkAcl" not in [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# existing-ACL flows
# ---------------------------------------------------------------------------


def test_existing_acl_no_drift_is_idempotent(monkeypatch):
    fake = FakeVpcClient(acls=[_acl(
        IngressEntries=[INGRESS_443],
        SubnetSet=[{"SubnetId": SUBNET_A}],
    )])
    _make_module(monkeypatch, fake)
    _name_args(state="present", ingress=[_ingress_rule()], subnet_ids=[SUBNET_A])
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["msg"] == "Network ACL is up to date"
    assert result["network_acl"]["NetworkAclId"] == ACL["NetworkAclId"]
    ops = [c for c, unused in fake.calls]
    assert "ModifyNetworkAclEntries" not in ops
    assert "ModifyNetworkAclAttribute" not in ops


def test_rename_acl_by_id(monkeypatch):
    fake = FakeVpcClient(acls=[_acl(NetworkAclName="old-name")])
    _make_module(monkeypatch, fake)
    _id_args(state="present", name="new-name")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["msg"] == "Network ACL reconciled"
    assert result["network_acl"]["NetworkAclName"] == "new-name"
    ops = [c for c, unused in fake.calls]
    assert "ModifyNetworkAclAttribute" in ops


def test_rules_drift_reconciles_entries(monkeypatch):
    fake = FakeVpcClient(acls=[_acl(
        IngressEntries=[INGRESS_443],
        SubnetSet=[{"SubnetId": SUBNET_A}],
    )])
    _make_module(monkeypatch, fake)
    _name_args(
        state="present",
        ingress=[_ingress_rule(priority=2, port="8443")],
        subnet_ids=[SUBNET_A],
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["network_acl"]["IngressEntries"][0]["Port"] == "8443"
    ops = [c for c, unused in fake.calls]
    assert "ModifyNetworkAclEntries" in ops


def test_subnet_drift_adds_and_removes(monkeypatch):
    fake = FakeVpcClient(acls=[_acl(
        IngressEntries=[INGRESS_443],
        SubnetSet=[{"SubnetId": SUBNET_A}, {"SubnetId": SUBNET_B}],
    )])
    _make_module(monkeypatch, fake)
    _name_args(state="present", ingress=[_ingress_rule()], subnet_ids=[SUBNET_A])
    result = run(mod.run_module)
    assert result["changed"] is True
    assert sorted(s["SubnetId"] for s in result["network_acl"]["SubnetSet"]) == [SUBNET_A]
    ops = [c for c, unused in fake.calls]
    assert "DisassociateNetworkAclSubnets" in ops
    assert "AssociateNetworkAclSubnets" not in ops


def test_ambiguous_name_match_fails(monkeypatch):
    fake = FakeVpcClient(acls=[_acl(), _acl(NetworkAclId="acl-dup")])
    _make_module(monkeypatch, fake)
    _name_args(state="present")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "Ambiguous network ACL reference" in exc.value.args[0]["msg"]


# ---------------------------------------------------------------------------
# failure paths
# ---------------------------------------------------------------------------


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeNetworkAcls(self, request):
            raise Boom("connection dropped")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    _name_args(state="present")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]
