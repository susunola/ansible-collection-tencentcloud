"""Unit tests for the tse_gateway_autoscaler_strategy write module.

Drives ``run_module()`` against an in-memory fake TSE client whose create /
modify / delete operations mutate an autoscaler-strategy store so post-write
describes converge immediately.

Scenario matrix:

* absent on a missing strategy, by ``strategy_id`` or by name (idempotent)
* absent with a live strategy (check-mode dry run, real delete)
* creation when missing by name (happy path, check mode)
* the ``name``-required-for-create guard
* existing strategy without drift (idempotent no-op using partial args)
* drift (``max_replicas``) triggers a modify (real update, check mode)
* the ambiguous-match guard and the blanket SDK failure path
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import tse_gateway_autoscaler_strategy as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

STRATEGY = {
    "GatewayId": "gateway-1001",
    "StrategyId": "strategy-1001",
    "StrategyName": "production-elasticity",
    "Description": "peak-time elasticity",
    "Config": {
        "Enabled": True,
        "MaxReplicas": 10,
        "Metrics": [{"Type": "Resource", "ResourceName": "cpu", "TargetType": "Utilization", "TargetValue": 60}],
    },
    "CronConfig": {"Enabled": False, "Params": []},
    "MaxReplicas": 10,
}


def _strategy(**overrides):
    item = copy.deepcopy(STRATEGY)
    item.update(overrides)
    return item


def _name_args(**overrides):
    params = {
        "gateway_id": "gateway-1001",
        "name": "production-elasticity",
        "description": "peak-time elasticity",
        "metric_config": copy.deepcopy(STRATEGY["Config"]),
        "cron_config": copy.deepcopy(STRATEGY["CronConfig"]),
        "max_replicas": 10,
    }
    params.update(overrides)
    return module_args(**params)


class FakeTseClient(object):
    """In-memory TSE client mutating an autoscaler-strategy store."""

    def __init__(self, strategies=None):
        self.strategies = [copy.deepcopy(t) for t in (strategies or [])]
        self.calls = []
        self._next = 0

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def DescribeAutoScalerResourceStrategies(self, request):
        self._record("DescribeAutoScalerResourceStrategies", request)
        gateway_id = getattr(request, "GatewayId", None)
        values = [FakeResource(t) for t in self.strategies if t.get("GatewayId") == gateway_id]
        return SimpleNamespace(Result=SimpleNamespace(StrategyList=values))

    def CreateAutoScalerResourceStrategy(self, request):
        self._record("CreateAutoScalerResourceStrategy", request)
        self._next += 1
        strategy_id = "strategy-%d" % (2000 + self._next)
        self.strategies.append({
            "GatewayId": getattr(request, "GatewayId", None),
            "StrategyId": strategy_id,
            "StrategyName": getattr(request, "StrategyName", None),
            "Description": getattr(request, "Description", None),
            "Config": getattr(request, "Config", None),
            "CronConfig": getattr(request, "CronConfig", None),
            "MaxReplicas": getattr(request, "MaxReplicas", None),
        })
        return SimpleNamespace(StrategyId=strategy_id, RequestId="req-fake")

    def ModifyAutoScalerResourceStrategy(self, request):
        self._record("ModifyAutoScalerResourceStrategy", request)
        for item in self.strategies:
            if item.get("StrategyId") == getattr(request, "StrategyId", None):
                item["StrategyName"] = getattr(request, "StrategyName", item.get("StrategyName"))
                item["Description"] = getattr(request, "Description", item.get("Description"))
                item["Config"] = getattr(request, "Config", item.get("Config"))
                item["CronConfig"] = getattr(request, "CronConfig", item.get("CronConfig"))
                item["MaxReplicas"] = getattr(request, "MaxReplicas", item.get("MaxReplicas"))
        return SimpleNamespace(RequestId="req-fake")

    def DeleteAutoScalerResourceStrategy(self, request):
        self._record("DeleteAutoScalerResourceStrategy", request)
        self.strategies = [
            t for t in self.strategies
            if not (t.get("GatewayId") == getattr(request, "GatewayId", None)
                    and t.get("StrategyId") == getattr(request, "StrategyId", None))
        ]
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake, models=None):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (models or FakeModels(), SimpleNamespace(TseClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


def _names(fake):
    return [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# absent flows
# ---------------------------------------------------------------------------


def test_absent_missing_by_strategy_id_is_idempotent(monkeypatch):
    fake = FakeTseClient(strategies=[])
    _make_module(monkeypatch, fake)
    module_args(state="absent", gateway_id="gateway-1001", strategy_id="strategy-ghost")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["strategy"] is None
    assert _names(fake) == ["DescribeAutoScalerResourceStrategies"]


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeTseClient(strategies=[_strategy()])
    _make_module(monkeypatch, fake)
    module_args(_ansible_check_mode=True, state="absent", gateway_id="gateway-1001", strategy_id="strategy-1001")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert len(fake.strategies) == 1
    assert "DeleteAutoScalerResourceStrategy" not in _names(fake)


def test_absent_deletes_strategy(monkeypatch):
    fake = FakeTseClient(strategies=[_strategy()])
    _make_module(monkeypatch, fake)
    module_args(state="absent", gateway_id="gateway-1001", strategy_id="strategy-1001")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["strategy"] is None
    assert fake.strategies == []
    assert "DeleteAutoScalerResourceStrategy" in _names(fake)


def test_absent_missing_by_name_is_idempotent(monkeypatch):
    fake = FakeTseClient(strategies=[])
    _make_module(monkeypatch, fake)
    module_args(state="absent", gateway_id="gateway-1001", name="ghost-strategy")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["strategy"] is None


# ---------------------------------------------------------------------------
# creation flows
# ---------------------------------------------------------------------------


def test_present_without_name_when_missing_fails(monkeypatch):
    fake = FakeTseClient(strategies=[])
    _make_module(monkeypatch, fake)
    module_args(state="present", gateway_id="gateway-1001", strategy_id="strategy-ghost")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "name is required for a new TSE autoscaler strategy" in exc.value.args[0]["msg"]


def test_create_strategy(monkeypatch):
    fake = FakeTseClient(strategies=[])
    _make_module(monkeypatch, fake)
    _name_args(state="present")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["strategy"]["StrategyName"] == "production-elasticity"
    assert result["strategy"]["StrategyId"]
    assert result["strategy"]["MaxReplicas"] == 10
    assert len(fake.strategies) == 1
    ops = _names(fake)
    assert ops[0] == "DescribeAutoScalerResourceStrategies"
    assert "CreateAutoScalerResourceStrategy" in ops


def test_create_check_mode_is_dry_run(monkeypatch):
    fake = FakeTseClient(strategies=[])
    _make_module(monkeypatch, fake)
    _name_args(_ansible_check_mode=True, state="present")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["strategy"]["StrategyName"] == "production-elasticity"
    assert fake.strategies == []
    assert "CreateAutoScalerResourceStrategy" not in _names(fake)


def test_ambiguous_name_match_fails(monkeypatch):
    fake = FakeTseClient(strategies=[_strategy(), _strategy(StrategyId="strategy-1002")])
    _make_module(monkeypatch, fake)
    module_args(state="present", gateway_id="gateway-1001", name="production-elasticity")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "Multiple TSE autoscaler strategies matched" in exc.value.args[0]["msg"]


# ---------------------------------------------------------------------------
# existing-strategy flows
# ---------------------------------------------------------------------------


def test_existing_strategy_partial_args_is_idempotent(monkeypatch):
    fake = FakeTseClient(strategies=[_strategy()])
    _make_module(monkeypatch, fake)
    # Only the name given; every other field falls back to the current state.
    module_args(state="present", gateway_id="gateway-1001", name="production-elasticity")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["strategy"]["StrategyId"] == "strategy-1001"
    assert "ModifyAutoScalerResourceStrategy" not in _names(fake)


def test_max_replicas_drift_modifies_strategy(monkeypatch):
    fake = FakeTseClient(strategies=[_strategy()])
    _make_module(monkeypatch, fake)
    _name_args(state="present", max_replicas=25)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["strategy"]["MaxReplicas"] == 25
    assert fake.strategies[0]["MaxReplicas"] == 25
    assert "ModifyAutoScalerResourceStrategy" in _names(fake)


def test_modify_check_mode_is_dry_run(monkeypatch):
    fake = FakeTseClient(strategies=[_strategy()])
    _make_module(monkeypatch, fake)
    _name_args(_ansible_check_mode=True, state="present", max_replicas=25)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert fake.strategies[0]["MaxReplicas"] == 10
    assert "ModifyAutoScalerResourceStrategy" not in _names(fake)


# ---------------------------------------------------------------------------
# failure paths
# ---------------------------------------------------------------------------


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeAutoScalerResourceStrategies(self, request):
            raise Boom("connection dropped")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    _name_args(state="present")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]


# ---------------------------------------------------------------------------
# legacy helper regression tests (folded from test_tse_gateway_autoscaler.py)
# ---------------------------------------------------------------------------


def test_strategy_target_preserves_unspecified_config():
    p = {
        "gateway_id": "g1",
        "name": None,
        "description": None,
        "metric_config": {"Enabled": True},
        "cron_config": None,
        "max_replicas": None,
    }
    current = {"StrategyId": "st1", "StrategyName": "elastic", "Description": "prod", "CronConfig": {"Enabled": False}, "MaxReplicas": 8}
    value = mod.target(p, current)
    assert value["Config"] == {"Enabled": True}
    assert value["CronConfig"] == {"Enabled": False}
    assert value["MaxReplicas"] == 8
    assert value["StrategyName"] == "elastic"
    assert mod.mutation_payload(p, current)["StrategyId"] == "st1"
    assert mod.mutation_payload(p, current)["GatewayId"] == "g1"


def test_strategy_target_uses_supplied_name_description_and_replicas():
    p = {"gateway_id": "g1", "name": "scaled", "description": "new", "metric_config": None, "cron_config": None, "max_replicas": 12}
    current = {"StrategyId": "st1", "StrategyName": "elastic", "Description": "prod", "MaxReplicas": 8}
    value = mod.target(p, current)
    assert value["StrategyName"] == "scaled"
    assert value["Description"] == "new"
    assert value["MaxReplicas"] == 12
