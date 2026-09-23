"""Unit tests for the monitor_grafana_whitelist write module.

Drives ``run_module()`` against an in-memory fake Monitor client whose
``UpdateGrafanaWhiteList`` operation rewrites the complete IP whitelist
stored for a Grafana instance.

Scenario matrix:

* empty whitelist + ``addresses: []`` (idempotent no-op)
* matching addresses given out of order (idempotent no-op after sorting)
* adding an address triggers an Update
* clearing every address triggers an Update
* drift in check mode (dry run, no Update call)
* the blanket SDK failure path
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import monitor_grafana_whitelist as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    module_args,
    run,
)

WHITELIST = ["203.0.113.10/32", "203.0.113.20/32"]


def _args(**overrides):
    params = {"instance_id": "grafana-abc123", "addresses": WHITELIST}
    params.update(overrides)
    return module_args(**params)


class FakeMonitorClient(object):
    """In-memory Monitor client owning a Grafana instance IP whitelist."""

    def __init__(self, whitelist=None):
        self.whitelist = list(copy.deepcopy(whitelist or []))
        self.calls = []

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def DescribeGrafanaWhiteList(self, request):
        self._record("DescribeGrafanaWhiteList", request)
        return SimpleNamespace(WhiteList=list(self.whitelist))

    def UpdateGrafanaWhiteList(self, request):
        self._record("UpdateGrafanaWhiteList", request)
        self.whitelist = list(getattr(request, "Whitelist", None) or [])
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (FakeModels(), SimpleNamespace(MonitorClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


# ---------------------------------------------------------------------------
# idempotent flows
# ---------------------------------------------------------------------------


def test_empty_whitelist_is_idempotent(monkeypatch):
    fake = FakeMonitorClient(whitelist=[])
    _make_module(monkeypatch, fake)
    _args(addresses=[])
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["whitelist"] == []
    assert [c for c, unused in fake.calls] == ["DescribeGrafanaWhiteList"]


def test_matching_addresses_out_of_order_is_idempotent(monkeypatch):
    fake = FakeMonitorClient(whitelist=WHITELIST)
    _make_module(monkeypatch, fake)
    _args(addresses=[WHITELIST[1], WHITELIST[0]])
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["whitelist"] == sorted(WHITELIST)


# ---------------------------------------------------------------------------
# drift flows
# ---------------------------------------------------------------------------


def test_addressing_drift_adds_entry(monkeypatch):
    fake = FakeMonitorClient(whitelist=WHITELIST)
    _make_module(monkeypatch, fake)
    _args(addresses=WHITELIST + ["198.51.100.5/32"])
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["whitelist"] == sorted(WHITELIST + ["198.51.100.5/32"])
    assert sorted(fake.whitelist) == sorted(WHITELIST + ["198.51.100.5/32"])
    ops = [c for c, unused in fake.calls]
    assert ops[0] == "DescribeGrafanaWhiteList"
    assert "UpdateGrafanaWhiteList" in ops


def test_clearing_every_address_updates(monkeypatch):
    fake = FakeMonitorClient(whitelist=WHITELIST)
    _make_module(monkeypatch, fake)
    _args(addresses=[])
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["whitelist"] == []
    assert fake.whitelist == []
    ops = [c for c, unused in fake.calls]
    assert "UpdateGrafanaWhiteList" in ops


def test_drift_check_mode_is_dry_run(monkeypatch):
    fake = FakeMonitorClient(whitelist=WHITELIST)
    _make_module(monkeypatch, fake)
    _args(_ansible_check_mode=True, addresses=WHITELIST + ["198.51.100.5/32"])
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["whitelist"] == sorted(WHITELIST + ["198.51.100.5/32"])
    assert fake.whitelist == WHITELIST
    assert "UpdateGrafanaWhiteList" not in [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# failure paths
# ---------------------------------------------------------------------------


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeGrafanaWhiteList(self, request):
            raise Boom("connection dropped")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    _args()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]
