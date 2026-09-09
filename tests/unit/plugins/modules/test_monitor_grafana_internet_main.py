"""Unit tests for the monitor_grafana_internet write module.

Drives ``run_module()`` against an in-memory fake Monitor client whose
``EnableGrafanaInternet`` operation toggles the ``InternetUrl`` stored on a
Grafana instance.

Scenario matrix:

* disabled instance + ``enabled: false`` (idempotent no-op)
* enabled instance + ``enabled: true`` (idempotent no-op)
* enabling and disabling drift (real update both ways)
* enabling drift in check mode (dry run, no update call)
* the blanket SDK failure path
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import monitor_grafana_internet as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

INSTANCE = {
    "InstanceId": "grafana-abc123",
    "InstanceName": "production-dashboards",
    "InternetUrl": "https://grafana-abc123.grafana.tencentcloud.com",
}


def _instance(**overrides):
    item = copy.deepcopy(INSTANCE)
    item.update(overrides)
    return item


def _args(**overrides):
    params = {"instance_id": "grafana-abc123"}
    params.update(overrides)
    return module_args(**params)


class FakeMonitorClient(object):
    """In-memory Monitor client toggling a Grafana instance's internet access."""

    def __init__(self, instances=None):
        self.instances = [copy.deepcopy(t) for t in (instances or [])]
        self.calls = []

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def DescribeGrafanaInstances(self, request):
        self._record("DescribeGrafanaInstances", request)
        ids = list(getattr(request, "InstanceIds", None) or [])
        matched = [t for t in self.instances if t.get("InstanceId") in ids]
        # The module reads ``InstanceSet or Instances or []``, so both
        # attributes must exist for the empty case.
        return SimpleNamespace(InstanceSet=[FakeResource(t) for t in matched], Instances=None)

    def EnableGrafanaInternet(self, request):
        self._record("EnableGrafanaInternet", request)
        for item in self.instances:
            if item.get("InstanceId") == getattr(request, "InstanceID", None):
                item["InternetUrl"] = (
                    "https://grafana-abc123.grafana.tencentcloud.com" if getattr(request, "EnableInternet", False) else ""
                )
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (FakeModels(), SimpleNamespace(MonitorClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


# ---------------------------------------------------------------------------
# idempotent flows
# ---------------------------------------------------------------------------


def test_disabled_matches_enabled_false_is_idempotent(monkeypatch):
    fake = FakeMonitorClient(instances=[_instance(InternetUrl="")])
    _make_module(monkeypatch, fake)
    _args(enabled=False)
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["enabled"] is False
    assert [c for c, unused in fake.calls] == ["DescribeGrafanaInstances"]


def test_enabled_matches_enabled_true_is_idempotent(monkeypatch):
    fake = FakeMonitorClient(instances=[_instance()])
    _make_module(monkeypatch, fake)
    _args(enabled=True)
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["enabled"] is True


def test_missing_instance_counts_as_disabled(monkeypatch):
    fake = FakeMonitorClient(instances=[])
    _make_module(monkeypatch, fake)
    _args(enabled=False)
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["enabled"] is False


# ---------------------------------------------------------------------------
# drift flows
# ---------------------------------------------------------------------------


def test_enable_drift_turns_internet_on(monkeypatch):
    fake = FakeMonitorClient(instances=[_instance(InternetUrl="")])
    _make_module(monkeypatch, fake)
    _args(enabled=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["enabled"] is True
    assert fake.instances[0]["InternetUrl"]
    ops = [c for c, unused in fake.calls]
    assert ops[0] == "DescribeGrafanaInstances"
    assert "EnableGrafanaInternet" in ops


def test_disable_drift_turns_internet_off(monkeypatch):
    fake = FakeMonitorClient(instances=[_instance()])
    _make_module(monkeypatch, fake)
    _args(enabled=False)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["enabled"] is False
    assert fake.instances[0]["InternetUrl"] == ""
    ops = [c for c, unused in fake.calls]
    assert "EnableGrafanaInternet" in ops


def test_enable_check_mode_is_dry_run(monkeypatch):
    fake = FakeMonitorClient(instances=[_instance(InternetUrl="")])
    _make_module(monkeypatch, fake)
    _args(_ansible_check_mode=True, enabled=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["enabled"] is True
    assert fake.instances[0]["InternetUrl"] == ""
    assert "EnableGrafanaInternet" not in [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# failure paths
# ---------------------------------------------------------------------------


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeGrafanaInstances(self, request):
            raise Boom("connection dropped")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    _args(enabled=True)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]
