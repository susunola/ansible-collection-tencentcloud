"""Unit tests for the dlc_user_vpc_connection write module (run_module flows)."""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import dlc_user_vpc_connection as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

CONNECTION = {
    "UserVpcEndpointId": "vpce-8b0a1c2d",
    "UserVpcEndpointName": "analytics-endpoint",
    "EngineNetworkId": "engine-network-abc",
    "UserVpcId": "vpc-abc",
}


def _connection(**overrides):
    item = copy.deepcopy(CONNECTION)
    item.update(overrides)
    return item


class FakeDlcClient(object):
    """In-memory DLC client mutating a user-VPC connection store."""

    def __init__(self, connections=None):
        self.connections = [copy.deepcopy(t) for t in (connections or [])]
        self.calls = []
        self._next = 0

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def _find(self, endpoint_id=None, name=None):
        for item in self.connections:
            if endpoint_id is not None and item.get("UserVpcEndpointId") == endpoint_id:
                return item
            if name is not None and item.get("UserVpcEndpointName") == name:
                return item
        return None

    def DescribeUserVpcConnection(self, request):
        self._record("DescribeUserVpcConnection", request)
        values = []
        ids = list(getattr(request, "UserVpcEndpointIds", None) or [])
        for item in self.connections:
            if item.get("EngineNetworkId") != getattr(request, "EngineNetworkId", None):
                continue
            if ids and item.get("UserVpcEndpointId") not in ids:
                continue
            values.append(FakeResource(dict(item)))
        return SimpleNamespace(UserVpcConnectionInfos=values)

    def CreateUserVpcConnection(self, request):
        self._record("CreateUserVpcConnection", request)
        self._next += 1
        item = {
            "UserVpcEndpointId": "vpce-new-%03d" % self._next,
            "UserVpcEndpointName": getattr(request, "UserVpcEndpointName", None),
            "EngineNetworkId": getattr(request, "EngineNetworkId", None),
            "UserVpcId": getattr(request, "UserVpcId", None),
        }
        self.connections.append(item)
        return SimpleNamespace(UserVpcEndpointId=item["UserVpcEndpointId"], RequestId="req-fake")

    def DeleteUserVpcConnection(self, request):
        self._record("DeleteUserVpcConnection", request)
        self.connections = [
            t
            for t in self.connections
            if not (
                t.get("EngineNetworkId") == getattr(request, "EngineNetworkId", None)
                and t.get("UserVpcEndpointId") == getattr(request, "UserVpcEndpointId", None)
            )
        ]
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake, models=None):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (models or FakeModels(), SimpleNamespace(DlcClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


def _base(**overrides):
    params = {"engine_network_id": "engine-network-abc", "endpoint_name": "analytics-endpoint"}
    params.update(overrides)
    return module_args(**params)


# ---------------------------------------------------------------------------
# absent flows
# ---------------------------------------------------------------------------


def test_absent_missing_is_idempotent(monkeypatch):
    fake = FakeDlcClient(connections=[])
    _make_module(monkeypatch, fake)
    _base(state="absent", endpoint_name="ghost")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["connection"] is None
    assert result["endpoint_id"] is None
    assert [c for c, unused in fake.calls] == ["DescribeUserVpcConnection"]


def test_absent_requires_allow_delete(monkeypatch):
    fake = FakeDlcClient(connections=[_connection()])
    _make_module(monkeypatch, fake)
    _base(state="absent")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "allow_delete=true" in exc.value.args[0]["msg"]


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeDlcClient(connections=[_connection()])
    _make_module(monkeypatch, fake)
    _base(_ansible_check_mode=True, state="absent", allow_delete=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["connection"] is None
    assert len(fake.connections) == 1
    assert "DeleteUserVpcConnection" not in [c for c, unused in fake.calls]


def test_absent_deletes(monkeypatch):
    fake = FakeDlcClient(connections=[_connection()])
    _make_module(monkeypatch, fake)
    _base(state="absent", allow_delete=True, wait=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["connection"] is None
    assert fake.connections == []
    ops = [c for c, unused in fake.calls]
    assert "DeleteUserVpcConnection" in ops


def test_absent_by_id_deletes(monkeypatch):
    fake = FakeDlcClient(connections=[_connection()])
    _make_module(monkeypatch, fake)
    module_args(engine_network_id="engine-network-abc", state="absent", endpoint_id="vpce-8b0a1c2d", allow_delete=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert fake.connections == []
    assert "DeleteUserVpcConnection" in [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# creation flows
# ---------------------------------------------------------------------------


def test_create_requires_creation_parameters(monkeypatch):
    fake = FakeDlcClient(connections=[])
    _make_module(monkeypatch, fake)
    module_args(engine_network_id="engine-network-abc", state="present", endpoint_name="ghost")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "creation parameters are required" in payload["msg"]
    assert payload["missing"] == ["vpc_id", "subnet_id"]


def test_create_connection(monkeypatch):
    fake = FakeDlcClient(connections=[])
    _make_module(monkeypatch, fake)
    _base(state="present", vpc_id="vpc-abc", subnet_id="subnet-abc", wait=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["connection"]["UserVpcEndpointName"] == "analytics-endpoint"
    assert result["connection"]["UserVpcId"] == "vpc-abc"
    assert result["endpoint_id"].startswith("vpce-new-")
    assert len(fake.connections) == 1
    ops = [c for c, unused in fake.calls]
    assert ops[0] == "DescribeUserVpcConnection"
    assert "CreateUserVpcConnection" in ops


def test_create_check_mode_is_dry_run(monkeypatch):
    fake = FakeDlcClient(connections=[])
    _make_module(monkeypatch, fake)
    _base(_ansible_check_mode=True, state="present", vpc_id="vpc-abc", subnet_id="subnet-abc")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["connection"]["UserVpcEndpointName"] == "analytics-endpoint"
    assert result["endpoint_id"] is None
    assert fake.connections == []
    assert "CreateUserVpcConnection" not in [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# existing-connection flows
# ---------------------------------------------------------------------------


def test_existing_no_drift_is_idempotent(monkeypatch):
    fake = FakeDlcClient(connections=[_connection()])
    _make_module(monkeypatch, fake)
    module_args(engine_network_id="engine-network-abc", state="present", endpoint_id="vpce-8b0a1c2d")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["connection"]["UserVpcEndpointId"] == "vpce-8b0a1c2d"
    assert result["endpoint_id"] == "vpce-8b0a1c2d"


def test_immutable_identity_drift_fails(monkeypatch):
    fake = FakeDlcClient(connections=[_connection()])
    _make_module(monkeypatch, fake)
    module_args(engine_network_id="engine-network-abc", state="present", endpoint_id="vpce-8b0a1c2d", vpc_id="vpc-other")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "identity is immutable" in payload["msg"]
    assert "UserVpcId" in payload["immutable_drift"]


def test_multiple_matches_fail(monkeypatch):
    fake = FakeDlcClient(connections=[_connection(), _connection(UserVpcEndpointId="vpce-dup")])
    _make_module(monkeypatch, fake)
    _base(state="present")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "Multiple DLC VPC connections matched" in exc.value.args[0]["msg"]


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeUserVpcConnection(self, request):
            raise Boom("connection dropped")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    _base(state="present", endpoint_name="ghost")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]


# ---------------------------------------------------------------------------
# legacy helper regression tests (folded from test_dlc_user_vpc_connection.py)
# ---------------------------------------------------------------------------


class LegacyObject(object):
    pass


class LegacyModels(object):
    DescribeUserVpcConnectionRequest = LegacyObject
    CreateUserVpcConnectionRequest = LegacyObject
    DeleteUserVpcConnectionRequest = LegacyObject


def test_describe_can_filter_by_exact_endpoint_id():
    request = mod.describe_request(LegacyModels, "network-1", "vpce-1")
    assert request.EngineNetworkId == "network-1" and request.UserVpcEndpointIds == ["vpce-1"]


def test_create_maps_network_endpoint_contract():
    request = mod.create_request(
        LegacyModels, {"engine_network_id": "network-1", "vpc_id": "vpc-1", "subnet_id": "subnet-1", "endpoint_name": "lake", "endpoint_vip": "10.0.0.8"}
    )
    assert request.EngineNetworkId == "network-1" and request.UserVpcId == "vpc-1"
    assert request.UserSubnetId == "subnet-1" and request.UserVpcEndpointVip == "10.0.0.8"


def test_delete_requires_both_network_and_endpoint_identity():
    request = mod.delete_request(LegacyModels, "network-1", "vpce-1")
    assert request.EngineNetworkId == "network-1" and request.UserVpcEndpointId == "vpce-1"
