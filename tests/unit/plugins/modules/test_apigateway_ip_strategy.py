"""Unit tests for the apigateway_ip_strategy write module (run_module flows).

Drives ``run_module()`` end to end against an in-memory fake API GW client that
mutates an IP-strategy store keyed by (service_id, name), so the module's
post-write ``DescribeIPStrategysStatus`` refetch observes the new state
immediately. The API GW responses wrap the object in a C(Result) field
(C(IPStrategiesStatus.StrategySet) for list, C(IPStrategy.StrategyId) for
create), which the module unwraps.

Scenario matrix:

* create when missing (real Create + converged refetch)
* idempotent no-op when the strategy already exists
* absent when missing (no-op)
* delete when present (real Delete + converged refetch)
* check-mode dry run for create (no Create call)
* check-mode dry run for delete (no Delete call)
* missing strategy_type/strategy_data on present fails (required_if)
* SDK failure surfaces via fail_sdk_error
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from types import SimpleNamespace

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import apigateway_ip_strategy as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    FakeModels,
    FakeResource,
    module_args,
    run,
)


def _strategy(sid, service_id, name):
    return FakeResource({"StrategyId": str(sid), "ServiceId": service_id, "StrategyName": name,
                         "StrategyType": "WHITE"})


class FakeApigwClient(object):
    """In-memory API GW client mutating an IP-strategy store keyed by (service, name)."""

    def __init__(self, strategies=None):
        self.strategies = list(strategies or [])
        self._seq = 0
        self.calls = []

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def _name_filter(self, request):
        for flt in getattr(request, "Filters", None) or []:
            if getattr(flt, "Name", None) == "StrategyName":
                return list(getattr(flt, "Values", None) or [])
        return []

    def DescribeIPStrategysStatus(self, request):
        self._record("DescribeIPStrategysStatus", request)
        service_id = getattr(request, "ServiceId", None)
        wanted = self._name_filter(request)
        if wanted:
            matched = [s for s in self.strategies
                       if s.ServiceId == service_id and s.StrategyName in wanted]
        else:
            matched = [s for s in self.strategies if s.ServiceId == service_id]
        summary = SimpleNamespace(StrategySet=[FakeResource(dict(s._data)) for s in matched],
                                  TotalCount=len(matched))
        return SimpleNamespace(Result=summary, RequestId="req-fake")

    def CreateIPStrategy(self, request):
        self._record("CreateIPStrategy", request)
        self._seq += 1
        sid = "strat-%d" % self._seq
        item = _strategy(sid, getattr(request, "ServiceId", ""), getattr(request, "StrategyName", ""))
        self.strategies.append(item)
        return SimpleNamespace(Result=SimpleNamespace(StrategyId=sid), RequestId="req-fake")

    def DeleteIPStrategy(self, request):
        self._record("DeleteIPStrategy", request)
        service_id = getattr(request, "ServiceId", None)
        sid = getattr(request, "StrategyId", None)
        self.strategies = [s for s in self.strategies
                           if not (s.ServiceId == service_id and s.StrategyId == sid)]
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake, models=None):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (models or FakeModels(), SimpleNamespace(ApigatewayClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


STRATEGY_DATA = "10.0.0.0/8\n192.168.1.0/24"


# ---------------------------------------------------------------------------
# create / delete flows
# ---------------------------------------------------------------------------


def test_create_when_missing(monkeypatch):
    fake = FakeApigwClient(strategies=[])
    _make_module(monkeypatch, fake)
    module_args(service_id="service-abc", strategy_name="allow-office",
                strategy_type="WHITE", strategy_data=STRATEGY_DATA, state="present")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["exists"] is True
    assert result["strategy_id"] is not None
    ops = [c for c, unused in fake.calls]
    assert ops[0] == "DescribeIPStrategysStatus"
    assert "CreateIPStrategy" in ops
    assert "DeleteIPStrategy" not in ops
    created = [r for c, r in fake.calls if c == "CreateIPStrategy"][0]
    assert created.ServiceId == "service-abc"
    assert created.StrategyName == "allow-office"


def test_delete_when_present(monkeypatch):
    fake = FakeApigwClient(strategies=[_strategy(1, "service-abc", "allow-office")])
    _make_module(monkeypatch, fake)
    module_args(service_id="service-abc", strategy_name="allow-office", state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["exists"] is False
    assert "DeleteIPStrategy" in [c for c, unused in fake.calls]
    assert "CreateIPStrategy" not in [c for c, unused in fake.calls]
    assert fake.strategies == []


# ---------------------------------------------------------------------------
# idempotent no-op flows
# ---------------------------------------------------------------------------


def test_already_present_is_idempotent(monkeypatch):
    fake = FakeApigwClient(strategies=[_strategy(1, "service-abc", "allow-office")])
    _make_module(monkeypatch, fake)
    module_args(service_id="service-abc", strategy_name="allow-office",
                strategy_type="WHITE", strategy_data=STRATEGY_DATA, state="present")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["strategy_id"] == "1"
    assert [c for c, unused in fake.calls] == ["DescribeIPStrategysStatus"]
    assert "CreateIPStrategy" not in [c for c, unused in fake.calls]


def test_absent_when_missing_is_idempotent(monkeypatch):
    fake = FakeApigwClient(strategies=[])
    _make_module(monkeypatch, fake)
    module_args(service_id="service-abc", strategy_name="allow-office", state="absent")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert "DeleteIPStrategy" not in [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# check-mode dry runs
# ---------------------------------------------------------------------------


def test_create_check_mode_is_dry_run(monkeypatch):
    fake = FakeApigwClient(strategies=[])
    _make_module(monkeypatch, fake)
    module_args(service_id="service-abc", strategy_name="allow-office",
                strategy_type="WHITE", strategy_data=STRATEGY_DATA,
                state="present", _ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert "CreateIPStrategy" not in [c for c, unused in fake.calls]
    assert fake.strategies == []


def test_delete_check_mode_is_dry_run(monkeypatch):
    fake = FakeApigwClient(strategies=[_strategy(1, "service-abc", "allow-office")])
    _make_module(monkeypatch, fake)
    module_args(service_id="service-abc", strategy_name="allow-office", state="absent", _ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert "DeleteIPStrategy" not in [c for c, unused in fake.calls]
    assert len(fake.strategies) == 1


# ---------------------------------------------------------------------------
# error / validation paths
# ---------------------------------------------------------------------------


def test_missing_strategy_type_on_present_fails(monkeypatch):
    fake = FakeApigwClient(strategies=[])
    _make_module(monkeypatch, fake)
    module_args(service_id="service-abc", strategy_name="allow-office", strategy_data=STRATEGY_DATA, state="present")
    try:
        run(mod.run_module)
    except SystemExit as exc:
        payload = getattr(exc, "args", [{}])[0]
        assert payload.get("failed")
    else:
        raise AssertionError("expected required_if strategy_type/strategy_data to fail the module")


def test_sdk_failure_fails(monkeypatch):
    fake = FakeApigwClient(strategies=[])

    def _raise_error(request):
        raise RuntimeError("boom")
    fake.CreateIPStrategy = _raise_error
    _make_module(monkeypatch, fake)
    module_args(service_id="service-abc", strategy_name="allow-office",
                strategy_type="WHITE", strategy_data=STRATEGY_DATA, state="present")
    try:
        run(mod.run_module)
    except SystemExit as exc:
        payload = getattr(exc, "args", [{}])[0]
        assert payload.get("failed")
    else:
        raise AssertionError("expected SDK failure to fail the module")
