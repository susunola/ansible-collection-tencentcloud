"""Unit tests for the tse_gateway_public_network write module (run_module flows).

Drives ``run_module()`` end to end against an in-memory fake TSE client
whose write operations mutate the gateway-group public-network store, so the
module's post-write ``current`` refetch and the converged-state waiter
return immediately.

Scenario matrix:

* absent on a missing public network (idempotent no-op)
* absent with a matching public network (check-mode dry run and real delete)
* creation when missing (with/without ``config``, by group name and group id,
  check mode)
* group-name resolution failures (not found / multiple matches)
* no-op when nothing drifts
* drift updates on CLB basics and on the access-control policy
* the immutable zone-topology guard
* the ``required_one_of`` identity guard and the blanket SDK-failure path
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import tse_gateway_public_network as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

NETWORK = {
    "NetworkId": "net-10001",
    "GroupId": "group-prod",
    "Vip": "203.0.113.10",
    "Status": "Open",
    "InternetMaxBandwidthOut": 20,
    "Description": "production ingress",
    "AccessControl": {"Mode": "Whitelist", "CidrWhiteList": ["203.0.113.0/24"]},
}

GROUPS = [{"GroupId": "group-prod", "Name": "production-secondary"}]

CONFIG = {
    "InternetAddressVersion": "IPV4",
    "InternetPayMode": "BANDWIDTH",
    "InternetMaxBandwidthOut": 20,
    "Description": "production ingress",
}

ACL = {"Mode": "Whitelist", "CidrWhiteList": ["203.0.113.0/24"]}


class NotFoundError(Exception):
    def get_code(self):
        return "ResourceNotFound.PublicNetworkNotExists"

    def get_request_id(self):
        return None


def _network(**overrides):
    item = copy.deepcopy(NETWORK)
    item.update(overrides)
    return item


def _base(**overrides):
    # group_id / group_name are mutually exclusive: start from group_id only.
    params = {"gateway_id": "gateway-abcdef", "group_id": "group-prod"}
    params.update(overrides)
    return module_args(**params)


def _name_base(**overrides):
    params = {"gateway_id": "gateway-abcdef", "group_name": "production-secondary"}
    params.update(overrides)
    return module_args(**params)


class FakeTseClient(object):
    """In-memory TSE client mutating a public-network store."""

    def __init__(self, networks=None, groups=None):
        self.networks = [copy.deepcopy(t) for t in (networks or [])]
        self.groups = [copy.deepcopy(t) for t in (GROUPS if groups is None else groups)]
        self.calls = []
        self._next = 0

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def _find(self, gateway_id, group_id, network_id=None):
        for item in self.networks:
            if item.get("GatewayId", "gateway-abcdef") != gateway_id:
                continue
            if item.get("GroupId") != group_id:
                continue
            if network_id and item.get("NetworkId") != network_id:
                continue
            return item
        return None

    def DescribeNativeGatewayServerGroups(self, request):
        self._record("DescribeNativeGatewayServerGroups", request)
        wanted = None
        for item in list(getattr(request, "Filters", None) or []):
            if getattr(item, "Name", None) == "Name":
                wanted = (getattr(item, "Values", None) or [None])[0]
        matches = [dict(t) for t in self.groups if wanted is None or t.get("Name") == wanted]
        return SimpleNamespace(
            Result=SimpleNamespace(GatewayGroupList=[FakeResource(t) for t in matches]),
        )

    def DescribePublicNetwork(self, request):
        self._record("DescribePublicNetwork", request)
        item = self._find(request.GatewayId, request.GroupId, getattr(request, "NetworkId", None))
        if item is None:
            raise NotFoundError()
        return SimpleNamespace(
            Result=SimpleNamespace(PublicNetwork=FakeResource(dict(item))),
        )

    def CreateCloudNativeAPIGatewayPublicNetwork(self, request):
        self._record("CreateCloudNativeAPIGatewayPublicNetwork", request)
        self._next += 1
        internet = dict(getattr(request, "InternetConfig", None) or {})
        item = {
            "GatewayId": request.GatewayId,
            "GroupId": request.GroupId,
            "NetworkId": "net-new-%03d" % self._next,
            "Vip": "203.0.113.%d" % (self._next + 10),
            "Status": "Open",
        }
        item.update(internet)
        self.networks.append(item)
        return SimpleNamespace(
            Result=SimpleNamespace(NetworkId=item["NetworkId"]),
            RequestId="req-fake",
        )

    def ModifyNetworkBasicInfo(self, request):
        self._record("ModifyNetworkBasicInfo", request)
        item = self._find(request.GatewayId, request.GroupId)
        if item is None:
            return SimpleNamespace(RequestId="req-fake")
        for attr in ("InternetMaxBandwidthOut", "Description", "SlaType"):
            value = getattr(request, attr, None)
            if value is not None:
                item[attr] = value
        return SimpleNamespace(RequestId="req-fake")

    def ModifyNetworkAccessStrategy(self, request):
        self._record("ModifyNetworkAccessStrategy", request)
        item = self._find(request.GatewayId, request.GroupId)
        if item is None:
            return SimpleNamespace(RequestId="req-fake")
        item["AccessControl"] = dict(vars(request.AccessControl))
        return SimpleNamespace(RequestId="req-fake")

    def DeleteCloudNativeAPIGatewayPublicNetwork(self, request):
        self._record("DeleteCloudNativeAPIGatewayPublicNetwork", request)
        item = self._find(request.GatewayId, request.GroupId)
        if item is not None:
            self.networks.remove(item)
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake, models=None):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (models or FakeModels(), SimpleNamespace(TseClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


# ---------------------------------------------------------------------------
# absent flows
# ---------------------------------------------------------------------------


def test_absent_missing_network_is_idempotent(monkeypatch):
    fake = FakeTseClient(networks=[])
    _make_module(monkeypatch, fake)
    _base(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["public_network"] is None
    ops = [c for c, unused in fake.calls]
    assert "DescribePublicNetwork" in ops


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeTseClient(networks=[_network()])
    _make_module(monkeypatch, fake)
    _base(_ansible_check_mode=True, state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert len(fake.networks) == 1
    assert "DeleteCloudNativeAPIGatewayPublicNetwork" not in [c for c, unused in fake.calls]


def test_absent_deletes_network(monkeypatch):
    fake = FakeTseClient(networks=[_network()])
    _make_module(monkeypatch, fake)
    _base(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["public_network"] is None
    assert fake.networks == []
    ops = [c for c, unused in fake.calls]
    assert "DeleteCloudNativeAPIGatewayPublicNetwork" in ops


# ---------------------------------------------------------------------------
# group-name resolution
# ---------------------------------------------------------------------------


def test_group_name_resolution_fails_when_unknown(monkeypatch):
    fake = FakeTseClient(networks=[], groups=[])
    _make_module(monkeypatch, fake)
    _name_base(state="present", group_name="production-secondary", config=CONFIG)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "TSE gateway group name was not found" in exc.value.args[0]["msg"]


def test_group_name_resolution_fails_when_ambiguous(monkeypatch):
    fake = FakeTseClient(networks=[], groups=[GROUPS[0], dict(GROUPS[0], GroupId="group-dup")])
    _make_module(monkeypatch, fake)
    _name_base(state="present", group_name="production-secondary", config=CONFIG)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "Multiple TSE gateway groups matched the name" in exc.value.args[0]["msg"]


def test_create_by_group_name_resolves_group_id(monkeypatch):
    fake = FakeTseClient(networks=[])
    _make_module(monkeypatch, fake)
    _name_base(state="present", group_name="production-secondary", config=CONFIG, access_control=ACL)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["public_network"]["GroupId"] == "group-prod"
    ops = [c for c, unused in fake.calls]
    assert "DescribeNativeGatewayServerGroups" in ops
    assert "CreateCloudNativeAPIGatewayPublicNetwork" in ops


# ---------------------------------------------------------------------------
# creation flows
# ---------------------------------------------------------------------------


def test_create_requires_config(monkeypatch):
    fake = FakeTseClient(networks=[])
    _make_module(monkeypatch, fake)
    _base(state="present")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "config is required for a new TSE gateway public network" in exc.value.args[0]["msg"]


def test_create_network(monkeypatch):
    fake = FakeTseClient(networks=[])
    _make_module(monkeypatch, fake)
    _base(state="present", config=CONFIG, access_control=ACL)
    result = run(mod.run_module)
    assert result["changed"] is True
    network = result["public_network"]
    assert network["NetworkId"].startswith("net-new-")
    assert network["InternetMaxBandwidthOut"] == 20
    assert network["Description"] == "production ingress"
    assert network["AccessControl"]["Mode"] == "Whitelist"
    assert len(fake.networks) == 1
    ops = [c for c, unused in fake.calls]
    assert ops[0] == "DescribePublicNetwork"
    assert "CreateCloudNativeAPIGatewayPublicNetwork" in ops
    assert "ModifyNetworkAccessStrategy" in ops


def test_create_check_mode_is_dry_run(monkeypatch):
    fake = FakeTseClient(networks=[])
    _make_module(monkeypatch, fake)
    _base(_ansible_check_mode=True, state="present", config=CONFIG)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["public_network"]["InternetMaxBandwidthOut"] == 20
    assert fake.networks == []
    assert "CreateCloudNativeAPIGatewayPublicNetwork" not in [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# existing-network flows
# ---------------------------------------------------------------------------


def test_existing_network_no_drift_is_idempotent(monkeypatch):
    fake = FakeTseClient(networks=[_network()])
    _make_module(monkeypatch, fake)
    _base(state="present", config=CONFIG, access_control=ACL)
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["public_network"]["NetworkId"] == "net-10001"


def test_basic_drift_updates_clb_info(monkeypatch):
    fake = FakeTseClient(networks=[_network(InternetMaxBandwidthOut=10)])
    _make_module(monkeypatch, fake)
    _base(state="present", config=dict(CONFIG, InternetMaxBandwidthOut=50))
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["public_network"]["InternetMaxBandwidthOut"] == 50
    ops = [c for c, unused in fake.calls]
    assert "ModifyNetworkBasicInfo" in ops
    assert "ModifyNetworkAccessStrategy" not in ops


def test_access_control_drift_updates_strategy(monkeypatch):
    fake = FakeTseClient(networks=[_network(AccessControl={"Mode": "Whitelist", "CidrWhiteList": ["198.51.100.0/24"]})])
    _make_module(monkeypatch, fake)
    _base(state="present", config=CONFIG, access_control=ACL)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["public_network"]["AccessControl"]["CidrWhiteList"] == ["203.0.113.0/24"]
    ops = [c for c, unused in fake.calls]
    assert "ModifyNetworkAccessStrategy" in ops


def test_zone_topology_is_immutable(monkeypatch):
    fake = FakeTseClient(networks=[_network()])
    _make_module(monkeypatch, fake)
    _base(state="present", config=dict(CONFIG, MultiZoneFlag=True, MasterZoneId="ap-guangzhou-3"))
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "zone topology is immutable" in payload["msg"]
    assert "MultiZoneFlag" in payload["immutable_drift"]
    assert "MasterZoneId" in payload["immutable_drift"]


# ---------------------------------------------------------------------------
# guards / failure paths
# ---------------------------------------------------------------------------


def test_identity_guard_requires_group(monkeypatch):
    fake = FakeTseClient(networks=[])
    _make_module(monkeypatch, fake)
    module_args(gateway_id="gateway-abcdef", state="present", config=CONFIG)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "one of the following is required: group_id, group_name" in exc.value.args[0]["msg"]


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribePublicNetwork(self, request):
            raise Boom("connection dropped")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    _base(state="present", config=CONFIG)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]
