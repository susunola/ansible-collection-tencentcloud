"""Tests for the monitor_grafana_whitelist pair.

The write module's whitelist waiters keep their own tests below. The info
module is driven end to end through the shared harness, which is where its
``run_module()`` -- argument handling, request building, the sorted whitelist
payload and the SDK failure envelope -- is executed.

``monitor_grafana_whitelist_info`` imports ``tencentcloud.monitor.v20180724``
itself, so the tests keep the ``sys.modules`` injection of the fake service and
patch the base class's ``require_sdk`` and ``create_client`` instead of
building a private ``AnsibleModule`` double.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import sys
import types

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import monitor_grafana_whitelist as write
from ansible_collections.susunola.tencentcloud.plugins.modules import monitor_grafana_whitelist_info as info
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    module_args,
    run,
)


class Request:
    pass


MODELS = types.SimpleNamespace(DescribeGrafanaWhiteListRequest=Request)


class Module:
    params = {"instance_id": "grafana-1", "waiter_timeout": 10, "waiter_delay": 0}

    def sdk_call(self, operation, request):
        return operation(request)

    def fail_json(self, **kwargs):
        raise ValueError(kwargs["msg"])


def test_info_request_addresses_exact_instance():
    request = info.build_request(MODELS, "grafana-1")
    assert request.InstanceId == "grafana-1"


def test_write_waits_for_observed_whitelist(monkeypatch):
    responses = iter([["192.0.2.1"], ["203.0.113.1"]])

    class Client:
        def DescribeGrafanaWhiteList(self, request):
            assert request.InstanceId == "grafana-1"
            return types.SimpleNamespace(WhiteList=next(responses))

    monkeypatch.setattr(write.time, "sleep", lambda seconds: None)
    assert write.wait_for_whitelist(Module(), Client(), MODELS,
                                    "grafana-1", ["203.0.113.1"]) == ["203.0.113.1"]


def test_write_fails_when_whitelist_does_not_converge(monkeypatch):
    class Client:
        def DescribeGrafanaWhiteList(self, request):
            return types.SimpleNamespace(WhiteList=["192.0.2.1"])

    ticks = iter([0, 11])
    monkeypatch.setattr(write.time, "monotonic", lambda: next(ticks))
    with pytest.raises(ValueError, match="Timed out waiting"):
        write.wait_for_whitelist(Module(), Client(), MODELS,
                                 "grafana-1", ["203.0.113.1"])


class MonitorClient:
    """Stand-in for ``monitor_client.MonitorClient`` (never constructed)."""


class FakeMonitorClient:
    """Monitor client answering ``DescribeGrafanaWhiteList`` with one document."""

    def __init__(self, whitelist=None, request_id="req-whitelist"):
        self.whitelist = whitelist
        self.request_id = request_id
        self.requests = []

    def DescribeGrafanaWhiteList(self, request):
        self.requests.append(request)
        return types.SimpleNamespace(WhiteList=self.whitelist, RequestId=self.request_id)


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


def test_run_module_returns_the_sorted_whitelist(monkeypatch):
    client = FakeMonitorClient(whitelist=["203.0.113.10/32", "192.0.2.7/32"])
    created = _patch_sdk(monkeypatch, client)
    module_args(instance_id="grafana-abc123")

    payload = run(info.run_module)

    audit = payload.pop("tc_api_calls")
    assert payload == {
        "changed": False,
        "whitelist": ["192.0.2.7/32", "203.0.113.10/32"],
        "request_id": "req-whitelist",
    }
    assert client.requests[0].InstanceId == "grafana-abc123"
    assert created == [(MonitorClient, "monitor.tencentcloudapi.com")]
    assert audit[0]["operation"] == "DescribeGrafanaWhiteList"
    assert audit[0]["status"] == "ok"
    assert audit[0]["error"] is None
    assert audit[0]["request_id"] == "req-whitelist"
    assert isinstance(audit[0]["duration_ms"], int)


def test_run_module_returns_an_empty_whitelist(monkeypatch):
    client = FakeMonitorClient(whitelist=None)
    _patch_sdk(monkeypatch, client)
    module_args(instance_id="grafana-abc123")

    payload = run(info.run_module)

    payload.pop("tc_api_calls")
    assert payload == {
        "changed": False,
        "whitelist": [],
        "request_id": "req-whitelist",
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
        def DescribeGrafanaWhiteList(self, request):
            raise _SdkError("UnauthorizedOperation", "api exploded", "req-err")

    _patch_sdk(monkeypatch, FailingClient())
    module_args(instance_id="grafana-abc123")

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
        ("DescribeGrafanaWhiteList", "error", "api exploded")]
