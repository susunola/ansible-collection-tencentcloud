"""Unit tests for the gaap_layer4_listener write module (run_module flows).

Drives ``run_module()`` end to end against an in-memory fake GAAP client
whose write operations mutate the listener store, so the module's post-write
``describe`` refetch converges immediately.

Scenario matrix:

* absent on a missing listener (idempotent no-op)
* absent with a matching listener (check-mode dry run and the real delete
  path, exercised over a proxy group)
* creation when missing for TCP and UDP (validation guards, check mode and
  the happy path)
* no-op when nothing drifts and scheduler drift update (plus check mode)
* immutable port / real_server_type replace guards
* the blanket ``sdk_error_payload`` failure path
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import gaap_layer4_listener as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

LISTENER = {
    "ListenerId": "listener-8b0a1c2d",
    "ListenerName": "mysql",
    "Port": 3306,
    "Protocol": "TCP",
    "Scheduler": "wrr",
    "RealServerType": "IP",
    "HealthCheck": 1,
    "FailoverSwitch": 0,
    "DelayLoop": 30,
    "ConnectTimeout": 5,
    "HealthyThreshold": 2,
    "UnhealthyThreshold": 3,
}


def _listener(**overrides):
    item = copy.deepcopy(LISTENER)
    item.update(overrides)
    return item


def _base(**overrides):
    params = {"protocol": "TCP"}
    params.update(overrides)
    return module_args(**params)


class FakeGaapClient(object):
    """In-memory GAAP client mutating a small listener store."""

    _COPY_ATTRS = (
        "ListenerName", "Scheduler", "HealthCheck", "FailoverSwitch", "DelayLoop",
        "ConnectTimeout", "HealthyThreshold", "UnhealthyThreshold",
        "ClientIPMethod", "CheckType", "CheckPort", "SendContext", "RecvContext",
    )

    def __init__(self, listeners=None):
        self.listeners = [copy.deepcopy(t) for t in (listeners or [])]
        self.calls = []
        self._next = 0

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def DescribeTCPListeners(self, request):
        self._record("DescribeTCPListeners", request)
        return SimpleNamespace(ListenerSet=[FakeResource(dict(t)) for t in self.listeners])

    def DescribeUDPListeners(self, request):
        self._record("DescribeUDPListeners", request)
        return SimpleNamespace(ListenerSet=[FakeResource(dict(t)) for t in self.listeners])

    def _create(self, protocol, request):
        self._record("Create%sListeners" % protocol, request)
        self._next += 1
        item = {
            "ListenerId": "listener-new-%03d" % self._next,
            "ListenerName": getattr(request, "ListenerName", None),
            "Port": (getattr(request, "Ports", None) or [None])[0],
            "Protocol": protocol,
            "Scheduler": getattr(request, "Scheduler", None),
            "RealServerType": getattr(request, "RealServerType", None),
            "HealthCheck": getattr(request, "HealthCheck", None),
            "FailoverSwitch": getattr(request, "FailoverSwitch", None),
        }
        for attr in self._COPY_ATTRS:
            value = getattr(request, attr, None)
            if value is not None:
                item[attr] = value
        self.listeners.append(item)
        return SimpleNamespace(ListenerIds=[item["ListenerId"]], RequestId="req-fake")

    def CreateTCPListeners(self, request):
        return self._create("TCP", request)

    def CreateUDPListeners(self, request):
        return self._create("UDP", request)

    def _update(self, protocol, request):
        self._record("Modify%sListenerAttribute" % protocol, request)
        for item in self.listeners:
            if item.get("ListenerId") != getattr(request, "ListenerId", None):
                continue
            for attr in self._COPY_ATTRS:
                value = getattr(request, attr, None)
                if value is not None:
                    item[attr] = value
        return SimpleNamespace(RequestId="req-fake")

    def ModifyTCPListenerAttribute(self, request):
        return self._update("TCP", request)

    def ModifyUDPListenerAttribute(self, request):
        return self._update("UDP", request)

    def DeleteListeners(self, request):
        self._record("DeleteListeners", request)
        ids = getattr(request, "ListenerIds", None) or []
        self.listeners = [t for t in self.listeners if t.get("ListenerId") not in ids]
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake, models=None):
    """Wire the shared monkeypatches; returns the fake client."""
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (models or FakeModels(), SimpleNamespace(GaapClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


# ---------------------------------------------------------------------------
# absent flows
# ---------------------------------------------------------------------------


def test_absent_missing_listener_is_idempotent(monkeypatch):
    fake = FakeGaapClient(listeners=[])
    _make_module(monkeypatch, fake)
    _base(state="absent", name="ghost", port=8080, proxy_id="proxy-x")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["listener"] is None
    assert [c for c, unused in fake.calls] == ["DescribeTCPListeners"]


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeGaapClient(listeners=[_listener()])
    _make_module(monkeypatch, fake)
    _base(_ansible_check_mode=True, state="absent", name="mysql", port=3306, proxy_id="proxy-x")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["listener"]["ListenerId"] == "listener-8b0a1c2d"
    assert len(fake.listeners) == 1
    assert "DeleteListeners" not in [c for c, unused in fake.calls]


def test_absent_deletes_listener_on_proxy_group(monkeypatch):
    fake = FakeGaapClient(listeners=[_listener()])
    _make_module(monkeypatch, fake)
    _base(state="absent", name="mysql", port=3306, group_id="group-g")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["listener"] is None
    assert fake.listeners == []
    ops = [c for c, unused in fake.calls]
    assert "DeleteListeners" in ops
    delete_call = fake.calls[[c for c, unused in fake.calls].index("DeleteListeners")][1]
    assert delete_call.ListenerIds == ["listener-8b0a1c2d"]
    assert delete_call.GroupId == "group-g"
    assert delete_call.Force == 0


# ---------------------------------------------------------------------------
# validation guards
# ---------------------------------------------------------------------------


def test_resolving_by_name_requires_port(monkeypatch):
    fake = FakeGaapClient(listeners=[])
    _make_module(monkeypatch, fake)
    _base(state="present", name="mysql", proxy_id="proxy-x")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "port is required when resolving a listener by name" in exc.value.args[0]["msg"]


def test_present_requires_name_to_create(monkeypatch):
    fake = FakeGaapClient(listeners=[])
    _make_module(monkeypatch, fake)
    _base(state="present", listener_id="listener-zzz", port=3306, proxy_id="proxy-x")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "name and port are required to create a listener" in exc.value.args[0]["msg"]


def test_missing_identity_arguments_fail(monkeypatch):
    fake = FakeGaapClient(listeners=[])
    _make_module(monkeypatch, fake)
    _base(state="present", proxy_id="proxy-x")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    message = exc.value.args[0]["msg"]
    assert "listener_id" in message
    assert "name" in message


def test_protocol_is_required(monkeypatch):
    fake = FakeGaapClient(listeners=[])
    _make_module(monkeypatch, fake)
    module_args(name="mysql", port=3306, proxy_id="proxy-x")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "protocol" in exc.value.args[0]["msg"]


# ---------------------------------------------------------------------------
# creation flows
# ---------------------------------------------------------------------------


def test_create_tcp_listener(monkeypatch):
    fake = FakeGaapClient(listeners=[])
    _make_module(monkeypatch, fake)
    _base(
        state="present",
        name="new-mysql",
        port=3307,
        proxy_id="proxy-x",
        scheduler="wrr",
        health_check=True,
        failover=False,
        real_server_type="IP",
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["listener"]["ListenerName"] == "new-mysql"
    assert result["listener"]["Port"] == 3307
    assert result["listener"]["Scheduler"] == "wrr"
    assert result["listener"]["HealthCheck"] == 1
    assert len(fake.listeners) == 1
    ops = [c for c, unused in fake.calls]
    assert ops[0] == "DescribeTCPListeners"
    assert "CreateTCPListeners" in ops
    create_call = fake.calls[[c for c, unused in fake.calls].index("CreateTCPListeners")][1]
    assert create_call.Ports == [3307]
    assert create_call.ProxyId == "proxy-x"


def test_create_udp_listener(monkeypatch):
    fake = FakeGaapClient(listeners=[])
    _make_module(monkeypatch, fake)
    _base(
        state="present",
        protocol="UDP",
        name="udp-syslog",
        port=514,
        proxy_id="proxy-x",
        scheduler="rr",
        health_check=True,
        udp_check_type="PORT",
        udp_check_port=514,
        send_context="probe",
        receive_context="pong",
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["listener"]["ListenerName"] == "udp-syslog"
    assert result["listener"]["CheckType"] == "PORT"
    assert result["listener"]["CheckPort"] == 514
    ops = [c for c, unused in fake.calls]
    assert "CreateUDPListeners" in ops


def test_create_check_mode_is_dry_run(monkeypatch):
    fake = FakeGaapClient(listeners=[])
    _make_module(monkeypatch, fake)
    _base(_ansible_check_mode=True, state="present", name="new-mysql", port=3307, proxy_id="proxy-x")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["listener"]["ListenerName"] == "new-mysql"
    assert fake.listeners == []
    assert "CreateTCPListeners" not in [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# existing-listener flows
# ---------------------------------------------------------------------------


def test_existing_listener_no_drift_is_idempotent(monkeypatch):
    fake = FakeGaapClient(listeners=[_listener()])
    _make_module(monkeypatch, fake)
    _base(
        state="present",
        name="mysql",
        port=3306,
        proxy_id="proxy-x",
        scheduler="wrr",
        health_check=True,
        failover=False,
        real_server_type="IP",
        delay_loop=30,
        connect_timeout=5,
        healthy_threshold=2,
        unhealthy_threshold=3,
    )
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["listener"]["ListenerId"] == "listener-8b0a1c2d"
    assert "ModifyTCPListenerAttribute" not in [c for c, unused in fake.calls]


def test_existing_listener_drift_updates(monkeypatch):
    fake = FakeGaapClient(listeners=[_listener()])
    _make_module(monkeypatch, fake)
    _base(
        state="present",
        name="mysql",
        port=3306,
        proxy_id="proxy-x",
        scheduler="lc",
        health_check=True,
        failover=False,
        real_server_type="IP",
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["listener"]["Scheduler"] == "lc"
    ops = [c for c, unused in fake.calls]
    assert "ModifyTCPListenerAttribute" in ops
    update_call = fake.calls[[c for c, unused in fake.calls].index("ModifyTCPListenerAttribute")][1]
    assert update_call.ListenerId == "listener-8b0a1c2d"
    assert update_call.Scheduler == "lc"


def test_existing_listener_drift_check_mode_is_dry_run(monkeypatch):
    fake = FakeGaapClient(listeners=[_listener()])
    _make_module(monkeypatch, fake)
    _base(
        _ansible_check_mode=True,
        state="present",
        name="mysql",
        port=3306,
        proxy_id="proxy-x",
        scheduler="lc",
        health_check=True,
        failover=False,
        real_server_type="IP",
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["listener"]["Scheduler"] == "lc"
    assert fake.listeners[0]["Scheduler"] == "wrr"
    assert "ModifyTCPListenerAttribute" not in [c for c, unused in fake.calls]


def test_port_change_is_rejected_as_immutable(monkeypatch):
    fake = FakeGaapClient(listeners=[_listener()])
    _make_module(monkeypatch, fake)
    _base(state="present", listener_id="listener-8b0a1c2d", name="mysql", port=3307, proxy_id="proxy-x")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    message = exc.value.args[0]["msg"]
    assert "port and real_server_type are immutable" in message


def test_real_server_type_change_is_rejected_as_immutable(monkeypatch):
    fake = FakeGaapClient(listeners=[_listener()])
    _make_module(monkeypatch, fake)
    _base(state="present", listener_id="listener-8b0a1c2d", name="mysql", port=3306, proxy_id="proxy-x", real_server_type="DOMAIN")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "port and real_server_type are immutable" in exc.value.args[0]["msg"]


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeTCPListeners(self, request):
            raise Boom("connection dropped")

    _make_module(monkeypatch, ExplodingClient())
    _base(state="present", name="mysql", port=3306, proxy_id="proxy-x")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]


# ---------------------------------------------------------------------------
# legacy helper regression tests (folded from test_gaap_layer4_listener.py)
# ---------------------------------------------------------------------------


def legacy_params(protocol="TCP"):
    return {"name": "database", "port": 3306, "scheduler": "wrr", "real_server_type": "IP",
            "health_check": True, "failover": False, "delay_loop": 10, "connect_timeout": 3,
            "healthy_threshold": 2, "unhealthy_threshold": 3, "client_ip_method": 1,
            "udp_check_type": None, "udp_check_port": None, "send_context": None,
            "receive_context": None, "protocol": protocol}


def test_target_maps_common_listener_fields():
    value = mod.target(legacy_params())
    assert value["ListenerName"] == "database"
    assert value["Port"] == 3306
    assert value["HealthCheck"] == 1
    assert value["FailoverSwitch"] == 0
    assert value["ClientIPMethod"] == 1


def test_target_maps_udp_probe_fields():
    value = legacy_params("UDP")
    value.update({"udp_check_type": "PORT", "udp_check_port": 8080,
                  "send_context": "ping", "receive_context": "pong"})
    result = mod.target(value)
    assert result["CheckType"] == "PORT"
    assert result["CheckPort"] == 8080
    assert result["RecvContext"] == "pong"
