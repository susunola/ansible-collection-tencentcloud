"""Unit tests for the vpn_connection write module.

Drives ``run_module()`` end to end against an in-memory fake VPC client that
keeps a mutable connection list and answers the paginated describe requests
the real module performs.  Create/modify/delete mutate the store, so the
post-mutation convergence poll inside ``wait_for_connection`` converges on
the first attempt for happy paths.

Scenario matrix:

* argument guards: missing identity, rotate without pre-shared key, missing
  create-only fields
* present: idempotent no-op, create-when-absent, check-mode dry runs,
  drift update, rotate-key forced update, ambiguous name lookup
* absent: no-op, delete and wait, gateway fallback from the record,
  check-mode dry run
* failure paths: blanket SDK failure, update convergence timeout,
  delete convergence timeout
* legacy pure-helper assertions folded from the shallow test file
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import vpn_connection as mod
from ansible_collections.susunola.tencentcloud.plugins.modules.vpn_connection import (
    build_create_request,
    build_delete_request,
)
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

NAME = "office"
GATEWAY_ID = "vpngw-1"
CUSTOMER_ID = "cgw-1"
VPC_ID = "vpc-1"
CONNECTION_ID = "vpnx-1"
POLICIES = [{"local_cidr": "10.0.0.0/16", "remote_cidr": "192.168.0.0/16"}]


def _base_params(**overrides):
    params = {
        "vpn_connection_id": None,
        "name": NAME,
        "vpn_gateway_id": GATEWAY_ID,
        "customer_gateway_id": CUSTOMER_ID,
        "vpc_id": VPC_ID,
        "pre_shared_key": "secret",
        "rotate_pre_shared_key": False,
        "security_policy_databases": [dict(p) for p in POLICIES],
        "route_type": "Policy",
        "negotiation_type": "active",
        "dpd_enabled": True,
        "dpd_timeout": 30,
        "dpd_action": "clear",
        "tags": {},
        "state": "present",
    }
    params.update(overrides)
    return params


def _store_record(connection_id=CONNECTION_ID, name=NAME, customer=CUSTOMER_ID, negotiation="active",
                  dpd_enabled=1, dpd_timeout="30", dpd_action="clear", policies=None):
    record = {
        "VpnConnectionId": connection_id,
        "VpnConnectionName": name,
        "CustomerGatewayId": customer,
        "VpnGatewayId": GATEWAY_ID,
        "VpcId": VPC_ID,
        "RouteType": "Policy",
        "NegotiationType": negotiation,
        "DpdEnable": dpd_enabled,
        "DpdTimeout": dpd_timeout,
        "DpdAction": dpd_action,
    }
    if policies is not None:
        record["SecurityPolicyDatabaseSet"] = policies
    return record


class FakeVpnClient(object):
    """In-memory VPC client backed by a mutable connection list."""

    def __init__(self, connections=None, converge=True):
        self.connections = [dict(c) for c in connections or []]
        self.converge = converge
        self._next = 1
        self.calls = []

    def _record(self, name, request):
        self.calls.append((name, request))

    def _filters(self, request):
        result = {}
        for item in getattr(request, "Filters", None) or []:
            name = getattr(item, "Name", None)
            if name:
                result[name] = list(getattr(item, "Values", None) or [])
        return result

    def _policy_list(self, request):
        if not hasattr(request, "SecurityPolicyDatabases"):
            return None
        return [
            {"LocalCidrBlock": p.LocalCidrBlock, "RemoteCidrBlock": list(p.RemoteCidrBlock)}
            for p in request.SecurityPolicyDatabases
        ]

    def _mutable_fields(self, request):
        out = {}
        for field in ("VpnConnectionName", "CustomerGatewayId", "NegotiationType", "DpdEnable", "DpdTimeout", "DpdAction"):
            if hasattr(request, field):
                out[field] = getattr(request, field)
        policies = self._policy_list(request)
        if policies is not None:
            out["SecurityPolicyDatabaseSet"] = policies
        return out

    def DescribeVpnConnections(self, request):
        self._record("DescribeVpnConnections", request)
        ids = getattr(request, "VpnConnectionIds", None) or []
        conns = list(self.connections)
        if ids:
            conns = [c for c in conns if c.get("VpnConnectionId") in ids]
        for fname, values in self._filters(request).items():
            wanted = values[0]
            if fname == "vpn-connection-name":
                conns = [c for c in conns if wanted in (c.get("VpnConnectionName") or "")]
            elif fname == "vpn-gateway-id":
                conns = [c for c in conns if c.get("VpnGatewayId") == wanted]
        payload = [FakeResource(c) for c in conns]
        return SimpleNamespace(VpnConnectionSet=payload, TotalCount=len(payload), RequestId="req-fake")

    def CreateVpnConnection(self, request):
        self._record("CreateVpnConnection", request)
        record = self._mutable_fields(request)
        record["VpnGatewayId"] = request.VpnGatewayId
        record["VpcId"] = request.VpcId
        record["RouteType"] = request.RouteType
        connection_id = "vpnx-%d" % self._next
        self._next += 1
        record["VpnConnectionId"] = connection_id
        self.connections.append(record)
        return SimpleNamespace(VpnConnection=SimpleNamespace(VpnConnectionId=connection_id), RequestId="req-fake")

    def ModifyVpnConnectionAttribute(self, request):
        self._record("ModifyVpnConnectionAttribute", request)
        if self.converge:
            for record in self.connections:
                if record.get("VpnConnectionId") == getattr(request, "VpnConnectionId", None):
                    record.update(self._mutable_fields(request))
        return SimpleNamespace(RequestId="req-fake")

    def DeleteVpnConnection(self, request):
        self._record("DeleteVpnConnection", request)
        if self.converge:
            self.connections = [
                c for c in self.connections
                if c.get("VpnConnectionId") != getattr(request, "VpnConnectionId", None)
            ]
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake, models=None):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load_vpc", lambda: (models or FakeModels(), SimpleNamespace(VpcClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


def _names(fake):
    return [c for c, unused in fake.calls]


def _find_call(fake, name):
    for c, request in fake.calls:
        if c == name:
            return request
    return None


# ---------------------------------------------------------------------------
# argument guards
# ---------------------------------------------------------------------------


def test_missing_identity_fails():
    args = _base_params()
    del args["vpn_connection_id"]
    del args["name"]
    module_args(**args)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "one of the following is required" in exc.value.args[0]["msg"]


def test_rotate_without_pre_shared_key_fails():
    module_args(**_base_params(rotate_pre_shared_key=True, pre_shared_key=None))
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "pre_shared_key is required when rotate_pre_shared_key=true" in exc.value.args[0]["msg"]


def test_create_missing_required_fields_fails(monkeypatch):
    fake = FakeVpnClient()
    _make_module(monkeypatch, fake)
    module_args(**_base_params(name=NAME, vpn_gateway_id=None, customer_gateway_id=None, vpc_id=None, pre_shared_key=None))
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    msg = exc.value.args[0]["msg"]
    assert "Required when creating" in msg
    for missing in ("vpn_gateway_id", "customer_gateway_id", "vpc_id", "pre_shared_key"):
        assert missing in msg


# ---------------------------------------------------------------------------
# present: reconcile flows
# ---------------------------------------------------------------------------


def test_present_up_to_date_is_idempotent(monkeypatch):
    record = _store_record(policies=[{"LocalCidrBlock": "10.0.0.0/16", "RemoteCidrBlock": ["192.168.0.0/16"]}])
    fake = FakeVpnClient(connections=[record])
    _make_module(monkeypatch, fake)
    module_args(**_base_params())
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["vpn_connection"]["VpnConnectionId"] == CONNECTION_ID
    assert "CreateVpnConnection" not in _names(fake)
    assert "ModifyVpnConnectionAttribute" not in _names(fake)


def test_create_when_absent(monkeypatch):
    fake = FakeVpnClient()
    _make_module(monkeypatch, fake)
    module_args(**_base_params())
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["vpn_connection"]["VpnConnectionName"] == NAME
    assert result["vpn_connection"]["VpnConnectionId"] == "vpnx-1"
    assert fake.connections[0]["VpcId"] == VPC_ID
    create = _find_call(fake, "CreateVpnConnection")
    assert create.VpnGatewayId == GATEWAY_ID
    assert create.SecurityPolicyDatabases[0].RemoteCidrBlock == ["192.168.0.0/16"]


def test_check_mode_create_reports_change_without_create(monkeypatch):
    fake = FakeVpnClient()
    _make_module(monkeypatch, fake)
    module_args(**_base_params(_ansible_check_mode=True))
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["vpn_connection"] is None
    assert "Would create VPN connection" in result["msg"]
    assert "diff" in result
    assert "CreateVpnConnection" not in _names(fake)
    assert fake.connections == []


def test_drift_update_negotiation(monkeypatch):
    record = _store_record(policies=[{"LocalCidrBlock": "10.0.0.0/16", "RemoteCidrBlock": ["192.168.0.0/16"]}])
    record["NegotiationType"] = "passive"
    record["DpdAction"] = "restart"
    fake = FakeVpnClient(connections=[record])
    _make_module(monkeypatch, fake)
    module_args(**_base_params())
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["vpn_connection"]["NegotiationType"] == "active"
    assert fake.connections[0]["NegotiationType"] == "active"
    assert fake.connections[0]["DpdAction"] == "clear"
    modify = _find_call(fake, "ModifyVpnConnectionAttribute")
    assert modify.VpnConnectionId == CONNECTION_ID


def test_check_mode_update_reports_would_update(monkeypatch):
    record = _store_record(negotiation="passive", policies=[{"LocalCidrBlock": "10.0.0.0/16", "RemoteCidrBlock": ["192.168.0.0/16"]}])
    fake = FakeVpnClient(connections=[record])
    _make_module(monkeypatch, fake)
    module_args(**_base_params(_ansible_check_mode=True))
    result = run(mod.run_module)
    assert result["changed"] is True
    assert "Would update VPN connection" in result["msg"]
    assert result["vpn_connection"]["NegotiationType"] == "passive"
    assert "diff" in result
    assert "ModifyVpnConnectionAttribute" not in _names(fake)
    assert fake.connections[0]["NegotiationType"] == "passive"


def test_ambiguous_name_lookup_fails(monkeypatch):
    fake = FakeVpnClient(connections=[
        _store_record(connection_id="vpnx-1", name="office-a"),
        _store_record(connection_id="vpnx-2", name="office-b"),
    ])
    _make_module(monkeypatch, fake)
    module_args(**_base_params(name=NAME, vpn_gateway_id=None))
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["ambiguous"] is True
    assert payload["match_count"] == 2
    assert "Ambiguous VPN connection reference" in payload["msg"]


def test_rotate_pre_shared_key_forces_update(monkeypatch):
    record = _store_record(policies=[{"LocalCidrBlock": "10.0.0.0/16", "RemoteCidrBlock": ["192.168.0.0/16"]}])
    fake = FakeVpnClient(connections=[record])
    _make_module(monkeypatch, fake)
    module_args(**_base_params(rotate_pre_shared_key=True, pre_shared_key="new-secret"))
    result = run(mod.run_module)
    assert result["changed"] is True
    assert "ModifyVpnConnectionAttribute" in _names(fake)
    modify = _find_call(fake, "ModifyVpnConnectionAttribute")
    assert modify.PreShareKey == "new-secret"
    assert fake.connections[0]["VpnConnectionName"] == NAME


# ---------------------------------------------------------------------------
# absent flows
# ---------------------------------------------------------------------------


def test_absent_without_match_is_noop(monkeypatch):
    fake = FakeVpnClient()
    _make_module(monkeypatch, fake)
    module_args(**_base_params(vpn_connection_id=CONNECTION_ID, name=None, state="absent"))
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["vpn_connection"] is None
    assert "VPN connection is absent" in result["msg"]
    assert "DeleteVpnConnection" not in _names(fake)


def test_absent_deletes_and_waits(monkeypatch):
    fake = FakeVpnClient(connections=[_store_record()])
    _make_module(monkeypatch, fake)
    module_args(**_base_params(name=NAME, state="absent"))
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["vpn_connection"] is None
    assert "VPN connection deleted" in result["msg"]
    assert fake.connections == []
    delete = _find_call(fake, "DeleteVpnConnection")
    assert delete.VpnConnectionId == CONNECTION_ID
    assert delete.VpnGatewayId == GATEWAY_ID


def test_absent_by_id_falls_back_to_record_gateway(monkeypatch):
    fake = FakeVpnClient(connections=[_store_record()])
    _make_module(monkeypatch, fake)
    module_args(**_base_params(name=None, vpn_connection_id=CONNECTION_ID, vpn_gateway_id=None, state="absent"))
    result = run(mod.run_module)
    assert result["changed"] is True
    delete = _find_call(fake, "DeleteVpnConnection")
    assert delete.VpnGatewayId == GATEWAY_ID


def test_check_mode_absent_does_not_delete(monkeypatch):
    fake = FakeVpnClient(connections=[_store_record()])
    _make_module(monkeypatch, fake)
    module_args(**_base_params(name=NAME, state="absent", _ansible_check_mode=True))
    result = run(mod.run_module)
    assert result["changed"] is True
    assert "Would delete VPN connection" in result["msg"]
    assert result["vpn_connection"]["VpnConnectionId"] == CONNECTION_ID
    assert "DeleteVpnConnection" not in _names(fake)
    assert len(fake.connections) == 1


# ---------------------------------------------------------------------------
# failure paths
# ---------------------------------------------------------------------------


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeVpnConnections(self, request):
            raise Boom("connection dropped")

    _make_module(monkeypatch, ExplodingClient())
    module_args(**_base_params())
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]


def test_update_convergence_timeout_fails(monkeypatch):
    record = _store_record(negotiation="passive", policies=[{"LocalCidrBlock": "10.0.0.0/16", "RemoteCidrBlock": ["192.168.0.0/16"]}])
    fake = FakeVpnClient(connections=[record], converge=False)
    _make_module(monkeypatch, fake)
    module_args(**_base_params(waiter_timeout=0))
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "Timed out waiting for VPN connection convergence" in exc.value.args[0]["msg"]


def test_delete_convergence_timeout_fails(monkeypatch):
    fake = FakeVpnClient(connections=[_store_record()], converge=False)
    _make_module(monkeypatch, fake)
    module_args(**_base_params(name=NAME, state="absent", waiter_timeout=0))
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "Timed out waiting for VPN connection convergence" in exc.value.args[0]["msg"]


# ---------------------------------------------------------------------------
# legacy pure-helper assertions (folded from the shallow test file)
# ---------------------------------------------------------------------------


def test_legacy_create_and_delete_request_builders():
    models = FakeModels()
    request = build_create_request(models, _base_params())
    assert request.VpnGatewayId == GATEWAY_ID
    assert request.SecurityPolicyDatabases[0].RemoteCidrBlock == ["192.168.0.0/16"]
    assert request.VpcId == VPC_ID
    assert request.PreShareKey == "secret"
    delete = build_delete_request(models, GATEWAY_ID, CONNECTION_ID)
    assert delete.VpnConnectionId == CONNECTION_ID
    assert delete.VpnGatewayId == GATEWAY_ID


def test_legacy_create_main_path_returns_created_connection(monkeypatch):
    models = FakeModels()
    response = SimpleNamespace(VpnConnection=SimpleNamespace(VpnConnectionId=CONNECTION_ID))
    client = SimpleNamespace(CreateVpnConnection=MagicMock(return_value=response))
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load_vpc", lambda: (models, SimpleNamespace(VpcClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, cls, endpoint: client)
    monkeypatch.setattr(mod, "find_connection", lambda *args: None)
    expected = {"VpnConnectionId": CONNECTION_ID, "VpnConnectionName": NAME}
    monkeypatch.setattr(mod, "wait_for_connection", MagicMock(return_value=expected))
    module_args(**_base_params())
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["vpn_connection"]["VpnConnectionId"] == CONNECTION_ID
    client.CreateVpnConnection.assert_called_once()


def test_legacy_check_mode_does_not_create(monkeypatch):
    models = FakeModels()
    client = SimpleNamespace(CreateVpnConnection=MagicMock())
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load_vpc", lambda: (models, SimpleNamespace(VpcClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, cls, endpoint: client)
    monkeypatch.setattr(mod, "find_connection", lambda *args: None)
    module_args(**_base_params(_ansible_check_mode=True))
    result = run(mod.run_module)
    assert result["changed"] is True
    assert "diff" in result
    client.CreateVpnConnection.assert_not_called()
