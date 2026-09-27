"""Tests for the monitor_prometheus_alertmanager_config pair.

The write module's configuration waiters keep their own tests below. The info
module is driven end to end through the shared harness, which is where its
``run_module()`` -- argument handling, request building, the serialised
Alertmanager configuration and the SDK failure envelope -- is executed.

``monitor_prometheus_alertmanager_config_info`` imports
``tencentcloud.monitor.v20180724`` itself, so the tests keep the ``sys.modules``
injection of the fake service and patch the base class's ``require_sdk`` and
``create_client`` instead of building a private ``AnsibleModule`` double.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import sys
import types

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import monitor_prometheus_alertmanager_config as write
from ansible_collections.susunola.tencentcloud.plugins.modules import monitor_prometheus_alertmanager_config_info as info
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    module_args,
    run,
)


class Request:
    pass


class Item:
    def __init__(self, config):
        self.config = config

    def _serialize(self, allow_none=True):
        return self.config


MODELS = types.SimpleNamespace(DescribePrometheusAlertmanagerConfigRequest=Request)

#: Alertmanager configuration in the shape the SDK model serialises it.
CONFIG = {
    "InhibitRules": [{"Equal": ["cluster"], "SourceMatch": [{"Name": "alertname", "Value": "DiskFull"}]}],
    "Receivers": [{"Name": "ops-webhook"}],
}


class Module:
    params = {"waiter_timeout": 10, "waiter_delay": 0}

    def sdk_call(self, operation, request):
        return operation(request)

    def fail_json(self, **kwargs):
        raise ValueError(kwargs["msg"])


def test_info_request_targets_instance():
    assert info.build_request(MODELS, "prom-1").InstanceId == "prom-1"


def test_write_waits_for_observed_config(monkeypatch):
    configs = iter([{"InhibitRules": []}, {"InhibitRules": [{"Equal": ["cluster"]}]}])

    class Client:
        def DescribePrometheusAlertmanagerConfig(self, request):
            assert request.InstanceId == "prom-1"
            return types.SimpleNamespace(AlertmanagerConfig=Item(next(configs)))

    monkeypatch.setattr(write.time, "sleep", lambda delay: None)
    target = {"InhibitRules": [{"Equal": ["cluster"]}]}
    assert write.wait_for_config(Module(), Client(), MODELS, "prom-1", target) == target


def test_write_timeout_reports_unsatisfied_config(monkeypatch):
    class Client:
        def DescribePrometheusAlertmanagerConfig(self, request):
            return types.SimpleNamespace(AlertmanagerConfig=Item({"InhibitRules": []}))

    ticks = iter([0, 11])
    monkeypatch.setattr(write.time, "monotonic", lambda: next(ticks))
    with pytest.raises(ValueError, match="Timed out waiting"):
        write.wait_for_config(Module(), Client(), MODELS, "prom-1", {"InhibitRules": [1]})


class MonitorClient:
    """Stand-in for ``monitor_client.MonitorClient`` (never constructed)."""


class FakeMonitorClient:
    """Monitor client answering with one Alertmanager configuration, or none."""

    def __init__(self, config=None, request_id="req-alertmanager"):
        self.config = config
        self.request_id = request_id
        self.requests = []

    def DescribePrometheusAlertmanagerConfig(self, request):
        self.requests.append(request)
        return types.SimpleNamespace(AlertmanagerConfig=self.config, RequestId=self.request_id)


def _patch_sdk(monkeypatch, client):
    """Install the fake Monitor service; return what ``create_client`` was asked for."""
    service = types.ModuleType("tencentcloud.monitor.v20180724")
    service.models = MODELS
    service.monitor_client = types.SimpleNamespace(MonitorClient=MonitorClient)
    monkeypatch.setitem(sys.modules, "tencentcloud", types.ModuleType("tencentcloud"))
    monkeypatch.setitem(sys.modules, "tencentcloud.monitor",
                        types.ModuleType("tencentcloud.monitor"))
    monkeypatch.setitem(sys.modules, "tencentcloud.monitor.v20180724", service)
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    created = []

    def create_client(self, client_class, endpoint):
        created.append((client_class, endpoint))
        return client

    monkeypatch.setattr(TencentCloudModule, "create_client", create_client)
    return created


def test_run_module_returns_the_serialised_config(monkeypatch):
    client = FakeMonitorClient(Item(CONFIG))
    created = _patch_sdk(monkeypatch, client)
    module_args(instance_id="prom-abc123")

    payload = run(info.run_module)

    audit = payload.pop("tc_api_calls")
    assert payload == {
        "changed": False,
        "config": CONFIG,
        "request_id": "req-alertmanager",
    }
    assert client.requests[0].InstanceId == "prom-abc123"
    assert created == [(MonitorClient, "monitor.tencentcloudapi.com")]
    assert audit[0]["operation"] == "DescribePrometheusAlertmanagerConfig"
    assert audit[0]["status"] == "ok"
    assert audit[0]["error"] is None
    assert audit[0]["request_id"] == "req-alertmanager"
    assert isinstance(audit[0]["duration_ms"], int)


def test_run_module_returns_an_empty_config_when_none_is_set(monkeypatch):
    client = FakeMonitorClient(None)
    _patch_sdk(monkeypatch, client)
    module_args(instance_id="prom-abc123")

    payload = run(info.run_module)

    payload.pop("tc_api_calls")
    assert payload == {
        "changed": False,
        "config": {},
        "request_id": "req-alertmanager",
    }


class _SdkError(Exception):
    """Stand-in for ``TencentCloudSDKException`` carrying a code/request id."""

    def __init__(self, code, message="", request_id=None):
        super(_SdkError, self).__init__(message)
        self._code = code
        self._request_id = request_id

    def get_code(self):
        return self._code

    def get_request_id(self):
        return self._request_id


def test_run_module_fails_with_the_sdk_error_envelope(monkeypatch):
    class FailingClient:
        def DescribePrometheusAlertmanagerConfig(self, request):
            raise _SdkError("UnauthorizedOperation", "api exploded", "req-err")

    _patch_sdk(monkeypatch, FailingClient())
    module_args(instance_id="prom-abc123")

    with pytest.raises(AnsibleFailJson) as failure:
        run(info.run_module)

    payload = failure.value.args[0]
    audit = payload.pop("tc_api_calls")
    assert payload == {
        "msg": "Tencent Cloud API request failed",
        "error": "api exploded",
        "error_code": "UnauthorizedOperation",
        "error_kind": "unauthorized",
        "request_id": "req-err",
        "operation": None,
        "failed": True,
    }
    assert [(call["operation"], call["status"], call["error"]) for call in audit] == [
        ("DescribePrometheusAlertmanagerConfig", "error", "api exploded")]
