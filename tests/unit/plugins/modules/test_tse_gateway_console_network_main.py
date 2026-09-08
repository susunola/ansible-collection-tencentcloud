"""Unit tests for the tse_gateway_console_network write module (run_module flows).

Drives ``run_module()`` end to end against an in-memory fake TSE client
whose ``ModifyConsoleNetwork`` mutates the console-config store, so the
module's post-write ``wait()`` reconverges on the first poll.

Scenario matrix:

* access_control/closed-state validation
* opening when the Konga console is absent or closed (with and without
  access_control), and check-mode dry run
* no-drift idempotency and closing an open console
* failed-terminal-state and timeout wait guards
* multiple-Konga-configurations guard and the blanket
  ``sdk_error_payload`` failure path
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import tse_gateway_console_network as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

ACCESS_CONTROL = {"Mode": "Whitelist", "CidrWhiteList": ["203.0.113.0/24"]}


def _console(**overrides):
    item = {
        "ConsoleType": "Konga",
        "NetType": "Open",
        "Status": "Open",
        "AdminPassword": "secret-token",
    }
    item.update(overrides)
    return item


def _plain(value):
    """Recursively unwrap FakeRequest/model stand-ins into plain data."""
    if value is None or isinstance(value, bool) or isinstance(value, (str, int, float)):
        return value
    if isinstance(value, list):
        return [_plain(item) for item in value]
    if isinstance(value, dict):
        return {key: _plain(item) for key, item in value.items()}
    return {key: _plain(item) for key, item in vars(value).items()}


class FakeGatewayConsoleClient(object):
    """In-memory TSE gateway console-network client."""

    def __init__(self, consoles=None, modify_status=None):
        self.consoles = [copy.deepcopy(item) for item in (consoles or [])]
        self.calls = []
        # None means "apply the requested Operate"; a string overrides the
        # resulting Status (used to force failure/terminal states).
        self.modify_status = modify_status

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def DescribeCloudNativeAPIGatewayConfig(self, request):
        self._record("DescribeCloudNativeAPIGatewayConfig", request)
        result = {"ConfigList": [FakeResource(item) for item in self.consoles]}
        return SimpleNamespace(Result=FakeResource(result), RequestId="req-fake")

    def ModifyConsoleNetwork(self, request):
        self._record("ModifyConsoleNetwork", request)
        desired = "Open" if request.Operate == "Open" else "Closed"
        if self.modify_status is not None:
            desired = self.modify_status
        # Update the single Konga console, creating it when absent.
        for item in self.consoles:
            if str(item.get("ConsoleType") or "").lower() == "konga":
                item["NetType"] = request.NetworkType
                item["Status"] = desired
                if getattr(request, "AccessControl", None) is not None:
                    item["AccessControl"] = _plain(request.AccessControl)
                return SimpleNamespace(RequestId="req-fake")
        console = {"ConsoleType": "Konga", "NetType": request.NetworkType, "Status": desired}
        if getattr(request, "AccessControl", None) is not None:
            console["AccessControl"] = _plain(request.AccessControl)
        self.consoles.append(console)
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake, models=None):
    """Wire the shared monkeypatches; returns the fake client."""
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (models or FakeModels(), SimpleNamespace(TseClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


def _args(**overrides):
    params = {"gateway_id": "gateway-1"}
    params.update(overrides)
    return module_args(**params)


def _ops(fake):
    return [name for name, unused in fake.calls]


# ---------------------------------------------------------------------------
# validation
# ---------------------------------------------------------------------------


def test_access_control_invalid_when_closed(monkeypatch):
    fake = FakeGatewayConsoleClient(consoles=[])
    _make_module(monkeypatch, fake)
    _args(state="closed", access_control=copy.deepcopy(ACCESS_CONTROL))
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "access_control is only valid when state=open" in exc.value.args[0]["msg"]


# ---------------------------------------------------------------------------
# opening flows
# ---------------------------------------------------------------------------


def test_open_when_console_absent(monkeypatch):
    fake = FakeGatewayConsoleClient(consoles=[])
    _make_module(monkeypatch, fake)
    _args()
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["console_network"]["Status"] == "Open"
    assert result["console_network"]["NetType"] == "Open"
    assert "AdminPassword" not in result["console_network"]
    assert len(fake.consoles) == 1
    assert fake.consoles[0]["Status"] == "Open"
    assert "ModifyConsoleNetwork" in _ops(fake)


def test_open_closed_console_with_access_control(monkeypatch):
    fake = FakeGatewayConsoleClient(consoles=[_console(Status="Closed")])
    _make_module(monkeypatch, fake)
    _args(access_control=copy.deepcopy(ACCESS_CONTROL))
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["console_network"]["Status"] == "Open"
    assert result["console_network"]["AccessControl"] == ACCESS_CONTROL
    assert fake.consoles[0]["Status"] == "Open"
    assert fake.consoles[0]["AccessControl"] == ACCESS_CONTROL
    assert "ModifyConsoleNetwork" in _ops(fake)


def test_open_check_mode_is_dry_run(monkeypatch):
    fake = FakeGatewayConsoleClient(consoles=[_console(Status="Closed")])
    _make_module(monkeypatch, fake)
    _args(_ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["console_network"]["Status"] == "Open"
    assert fake.consoles[0]["Status"] == "Closed"
    assert "ModifyConsoleNetwork" not in _ops(fake)


def test_existing_open_console_no_drift_is_idempotent(monkeypatch):
    fake = FakeGatewayConsoleClient(consoles=[_console(Status="Open")])
    _make_module(monkeypatch, fake)
    _args()
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["console_network"]["Status"] == "Open"
    assert result["console_network"]["ConsoleType"] == "Konga"
    assert "AdminPassword" not in result["console_network"]
    assert "ModifyConsoleNetwork" not in _ops(fake)


def test_open_with_access_control_no_drift_is_idempotent(monkeypatch):
    fake = FakeGatewayConsoleClient(
        consoles=[_console(Status="Open", AccessControl=copy.deepcopy(ACCESS_CONTROL))]
    )
    _make_module(monkeypatch, fake)
    _args(access_control=copy.deepcopy(ACCESS_CONTROL))
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["console_network"]["AccessControl"] == ACCESS_CONTROL
    assert "ModifyConsoleNetwork" not in _ops(fake)


# ---------------------------------------------------------------------------
# closing flows
# ---------------------------------------------------------------------------


def test_close_open_console(monkeypatch):
    fake = FakeGatewayConsoleClient(consoles=[_console(Status="Open")])
    _make_module(monkeypatch, fake)
    _args(state="closed")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["console_network"]["Status"] == "Closed"
    assert fake.consoles[0]["Status"] == "Closed"
    assert "ModifyConsoleNetwork" in _ops(fake)


def test_close_check_mode_is_dry_run(monkeypatch):
    fake = FakeGatewayConsoleClient(consoles=[_console(Status="Open")])
    _make_module(monkeypatch, fake)
    _args(_ansible_check_mode=True, state="closed")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["console_network"]["Status"] == "Closed"
    assert fake.consoles[0]["Status"] == "Open"
    assert "ModifyConsoleNetwork" not in _ops(fake)


# ---------------------------------------------------------------------------
# wait guards
# ---------------------------------------------------------------------------


def test_wait_fails_on_terminal_error_status(monkeypatch):
    fake = FakeGatewayConsoleClient(consoles=[_console(Status="Closed")], modify_status="Error")
    _make_module(monkeypatch, fake)
    _args()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "TSE gateway console network operation failed" in payload["msg"]
    assert payload["console_network"]["Status"] == "Error"


def test_wait_timeout_when_status_never_converges(monkeypatch):
    fake = FakeGatewayConsoleClient(consoles=[_console(Status="Closed")], modify_status="Pending")
    _make_module(monkeypatch, fake)
    _args(waiter_timeout=0)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "Timed out waiting for TSE gateway console network convergence" in payload["msg"]
    assert payload["expected"] == {"NetType": "Open", "Status": "Open"}


# ---------------------------------------------------------------------------
# guards / failure paths
# ---------------------------------------------------------------------------


def test_multiple_konga_configs_fail(monkeypatch):
    fake = FakeGatewayConsoleClient(consoles=[_console(), _console(Status="Closed")])
    _make_module(monkeypatch, fake)
    _args()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "Multiple TSE Konga console network configurations were returned" in exc.value.args[0]["msg"]


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeCloudNativeAPIGatewayConfig(self, request):
            raise Boom("engine down")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    _args()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "engine down" in payload["error"]
