"""Main-path unit tests for the route_table module (run_module level)."""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import route_table
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    FakeModels,
    FakeResource,
    module_args,
    run,
)

TABLE = {
    "RouteTableId": "rtb-existing1",
    "VpcId": "vpc-existing1",
    "RouteTableName": "app-rtb",
    "RouteSet": [],
    "TagSet": [],
}


class FakeVpcClient(object):
    def __init__(self, tables=None):
        self.tables = list(tables or [])
        self.CreateRouteTable = MagicMock(side_effect=self._create)
        self.DeleteRouteTable = MagicMock(side_effect=self._delete)
        self.ModifyRouteTableAttribute = MagicMock()
        self.CreateRoutes = MagicMock()
        self.DeleteRoutes = MagicMock()

    def DescribeRouteTables(self, request):
        matched = self.tables
        ids = getattr(request, "RouteTableIds", None)
        if ids:
            matched = [t for t in matched if t["RouteTableId"] in ids]
        return SimpleNamespace(RouteTableSet=[FakeResource(t) for t in matched])

    def _create(self, request):
        new_table = {
            "RouteTableId": "rtb-new000001",
            "VpcId": request.VpcId,
            "RouteTableName": request.RouteTableName,
            "RouteSet": [],
            "TagSet": [],
        }
        self.tables.append(new_table)
        return SimpleNamespace(RouteTable=FakeResource(new_table))

    def _delete(self, request):
        self.tables = [t for t in self.tables if t["RouteTableId"] != request.RouteTableId]
        return SimpleNamespace()


@pytest.fixture
def client(monkeypatch):
    fake = FakeVpcClient()
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(
        route_table, "_load_vpc",
        lambda: (FakeModels(), SimpleNamespace(VpcClient=object)),
    )
    monkeypatch.setattr(
        TencentCloudModule, "create_client",
        lambda self, client_class, endpoint: fake,
    )
    return fake


def test_create_reports_changed(client):
    module_args(state="present", name="app-rtb", vpc_id="vpc-existing1")
    result = run(route_table.run_module)
    assert result["changed"] is True
    assert result["route_table"]["RouteTableName"] == "app-rtb"
    client.CreateRouteTable.assert_called_once()
    assert "diff" not in result


def test_second_run_is_idempotent(client):
    client.tables.append(dict(TABLE))
    module_args(state="present", name="app-rtb", vpc_id="vpc-existing1")
    result = run(route_table.run_module)
    assert result["changed"] is False
    assert result["route_table"]["RouteTableId"] == "rtb-existing1"
    client.CreateRouteTable.assert_not_called()
    client.ModifyRouteTableAttribute.assert_not_called()
    client.CreateRoutes.assert_not_called()
    client.DeleteRoutes.assert_not_called()


def test_absent_deletes_existing_table(client):
    client.tables.append(dict(TABLE))
    module_args(state="absent", route_table_id="rtb-existing1")
    result = run(route_table.run_module)
    assert result["changed"] is True
    client.DeleteRouteTable.assert_called_once()
    assert client.tables == []


def test_absent_on_missing_table_is_unchanged(client):
    module_args(state="absent", route_table_id="rtb-existing1")
    result = run(route_table.run_module)
    assert result["changed"] is False
    client.DeleteRouteTable.assert_not_called()


def test_check_mode_create_makes_no_sdk_writes(client):
    module_args(
        state="present", name="app-rtb", vpc_id="vpc-existing1",
        _ansible_check_mode=True,
    )
    result = run(route_table.run_module)
    assert result["changed"] is True
    assert "diff" in result
    client.CreateRouteTable.assert_not_called()
    client.DeleteRouteTable.assert_not_called()
    client.CreateRoutes.assert_not_called()


def test_diff_mode_create_includes_diff(client):
    module_args(
        state="present", name="app-rtb", vpc_id="vpc-existing1",
        _ansible_diff=True,
    )
    result = run(route_table.run_module)
    assert result["changed"] is True
    assert result["diff"]["before"] is None
    assert result["diff"]["after"]["name"] == "app-rtb"
    client.CreateRouteTable.assert_called_once()
