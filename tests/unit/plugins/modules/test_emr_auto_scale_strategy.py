"""Tests for EMR automatic scaling strategy helpers."""
from ansible_collections.susunola.tencentcloud.plugins.modules.emr_auto_scale_strategy import find, subset, wanted


def test_wanted_enforces_identity_and_group():
    value = wanted({"name": "task-scale", "group_id": 2, "strategy": {"ScaleNum": 3}})
    assert value == {"StrategyName": "task-scale", "GroupId": 2, "ScaleNum": 3}


def test_subset_ignores_server_fields():
    target = {"StrategyName": "task-scale", "ScaleNum": 3}
    assert subset({"StrategyName": "task-scale", "ScaleNum": 3, "StrategyId": 42}, target) == target


def test_find_uses_exact_strategy_name():
    values = [{"StrategyName": "task-scale-old", "StrategyId": 1}, {"StrategyName": "task-scale", "StrategyId": 2}]
    assert find(values, "task-scale")["StrategyId"] == 2
