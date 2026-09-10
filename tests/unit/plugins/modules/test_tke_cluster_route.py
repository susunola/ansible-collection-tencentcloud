"""Unit tests for the tke_cluster_route write module (run_module flows).

Drives ``run_module()`` end to end against an in-memory fake TKE client whose
Create/Delete operations mutate a per-(table, destination) route store, so the
module's post-write ``describe_state`` refetch observes the new state
immediately.

Scenario matrix:

* create when missing (real Create + converged refetch)
* idempotent no-op when the route already exists
* absent when missing (no-op)
* delete when present (real Delete + converged refetch)
* check-mode dry run for create (no Create call)
* check-mode dry run for delete (no Delete call)
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from types import SimpleNamespace

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import tke_cluster_route as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    FakeModels,
    FakeResource,
    module_args,
    run,
)


def _route(dest, gateway="10.4.0.12"):
    return FakeResource({"RouteTableName": "cls-abc123", "DestinationCidrBlock": dest, "GatewayIp": gateway})


class FakeTkeClient(object):
    """In-memory TKE client mutating a route store keyed by destination CIDR."""

    def __init__(self, routes=None):
        # routes: list of FakeResource routes (all belonging to one route table)
        self.routes = list(routes or [])
        self.calls = []

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def DescribeClusterRoutes(self, request):
        self._record("DescribeClusterRoutes", request)
        return SimpleNamespace(
            RouteSet=[FakeResource(dict(t._data)) for t in self.routes],
            TotalCount=len(self.routes),
            RequestId="req-fake",
        )

    def CreateClusterRoute(self, request):
        self._record("CreateClusterRoute", request)
        self.routes.append(_route(request.DestinationCidrBlock, getattr(request, "GatewayIp", "")))
        return SimpleNamespace(RequestId="req-fake")

    def DeleteClusterRoute(self, request):
        self._record("DeleteClusterRoute", request)
        self.routes = [t for t in self.routes if t.DestinationCidrBlock != request.DestinationCidrBlock]
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake, models=None):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load_tke", lambda: (models or FakeModels(), SimpleNamespace(TkeClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


# ---------------------------------------------------------------------------
# create / delete flows
# ---------------------------------------------------------------------------


def test_create_when_missing(monkeypatch):
    fake = FakeTkeClient(routes=[])
    _make_module(monkeypatch, fake)
    module_args(route_table_name="cls-abc123", destination_cidr_block="10.4.0.0/16", gateway_ip="10.4.0.12", state="present")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["route_table_name"] == "cls-abc123"
    assert result["destination_cidr_block"] == "10.4.0.0/16"
    assert result["gateway_ip"] == "10.4.0.12"
    assert result["exists"] is True
    ops = [c for c, unused in fake.calls]
    assert ops[0] == "DescribeClusterRoutes"
    assert "CreateClusterRoute" in ops
    assert "DeleteClusterRoute" not in ops
    assert len(fake.routes) == 1


def test_delete_when_present(monkeypatch):
    fake = FakeTkeClient(routes=[_route("10.4.0.0/16")])
    _make_module(monkeypatch, fake)
    module_args(route_table_name="cls-abc123", destination_cidr_block="10.4.0.0/16", gateway_ip="10.4.0.12", state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["exists"] is False
    ops = [c for c, unused in fake.calls]
    assert "DeleteClusterRoute" in ops
    assert "CreateClusterRoute" not in ops
    assert fake.routes == []


# ---------------------------------------------------------------------------
# idempotent no-op flows
# ---------------------------------------------------------------------------


def test_already_present_is_idempotent(monkeypatch):
    fake = FakeTkeClient(routes=[_route("10.4.0.0/16")])
    _make_module(monkeypatch, fake)
    module_args(route_table_name="cls-abc123", destination_cidr_block="10.4.0.0/16", gateway_ip="10.4.0.12", state="present")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["exists"] is True
    ops = [c for c, unused in fake.calls]
    assert ops == ["DescribeClusterRoutes"]
    assert "CreateClusterRoute" not in ops


def test_absent_when_missing_is_idempotent(monkeypatch):
    fake = FakeTkeClient(routes=[])
    _make_module(monkeypatch, fake)
    module_args(route_table_name="cls-abc123", destination_cidr_block="10.4.0.0/16", gateway_ip="10.4.0.12", state="absent")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["exists"] is False
    assert "DeleteClusterRoute" not in [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# check-mode dry runs
# ---------------------------------------------------------------------------


def test_create_check_mode_is_dry_run(monkeypatch):
    fake = FakeTkeClient(routes=[])
    _make_module(monkeypatch, fake)
    module_args(route_table_name="cls-abc123", destination_cidr_block="10.4.0.0/16", gateway_ip="10.4.0.12",
                state="present", _ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["exists"] is True
    assert "CreateClusterRoute" not in [c for c, unused in fake.calls]
    assert fake.routes == []


def test_delete_check_mode_is_dry_run(monkeypatch):
    fake = FakeTkeClient(routes=[_route("10.4.0.0/16")])
    _make_module(monkeypatch, fake)
    module_args(route_table_name="cls-abc123", destination_cidr_block="10.4.0.0/16", gateway_ip="10.4.0.12",
                state="absent", _ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["exists"] is False
    assert "DeleteClusterRoute" not in [c for c, unused in fake.calls]
    assert len(fake.routes) == 1
