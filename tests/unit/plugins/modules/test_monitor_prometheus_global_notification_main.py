"""Unit tests for the monitor_prometheus_global_notification write module.

Drives ``run_module()`` against an in-memory fake Monitor client whose
``ModifyPrometheusGlobalNotification`` operation rewrites the singleton
global-notification config stored for a Prometheus instance.

Scenario matrix:

* notification already matching (idempotent no-op)
* no remote notification yet (describe returns nothing) -> reconcile
* notification drift triggers a Modify
* drift in check mode (dry run, no Modify call)
* the blanket SDK failure path
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import monitor_prometheus_global_notification as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

NOTIFICATION = {
    "Enabled": True,
    "Type": "amp",
    "RepeatInterval": "1h",
    "ReceiverGroups": ["notice-abc123"],
}


def _args(**overrides):
    params = {"instance_id": "prom-abc123", "notification": NOTIFICATION}
    params.update(overrides)
    return module_args(**params)


class FakeMonitorClient(object):
    """In-memory Monitor client owning a singleton global notification."""

    def __init__(self, notification=None):
        # ``None`` means "no remote notification yet", matching the module's
        # ``current = item._serialize() if item else {}`` handling.
        self.notification = copy.deepcopy(notification)
        self.calls = []

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def DescribePrometheusGlobalNotification(self, request):
        self._record("DescribePrometheusGlobalNotification", request)
        return SimpleNamespace(
            Notification=FakeResource(self.notification) if self.notification is not None else None,
        )

    def ModifyPrometheusGlobalNotification(self, request):
        self._record("ModifyPrometheusGlobalNotification", request)
        item = getattr(request, "Notification", None)
        self.notification = dict(getattr(item, "__dict__", {})) if item is not None else {}
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (FakeModels(), SimpleNamespace(MonitorClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


# ---------------------------------------------------------------------------
# idempotent flows
# ---------------------------------------------------------------------------


def test_notification_already_matching_is_idempotent(monkeypatch):
    fake = FakeMonitorClient(notification=NOTIFICATION)
    _make_module(monkeypatch, fake)
    _args()
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["notification"] == NOTIFICATION
    assert [c for c, unused in fake.calls] == ["DescribePrometheusGlobalNotification"]


# ---------------------------------------------------------------------------
# reconcile flows
# ---------------------------------------------------------------------------


def test_no_remote_notification_reconciles(monkeypatch):
    fake = FakeMonitorClient(notification=None)
    _make_module(monkeypatch, fake)
    _args()
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["notification"] == NOTIFICATION
    ops = [c for c, unused in fake.calls]
    assert ops[0] == "DescribePrometheusGlobalNotification"
    assert "ModifyPrometheusGlobalNotification" in ops


def test_notification_drift_modifies(monkeypatch):
    drift = dict(NOTIFICATION)
    drift["Enabled"] = False
    drift["RepeatInterval"] = "30m"
    fake = FakeMonitorClient(notification=NOTIFICATION)
    _make_module(monkeypatch, fake)
    _args(notification=drift)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["notification"] == drift
    assert fake.notification["RepeatInterval"] == "30m"
    ops = [c for c, unused in fake.calls]
    assert "ModifyPrometheusGlobalNotification" in ops


def test_notification_drift_check_mode_is_dry_run(monkeypatch):
    drift = dict(NOTIFICATION)
    drift["Enabled"] = False
    fake = FakeMonitorClient(notification=NOTIFICATION)
    _make_module(monkeypatch, fake)
    _args(_ansible_check_mode=True, notification=drift)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["notification"] == drift
    assert fake.notification == NOTIFICATION
    assert "ModifyPrometheusGlobalNotification" not in [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# failure paths
# ---------------------------------------------------------------------------


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribePrometheusGlobalNotification(self, request):
            raise Boom("connection dropped")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    _args()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]
