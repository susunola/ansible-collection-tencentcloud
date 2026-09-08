"""Main-path (run_module) unit tests for the tse_cloud_native_gateway write module.

Complements ``test_tse_cloud_native_gateway.py`` (request-builder level) by
driving ``run_module()`` end to end against an in-memory fake TSE client
whose write operations mutate a gateway store so post-write ``find`` and the
in-module wait loop converge on the first poll.

Scenario matrix:
* absent flows (missing, delete_protect guard, check mode, real delete)
* creation flows (missing-parameters guard, check mode, real create)
* no-op when nothing drifts
* metadata drift, CLS-disable guard, node_config guards and node spec change
* immutable-field drift and multiple-match guards
* the blanket ``sdk_error_payload`` failure path
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import tse_cloud_native_gateway as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

GATEWAY = {
    "GatewayId": "gateway-1",
    "Name": "production-gateway",
    "Type": "kong",
    "GatewayVersion": "2.8.1",
    "Status": "running",
    "Description": "Production gateway",
    "EnableCls": True,
    "InternetPayMode": "BANDWIDTH",
    "DeleteProtect": False,
    "NodeConfig": {"Specification": "4c8g", "Number": 2},
    "VpcConfig": {"VpcId": "vpc-1", "SubnetId": "subnet-1"},
    "FeatureVersion": "STANDARD",
    "TradeType": 0,
    "IngressClassName": "kong",
}


def _gateway(**overrides):
    item = copy.deepcopy(GATEWAY)
    item.update(overrides)
    return item


def _base(**overrides):
    params = {"name": "production-gateway"}
    params.update(overrides)
    return module_args(**params)


class FakeTseClient(object):
    """In-memory TSE client mutating a cloud-native gateway store."""

    def __init__(self, gateways=None):
        self.gateways = [copy.deepcopy(g) for g in (gateways or [])]
        self.calls = []
        self._next = 0

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def _by_id(self, gateway_id):
        return next((g for g in self.gateways if g.get("GatewayId") == gateway_id), None)

    def _by_name(self, name):
        return next((g for g in self.gateways if g.get("Name") == name), None)

    def DescribeCloudNativeAPIGateways(self, request):
        self._record("DescribeCloudNativeAPIGateways", request)
        filters = getattr(request, "Filters", None) or []
        if filters:
            name = filters[0].Name
            values = filters[0].Values or []
            items = [g for g in self.gateways if g.get(name) == values[0]]
        else:
            items = list(self.gateways)
        return SimpleNamespace(Result=SimpleNamespace(GatewayList=[FakeResource(copy.deepcopy(g)) for g in items]))

    def DescribeCloudNativeAPIGateway(self, request):
        self._record("DescribeCloudNativeAPIGateway", request)
        item = self._by_id(getattr(request, "GatewayId", None))
        return SimpleNamespace(Result=FakeResource(copy.deepcopy(item)) if item else None)

    def CreateCloudNativeAPIGateway(self, request):
        self._record("CreateCloudNativeAPIGateway", request)
        self._next += 1
        item = {k: copy.deepcopy(v) for k, v in vars(request).items() if not k.startswith("_")}
        item["GatewayId"] = "gateway-new-%d" % self._next
        item.setdefault("Status", "running")
        item.setdefault("Type", "kong")
        self.gateways.append(item)
        return SimpleNamespace(Result=SimpleNamespace(GatewayId=item["GatewayId"]))

    def ModifyCloudNativeAPIGateway(self, request):
        self._record("ModifyCloudNativeAPIGateway", request)
        item = self._by_id(getattr(request, "GatewayId", None))
        if item is None:
            return SimpleNamespace(RequestId="req-fake")
        for key in ("Name", "Description", "EnableCls", "InternetPayMode", "DeleteProtect"):
            value = getattr(request, key, None)
            if value is not None:
                item[key] = value
        return SimpleNamespace(RequestId="req-fake")

    def UpdateCloudNativeAPIGatewaySpec(self, request):
        self._record("UpdateCloudNativeAPIGatewaySpec", request)
        item = self._by_id(getattr(request, "GatewayId", None))
        if item is not None:
            item["NodeConfig"] = copy.deepcopy(getattr(request, "NodeConfig", None))
        return SimpleNamespace(Result=SimpleNamespace(TaskId="task-99"))

    def DeleteCloudNativeAPIGateway(self, request):
        self._record("DeleteCloudNativeAPIGateway", request)
        gateway_id = getattr(request, "GatewayId", None)
        self.gateways = [g for g in self.gateways if g.get("GatewayId") != gateway_id]
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake, models=None):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (models or FakeModels(), SimpleNamespace(TseClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


# ---------------------------------------------------------------------------
# absent flows
# ---------------------------------------------------------------------------


def test_absent_missing_gateway_is_idempotent(monkeypatch):
    fake = FakeTseClient(gateways=[])
    _make_module(monkeypatch, fake)
    _base(state="absent", name="ghost-gateway")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["gateway"] is None


def test_absent_requires_delete_protect_disabled(monkeypatch):
    fake = FakeTseClient(gateways=[_gateway(DeleteProtect=True)])
    _make_module(monkeypatch, fake)
    _base(state="absent")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "Disable delete_protect" in exc.value.args[0]["msg"]


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeTseClient(gateways=[_gateway()])
    _make_module(monkeypatch, fake)
    _base(_ansible_check_mode=True, state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert len(fake.gateways) == 1
    assert "DeleteCloudNativeAPIGateway" not in [c for c, unused in fake.calls]


def test_absent_deletes_gateway(monkeypatch):
    fake = FakeTseClient(gateways=[_gateway()])
    _make_module(monkeypatch, fake)
    _base(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert fake.gateways == []
    ops = [c for c, unused in fake.calls]
    assert "DeleteCloudNativeAPIGateway" in ops


# ---------------------------------------------------------------------------
# creation flows
# ---------------------------------------------------------------------------


def test_create_requires_creation_parameters(monkeypatch):
    fake = FakeTseClient(gateways=[])
    _make_module(monkeypatch, fake)
    _base(state="present")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "creation parameters are required" in payload["msg"]
    assert set(payload["missing"]) == {"gateway_version", "node_config", "vpc_config", "feature_version"}


def test_create_check_mode_is_dry_run(monkeypatch):
    fake = FakeTseClient(gateways=[])
    _make_module(monkeypatch, fake)
    _base(
        _ansible_check_mode=True,
        state="present",
        gateway_version="2.8.1",
        node_config={"Specification": "4c8g", "Number": 2},
        vpc_config={"VpcId": "vpc-1", "SubnetId": "subnet-1"},
        feature_version="STANDARD",
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert fake.gateways == []
    assert "CreateCloudNativeAPIGateway" not in [c for c, unused in fake.calls]
    assert result["gateway"]["Name"] == "production-gateway"


def test_create_gateway(monkeypatch):
    fake = FakeTseClient(gateways=[])
    _make_module(monkeypatch, fake)
    _base(
        state="present",
        gateway_version="2.8.1",
        node_config={"Specification": "4c8g", "Number": 2},
        vpc_config={"VpcId": "vpc-1", "SubnetId": "subnet-1"},
        feature_version="STANDARD",
        description="Production gateway",
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["gateway"]["Name"] == "production-gateway"
    assert len(fake.gateways) == 1
    ops = [c for c, unused in fake.calls]
    assert "CreateCloudNativeAPIGateway" in ops


# ---------------------------------------------------------------------------
# existing-gateway flows
# ---------------------------------------------------------------------------


def test_existing_gateway_no_drift_is_idempotent(monkeypatch):
    fake = FakeTseClient(gateways=[_gateway()])
    _make_module(monkeypatch, fake)
    _base(state="present", description="Production gateway")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["gateway"]["GatewayId"] == "gateway-1"


def test_description_drift_updates_gateway(monkeypatch):
    fake = FakeTseClient(gateways=[_gateway()])
    _make_module(monkeypatch, fake)
    _base(state="present", description="Renamed production gateway")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["gateway"]["Description"] == "Renamed production gateway"
    ops = [c for c, unused in fake.calls]
    assert "ModifyCloudNativeAPIGateway" in ops


def test_cannot_disable_cls_after_enabled(monkeypatch):
    fake = FakeTseClient(gateways=[_gateway(EnableCls=True)])
    _make_module(monkeypatch, fake)
    _base(state="present", enable_cls=False)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "cannot disable CLS" in exc.value.args[0]["msg"]


def test_node_config_change_requires_spec_group_id(monkeypatch):
    fake = FakeTseClient(gateways=[_gateway()])
    _make_module(monkeypatch, fake)
    _base(state="present", node_config={"Specification": "8c16g", "Number": 4})
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "spec_group_id is required" in exc.value.args[0]["msg"]


def test_node_config_change_authorized(monkeypatch):
    fake = FakeTseClient(gateways=[_gateway()])
    _make_module(monkeypatch, fake)
    _base(
        state="present",
        node_config={"Specification": "8c16g", "Number": 4},
        spec_group_id="group-1",
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["gateway"]["NodeConfig"] == {"Specification": "8c16g", "Number": 4}
    assert result["task_id"] == "task-99"
    ops = [c for c, unused in fake.calls]
    assert "UpdateCloudNativeAPIGatewaySpec" in ops


def test_immutable_drift_fails(monkeypatch):
    fake = FakeTseClient(gateways=[_gateway()])
    _make_module(monkeypatch, fake)
    _base(state="present", feature_version="PROFESSIONAL")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "immutable" in payload["msg"]
    assert "FeatureVersion" in payload["immutable_drift"]


def test_metadata_check_mode_is_dry_run(monkeypatch):
    fake = FakeTseClient(gateways=[_gateway()])
    _make_module(monkeypatch, fake)
    _base(_ansible_check_mode=True, state="present", description="Preview description")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert fake.gateways[0]["Description"] == "Production gateway"
    assert "ModifyCloudNativeAPIGateway" not in [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# failure paths
# ---------------------------------------------------------------------------


def test_multiple_matches_fail(monkeypatch):
    fake = FakeTseClient(gateways=[_gateway(), _gateway(GatewayId="gateway-2")])
    _make_module(monkeypatch, fake)
    _base(state="present")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "Multiple TSE gateways matched" in exc.value.args[0]["msg"]


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeCloudNativeAPIGateways(self, request):
            raise Boom("connection dropped")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    _base(state="present")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]
