"""Unit tests for the tem_application_service write module.

``tem_application_service`` creates, updates and deletes one TEM service
access mapping (name + access type). The desired mapping payload is
passed as an SDK-shaped ``service`` dict merged with ``ServiceName`` /
``Type``; drift is a recursive ``contains`` over the serialized mapping.

Scenario matrix:

* absent on a missing mapping / existing mapping (check-mode, real delete)
* present no-drift idempotence
* create / update (real, check mode)
* ambiguous mapping guard and blanket SDK failure path
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import tem_application_service as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

APP_ID = "app-abc123"
ENV_ID = "en-abc123"
SERVICE_NAME = "order-api"
ACCESS_TYPE = "CLUSTER"

SERVICE = {
    "ServiceName": SERVICE_NAME,
    "Type": ACCESS_TYPE,
    "Ports": [8080],
    "PortMappingItemList": [
        {"Port": 80, "TargetPort": 8080, "Protocol": "TCP"},
    ],
}


def _service(**overrides):
    item = copy.deepcopy(SERVICE)
    item.update(overrides)
    return item


def _s_args(**overrides):
    params = {
        "application_id": APP_ID,
        "environment_id": ENV_ID,
        "name": SERVICE_NAME,
        "access_type": ACCESS_TYPE,
    }
    params.update(overrides)
    return module_args(**params)


class FakeTemClient(object):
    """In-memory TEM client storing service access mappings per application."""

    def __init__(self, services=None):
        self.services = [copy.deepcopy(s) for s in (services or [])]
        self.calls = []

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def DescribeApplicationServiceList(self, request):
        self._record("DescribeApplicationServiceList", request)
        result = FakeResource({"ServicePortMappingList": [FakeResource(dict(s)) for s in self.services]})
        return SimpleNamespace(Result=result)

    def CreateApplicationService(self, request):
        self._record("CreateApplicationService", request)
        self.services.append(copy.deepcopy(request.Service.__dict__))
        return SimpleNamespace()

    def ModifyApplicationService(self, request):
        self._record("ModifyApplicationService", request)
        value = copy.deepcopy(request.Data.__dict__)
        self.services = [
            s for s in self.services
            if not (s.get("ServiceName") == value.get("ServiceName") and s.get("Type") == value.get("Type"))
        ]
        self.services.append(value)
        return SimpleNamespace()

    def DeleteApplicationService(self, request):
        self._record("DeleteApplicationService", request)
        self.services = [s for s in self.services if s.get("ServiceName") != request.ServiceName]
        return SimpleNamespace()


def _make_module(monkeypatch, fake):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (FakeModels(), SimpleNamespace(TemClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


# ---------------------------------------------------------------------------
# absent flows
# ---------------------------------------------------------------------------


def test_absent_on_missing_service_is_idempotent(monkeypatch):
    fake = FakeTemClient(services=[])
    _make_module(monkeypatch, fake)
    _s_args(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["service"] is None
    assert [c for c, unused in fake.calls] == ["DescribeApplicationServiceList"]


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeTemClient(services=[_service()])
    _make_module(monkeypatch, fake)
    _s_args(_ansible_check_mode=True, state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["service"] is None
    assert len(fake.services) == 1
    assert "DeleteApplicationService" not in [c for c, unused in fake.calls]


def test_absent_deletes_service(monkeypatch):
    fake = FakeTemClient(services=[_service()])
    _make_module(monkeypatch, fake)
    _s_args(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["service"] is None
    assert fake.services == []
    ops = [c for c, unused in fake.calls]
    assert "DeleteApplicationService" in ops


# ---------------------------------------------------------------------------
# present flows
# ---------------------------------------------------------------------------


def test_present_no_drift_is_idempotent(monkeypatch):
    fake = FakeTemClient(services=[_service()])
    _make_module(monkeypatch, fake)
    _s_args(state="present", service={"Ports": [8080], "PortMappingItemList": [{"Port": 80, "TargetPort": 8080, "Protocol": "TCP"}]})
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["service"]["ServiceName"] == SERVICE_NAME
    ops = [c for c, unused in fake.calls]
    assert "CreateApplicationService" not in ops
    assert "ModifyApplicationService" not in ops


def test_present_creates_service(monkeypatch):
    fake = FakeTemClient(services=[])
    _make_module(monkeypatch, fake)
    _s_args(state="present", service={"Ports": [8080], "PortMappingItemList": [{"Port": 80, "TargetPort": 8080, "Protocol": "TCP"}]})
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["service"]["ServiceName"] == SERVICE_NAME
    assert result["service"]["Type"] == ACCESS_TYPE
    assert result["service"]["Ports"] == [8080]
    assert len(fake.services) == 1
    ops = [c for c, unused in fake.calls]
    assert ops[0] == "DescribeApplicationServiceList"
    assert "CreateApplicationService" in ops


def test_present_create_check_mode_is_dry_run(monkeypatch):
    fake = FakeTemClient(services=[])
    _make_module(monkeypatch, fake)
    _s_args(_ansible_check_mode=True, state="present", service={"Ports": [8080]})
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["service"]["ServiceName"] == SERVICE_NAME
    assert fake.services == []
    assert "CreateApplicationService" not in [c for c, unused in fake.calls]


def test_port_drift_updates_service(monkeypatch):
    fake = FakeTemClient(services=[_service()])
    _make_module(monkeypatch, fake)
    _s_args(state="present", service={"Ports": [9090]})
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["service"]["Ports"] == [9090]
    assert fake.services[0]["Ports"] == [9090]
    ops = [c for c, unused in fake.calls]
    assert "ModifyApplicationService" in ops


def test_present_update_check_mode_is_dry_run(monkeypatch):
    fake = FakeTemClient(services=[_service()])
    _make_module(monkeypatch, fake)
    _s_args(_ansible_check_mode=True, state="present", service={"Ports": [9090]})
    result = run(mod.run_module)
    assert result["changed"] is True
    assert fake.services[0]["Ports"] == [8080]
    assert "ModifyApplicationService" not in [c for c, unused in fake.calls]


def test_multiple_matching_services_fail(monkeypatch):
    fake = FakeTemClient(services=[_service(), _service(Ports=[9999])])
    _make_module(monkeypatch, fake)
    _s_args(state="present", service={"Ports": [8080]})
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "Multiple TEM application service mappings" in exc.value.args[0]["msg"]


# ---------------------------------------------------------------------------
# failure paths
# ---------------------------------------------------------------------------


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeApplicationServiceList(self, request):
            raise Boom("connection dropped")

    _make_module(monkeypatch, ExplodingClient())
    _s_args(state="present", service={"Ports": [8080]})
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]
