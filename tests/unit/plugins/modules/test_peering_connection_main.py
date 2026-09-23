"""Unit tests for the peering_connection write module (run_module flows).

Drives ``run_module()`` end to end against an in-memory fake VPC client
whose write operations mutate the connection store, so the module's
post-write ``find_connection`` refetch returns the mutated state.

The module resolves connections through ``resolver.resolve_one``, so the
fake describes the same way the real API does: ``peering-connection-name``
is a *substring* filter while ``vpc-id`` is exact. Client-side exact-match
re-resolution is then exercised for real.

Scenario matrix:

* the id-or-name identity guard
* absent on a missing connection (idempotent no-op)
* absent with a matching connection (check-mode dry run and real delete)
* creation when missing (source/destination VPC required, check mode, accept)
* no-op when nothing drifts
* drift updates on name / bandwidth / charge_type
* update check-mode dry run
* the ambiguous-name guard and the blanket SDK-failure path
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import peering_connection as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

CONNECTION = {
    "PeeringConnectionId": "pcx-abcd1234",
    "PeeringConnectionName": "app-to-db",
    "SourceVpcId": "vpc-aaaaaaaa",
    "DestinationVpcId": "vpc-bbbbbbbb",
    "DestinationRegion": "ap-guangzhou",
    "State": "ACTIVE",
    "Bandwidth": 100,
    "ChargeType": "POSTPAID_BY_DAY",
}


def _connection(**overrides):
    item = copy.deepcopy(CONNECTION)
    item.update(overrides)
    return item


def _base(**overrides):
    # peering_connection_id and name are alternatives; start from the name.
    params = {"name": "app-to-db", "source_vpc_id": "vpc-aaaaaaaa"}
    params.update(overrides)
    return module_args(**params)


def _id_base(**overrides):
    params = {"peering_connection_id": "pcx-abcd1234"}
    params.update(overrides)
    return module_args(**params)


class FakeVpcClient(object):
    """In-memory VPC client mutating a peering-connection store.

    ``peering-connection-name`` is matched as a substring (as the real API
    does); every write mutates the store so post-write refetches converge.
    """

    def __init__(self, connections=None):
        self.connections = [copy.deepcopy(t) for t in (connections or [])]
        self.calls = []
        self._next = 1

    def _record(self, name, request):
        self.calls.append((name, request))

    def DescribeVpcPeeringConnections(self, request):
        self._record("DescribeVpcPeeringConnections", request)
        items = [dict(t) for t in self.connections]
        ids = list(getattr(request, "PeeringConnectionIds", None) or [])
        if ids:
            # An explicit id list identifies the connection uniquely; the
            # module's own request builder treats ids and name/vpc filters as
            # alternatives, so an id lookup wins over the fuzzy filters.
            items = [t for t in items if t.get("PeeringConnectionId") in ids]
            return SimpleNamespace(
                PeerConnectionSet=[FakeResource(t) for t in items],
                TotalCount=len(items),
            )
        name_value = None
        vpc_value = None
        for item in list(getattr(request, "Filters", None) or []):
            name = getattr(item, "Name", None)
            values = list(getattr(item, "Values", None) or [])
            if name == "peering-connection-name":
                name_value = values[0] if values else None
            elif name == "vpc-id":
                vpc_value = values[0] if values else None
        if name_value is not None:
            items = [t for t in items if name_value in t.get("PeeringConnectionName", "")]
        if vpc_value is not None:
            items = [t for t in items if t.get("SourceVpcId") == vpc_value]
        return SimpleNamespace(
            PeerConnectionSet=[FakeResource(t) for t in items],
            TotalCount=len(items),
        )

    def CreateVpcPeeringConnection(self, request):
        self._record("CreateVpcPeeringConnection", request)
        item = {
            "PeeringConnectionId": "pcx-new-%04d" % self._next,
            "PeeringConnectionName": request.PeeringConnectionName,
            "SourceVpcId": request.SourceVpcId,
            "DestinationVpcId": request.DestinationVpcId,
            "DestinationRegion": getattr(request, "DestinationRegion", None),
            "DestinationUin": getattr(request, "DestinationUin", None),
            "Bandwidth": getattr(request, "Bandwidth", None),
            "ChargeType": getattr(request, "ChargeType", None),
            "QosLevel": getattr(request, "QosLevel", None),
            "State": "PENDING_ACCEPTANCE",
        }
        self._next += 1
        self.connections.append(item)
        return SimpleNamespace(PeeringConnectionId=item["PeeringConnectionId"], RequestId="req-fake")

    def AcceptVpcPeeringConnection(self, request):
        self._record("AcceptVpcPeeringConnection", request)
        for item in self.connections:
            if item.get("PeeringConnectionId") == request.PeeringConnectionId:
                item["State"] = "ACTIVE"
        return SimpleNamespace(RequestId="req-fake")

    def ModifyVpcPeeringConnection(self, request):
        self._record("ModifyVpcPeeringConnection", request)
        for item in self.connections:
            if item.get("PeeringConnectionId") != request.PeeringConnectionId:
                continue
            for attr in ("PeeringConnectionName", "Bandwidth", "ChargeType"):
                value = getattr(request, attr, None)
                if value is not None:
                    item[attr] = value
        return SimpleNamespace(RequestId="req-fake")

    def DeleteVpcPeeringConnection(self, request):
        self._record("DeleteVpcPeeringConnection", request)
        self.connections = [
            t for t in self.connections if t.get("PeeringConnectionId") != request.PeeringConnectionId
        ]
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake, models=None):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load_vpc", lambda: (models or FakeModels(), SimpleNamespace(VpcClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


# ---------------------------------------------------------------------------
# identity guard
# ---------------------------------------------------------------------------


def test_id_or_name_required(monkeypatch):
    fake = FakeVpcClient()
    _make_module(monkeypatch, fake)
    module_args(state="present", source_vpc_id="vpc-aaaaaaaa", destination_vpc_id="vpc-bbbbbbbb")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "peering_connection_id or name is required" in exc.value.args[0]["msg"]


# ---------------------------------------------------------------------------
# absent flows
# ---------------------------------------------------------------------------


def test_absent_missing_connection_is_idempotent(monkeypatch):
    fake = FakeVpcClient()
    _make_module(monkeypatch, fake)
    _base(state="absent", name="ghost-link")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["msg"] == "Peering connection already absent"
    assert [c for c, unused in fake.calls] == ["DescribeVpcPeeringConnections"]


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeVpcClient(connections=[_connection()])
    _make_module(monkeypatch, fake)
    _base(_ansible_check_mode=True, state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["msg"] == "Would delete peering connection"
    assert "DeleteVpcPeeringConnection" not in [c for c, unused in fake.calls]


def test_absent_deletes_connection(monkeypatch):
    fake = FakeVpcClient(connections=[_connection()])
    _make_module(monkeypatch, fake)
    _base(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["peering_connection"] is None
    assert fake.connections == []
    assert "DeleteVpcPeeringConnection" in [c for c, unused in fake.calls]


def test_absent_by_id(monkeypatch):
    fake = FakeVpcClient(connections=[_connection()])
    _make_module(monkeypatch, fake)
    _id_base(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert fake.connections == []


# ---------------------------------------------------------------------------
# creation flows
# ---------------------------------------------------------------------------


def test_create_requires_source_vpc(monkeypatch):
    fake = FakeVpcClient()
    _make_module(monkeypatch, fake)
    module_args(state="present", name="app-to-db", destination_vpc_id="vpc-bbbbbbbb")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "source_vpc_id is required when creating" in exc.value.args[0]["msg"]


def test_create_requires_destination_vpc(monkeypatch):
    fake = FakeVpcClient()
    _make_module(monkeypatch, fake)
    module_args(state="present", name="app-to-db", source_vpc_id="vpc-aaaaaaaa")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "destination_vpc_id is required when creating" in exc.value.args[0]["msg"]


def test_create_check_mode_is_dry_run(monkeypatch):
    fake = FakeVpcClient()
    _make_module(monkeypatch, fake)
    _base(_ansible_check_mode=True, state="present", name="new-link", destination_vpc_id="vpc-bbbbbbbb")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["msg"] == "Would create peering connection"
    assert fake.connections == []
    assert "CreateVpcPeeringConnection" not in [c for c, unused in fake.calls]


def test_create_accepts_pending_connection(monkeypatch):
    fake = FakeVpcClient()
    _make_module(monkeypatch, fake)
    _base(state="present", name="new-link", destination_vpc_id="vpc-bbbbbbbb", bandwidth=500)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["msg"] == "Peering connection created"
    assert result["peering_connection"]["State"] == "ACTIVE"
    ops = [c for c, unused in fake.calls]
    assert ops[0] == "DescribeVpcPeeringConnections"
    assert "CreateVpcPeeringConnection" in ops
    assert "AcceptVpcPeeringConnection" in ops


def test_create_without_accept_leaves_pending(monkeypatch):
    fake = FakeVpcClient()
    _make_module(monkeypatch, fake)
    _base(state="present", name="new-link", destination_vpc_id="vpc-bbbbbbbb", accept=False)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["peering_connection"]["State"] == "PENDING_ACCEPTANCE"
    assert "AcceptVpcPeeringConnection" not in [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# existing-connection flows
# ---------------------------------------------------------------------------


def test_connection_no_drift_is_idempotent(monkeypatch):
    fake = FakeVpcClient(connections=[_connection()])
    _make_module(monkeypatch, fake)
    _base(state="present", bandwidth=100)
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["peering_connection"]["PeeringConnectionId"] == "pcx-abcd1234"
    assert "ModifyVpcPeeringConnection" not in [c for c, unused in fake.calls]


def test_rename_requires_id_not_name(monkeypatch):
    # With a name-only identity the module looks the desired (new) name up,
    # finds nothing and falls into the create path; renaming therefore needs
    # peering_connection_id (see test_update_rename_by_id).
    fake = FakeVpcClient(connections=[_connection()])
    _make_module(monkeypatch, fake)
    _base(state="present", name="db-to-cache", bandwidth=100)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "destination_vpc_id is required when creating" in exc.value.args[0]["msg"]
    assert len(fake.connections) == 1


def test_update_bandwidth_and_charge_type_drift(monkeypatch):
    fake = FakeVpcClient(connections=[_connection()])
    _make_module(monkeypatch, fake)
    _base(
        state="present",
        name="app-to-db",
        bandwidth=200,
        charge_type="BANDWIDTH_POSTPAID_BY_HOUR",
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["peering_connection"]["Bandwidth"] == 200
    assert result["peering_connection"]["ChargeType"] == "BANDWIDTH_POSTPAID_BY_HOUR"
    assert "ModifyVpcPeeringConnection" in [c for c, unused in fake.calls]


def test_update_check_mode_is_dry_run(monkeypatch):
    fake = FakeVpcClient(connections=[_connection()])
    _make_module(monkeypatch, fake)
    _base(_ansible_check_mode=True, state="present", name="app-to-db", bandwidth=200)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["msg"] == "Would update peering connection"
    assert "ModifyVpcPeeringConnection" not in [c for c, unused in fake.calls]


def test_update_rename_by_id(monkeypatch):
    fake = FakeVpcClient(connections=[_connection()])
    _make_module(monkeypatch, fake)
    _id_base(state="present", name="renamed-link", bandwidth=100)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["peering_connection"]["PeeringConnectionName"] == "renamed-link"
    assert fake.connections[0]["PeeringConnectionId"] == "pcx-abcd1234"


# ---------------------------------------------------------------------------
# guards / failure paths
# ---------------------------------------------------------------------------


def test_ambiguous_name_fails(monkeypatch):
    fake = FakeVpcClient(connections=[
        _connection(),
        _connection(PeeringConnectionId="pcx-dup0000"),
    ])
    _make_module(monkeypatch, fake)
    _base(state="present", name="app-to-db", bandwidth=100)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "Ambiguous peering connection reference" in payload["msg"]
    assert payload["ambiguous"] is True


def test_fuzzy_single_candidate_is_accepted(monkeypatch):
    # ``peering-connection-name`` is a substring filter. When a name lookup
    # has no exact match but the substring filter returns exactly one
    # candidate, that candidate is the resource being managed (not a create).
    fake = FakeVpcClient(connections=[_connection(PeeringConnectionName="prod-backbone")])
    _make_module(monkeypatch, fake)
    _base(state="present", name="backbone", bandwidth=200)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["peering_connection"]["PeeringConnectionId"] == "pcx-abcd1234"
    assert result["peering_connection"]["Bandwidth"] == 200
    assert len(fake.connections) == 1
    assert "ModifyVpcPeeringConnection" in [c for c, unused in fake.calls]


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeVpcPeeringConnections(self, request):
            raise Boom("connection dropped")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    _base(state="present")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]
