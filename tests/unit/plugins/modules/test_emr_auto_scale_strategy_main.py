"""Unit tests for the emr_auto_scale_strategy write module (run_module flows).

``run_module()`` is driven end to end against an in-memory fake EMR client
whose add/modify/delete operations mutate the per-cluster strategy store, so
the post-write ``DescribeAutoScaleStrategies`` refetch converges immediately.

Scenario matrix:

* absent on a missing strategy (idempotent) / check-mode delete / real delete
* present on a missing strategy (check mode and real create via
  ``AddMetricScaleStrategy``)
* idempotent no-op when the strategy already matches
* drift update through ``ModifyAutoScaleStrategy`` with captured request fields
* delete authorization guard (``allow_node_termination``)
* argument-validation failure before any SDK call
* the blanket ``sdk_error_payload`` failure path
* legacy helper regression tests (folded from test_emr_auto_scale_strategy.py)
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import emr_auto_scale_strategy as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

STRATEGY = {
    "StrategyName": "task-scale-on-yarn",
    "StrategyId": "as-strategy-1",
    "GroupId": 2,
    "ScaleAction": 1,
    "ScaleNum": 2,
    "StrategyStatus": 1,
    "CalmDownTime": 300,
    "LoadMetricsConditions": {"LoadMetrics": []},
}


def _strategy(**overrides):
    item = copy.deepcopy(STRATEGY)
    item.update(overrides)
    return item


def _base(**overrides):
    params = {
        "cluster_id": "emr-abcdefgh",
        "group_id": 2,
        "strategy_type": "load",
        "name": "task-scale-on-yarn",
        "strategy": {
            "ScaleAction": 1,
            "ScaleNum": 2,
            "StrategyStatus": 1,
            "CalmDownTime": 300,
            "LoadMetricsConditions": {"LoadMetrics": []},
        },
    }
    params.update(overrides)
    return module_args(**params)


class FakeEmrClient(object):
    """In-memory EMR client mutating load/time scaling-strategy stores."""

    def __init__(self, load=None, time=None):
        self.strategies = {
            "LoadAutoScaleStrategies": [copy.deepcopy(t) for t in (load or [])],
            "TimeAutoScaleStrategies": [copy.deepcopy(t) for t in (time or [])],
        }
        self.calls = []
        self._next = 0

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def DescribeAutoScaleStrategies(self, request):
        self._record("DescribeAutoScaleStrategies", request)
        return SimpleNamespace(
            LoadAutoScaleStrategies=[FakeResource(dict(t)) for t in self.strategies["LoadAutoScaleStrategies"]],
            TimeBasedAutoScaleStrategies=[FakeResource(dict(t)) for t in self.strategies["TimeAutoScaleStrategies"]],
            RequestId="req-fake",
        )

    def _bucket(self, strategy_type):
        return "LoadAutoScaleStrategies" if strategy_type == 1 else "TimeAutoScaleStrategies"

    def AddMetricScaleStrategy(self, request):
        self._record("AddMetricScaleStrategy", request)
        bucket = self._bucket(request.StrategyType)
        single = "LoadAutoScaleStrategy" if request.StrategyType == 1 else "TimeAutoScaleStrategy"
        item = copy.deepcopy(getattr(request, single))
        self._next += 1
        item["StrategyId"] = "as-strategy-new-%03d" % self._next
        self.strategies[bucket].append(item)
        return SimpleNamespace(RequestId="req-fake")

    def ModifyAutoScaleStrategy(self, request):
        self._record("ModifyAutoScaleStrategy", request)
        bucket = self._bucket(request.StrategyType)
        merged = getattr(request, bucket)
        self.strategies[bucket] = [copy.deepcopy(t) for t in merged]
        return SimpleNamespace(RequestId="req-fake")

    def DeleteAutoScaleStrategy(self, request):
        self._record("DeleteAutoScaleStrategy", request)
        bucket = self._bucket(request.StrategyType)
        self.strategies[bucket] = [t for t in self.strategies[bucket] if t.get("StrategyId") != request.StrategyId]
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake, models=None):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (models or FakeModels(), SimpleNamespace(EmrClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


def _find_call(fake, operation):
    return next(request for name, request in fake.calls if name == operation)


# ---------------------------------------------------------------------------
# absent flows
# ---------------------------------------------------------------------------


def test_absent_missing_strategy_is_idempotent(monkeypatch):
    fake = FakeEmrClient(load=[])
    _make_module(monkeypatch, fake)
    _base(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["strategy"] is None


def test_absent_requires_node_termination_authorization(monkeypatch):
    fake = FakeEmrClient(load=[_strategy()])
    _make_module(monkeypatch, fake)
    _base(state="absent")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "allow_node_termination=true" in exc.value.args[0]["msg"]


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeEmrClient(load=[_strategy()])
    _make_module(monkeypatch, fake)
    _base(_ansible_check_mode=True, state="absent", allow_node_termination=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["strategy"]["StrategyId"] == "as-strategy-1"
    assert len(fake.strategies["LoadAutoScaleStrategies"]) == 1
    assert "DeleteAutoScaleStrategy" not in [name for name, unused in fake.calls]


def test_absent_deletes_strategy(monkeypatch):
    fake = FakeEmrClient(load=[_strategy()])
    _make_module(monkeypatch, fake)
    _base(state="absent", allow_node_termination=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["strategy"] is None
    assert fake.strategies["LoadAutoScaleStrategies"] == []
    request = _find_call(fake, "DeleteAutoScaleStrategy")
    assert request.InstanceId == "emr-abcdefgh"
    assert request.GroupId == 2
    assert request.StrategyType == 1
    assert request.StrategyId == "as-strategy-1"


# ---------------------------------------------------------------------------
# creation flows
# ---------------------------------------------------------------------------


def test_create_strategy(monkeypatch):
    fake = FakeEmrClient(load=[])
    _make_module(monkeypatch, fake)
    _base()
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["strategy"]["StrategyName"] == "task-scale-on-yarn"
    assert result["strategy"]["ScaleNum"] == 2
    assert result["strategy"]["StrategyId"].startswith("as-strategy-new-")
    request = _find_call(fake, "AddMetricScaleStrategy")
    assert request.InstanceId == "emr-abcdefgh"
    assert request.StrategyType == 1
    assert request.LoadAutoScaleStrategy["ScaleNum"] == 2
    ops = [name for name, unused in fake.calls]
    assert ops[0] == "DescribeAutoScaleStrategies"
    assert ops[-1] == "DescribeAutoScaleStrategies"  # post-write refetch


def test_create_check_mode_is_dry_run(monkeypatch):
    fake = FakeEmrClient(load=[])
    _make_module(monkeypatch, fake)
    _base(_ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["strategy"]["StrategyName"] == "task-scale-on-yarn"
    assert "StrategyId" not in result["strategy"]
    assert fake.strategies["LoadAutoScaleStrategies"] == []
    assert "AddMetricScaleStrategy" not in [name for name, unused in fake.calls]


# ---------------------------------------------------------------------------
# existing-strategy flows
# ---------------------------------------------------------------------------


def test_matching_strategy_is_idempotent(monkeypatch):
    fake = FakeEmrClient(load=[_strategy()])
    _make_module(monkeypatch, fake)
    _base()
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["strategy"]["StrategyId"] == "as-strategy-1"
    assert [name for name, unused in fake.calls] == ["DescribeAutoScaleStrategies"]


def test_strategy_drift_updates_in_place(monkeypatch):
    fake = FakeEmrClient(load=[_strategy(ScaleNum=5)])
    _make_module(monkeypatch, fake)
    _base()
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["strategy"]["StrategyId"] == "as-strategy-1"
    assert result["strategy"]["ScaleNum"] == 2
    request = _find_call(fake, "ModifyAutoScaleStrategy")
    assert request.InstanceId == "emr-abcdefgh"
    assert request.StrategyType == 1
    replaced = request.LoadAutoScaleStrategies[0]
    assert replaced["StrategyName"] == "task-scale-on-yarn"
    assert replaced["StrategyId"] == "as-strategy-1"
    assert replaced["ScaleNum"] == 2


def test_update_check_mode_is_dry_run(monkeypatch):
    fake = FakeEmrClient(load=[_strategy(ScaleNum=5)])
    _make_module(monkeypatch, fake)
    _base(_ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["strategy"]["ScaleNum"] == 2
    assert fake.strategies["LoadAutoScaleStrategies"][0]["ScaleNum"] == 5
    assert "ModifyAutoScaleStrategy" not in [name for name, unused in fake.calls]


# ---------------------------------------------------------------------------
# argument validation and failure paths
# ---------------------------------------------------------------------------


def test_present_requires_strategy_payload(monkeypatch):
    fake = FakeEmrClient(load=[])
    _make_module(monkeypatch, fake)
    module_args(cluster_id="emr-abcdefgh", group_id=2, strategy_type="load", name="x")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "strategy" in exc.value.args[0]["msg"]
    assert fake.calls == []


def test_missing_cluster_id_fails(monkeypatch):
    fake = FakeEmrClient(load=[])
    _make_module(monkeypatch, fake)
    module_args(group_id=2, strategy_type="load", name="x", strategy={"ScaleNum": 1})
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "cluster_id" in exc.value.args[0]["msg"]
    assert fake.calls == []


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeAutoScaleStrategies(self, request):
            raise Boom("connection dropped")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    _base()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]


# ---------------------------------------------------------------------------
# legacy helper regression tests (folded from test_emr_auto_scale_strategy.py)
# ---------------------------------------------------------------------------


def test_wanted_enforces_identity_and_group():
    value = mod.wanted({"name": "task-scale", "group_id": 2, "strategy": {"ScaleNum": 3}})
    assert value == {"StrategyName": "task-scale", "GroupId": 2, "ScaleNum": 3}


def test_wanted_without_group_omits_group_id():
    value = mod.wanted({"name": "task-scale", "group_id": None, "strategy": {"ScaleNum": 3}})
    assert value == {"StrategyName": "task-scale", "ScaleNum": 3}


def test_subset_ignores_server_fields():
    target = {"StrategyName": "task-scale", "ScaleNum": 3}
    assert mod.subset({"StrategyName": "task-scale", "ScaleNum": 3, "StrategyId": 42}, target) == target


def test_find_uses_exact_strategy_name():
    values = [{"StrategyName": "task-scale-old", "StrategyId": 1}, {"StrategyName": "task-scale", "StrategyId": 2}]
    assert mod.find(values, "task-scale")["StrategyId"] == 2
    assert mod.find(values, "ghost") is None
