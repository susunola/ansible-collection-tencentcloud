"""Unit tests for the dlc_network_connection write module (run_module flows).

The DLC API exposes no create/delete for network connections, so the module
discovers an existing connection by exact name and reconciles its
description. The fake DLC client mutates a connection store so post-write
``find`` calls and the optional waiter converge immediately.

Scenario matrix:

* argument validation (missing name/description)
* no-op when the description already matches
* description drift applies ``UpdateNetworkConnection``
* ambiguous names fail without a disambiguator
* check-mode dry run
* the blanket SDK failure path
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import dlc_network_connection as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

CONNECTION = {
    "DatasourceConnectionName": "analytics-vpc",
    "NetworkConnectionDesc": "old description",
    "HouseName": "spark-prod",
    "DatasourceConnectionVpcId": "vpc-1",
    "NetworkConnectionType": 2,
}


def _args(**overrides):
    params = {"name": "analytics-vpc", "description": "production route"}
    params.update(overrides)
    return module_args(**params)


class FakeDlcClient(object):
    """In-memory DLC client mutating a network-connection store."""

    def __init__(self, connections=None):
        self.connections = [copy.deepcopy(c) for c in (connections or [])]
        self.calls = []

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def DescribeNetworkConnections(self, request):
        self._record("DescribeNetworkConnections", request)
        matches = []
        for item in self.connections:
            if item.get("DatasourceConnectionName") != getattr(request, "NetworkConnectionName", None):
                continue
            if getattr(request, "DataEngineName", None) is not None and item.get("HouseName") != request.DataEngineName:
                continue
            if getattr(request, "DatasourceConnectionVpcId", None) is not None and item.get("DatasourceConnectionVpcId") != request.DatasourceConnectionVpcId:
                continue
            if getattr(request, "NetworkConnectionType", None) is not None and item.get("NetworkConnectionType") != request.NetworkConnectionType:
                continue
            matches.append(item)
        return SimpleNamespace(NetworkConnectionSet=[FakeResource(c) for c in matches], TotalCount=len(matches))

    def UpdateNetworkConnection(self, request):
        self._record("UpdateNetworkConnection", request)
        for item in self.connections:
            if item.get("DatasourceConnectionName") == getattr(request, "NetworkConnectionName", None):
                item["NetworkConnectionDesc"] = getattr(request, "NetworkConnectionDesc", None)
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake, models=None):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (models or FakeModels(), SimpleNamespace(DlcClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


def test_missing_required_args_fails(monkeypatch):
    fake = FakeDlcClient()
    _make_module(monkeypatch, fake)
    module_args()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "missing required arguments" in exc.value.args[0]["msg"]
    assert fake.calls == []


def test_idempotent_when_description_matches(monkeypatch):
    connection = dict(CONNECTION)
    connection["NetworkConnectionDesc"] = "production route"
    fake = FakeDlcClient(connections=[connection])
    _make_module(monkeypatch, fake)
    _args()
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["network_connection"]["NetworkConnectionDesc"] == "production route"
    assert [c for c, unused in fake.calls] == ["DescribeNetworkConnections"]


def test_description_drift_updates_connection(monkeypatch):
    fake = FakeDlcClient(connections=[CONNECTION])
    _make_module(monkeypatch, fake)
    _args()
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["network_connection"]["NetworkConnectionDesc"] == "production route"
    update_call = next((c, r) for c, r in fake.calls if c == "UpdateNetworkConnection")
    assert getattr(update_call[1], "NetworkConnectionName") == "analytics-vpc"
    assert getattr(update_call[1], "NetworkConnectionDesc") == "production route"


def test_disambiguated_drift_uses_scoping_request(monkeypatch):
    fake = FakeDlcClient(connections=[CONNECTION])
    _make_module(monkeypatch, fake)
    _args(data_engine_name="spark-prod", vpc_id="vpc-1", connection_type=2)
    result = run(mod.run_module)
    assert result["changed"] is True
    describe_calls = [r for c, r in fake.calls if c == "DescribeNetworkConnections"]
    assert describe_calls[0].DataEngineName == "spark-prod"
    assert describe_calls[0].DatasourceConnectionVpcId == "vpc-1"
    assert describe_calls[0].NetworkConnectionType == 2


def test_update_check_mode_is_dry_run(monkeypatch):
    fake = FakeDlcClient(connections=[CONNECTION])
    _make_module(monkeypatch, fake)
    _args(_ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["network_connection"]["NetworkConnectionDesc"] == "production route"
    assert "UpdateNetworkConnection" not in [c for c, unused in fake.calls]
    assert fake.connections[0]["NetworkConnectionDesc"] == "old description"


def test_ambiguous_connection_fails(monkeypatch):
    second = dict(CONNECTION)
    second["HouseName"] = "flink-prod"
    fake = FakeDlcClient(connections=[CONNECTION, second])
    _make_module(monkeypatch, fake)
    _args()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "Multiple DLC network connections matched" in payload["msg"]
    assert "data_engine_name, vpc_id or connection_type" in payload["msg"]


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeNetworkConnections(self, request):
            raise Boom("connection dropped")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    _args()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]


# ---------------------------------------------------------------------------
# legacy helper regression tests (folded from test_dlc_network_connection.py)
# ---------------------------------------------------------------------------


def legacy_params():
    return {"name": "analytics-vpc", "data_engine_name": "spark-prod", "vpc_id": "vpc-1", "connection_type": 2}


def test_describe_request_scopes_exact_connection_identity_and_paginates():
    request = mod.describe_request(FakeModels(), legacy_params(), 100)
    assert request.NetworkConnectionName == "analytics-vpc"
    assert request.DataEngineName == "spark-prod"
    assert request.DatasourceConnectionVpcId == "vpc-1"
    assert request.NetworkConnectionType == 2
    assert request.Offset == 100
    assert request.Limit == 100


def test_update_request_only_changes_description_for_exact_name():
    request = mod.update_request(FakeModels(), "analytics-vpc", "production route")
    assert request.NetworkConnectionName == "analytics-vpc"
    assert request.NetworkConnectionDesc == "production route"
