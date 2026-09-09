"""Unit tests for the tdmysql_ssl write module (run_module flows).

The module reconciles instance SSL enablement and (optionally) waits for the
asynchronous Flow that carries the SSL change. The fake TDSQL client mutates
its SSL status when ``ModifyInstanceSSLStatus`` is called and reports a flow
status the module can converge on or fail on.

Scenario matrix:

* an instance already in the desired SSL state is idempotent
* enabling / disabling drives ``ModifyInstanceSSLStatus`` and waits for the
  flow to succeed
* ``wait=false`` skips the flow waiter
* check mode reports the change without writing
* a failed async flow fails the module
* the blanket SDK failure path
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import tdmysql_ssl as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    module_args,
    run,
)

INSTANCE_ID = "tdsql3-abcdef12"


def _args(**overrides):
    params = {"instance_id": INSTANCE_ID, "enabled": True, "wait": True}
    params.update(overrides)
    return module_args(**params)


class FakeTdmysqlClient(object):
    """In-memory TDSQL client with a mutable SSL status and async flow."""

    def __init__(self, ssl_status, flow_status="success"):
        self.ssl_status = ssl_status
        self.flow_status = flow_status
        self.calls = []

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def DescribeInstanceSSLStatus(self, request):
        self._record("DescribeInstanceSSLStatus", request)
        return SimpleNamespace(SSLStatus=self.ssl_status)

    def DescribeFlow(self, request):
        self._record("DescribeFlow", request)
        return SimpleNamespace(Status=self.flow_status)

    def ModifyInstanceSSLStatus(self, request):
        self._record("ModifyInstanceSSLStatus", request)
        self.ssl_status = "enabled" if request.Enabled else "disabled"
        return SimpleNamespace(FlowId=456)


def _make_module(monkeypatch, fake):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (FakeModels(), SimpleNamespace(TdmysqlClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


def test_already_enabled_is_idempotent(monkeypatch):
    fake = FakeTdmysqlClient("enabled")
    _make_module(monkeypatch, fake)
    _args(enabled=True)
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["ssl"] == {"InstanceId": INSTANCE_ID, "SSLStatus": "enabled"}
    assert [c for c, unused in fake.calls] == ["DescribeInstanceSSLStatus"]


def test_already_disabled_is_idempotent(monkeypatch):
    fake = FakeTdmysqlClient("disabled")
    _make_module(monkeypatch, fake)
    _args(enabled=False)
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["ssl"]["SSLStatus"] == "disabled"


def test_enable_waits_for_flow_and_converges(monkeypatch):
    fake = FakeTdmysqlClient("disabled")
    _make_module(monkeypatch, fake)
    _args(enabled=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["ssl"]["SSLStatus"] == "enabled"
    ops = [c for c, unused in fake.calls]
    assert ops[0] == "DescribeInstanceSSLStatus"
    assert "ModifyInstanceSSLStatus" in ops
    assert "DescribeFlow" in ops


def test_disable_transitions_instance(monkeypatch):
    fake = FakeTdmysqlClient("enabled")
    _make_module(monkeypatch, fake)
    _args(enabled=False)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["ssl"]["SSLStatus"] == "disabled"
    ops = [c for c, unused in fake.calls]
    assert "ModifyInstanceSSLStatus" in ops


def test_wait_false_skips_flow_waiter(monkeypatch):
    fake = FakeTdmysqlClient("disabled")
    _make_module(monkeypatch, fake)
    _args(enabled=True, wait=False)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["ssl"]["SSLStatus"] == "enabled"
    assert "DescribeFlow" not in [c for c, unused in fake.calls]


def test_check_mode_reports_change_without_writing(monkeypatch):
    fake = FakeTdmysqlClient("disabled")
    _make_module(monkeypatch, fake)
    _args(_ansible_check_mode=True, enabled=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    # Check mode returns the target shape (capitalised SSLStatus).
    assert result["ssl"] == {"InstanceId": INSTANCE_ID, "SSLStatus": "Enabled"}
    assert "ModifyInstanceSSLStatus" not in [c for c, unused in fake.calls]


def test_failed_flow_fails_module(monkeypatch):
    fake = FakeTdmysqlClient("disabled", flow_status="failed")
    _make_module(monkeypatch, fake)
    _args(enabled=True)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "TDSQL MySQL SSL operation failed"
    assert payload["flow_id"] == 456
    assert payload["status"] == "failed"


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeInstanceSSLStatus(self, request):
            raise Boom("connection dropped")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    _args(enabled=True)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]
