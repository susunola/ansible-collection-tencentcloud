"""Unit tests for the monitor_grafana_notification_channel write module.

Drives ``run_module()`` against an in-memory fake Monitor client whose
create / update / delete operations mutate a notification-channel store so
the module's post-write ``find`` converges immediately.

Scenario matrix:

* the ``name``-required-when-present guard
* absent on a missing channel (idempotent no-op, by id and by name)
* absent with a matching channel (check-mode dry run, real delete)
* creation when missing (happy path and check mode)
* no-op when receivers / organization ids already match
* receiver / organization-id drift triggers an Update
* the ambiguous-name guard and the blanket SDK failure path
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import monitor_grafana_notification_channel as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

CHANNEL = {
    "ChannelId": "channel-abc123",
    "ChannelName": "operations",
    "Receivers": ["notice-1"],
    "OrganizationIds": ["1"],
}


def _channel(**overrides):
    item = copy.deepcopy(CHANNEL)
    item.update(overrides)
    return item


def _args(**overrides):
    params = {"instance_id": "grafana-abc123", "name": "operations"}
    params.update(overrides)
    return module_args(**params)


class FakeMonitorClient(object):
    """In-memory Monitor client mutating a notification-channel store."""

    def __init__(self, channels=None):
        self.channels = [copy.deepcopy(t) for t in (channels or [])]
        self.calls = []
        self._next = 0

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def DescribeGrafanaNotificationChannels(self, request):
        self._record("DescribeGrafanaNotificationChannels", request)
        matched = list(self.channels)
        ids = list(getattr(request, "ChannelIDs", None) or [])
        if ids:
            matched = [t for t in matched if t.get("ChannelId") in ids]
        else:
            name = getattr(request, "ChannelName", None)
            if name:
                matched = [t for t in matched if t.get("ChannelName") == name]
        return SimpleNamespace(NotificationChannelSet=[FakeResource(t) for t in matched])

    def CreateGrafanaNotificationChannel(self, request):
        self._record("CreateGrafanaNotificationChannel", request)
        self._next += 1
        item = {
            "ChannelId": "channel-new-%03d" % self._next,
            "ChannelName": getattr(request, "ChannelName", None),
            "Receivers": list(getattr(request, "Receivers", None) or []),
            "OrganizationIds": list(getattr(request, "OrganizationIds", None) or []),
        }
        self.channels.append(item)
        return SimpleNamespace(ChannelId=item["ChannelId"], RequestId="req-fake")

    def UpdateGrafanaNotificationChannel(self, request):
        self._record("UpdateGrafanaNotificationChannel", request)
        for item in self.channels:
            if item.get("ChannelId") == getattr(request, "ChannelId", None):
                item["Receivers"] = list(getattr(request, "Receivers", None) or [])
                item["OrganizationIds"] = list(getattr(request, "OrganizationIds", None) or [])
        return SimpleNamespace(RequestId="req-fake")

    def DeleteGrafanaNotificationChannel(self, request):
        self._record("DeleteGrafanaNotificationChannel", request)
        ids = list(getattr(request, "ChannelIDs", None) or [])
        self.channels = [t for t in self.channels if t.get("ChannelId") not in ids]
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (FakeModels(), SimpleNamespace(MonitorClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


# ---------------------------------------------------------------------------
# guards
# ---------------------------------------------------------------------------


def test_present_requires_name(monkeypatch):
    fake = FakeMonitorClient(channels=[])
    _make_module(monkeypatch, fake)
    module_args(state="present", instance_id="grafana-abc123", channel_id="channel-abc123")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert exc.value.args[0]["msg"] == "name is required when state=present"


# ---------------------------------------------------------------------------
# absent flows
# ---------------------------------------------------------------------------


def test_absent_missing_by_id_is_idempotent(monkeypatch):
    fake = FakeMonitorClient(channels=[])
    _make_module(monkeypatch, fake)
    _args(state="absent", name=None, channel_id="channel-999")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["channel"] is None
    assert [c for c, unused in fake.calls] == ["DescribeGrafanaNotificationChannels"]


def test_absent_missing_by_name_is_idempotent(monkeypatch):
    fake = FakeMonitorClient(channels=[])
    _make_module(monkeypatch, fake)
    _args(state="absent", name="ghost-channel")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["channel"] is None


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeMonitorClient(channels=[_channel()])
    _make_module(monkeypatch, fake)
    _args(_ansible_check_mode=True, state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["channel"]["ChannelId"] == "channel-abc123"
    assert len(fake.channels) == 1
    assert "DeleteGrafanaNotificationChannel" not in [c for c, unused in fake.calls]


def test_absent_deletes_channel(monkeypatch):
    fake = FakeMonitorClient(channels=[_channel()])
    _make_module(monkeypatch, fake)
    _args(state="absent", name=None, channel_id="channel-abc123")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["channel"] is None
    assert fake.channels == []
    ops = [c for c, unused in fake.calls]
    assert "DeleteGrafanaNotificationChannel" in ops


# ---------------------------------------------------------------------------
# creation flows
# ---------------------------------------------------------------------------


def test_create_channel(monkeypatch):
    fake = FakeMonitorClient(channels=[])
    _make_module(monkeypatch, fake)
    _args(
        state="present",
        name="metrics-alerts",
        receivers=["notice-1", "notice-2"],
        organization_ids=["1", "2"],
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["channel"]["ChannelName"] == "metrics-alerts"
    assert result["channel"]["ChannelId"].startswith("channel-new-")
    assert result["channel"]["Receivers"] == ["notice-1", "notice-2"]
    assert len(fake.channels) == 1
    ops = [c for c, unused in fake.calls]
    assert ops[0] == "DescribeGrafanaNotificationChannels"
    assert "CreateGrafanaNotificationChannel" in ops


def test_create_check_mode_is_dry_run(monkeypatch):
    fake = FakeMonitorClient(channels=[])
    _make_module(monkeypatch, fake)
    _args(_ansible_check_mode=True, state="present", name="metrics-alerts", receivers=["notice-1"])
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["channel"] is None
    assert fake.channels == []
    assert "CreateGrafanaNotificationChannel" not in [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# existing-channel flows
# ---------------------------------------------------------------------------


def test_existing_channel_no_drift_is_idempotent(monkeypatch):
    fake = FakeMonitorClient(channels=[_channel()])
    _make_module(monkeypatch, fake)
    _args(state="present", receivers=["notice-1"])
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["channel"]["ChannelId"] == "channel-abc123"
    assert "UpdateGrafanaNotificationChannel" not in [c for c, unused in fake.calls]


def test_receiver_drift_updates_channel(monkeypatch):
    fake = FakeMonitorClient(channels=[_channel()])
    _make_module(monkeypatch, fake)
    _args(state="present", receivers=["notice-1", "notice-2"])
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["channel"]["Receivers"] == ["notice-1", "notice-2"]
    assert fake.channels[0]["Receivers"] == ["notice-1", "notice-2"]
    ops = [c for c, unused in fake.calls]
    assert "UpdateGrafanaNotificationChannel" in ops


def test_organization_drift_updates_channel(monkeypatch):
    fake = FakeMonitorClient(channels=[_channel()])
    _make_module(monkeypatch, fake)
    _args(state="present", organization_ids=["2"])
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["channel"]["OrganizationIds"] == ["2"]
    ops = [c for c, unused in fake.calls]
    assert "UpdateGrafanaNotificationChannel" in ops


def test_ambiguous_name_match_fails(monkeypatch):
    fake = FakeMonitorClient(channels=[_channel(), _channel(ChannelId="channel-xyz789")])
    _make_module(monkeypatch, fake)
    _args(state="present")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "Multiple Grafana channels have the requested name" in exc.value.args[0]["msg"]


# ---------------------------------------------------------------------------
# failure paths
# ---------------------------------------------------------------------------


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeGrafanaNotificationChannels(self, request):
            raise Boom("connection dropped")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    _args(state="present")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]
