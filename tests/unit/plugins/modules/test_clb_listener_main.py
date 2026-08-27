"""Main-path unit tests for the clb_listener module (run_module level)."""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import clb_listener
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    FakeModels,
    FakeResource,
    module_args,
    run,
)

LISTENER = {
    "ListenerId": "lbl-existing1",
    "ListenerName": "tcp-8080",
    "Protocol": "TCP",
    "Port": 8080,
    "Scheduler": "WRR",
    "SessionExpireTime": 0,
    "HealthCheck": {
        "HealthSwitch": 1,
        "IntervalTime": 5,
        "HealthNum": 3,
        "UnHealthNum": 3,
        "TimeOut": 2,
    },
    "SniSwitch": 0,
}

CREATE_ARGS = dict(
    state="present",
    load_balancer_id="lb-xxxxxxxx",
    protocol="TCP",
    port=8080,
    name="tcp-8080",
)


class FakeClbClient(object):
    def __init__(self, listeners=None):
        self.listeners = list(listeners or [])
        self.CreateListener = MagicMock(side_effect=self._create)
        self.DeleteListener = MagicMock(side_effect=self._delete)
        self.ModifyListener = MagicMock(side_effect=self._modify)
        self.DescribeTaskStatus = MagicMock(
            return_value=SimpleNamespace(Status=0, Message=None, LoadBalancerIds=[]))

    def DescribeListeners(self, request):
        matched = self.listeners
        ids = getattr(request, "ListenerIds", None)
        if ids:
            matched = [l for l in matched if l["ListenerId"] in ids]
        else:
            port = getattr(request, "Port", None)
            protocol = getattr(request, "Protocol", None)
            if port is not None:
                matched = [l for l in matched if l["Port"] == port]
            if protocol:
                matched = [l for l in matched if l["Protocol"] == protocol]
        return SimpleNamespace(
            Listeners=[FakeResource(l) for l in matched], TotalCount=len(matched))

    def _create(self, request):
        health_check = getattr(request, "HealthCheck", None)
        listener = {
            "ListenerId": "lbl-new00001",
            "ListenerName": (request.ListenerNames[0]
                             if getattr(request, "ListenerNames", None) else ""),
            "Protocol": request.Protocol,
            "Port": request.Ports[0],
            "Scheduler": getattr(request, "Scheduler", "WRR"),
            "SessionExpireTime": getattr(request, "SessionExpireTime", 0),
            "HealthCheck": (
                {"HealthSwitch": health_check.HealthSwitch}
                if health_check is not None and hasattr(health_check, "HealthSwitch")
                else None
            ),
            "SniSwitch": getattr(request, "SniSwitch", 0),
        }
        self.listeners.append(listener)
        return SimpleNamespace(ListenerIds=[listener["ListenerId"]], RequestId="req-create")

    def _delete(self, request):
        self.listeners = [l for l in self.listeners if l["ListenerId"] != request.ListenerId]
        return SimpleNamespace(RequestId="req-delete")

    def _modify(self, request):
        for listener in self.listeners:
            if listener["ListenerId"] != request.ListenerId:
                continue
            for attribute in ("ListenerName", "Scheduler", "SessionExpireTime",
                              "SniSwitch", "KeepaliveEnable"):
                value = getattr(request, attribute, None)
                if value is not None:
                    listener[attribute] = value
        return SimpleNamespace(RequestId="req-modify")


@pytest.fixture
def client(monkeypatch):
    fake = FakeClbClient()
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(
        clb_listener, "_load_clb",
        lambda: (FakeModels(), SimpleNamespace(ClbClient=object)),
    )
    monkeypatch.setattr(
        TencentCloudModule, "create_client",
        lambda self, client_class, endpoint: fake,
    )
    return fake


def test_create_reports_changed(client):
    module_args(**CREATE_ARGS)
    result = run(clb_listener.run_module)
    assert result["changed"] is True
    assert result["listener"]["ListenerId"] == "lbl-new00001"
    assert result["listener_id"] == "lbl-new00001"
    client.CreateListener.assert_called_once()
    client.DescribeTaskStatus.assert_called_once()
    assert "diff" not in result


def test_second_run_is_idempotent(client):
    client.listeners.append(dict(LISTENER))
    module_args(**CREATE_ARGS)
    result = run(clb_listener.run_module)
    assert result["changed"] is False
    assert result["listener"]["ListenerId"] == "lbl-existing1"
    client.CreateListener.assert_not_called()
    client.ModifyListener.assert_not_called()


def test_absent_deletes_existing_listener(client):
    client.listeners.append(dict(LISTENER))
    module_args(state="absent", load_balancer_id="lb-xxxxxxxx", protocol="TCP", port=8080)
    result = run(clb_listener.run_module)
    assert result["changed"] is True
    client.DeleteListener.assert_called_once()
    client.DescribeTaskStatus.assert_called_once()
    assert client.listeners == []


def test_absent_on_missing_listener_is_unchanged(client):
    module_args(state="absent", load_balancer_id="lb-xxxxxxxx", protocol="TCP", port=8080)
    result = run(clb_listener.run_module)
    assert result["changed"] is False
    client.DeleteListener.assert_not_called()


def test_check_mode_create_makes_no_sdk_writes(client):
    module_args(_ansible_check_mode=True, **CREATE_ARGS)
    result = run(clb_listener.run_module)
    assert result["changed"] is True
    assert "diff" in result
    client.CreateListener.assert_not_called()
    client.DeleteListener.assert_not_called()
    client.ModifyListener.assert_not_called()


def test_check_mode_update_makes_no_sdk_writes(client):
    client.listeners.append(dict(LISTENER))
    module_args(_ansible_check_mode=True, scheduler="LEAST_CONN", **CREATE_ARGS)
    result = run(clb_listener.run_module)
    assert result["changed"] is True
    assert "diff" in result
    client.ModifyListener.assert_not_called()


def test_update_scheduler(client):
    client.listeners.append(dict(LISTENER))
    module_args(scheduler="LEAST_CONN", **CREATE_ARGS)
    result = run(clb_listener.run_module)
    assert result["changed"] is True
    assert client.listeners[0]["Scheduler"] == "LEAST_CONN"
    client.ModifyListener.assert_called_once()
    request = client.ModifyListener.call_args[0][0]
    assert request.Scheduler == "LEAST_CONN"
    assert not hasattr(request, "ListenerName")


def test_health_check_drift_triggers_update(client):
    client.listeners.append(dict(LISTENER))
    module_args(health_check={"interval_time": 10}, **CREATE_ARGS)
    result = run(clb_listener.run_module)
    assert result["changed"] is True
    client.ModifyListener.assert_called_once()
    request = client.ModifyListener.call_args[0][0]
    assert request.HealthCheck.IntervalTime == 10


def test_health_check_matching_is_idempotent(client):
    client.listeners.append(dict(LISTENER))
    module_args(
        health_check={
            "health_switch": True, "interval_time": 5, "health_num": 3,
            "un_health_num": 3, "time_out": 2,
        },
        **CREATE_ARGS
    )
    result = run(clb_listener.run_module)
    assert result["changed"] is False
    client.ModifyListener.assert_not_called()


def test_diff_mode_create_includes_diff(client):
    module_args(_ansible_diff=True, **CREATE_ARGS)
    result = run(clb_listener.run_module)
    assert result["changed"] is True
    assert result["diff"]["before"] is None
    assert result["diff"]["after"]["Port"] == 8080
    client.CreateListener.assert_called_once()
