"""Unit tests for the monitor_prometheus_grafana_binding write module.

Drives ``run_module()`` against an in-memory fake Monitor client whose
bind / unbind operations mutate the Grafana binding stored on a Prometheus
instance.

Scenario matrix:

* present when the instances are already bound (idempotent no-op)
* absent when they are not bound (idempotent no-op)
* present bind when unbound (happy path and check-mode dry run)
* absent unbind when bound (real delete and check-mode dry run)
* the blanket SDK failure path
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import monitor_prometheus_grafana_binding as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

INSTANCE = {
    "InstanceId": "prom-abc123",
    "InstanceName": "prometheus-prod",
    "GrafanaInstanceId": "grafana-abc123",
}


def _instance(**overrides):
    item = copy.deepcopy(INSTANCE)
    item.update(overrides)
    return item


def _args(**overrides):
    params = {"instance_id": "prom-abc123", "grafana_id": "grafana-abc123"}
    params.update(overrides)
    return module_args(**params)


class FakeMonitorClient(object):
    """In-memory Monitor client binding Prometheus to a Grafana instance."""

    def __init__(self, instances=None):
        self.instances = [copy.deepcopy(t) for t in (instances or [])]
        self.calls = []

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def DescribePrometheusInstances(self, request):
        self._record("DescribePrometheusInstances", request)
        ids = list(getattr(request, "InstanceIds", None) or [])
        matched = [t for t in self.instances if t.get("InstanceId") in ids]
        return SimpleNamespace(InstanceSet=[FakeResource(t) for t in matched])

    def BindPrometheusManagedGrafana(self, request):
        self._record("BindPrometheusManagedGrafana", request)
        self._set_binding(getattr(request, "InstanceId", None), getattr(request, "GrafanaId", None))
        return SimpleNamespace(RequestId="req-fake")

    def UnbindPrometheusManagedGrafana(self, request):
        self._record("UnbindPrometheusManagedGrafana", request)
        self._set_binding(getattr(request, "InstanceId", None), None)
        return SimpleNamespace(RequestId="req-fake")

    def _set_binding(self, iid, gid):
        for item in self.instances:
            if item.get("InstanceId") == iid:
                item["GrafanaInstanceId"] = gid


def _make_module(monkeypatch, fake):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (FakeModels(), SimpleNamespace(MonitorClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


# ---------------------------------------------------------------------------
# idempotent flows
# ---------------------------------------------------------------------------


def test_present_when_bound_is_idempotent(monkeypatch):
    fake = FakeMonitorClient(instances=[_instance()])
    _make_module(monkeypatch, fake)
    _args(state="present")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["binding"] == {"InstanceId": "prom-abc123", "GrafanaId": "grafana-abc123"}
    assert [c for c, unused in fake.calls] == ["DescribePrometheusInstances"]


def test_absent_when_not_bound_is_idempotent(monkeypatch):
    fake = FakeMonitorClient(instances=[_instance(GrafanaInstanceId="grafana-other")])
    _make_module(monkeypatch, fake)
    _args(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["binding"] is None
    assert [c for c, unused in fake.calls] == ["DescribePrometheusInstances"]


# ---------------------------------------------------------------------------
# binding flows
# ---------------------------------------------------------------------------


def test_present_binds_grafana(monkeypatch):
    fake = FakeMonitorClient(instances=[_instance(GrafanaInstanceId=None)])
    _make_module(monkeypatch, fake)
    _args(state="present")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["binding"] == {"InstanceId": "prom-abc123", "GrafanaId": "grafana-abc123"}
    assert fake.instances[0]["GrafanaInstanceId"] == "grafana-abc123"
    ops = [c for c, unused in fake.calls]
    assert ops[0] == "DescribePrometheusInstances"
    assert "BindPrometheusManagedGrafana" in ops


def test_present_check_mode_is_dry_run(monkeypatch):
    fake = FakeMonitorClient(instances=[_instance(GrafanaInstanceId=None)])
    _make_module(monkeypatch, fake)
    _args(_ansible_check_mode=True, state="present")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["binding"] == {"InstanceId": "prom-abc123", "GrafanaId": "grafana-abc123"}
    assert fake.instances[0]["GrafanaInstanceId"] is None
    assert "BindPrometheusManagedGrafana" not in [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# unbinding flows
# ---------------------------------------------------------------------------


def test_absent_unbinds_grafana(monkeypatch):
    fake = FakeMonitorClient(instances=[_instance()])
    _make_module(monkeypatch, fake)
    _args(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["binding"] is None
    assert fake.instances[0]["GrafanaInstanceId"] is None
    ops = [c for c, unused in fake.calls]
    assert "UnbindPrometheusManagedGrafana" in ops


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeMonitorClient(instances=[_instance()])
    _make_module(monkeypatch, fake)
    _args(_ansible_check_mode=True, state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["binding"] is None
    assert fake.instances[0]["GrafanaInstanceId"] == "grafana-abc123"
    assert "UnbindPrometheusManagedGrafana" not in [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# failure paths
# ---------------------------------------------------------------------------


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribePrometheusInstances(self, request):
            raise Boom("connection dropped")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    _args(state="present")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]
