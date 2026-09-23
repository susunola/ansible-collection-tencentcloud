"""Unit tests for the tke_cluster_route_table write module (run_module flows).

Drives ``run_module()`` end to end against an in-memory fake TKE client whose
Create/Delete operations mutate a route-table store, so the module's
post-write ``describe_state`` refetch observes the new state immediately.

Scenario matrix:

* create when missing (real Create + converged refetch)
* idempotent no-op when the table already exists
* absent when missing (no-op)
* delete when present (real Delete + converged refetch)
* check-mode dry run for create (no Create call)
* check-mode dry run for delete (no Delete call)
* required_if guard (state=present needs cidr block and vpc id)
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import tke_cluster_route_table as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)


def _table(name, cidr="10.4.0.0/16", vpc="vpc-abc", enabled=1):
    return FakeResource({"RouteTableName": name, "RouteTableCidrBlock": cidr, "VpcId": vpc, "Enabled": enabled})


class FakeTkeClient(object):
    """In-memory TKE client mutating a route-table store keyed by name."""

    def __init__(self, tables=None):
        # tables: list of FakeResource route tables
        self.tables = list(tables or [])
        self.calls = []

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def DescribeClusterRouteTables(self, request):
        self._record("DescribeClusterRouteTables", request)
        return SimpleNamespace(
            RouteTableSet=[FakeResource(dict(t._data)) for t in self.tables],
            TotalCount=len(self.tables),
            RequestId="req-fake",
        )

    def CreateClusterRouteTable(self, request):
        self._record("CreateClusterRouteTable", request)
        self.tables.append(_table(
            request.RouteTableName,
            getattr(request, "RouteTableCidrBlock", "0.0.0.0/0"),
            getattr(request, "VpcId", ""),
        ))
        return SimpleNamespace(RouteTableCidrBlock=request.RouteTableCidrBlock, RequestId="req-fake")

    def DeleteClusterRouteTable(self, request):
        self._record("DeleteClusterRouteTable", request)
        self.tables = [t for t in self.tables if t.RouteTableName != request.RouteTableName]
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
    fake = FakeTkeClient(tables=[])
    _make_module(monkeypatch, fake)
    module_args(route_table_name="cls-abc123", route_table_cidr_block="10.4.0.0/16", vpc_id="vpc-abc", state="present")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["route_table_name"] == "cls-abc123"
    assert result["exists"] is True
    ops = [c for c, unused in fake.calls]
    assert ops[0] == "DescribeClusterRouteTables"
    assert "CreateClusterRouteTable" in ops
    assert "DeleteClusterRouteTable" not in ops
    assert len(fake.tables) == 1


def test_delete_when_present(monkeypatch):
    fake = FakeTkeClient(tables=[_table("cls-abc123")])
    _make_module(monkeypatch, fake)
    module_args(route_table_name="cls-abc123", state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["exists"] is False
    ops = [c for c, unused in fake.calls]
    assert "DeleteClusterRouteTable" in ops
    assert "CreateClusterRouteTable" not in ops
    assert fake.tables == []


# ---------------------------------------------------------------------------
# idempotent no-op flows
# ---------------------------------------------------------------------------


def test_already_present_is_idempotent(monkeypatch):
    fake = FakeTkeClient(tables=[_table("cls-abc123")])
    _make_module(monkeypatch, fake)
    module_args(route_table_name="cls-abc123", route_table_cidr_block="10.4.0.0/16", vpc_id="vpc-abc", state="present")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["exists"] is True
    ops = [c for c, unused in fake.calls]
    assert ops == ["DescribeClusterRouteTables"]
    assert "CreateClusterRouteTable" not in ops


def test_absent_when_missing_is_idempotent(monkeypatch):
    fake = FakeTkeClient(tables=[])
    _make_module(monkeypatch, fake)
    module_args(route_table_name="cls-ghost", state="absent")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["exists"] is False
    assert "DeleteClusterRouteTable" not in [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# check-mode dry runs
# ---------------------------------------------------------------------------


def test_create_check_mode_is_dry_run(monkeypatch):
    fake = FakeTkeClient(tables=[])
    _make_module(monkeypatch, fake)
    module_args(route_table_name="cls-abc123", route_table_cidr_block="10.4.0.0/16", vpc_id="vpc-abc",
                state="present", _ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["exists"] is True
    assert "CreateClusterRouteTable" not in [c for c, unused in fake.calls]
    assert fake.tables == []


def test_delete_check_mode_is_dry_run(monkeypatch):
    fake = FakeTkeClient(tables=[_table("cls-abc123")])
    _make_module(monkeypatch, fake)
    module_args(route_table_name="cls-abc123", state="absent", _ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["exists"] is False
    assert "DeleteClusterRouteTable" not in [c for c, unused in fake.calls]
    assert len(fake.tables) == 1


# ---------------------------------------------------------------------------
# guards
# ---------------------------------------------------------------------------


def test_present_requires_cidr_and_vpc(monkeypatch):
    fake = FakeTkeClient(tables=[])
    _make_module(monkeypatch, fake)
    module_args(route_table_name="cls-abc123", state="present")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "route_table_cidr_block" in exc.value.args[0]["msg"]
