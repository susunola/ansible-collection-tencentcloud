"""Unit tests for the monitor_prometheus_alertmanager_config write module.

Drives ``run_module()`` against an in-memory fake Monitor client whose
``ReplacePrometheusAlertmanagerConfig`` operation rewrites the singleton
Alertmanager config stored for a Prometheus instance.

Scenario matrix:

* config already matching (idempotent no-op)
* no remote config yet (describe returns nothing) -> reconcile to the target
* config drift triggers a Replace
* drift in check mode (dry run, no Replace call)
* the blanket SDK failure path
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import monitor_prometheus_alertmanager_config as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

CONFIG = {
    "InhibitRules": [],
    "Receivers": [{"Name": "default", "EmailConfigs": [{"To": "oncall@example.com"}]}],
}


def _args(**overrides):
    params = {"instance_id": "prom-abc123", "config": CONFIG}
    params.update(overrides)
    return module_args(**params)


class FakeMonitorClient(object):
    """In-memory Monitor client owning a singleton Alertmanager config."""

    def __init__(self, config=None):
        # ``None`` means "no remote config yet", matching the module's
        # ``current = item._serialize() if item else {}`` handling.
        self.config = copy.deepcopy(config)
        self.calls = []

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def DescribePrometheusAlertmanagerConfig(self, request):
        self._record("DescribePrometheusAlertmanagerConfig", request)
        return SimpleNamespace(
            AlertmanagerConfig=FakeResource(self.config) if self.config is not None else None,
        )

    def ReplacePrometheusAlertmanagerConfig(self, request):
        self._record("ReplacePrometheusAlertmanagerConfig", request)
        item = getattr(request, "AlertmanagerConfig", None)
        self.config = dict(getattr(item, "__dict__", {})) if item is not None else {}
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (FakeModels(), SimpleNamespace(MonitorClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


# ---------------------------------------------------------------------------
# idempotent flows
# ---------------------------------------------------------------------------


def test_config_already_matching_is_idempotent(monkeypatch):
    fake = FakeMonitorClient(config=CONFIG)
    _make_module(monkeypatch, fake)
    _args()
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["config"] == CONFIG
    assert [c for c, unused in fake.calls] == ["DescribePrometheusAlertmanagerConfig"]


# ---------------------------------------------------------------------------
# reconcile flows
# ---------------------------------------------------------------------------


def test_no_remote_config_replaces(monkeypatch):
    fake = FakeMonitorClient(config=None)
    _make_module(monkeypatch, fake)
    _args()
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["config"] == CONFIG
    ops = [c for c, unused in fake.calls]
    assert ops[0] == "DescribePrometheusAlertmanagerConfig"
    assert "ReplacePrometheusAlertmanagerConfig" in ops


def test_config_drift_replaces(monkeypatch):
    drift = dict(CONFIG)
    drift["Receivers"] = [{"Name": "pager", "WebhookConfigs": [{"Url": "https://hooks.example.com/1"}]}]
    fake = FakeMonitorClient(config=CONFIG)
    _make_module(monkeypatch, fake)
    _args(config=drift)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["config"] == drift
    assert fake.config["Receivers"][0]["Name"] == "pager"
    ops = [c for c, unused in fake.calls]
    assert "ReplacePrometheusAlertmanagerConfig" in ops


def test_config_drift_check_mode_is_dry_run(monkeypatch):
    drift = {"InhibitRules": [{"SourceMatchers": ["severity=critical"]}]}
    fake = FakeMonitorClient(config=CONFIG)
    _make_module(monkeypatch, fake)
    _args(_ansible_check_mode=True, config=drift)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["config"] == drift
    assert fake.config == CONFIG
    assert "ReplacePrometheusAlertmanagerConfig" not in [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# failure paths
# ---------------------------------------------------------------------------


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribePrometheusAlertmanagerConfig(self, request):
            raise Boom("connection dropped")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    _args()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]
