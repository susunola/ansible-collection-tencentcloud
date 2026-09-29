"""Tests for the Grafana notification-channel writer: monitor_grafana_notification_channel.

A channel is identified either by ``channel_id`` (exact, and the only way to
reach a channel whose name differs from the task's ``name``) or by ``name``
(the API's fuzzy ``ChannelName`` filter plus an exact client-side match, paged
100 at a time). The name is immutable once the channel exists, and the
receivers / organization ids are reconciled as sorted sets.

The three lookup tests came first and stay as they were: the name lookup pages
past a full first page and matches exactly, the id lookup does not send the
name filter, and a name that differs from the live one is rejected rather than
silently ignored. Everything below drives the module through the shared
harness: the request builders, the lookup edge cases (no match, ambiguous name)
and ``run_module()`` end to end against an in-memory Monitor client whose write
operations mutate the store, so create / update / delete and the idempotent
no-op are observable through the payload and the call list.

``_load`` and ``TencentCloudModule.create_client`` are patched, so the SDK is
never imported; the real ``sdk_call`` runs, which is what makes the failure
envelope the module's own behaviour.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import types

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


class Request:
    pass


class Item:
    def __init__(self, channel_id, name):
        self.ChannelId, self.ChannelName = channel_id, name

    def _serialize(self, allow_none=True):
        return {"ChannelId": self.ChannelId, "ChannelName": self.ChannelName}


class Client:
    def __init__(self, values):
        self.values = values
        self.requests = []

    def DescribeGrafanaNotificationChannels(self, request):
        self.requests.append(request)
        values = self.values
        if request.ChannelIDs:
            values = [item for item in values if item.ChannelId in request.ChannelIDs]
        if request.ChannelName:
            values = [item for item in values if request.ChannelName in item.ChannelName]
        return types.SimpleNamespace(NotificationChannelSet=values[request.Offset:request.Offset + request.Limit])


class Module:
    def sdk_call(self, operation, request):
        return operation(request)

    def fail_json(self, **kwargs):
        raise ValueError(kwargs["msg"])


MODELS = types.SimpleNamespace(DescribeGrafanaNotificationChannelsRequest=Request)


def test_find_name_paginates_and_filters_exact_match():
    values = [Item(str(index), "target-extra") for index in range(100)] + [Item("wanted", "target")]
    client = Client(values)
    result = mod.find(Module(), client, MODELS,
                      {"instance_id": "grafana-1", "channel_id": None, "name": "target"})
    assert result["ChannelId"] == "wanted"
    assert [request.Offset for request in client.requests] == [0, 100]


def test_find_id_ignores_name_query_filter():
    client = Client([Item("wanted", "old-name")])
    result = mod.find(Module(), client, MODELS,
                      {"instance_id": "grafana-1", "channel_id": "wanted", "name": "new-name"})
    assert result["ChannelName"] == "old-name"
    assert client.requests[0].ChannelName is None


def test_immutable_name_drift_is_rejected():
    with pytest.raises(ValueError, match="cannot be changed"):
        mod.validate_immutable_name(Module(), {"ChannelId": "wanted", "ChannelName": "old-name"}, "new-name")


INSTANCE_ID = "grafana-abc123"
CHANNEL_ID = "channel-abc123"
CHANNEL_NAME = "operations"
ENDPOINT = "monitor.tencentcloudapi.com"

#: One notification channel as ``DescribeGrafanaNotificationChannels`` returns
#: it: the four fields the module reconciles and reports.
CHANNEL = {
    "ChannelId": CHANNEL_ID,
    "ChannelName": CHANNEL_NAME,
    "Receivers": ["notice-1"],
    "OrganizationIds": ["1"],
}


def _params(**overrides):
    params = {
        "state": "present",
        "instance_id": INSTANCE_ID,
        "channel_id": None,
        "name": CHANNEL_NAME,
        "receivers": ["notice-1"],
        "organization_ids": ["1"],
    }
    params.update(overrides)
    return params


def _module_args(**overrides):
    args = {
        "state": "present",
        "instance_id": INSTANCE_ID,
        "name": CHANNEL_NAME,
        "receivers": ["notice-1"],
        "organization_ids": ["1"],
    }
    args.update(overrides)
    return module_args(**args)


class FakeMonitorClient(object):
    """In-memory Monitor client mutating a notification-channel store."""

    def __init__(self, channels=None, error=None):
        self.channels = [dict(item) for item in (channels or [])]
        self.error = error
        self.calls = []

    def _record(self, name, request):
        self.calls.append((name, request))
        if self.error is not None:
            raise self.error

    @property
    def operations(self):
        return [name for name, _request in self.calls]

    def DescribeGrafanaNotificationChannels(self, request):
        self._record("DescribeGrafanaNotificationChannels", request)
        values = list(self.channels)
        if request.ChannelIDs:
            values = [item for item in values if item["ChannelId"] in request.ChannelIDs]
        elif request.ChannelName:
            values = [item for item in values if item["ChannelName"] == request.ChannelName]
        offset, limit = request.Offset or 0, request.Limit or 100
        return types.SimpleNamespace(
            NotificationChannelSet=[FakeResource(item) for item in values[offset:offset + limit]],
            RequestId="req-monitor-1",
        )

    def CreateGrafanaNotificationChannel(self, request):
        self._record("CreateGrafanaNotificationChannel", request)
        item = {
            "ChannelId": "channel-new-001",
            "ChannelName": request.ChannelName,
            "Receivers": list(request.Receivers or []),
            "OrganizationIds": list(request.OrganizationIds or []),
        }
        self.channels.append(item)
        return types.SimpleNamespace(ChannelId=item["ChannelId"], RequestId="req-monitor-1")

    def UpdateGrafanaNotificationChannel(self, request):
        self._record("UpdateGrafanaNotificationChannel", request)
        for item in self.channels:
            if item["ChannelId"] == request.ChannelId:
                item["Receivers"] = list(request.Receivers or [])
                item["OrganizationIds"] = list(request.OrganizationIds or [])
        return types.SimpleNamespace(RequestId="req-monitor-1")

    def DeleteGrafanaNotificationChannel(self, request):
        self._record("DeleteGrafanaNotificationChannel", request)
        removed = set(request.ChannelIDs or [])
        self.channels = [item for item in self.channels if item["ChannelId"] not in removed]
        return types.SimpleNamespace(RequestId="req-monitor-1")


def _patch_module(monkeypatch, client):
    """Point ``mod`` at ``client`` through its ``_load``/``create_client`` seams."""
    clients = []
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (FakeModels(), types.SimpleNamespace(MonitorClient=object)))

    def create_client(self, client_class, endpoint):
        clients.append((client_class, endpoint))
        return client

    monkeypatch.setattr(TencentCloudModule, "create_client", create_client)
    return clients


# ---------------------------------------------------------------------------
# request builders
# ---------------------------------------------------------------------------


def test_describe_request_by_id_clears_the_name_filter():
    """The API's ``ChannelName`` filter is fuzzy; the id lookup must not send it."""
    request = mod.build_describe(FakeModels(), _params(channel_id=CHANNEL_ID), offset=0)

    assert request.ChannelIDs == [CHANNEL_ID]
    assert request.ChannelName is None
    assert (request.Offset, request.Limit) == (0, 100)
    assert request.InstanceId == INSTANCE_ID


def test_describe_request_by_name_pages_from_the_requested_offset():
    request = mod.build_describe(FakeModels(), _params(), offset=200)

    assert request.ChannelName == CHANNEL_NAME
    assert request.ChannelIDs is None
    assert (request.Offset, request.Limit) == (200, 100)


def test_create_request_carries_the_name_receivers_and_organizations():
    request = mod.build_create(FakeModels(), _params(receivers=["notice-2", "notice-1"], organization_ids=["1", "2"]))

    assert request.InstanceId == INSTANCE_ID
    assert request.ChannelName == CHANNEL_NAME
    assert request.Receivers == ["notice-2", "notice-1"]
    assert request.OrganizationIds == ["1", "2"]


def test_update_request_targets_the_channel_id_without_a_name():
    """The name is immutable, so the update request has no field for it."""
    request = mod.build_update(FakeModels(), _params(), CHANNEL_ID)

    assert (request.InstanceId, request.ChannelId) == (INSTANCE_ID, CHANNEL_ID)
    assert request.Receivers == ["notice-1"]
    assert request.OrganizationIds == ["1"]
    assert not hasattr(request, "ChannelName")


def test_delete_request_targets_the_channel_id():
    request = mod.build_delete(FakeModels(), _params(), CHANNEL_ID)

    assert (request.InstanceId, request.ChannelIDs) == (INSTANCE_ID, [CHANNEL_ID])


def test_target_and_comparable_normalise_receivers_and_organizations():
    wanted = mod.target(_params(receivers=["notice-2", "notice-1"], organization_ids=["2", "1"]))

    assert wanted == {
        "ChannelName": CHANNEL_NAME,
        "Receivers": ["notice-1", "notice-2"],
        "OrganizationIds": ["1", "2"],
    }
    assert mod.comparable({"ChannelName": CHANNEL_NAME}) == {
        "ChannelName": CHANNEL_NAME,
        "Receivers": [],
        "OrganizationIds": [],
    }
    assert mod.comparable({"ChannelName": CHANNEL_NAME, "Receivers": None, "OrganizationIds": ["1"]}) == {
        "ChannelName": CHANNEL_NAME,
        "Receivers": [],
        "OrganizationIds": ["1"],
    }


# ---------------------------------------------------------------------------
# lookup edge cases
# ---------------------------------------------------------------------------


def test_find_returns_none_when_the_name_does_not_match():
    """The API filter is a substring match; a suffix is not the channel."""
    client = Client([Item("channel-1", "operations-old")])

    assert mod.find(Module(), client, MODELS,
                    {"instance_id": INSTANCE_ID, "channel_id": None, "name": "operations"}) is None


def test_find_returns_none_when_the_id_does_not_match():
    client = Client([Item("channel-1", "operations")])

    assert mod.find(Module(), client, MODELS,
                    {"instance_id": INSTANCE_ID, "channel_id": "channel-missing", "name": None}) is None


def test_find_rejects_an_ambiguous_name():
    client = Client([Item("channel-1", "operations"), Item("channel-2", "operations")])

    with pytest.raises(ValueError, match="Multiple Grafana channels have the requested name"):
        mod.find(Module(), client, MODELS, {"instance_id": INSTANCE_ID, "channel_id": None, "name": "operations"})


# ---------------------------------------------------------------------------
# run_module
# ---------------------------------------------------------------------------


def test_run_module_creates_a_missing_channel_and_reports_it(monkeypatch):
    client = FakeMonitorClient()
    clients = _patch_module(monkeypatch, client)
    _module_args()

    payload = run(mod.run_module)

    assert payload.keys() == {"changed", "channel", "tc_api_calls"}
    assert payload["changed"] is True
    assert payload["channel"] == {
        "ChannelId": "channel-new-001",
        "ChannelName": CHANNEL_NAME,
        "Receivers": ["notice-1"],
        "OrganizationIds": ["1"],
    }
    assert payload["channel"].keys() == set(CHANNEL)
    assert client.operations == [
        "DescribeGrafanaNotificationChannels", "CreateGrafanaNotificationChannel",
        "DescribeGrafanaNotificationChannels",
    ]
    create_request = [request for name, request in client.calls if name == "CreateGrafanaNotificationChannel"][0]
    assert (create_request.InstanceId, create_request.ChannelName) == (INSTANCE_ID, CHANNEL_NAME)
    assert clients == [(object, ENDPOINT)]


def test_run_module_is_idempotent_for_a_matching_channel(monkeypatch):
    client = FakeMonitorClient(channels=[CHANNEL])
    _patch_module(monkeypatch, client)
    _module_args()

    payload = run(mod.run_module)

    assert payload.keys() == {"changed", "channel", "tc_api_calls"}
    assert payload["changed"] is False
    assert payload["channel"] == CHANNEL
    assert client.operations == ["DescribeGrafanaNotificationChannels"]
    assert client.channels == [CHANNEL]


def test_run_module_updates_receiver_drift(monkeypatch):
    client = FakeMonitorClient(channels=[CHANNEL])
    _patch_module(monkeypatch, client)
    _module_args(receivers=["notice-1", "notice-2"])

    payload = run(mod.run_module)

    assert payload["changed"] is True
    assert payload["channel"]["Receivers"] == ["notice-1", "notice-2"]
    assert client.operations == [
        "DescribeGrafanaNotificationChannels", "UpdateGrafanaNotificationChannel",
        "DescribeGrafanaNotificationChannels",
    ]
    update_request = [request for name, request in client.calls if name == "UpdateGrafanaNotificationChannel"][0]
    assert (update_request.InstanceId, update_request.ChannelId) == (INSTANCE_ID, CHANNEL_ID)


def test_run_module_updates_organization_drift_by_id(monkeypatch):
    """``channel_id`` reaches a channel whose name the lookup filter would miss."""
    client = FakeMonitorClient(channels=[dict(CHANNEL, ChannelName="legacy-name")])
    _patch_module(monkeypatch, client)
    _module_args(name="legacy-name", channel_id=CHANNEL_ID, organization_ids=["1", "2"])

    payload = run(mod.run_module)

    assert payload["changed"] is True
    assert payload["channel"]["OrganizationIds"] == ["1", "2"]
    describe_requests = [request for name, request in client.calls if name == "DescribeGrafanaNotificationChannels"]
    assert [request.ChannelIDs for request in describe_requests] == [[CHANNEL_ID], [CHANNEL_ID]]
    assert [request.ChannelName for request in describe_requests] == [None, None]


def test_run_module_check_mode_predicts_the_update_without_writing(monkeypatch):
    client = FakeMonitorClient(channels=[CHANNEL])
    _patch_module(monkeypatch, client)
    _module_args(receivers=["notice-2"], _ansible_check_mode=True)

    payload = run(mod.run_module)

    assert payload.keys() == {"changed", "channel", "diff", "tc_api_calls"}
    assert payload["changed"] is True
    assert payload["channel"] == CHANNEL
    assert payload["diff"] == {
        "before": {"ChannelName": CHANNEL_NAME, "Receivers": ["notice-1"], "OrganizationIds": ["1"]},
        "after": {"ChannelName": CHANNEL_NAME, "Receivers": ["notice-2"], "OrganizationIds": ["1"]},
    }
    assert client.operations == ["DescribeGrafanaNotificationChannels"]
    assert client.channels == [CHANNEL]


def test_run_module_deletes_a_matching_channel(monkeypatch):
    client = FakeMonitorClient(channels=[CHANNEL])
    _patch_module(monkeypatch, client)
    _module_args(state="absent")

    payload = run(mod.run_module)

    assert payload.keys() == {"changed", "channel", "tc_api_calls"}
    assert payload["changed"] is True
    assert payload["channel"] is None
    assert client.channels == []
    delete_request = [request for name, request in client.calls if name == "DeleteGrafanaNotificationChannel"][0]
    assert delete_request.ChannelIDs == [CHANNEL_ID]


def test_run_module_absent_on_a_missing_channel_is_unchanged(monkeypatch):
    client = FakeMonitorClient()
    _patch_module(monkeypatch, client)
    _module_args(state="absent", name="not-there")

    payload = run(mod.run_module)

    assert payload.keys() == {"changed", "channel", "tc_api_calls"}
    assert payload["changed"] is False
    assert payload["channel"] is None
    assert client.operations == ["DescribeGrafanaNotificationChannels"]


def test_run_module_absent_check_mode_keeps_the_channel(monkeypatch):
    client = FakeMonitorClient(channels=[CHANNEL])
    _patch_module(monkeypatch, client)
    _module_args(state="absent", _ansible_check_mode=True)

    payload = run(mod.run_module)

    assert payload["changed"] is True
    assert payload["channel"] == CHANNEL
    assert payload["diff"] == {"before": CHANNEL, "after": None}
    assert client.operations == ["DescribeGrafanaNotificationChannels"]
    assert client.channels == [CHANNEL]


def test_run_module_refuses_to_rename_an_existing_channel(monkeypatch):
    client = FakeMonitorClient(channels=[CHANNEL])
    _patch_module(monkeypatch, client)
    _module_args(channel_id=CHANNEL_ID, name="renamed", receivers=["notice-1"])

    with pytest.raises(AnsibleFailJson) as failure:
        run(mod.run_module)

    payload = failure.value.args[0]
    assert payload["msg"] == "Grafana notification channel name cannot be changed"
    assert payload["channel_id"] == CHANNEL_ID
    assert payload["current_name"] == CHANNEL_NAME
    assert payload["desired_name"] == "renamed"
    assert client.operations == ["DescribeGrafanaNotificationChannels"]


def test_run_module_requires_the_instance_id(monkeypatch):
    _patch_module(monkeypatch, FakeMonitorClient())
    module_args()

    with pytest.raises(AnsibleFailJson) as failure:
        run(mod.run_module)

    assert failure.value.args[0]["msg"] == "missing required arguments: instance_id"


def test_run_module_requires_the_channel_id_or_the_name(monkeypatch):
    _patch_module(monkeypatch, FakeMonitorClient())
    module_args(instance_id=INSTANCE_ID)

    with pytest.raises(AnsibleFailJson) as failure:
        run(mod.run_module)

    assert failure.value.args[0]["msg"] == "one of the following is required: channel_id, name"


def test_run_module_requires_the_name_when_state_is_present(monkeypatch):
    _patch_module(monkeypatch, FakeMonitorClient())
    module_args(state="present", instance_id=INSTANCE_ID, channel_id=CHANNEL_ID)

    with pytest.raises(AnsibleFailJson) as failure:
        run(mod.run_module)

    assert failure.value.args[0]["msg"] == "name is required when state=present"


def test_run_module_maps_an_sdk_error_to_the_failure_envelope(monkeypatch):
    class FakeSdkException(Exception):
        def get_code(self):
            return "ResourceNotFound.NotificationChannelNotFound"

        def get_request_id(self):
            return "req-monitor-missing"

    client = FakeMonitorClient(error=FakeSdkException("channel does not exist"))
    _patch_module(monkeypatch, client)
    _module_args()

    with pytest.raises(AnsibleFailJson) as failure:
        run(mod.run_module)

    payload = failure.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert payload["error"] == "channel does not exist"
    assert payload["error_code"] == "ResourceNotFound.NotificationChannelNotFound"
    assert payload["request_id"] == "req-monitor-missing"
    assert payload["error_kind"] == "not_found"
