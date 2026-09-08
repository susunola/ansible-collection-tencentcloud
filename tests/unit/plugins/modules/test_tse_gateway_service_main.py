"""Unit tests for the tse_gateway_service write module (run_module flows)."""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import tse_gateway_service as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

SERVICE = {
    "ID": "svc-orders",
    "Name": "orders",
    "Protocol": "http",
    "Timeout": 30000,
    "Retries": 2,
    "UpstreamType": "IPList",
    "UpstreamInfo": {"Targets": [{"Host": "10.0.0.10", "Port": 8080, "Weight": 100}]},
    "Path": "/orders",
    "HealthCheckConfig": {"EnableActiveHealthCheck": True, "ActiveHealthCheck": {"HttpPath": "/healthz"}},
}

TARGETS = [{"Host": "10.0.0.10", "Port": 8080, "Weight": 100}]
HEALTH = {"EnableActiveHealthCheck": True, "ActiveHealthCheck": {"HttpPath": "/healthz"}}


def _service(**overrides):
    item = copy.deepcopy(SERVICE)
    item.update(overrides)
    return item


def _base(**overrides):
    params = {"gateway_id": "gateway-abc", "name": "orders"}
    params.update(overrides)
    return module_args(**params)


class FakeTseClient(object):
    """In-memory TSE client mutating a gateway-service store."""

    def __init__(self, services=None):
        self.services = [copy.deepcopy(t) for t in (services or [])]
        self.calls = []
        self._next = 0

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def _find(self, service_id=None, name=None):
        for item in self.services:
            if service_id is not None and item.get("ID") == service_id:
                return item
            if name is not None and item.get("Name") == name:
                return item
        return None

    def DescribeCloudNativeAPIGatewayServices(self, request):
        self._record("DescribeCloudNativeAPIGatewayServices", request)
        return SimpleNamespace(Result=SimpleNamespace(ServiceList=[FakeResource(dict(t)) for t in self.services]))

    def DescribeOneCloudNativeAPIGatewayService(self, request):
        self._record("DescribeOneCloudNativeAPIGatewayService", request)
        item = self._find(name=getattr(request, "ServiceName", None))
        if item is None:
            item = self._find(service_id=getattr(request, "ServiceName", None))
        return SimpleNamespace(Result=FakeResource(dict(item)) if item else None)

    def DescribeUpstreamHealthCheckConfig(self, request):
        self._record("DescribeUpstreamHealthCheckConfig", request)
        item = self._find(name=getattr(request, "Name", None)) or self._find(service_id=getattr(request, "Name", None))
        value = item.get("HealthCheckConfig") if item else None
        return SimpleNamespace(Result=FakeResource(dict(value)) if value else None)

    def CreateCloudNativeAPIGatewayService(self, request):
        self._record("CreateCloudNativeAPIGatewayService", request)
        self._next += 1
        item = {"ID": "svc-new-%03d" % self._next}
        for attr in ("Name", "Protocol", "Timeout", "Retries", "UpstreamType", "UpstreamInfo", "Path"):
            if hasattr(request, attr):
                item[attr] = getattr(request, attr)
        self.services.append(item)
        return SimpleNamespace(Result=True, RequestId="req-fake")

    def ModifyCloudNativeAPIGatewayService(self, request):
        self._record("ModifyCloudNativeAPIGatewayService", request)
        item = self._find(service_id=getattr(request, "ID", None))
        if item is None:
            item = self._find(name=getattr(request, "Name", None))
        if item is not None:
            for attr in ("Name", "Protocol", "Timeout", "Retries", "UpstreamType", "UpstreamInfo", "Path"):
                if hasattr(request, attr):
                    item[attr] = getattr(request, attr)
        return SimpleNamespace(Result=True, RequestId="req-fake")

    def UpdateUpstreamTargets(self, request):
        self._record("UpdateUpstreamTargets", request)
        item = self._find(name=getattr(request, "Name", None))
        if item is None:
            item = self._find(service_id=getattr(request, "Name", None))
        if item is not None:
            upstream = dict(item.get("UpstreamInfo") or {})
            upstream["Targets"] = copy.deepcopy(getattr(request, "Targets", None) or [])
            item["UpstreamInfo"] = upstream
        return SimpleNamespace(Result=True, RequestId="req-fake")

    def UpdateUpstreamHealthCheckConfig(self, request):
        self._record("UpdateUpstreamHealthCheckConfig", request)
        item = self._find(name=getattr(request, "Name", None))
        if item is None:
            item = self._find(service_id=getattr(request, "Name", None))
        if item is not None:
            item["HealthCheckConfig"] = copy.deepcopy(getattr(request, "HealthCheckConfig", None))
        return SimpleNamespace(Result=True, RequestId="req-fake")

    def DeleteCloudNativeAPIGatewayService(self, request):
        self._record("DeleteCloudNativeAPIGatewayService", request)
        name = getattr(request, "Name", None)
        self.services = [t for t in self.services if t.get("ID") != name and t.get("Name") != name]
        return SimpleNamespace(Result=True, RequestId="req-fake")


def _make_module(monkeypatch, fake, models=None):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (models or FakeModels(), SimpleNamespace(TseClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


# ---------------------------------------------------------------------------
# absent flows
# ---------------------------------------------------------------------------


def test_absent_missing_is_idempotent(monkeypatch):
    fake = FakeTseClient(services=[])
    _make_module(monkeypatch, fake)
    _base(state="absent", name="ghost")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["service"] is None
    assert [c for c, unused in fake.calls] == ["DescribeCloudNativeAPIGatewayServices"]


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeTseClient(services=[_service()])
    _make_module(monkeypatch, fake)
    _base(_ansible_check_mode=True, state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["service"] is None
    assert len(fake.services) == 1
    assert "DeleteCloudNativeAPIGatewayService" not in [c for c, unused in fake.calls]


def test_absent_deletes_service(monkeypatch):
    fake = FakeTseClient(services=[_service()])
    _make_module(monkeypatch, fake)
    _base(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["service"] is None
    assert fake.services == []
    ops = [c for c, unused in fake.calls]
    assert "DeleteCloudNativeAPIGatewayService" in ops


# ---------------------------------------------------------------------------
# creation flows
# ---------------------------------------------------------------------------


def test_create_requires_creation_parameters(monkeypatch):
    fake = FakeTseClient(services=[])
    _make_module(monkeypatch, fake)
    _base(state="present", name="ghost")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "creation parameters are required" in payload["msg"]
    assert payload["missing"] == ["protocol", "timeout", "retries_count", "upstream_type", "upstream_info"]


def test_create_service(monkeypatch):
    fake = FakeTseClient(services=[])
    _make_module(monkeypatch, fake)
    _base(
        state="present",
        name="orders",
        protocol="http",
        timeout=30000,
        retries_count=2,
        upstream_type="IPList",
        upstream_info={"Targets": [{"Host": "10.0.0.10", "Port": 8080, "Weight": 100}]},
        path="/orders",
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["service"]["Name"] == "orders"
    assert result["service"]["Protocol"] == "http"
    assert len(fake.services) == 1
    ops = [c for c, unused in fake.calls]
    assert ops[0] == "DescribeCloudNativeAPIGatewayServices"
    assert "CreateCloudNativeAPIGatewayService" in ops


def test_create_check_mode_is_dry_run(monkeypatch):
    fake = FakeTseClient(services=[])
    _make_module(monkeypatch, fake)
    _base(
        _ansible_check_mode=True,
        state="present",
        name="orders",
        protocol="http",
        timeout=30000,
        retries_count=2,
        upstream_type="IPList",
        upstream_info={"Targets": []},
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["service"]["Name"] == "orders"
    assert fake.services == []
    assert "CreateCloudNativeAPIGatewayService" not in [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# existing-service flows
# ---------------------------------------------------------------------------


def test_existing_no_drift_is_idempotent(monkeypatch):
    fake = FakeTseClient(services=[_service()])
    _make_module(monkeypatch, fake)
    _base(
        state="present",
        name="orders",
        protocol="http",
        timeout=30000,
        retries_count=2,
        upstream_type="IPList",
        upstream_info={"Targets": [{"Host": "10.0.0.10", "Port": 8080, "Weight": 100}]},
        path="/orders",
    )
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["service"]["ID"] == "svc-orders"


def test_existing_no_drift_with_targets_and_health(monkeypatch):
    fake = FakeTseClient(services=[_service()])
    _make_module(monkeypatch, fake)
    _base(
        state="present",
        name="orders",
        protocol="http",
        timeout=30000,
        retries_count=2,
        upstream_type="IPList",
        upstream_info={"Targets": [{"Host": "10.0.0.10", "Port": 8080, "Weight": 100}]},
        path="/orders",
        targets=TARGETS,
        health_check_config=HEALTH,
    )
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["service"]["ID"] == "svc-orders"
    ops = [c for c, unused in fake.calls]
    assert "DescribeUpstreamHealthCheckConfig" in ops


def test_update_protocol_drift(monkeypatch):
    fake = FakeTseClient(services=[_service()])
    _make_module(monkeypatch, fake)
    _base(state="present", protocol="https")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["service"]["Protocol"] == "https"
    ops = [c for c, unused in fake.calls]
    assert "ModifyCloudNativeAPIGatewayService" in ops


def test_targets_drift_updates(monkeypatch):
    fake = FakeTseClient(services=[_service()])
    _make_module(monkeypatch, fake)
    new_targets = [{"Host": "10.0.0.20", "Port": 9090, "Weight": 100}]
    _base(state="present", targets=new_targets)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["service"]["UpstreamInfo"]["Targets"] == new_targets
    ops = [c for c, unused in fake.calls]
    assert "UpdateUpstreamTargets" in ops


def test_health_config_drift_updates(monkeypatch):
    fake = FakeTseClient(services=[_service()])
    _make_module(monkeypatch, fake)
    new_health = {"EnableActiveHealthCheck": False}
    _base(state="present", health_check_config=new_health)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["service"]["HealthCheckConfig"] == new_health
    ops = [c for c, unused in fake.calls]
    assert "UpdateUpstreamHealthCheckConfig" in ops


def test_multiple_matches_fail(monkeypatch):
    fake = FakeTseClient(services=[_service(), _service(ID="svc-orders-2")])
    _make_module(monkeypatch, fake)
    _base(state="present")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "Multiple TSE gateway services matched" in exc.value.args[0]["msg"]


def test_target_update_unsuccessful_fails(monkeypatch):
    service = _service()

    class UnsuccessfulTseClient(FakeTseClient):
        def UpdateUpstreamTargets(self, request):
            self._record("UpdateUpstreamTargets", request)
            return SimpleNamespace(Result=False, RequestId="req-fake")

    fake = UnsuccessfulTseClient(services=[service])
    _make_module(monkeypatch, fake)
    _base(state="present", targets=[{"Host": "10.0.0.20", "Port": 9090, "Weight": 100}])
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "unsuccessful result" in payload["msg"]
    assert payload["operation"] == "UpdateUpstreamTargets"


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeCloudNativeAPIGatewayServices(self, request):
            raise Boom("connection dropped")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    _base(state="present", name="orders")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]
