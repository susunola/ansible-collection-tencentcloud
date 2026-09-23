"""Unit tests for the dlc_data_mask_strategy write module (run_module flows)."""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import dlc_data_mask_strategy as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

STRATEGY = {
    "StrategyId": "dms-000001",
    "StrategyName": "mask-customer-phone",
    "StrategyType": "MASK_SHOW_LAST_4",
    "StrategyDesc": "Reveal only the final four digits",
    "Groups": [{"WorkGroupId": 10042, "StrategyType": "MASK_SHOW_LAST_4"}],
    "Users": "100012345678",
    "State": 1,
}


def _strategy(**overrides):
    item = copy.deepcopy(STRATEGY)
    item.update(overrides)
    return item


def _make_module(monkeypatch, fake, models=None):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (models or FakeModels(), SimpleNamespace(DlcClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


class FakeDlcClient(object):
    """In-memory DLC client mutating a masking-strategy store."""

    def __init__(self, strategies=None):
        self.strategies = [copy.deepcopy(t) for t in (strategies or [])]
        self.calls = []
        self._next = 0

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def _by_id(self, strategy_id):
        for item in self.strategies:
            if item.get("StrategyId") == strategy_id:
                return item
        return None

    def DescribeDataMaskStrategies(self, request):
        self._record("DescribeDataMaskStrategies", request)
        return SimpleNamespace(Strategies=[FakeResource(t) for t in self.strategies], TotalCount=len(self.strategies))

    def CreateDataMaskStrategy(self, request):
        self._record("CreateDataMaskStrategy", request)
        self._next += 1
        item = dict(getattr(request.Strategy, "__dict__", {}) or {})
        item["StrategyId"] = "dms-new-%03d" % self._next
        item["State"] = 1
        self.strategies.append(item)
        return SimpleNamespace(StrategyId=item["StrategyId"], RequestId="req-fake")

    def UpdateDataMaskStrategy(self, request):
        self._record("UpdateDataMaskStrategy", request)
        item = self._by_id(getattr(request.Strategy, "StrategyId", None))
        if item is None:
            return SimpleNamespace(RequestId="req-fake")
        item.update({k: v for k, v in dict(getattr(request.Strategy, "__dict__", {}) or {}).items() if k != "State"})
        item["State"] = 1
        return SimpleNamespace(RequestId="req-fake")

    def DeleteDataMaskStrategy(self, request):
        self._record("DeleteDataMaskStrategy", request)
        self.strategies = [t for t in self.strategies if t.get("StrategyId") != getattr(request, "StrategyId", None)]
        return SimpleNamespace(RequestId="req-fake")


# ---------------------------------------------------------------------------
# absent flows
# ---------------------------------------------------------------------------


def test_absent_missing_strategy_is_idempotent(monkeypatch):
    fake = FakeDlcClient(strategies=[])
    _make_module(monkeypatch, fake)
    module_args(state="absent", name="ghost-strategy")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["strategy"] is None
    assert result["strategy_id"] is None
    assert [c for c, unused in fake.calls] == ["DescribeDataMaskStrategies"]


def test_absent_soft_deleted_strategy_is_ignored(monkeypatch):
    fake = FakeDlcClient(strategies=[_strategy(State=0)])
    _make_module(monkeypatch, fake)
    module_args(state="absent", name="mask-customer-phone")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["strategy"] is None


def test_absent_requires_allow_delete(monkeypatch):
    fake = FakeDlcClient(strategies=[_strategy()])
    _make_module(monkeypatch, fake)
    module_args(state="absent", name="mask-customer-phone")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "allow_delete=true" in exc.value.args[0]["msg"]


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeDlcClient(strategies=[_strategy()])
    _make_module(monkeypatch, fake)
    module_args(_ansible_check_mode=True, state="absent", name="mask-customer-phone", allow_delete=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert len(fake.strategies) == 1
    assert "DeleteDataMaskStrategy" not in [c for c, unused in fake.calls]


def test_absent_deletes_strategy(monkeypatch):
    fake = FakeDlcClient(strategies=[_strategy()])
    _make_module(monkeypatch, fake)
    module_args(state="absent", name="mask-customer-phone", allow_delete=True, wait=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["strategy"] is None
    assert fake.strategies == []
    assert "DeleteDataMaskStrategy" in [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# creation flows
# ---------------------------------------------------------------------------


def test_create_requires_creation_parameters(monkeypatch):
    fake = FakeDlcClient(strategies=[])
    _make_module(monkeypatch, fake)
    module_args(state="present", name="brand-new")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "creation parameters are required" in payload["msg"]
    assert payload["missing"] == ["strategy_type"]


def test_create_strategy(monkeypatch):
    fake = FakeDlcClient(strategies=[])
    _make_module(monkeypatch, fake)
    module_args(
        state="present",
        name="mask-customer-phone",
        strategy_type="MASK_SHOW_LAST_4",
        description="Reveal only the final four digits",
        groups=[{"WorkGroupId": 10042, "StrategyType": "MASK_SHOW_LAST_4"}],
        users=["100012345678"],
        wait=True,
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["strategy_id"].startswith("dms-new-")
    assert result["strategy"]["StrategyName"] == "mask-customer-phone"
    assert result["strategy"]["Groups"] == [{"WorkGroupId": 10042, "StrategyType": "MASK_SHOW_LAST_4"}]
    assert result["strategy"]["Users"] == ["100012345678"]
    assert len(fake.strategies) == 1
    assert "CreateDataMaskStrategy" in [c for c, unused in fake.calls]


def test_create_check_mode_is_dry_run(monkeypatch):
    fake = FakeDlcClient(strategies=[])
    _make_module(monkeypatch, fake)
    module_args(
        _ansible_check_mode=True,
        state="present",
        name="mask-customer-phone",
        strategy_type="MASK_SHOW_LAST_4",
        description="Reveal only the final four digits",
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["strategy_id"] is None
    assert result["strategy"]["StrategyName"] == "mask-customer-phone"
    assert fake.strategies == []
    assert "CreateDataMaskStrategy" not in [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# existing-strategy flows
# ---------------------------------------------------------------------------


def test_existing_strategy_no_drift_is_idempotent(monkeypatch):
    fake = FakeDlcClient(strategies=[_strategy()])
    _make_module(monkeypatch, fake)
    module_args(
        state="present",
        name="mask-customer-phone",
        strategy_type="MASK_SHOW_LAST_4",
        description="Reveal only the final four digits",
        groups=[{"WorkGroupId": 10042, "StrategyType": "MASK_SHOW_LAST_4"}],
        users=["100012345678"],
    )
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["strategy"]["StrategyId"] == "dms-000001"
    assert result["strategy_id"] == "dms-000001"


def test_existing_strategy_by_id_no_drift(monkeypatch):
    fake = FakeDlcClient(strategies=[_strategy()])
    _make_module(monkeypatch, fake)
    module_args(state="present", strategy_id="dms-000001")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["strategy"]["StrategyName"] == "mask-customer-phone"


def test_update_description_drift(monkeypatch):
    fake = FakeDlcClient(strategies=[_strategy()])
    _make_module(monkeypatch, fake)
    module_args(
        state="present",
        name="mask-customer-phone",
        strategy_type="MASK_SHOW_LAST_4",
        description="Updated description",
        wait=True,
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["strategy"]["StrategyDesc"] == "Updated description"
    ops = [c for c, unused in fake.calls]
    assert "UpdateDataMaskStrategy" in ops
    assert "CreateDataMaskStrategy" not in ops


def test_update_users_drift(monkeypatch):
    fake = FakeDlcClient(strategies=[_strategy()])
    _make_module(monkeypatch, fake)
    module_args(
        state="present",
        name="mask-customer-phone",
        strategy_type="MASK_SHOW_LAST_4",
        users=["1000999888777", "100012345678"],
        wait=True,
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["strategy"]["Users"] == ["100012345678", "1000999888777"]


def test_update_check_mode_is_dry_run(monkeypatch):
    fake = FakeDlcClient(strategies=[_strategy()])
    _make_module(monkeypatch, fake)
    module_args(
        _ansible_check_mode=True,
        state="present",
        name="mask-customer-phone",
        strategy_type="MASK_SHOW_LAST_4",
        description="Updated description",
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["strategy"]["StrategyDesc"] == "Updated description"
    assert "UpdateDataMaskStrategy" not in [c for c, unused in fake.calls]


def test_multiple_matches_fail(monkeypatch):
    fake = FakeDlcClient(strategies=[_strategy(), _strategy(StrategyId="dms-000002")])
    _make_module(monkeypatch, fake)
    module_args(state="present", name="mask-customer-phone")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "Multiple DLC masking strategies matched" in exc.value.args[0]["msg"]


# ---------------------------------------------------------------------------
# validation / failure paths
# ---------------------------------------------------------------------------


def test_duplicate_groups_fail(monkeypatch):
    fake = FakeDlcClient(strategies=[])
    _make_module(monkeypatch, fake)
    module_args(
        state="present",
        name="mask-customer-phone",
        strategy_type="MASK_SHOW_LAST_4",
        groups=[{"WorkGroupId": 10042, "StrategyType": "MASK_SHOW_LAST_4"}] * 2,
    )
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "duplicate" in payload["error"]


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeDataMaskStrategies(self, request):
            raise Boom("connection dropped")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    module_args(state="present", name="mask-customer-phone")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]


# ---------------------------------------------------------------------------
# legacy helper regression tests (folded from test_dlc_data_mask_strategy.py)
# ---------------------------------------------------------------------------


class LegacyObject(object):
    def from_json_string(self, value):
        import json

        for key, item in json.loads(value).items():
            setattr(self, key, item)


class LegacyFilter(LegacyObject):
    pass


class LegacyModels(object):
    DescribeDataMaskStrategiesRequest = LegacyObject
    CreateDataMaskStrategyRequest = LegacyObject
    UpdateDataMaskStrategyRequest = LegacyObject
    DeleteDataMaskStrategyRequest = LegacyObject
    DataMaskStrategyInfo = LegacyObject
    Filter = LegacyFilter


def legacy_target():
    return {
        "StrategyId": "mask-1",
        "StrategyName": "phone",
        "StrategyType": "MASK_SHOW_LAST_4",
        "StrategyDesc": "phone mask",
        "Groups": [{"WorkGroupId": 2, "StrategyType": "MASK_HASH"}],
        "Users": ["10001", "10002"],
    }


def test_normalization_stabilizes_groups_and_users():
    assert mod.normalize_users("10002;10001;10001") == ["10001", "10002"]
    assert mod.normalize_groups([{"WorkGroupId": 2, "StrategyType": "B"}, {"WorkGroupId": 1, "StrategyType": "A"}])[0]["WorkGroupId"] == 1
    assert mod.normalize({**legacy_target(), "Users": "10002;10001"}) == legacy_target()


def test_describe_uses_name_filter_and_pagination():
    request = mod.describe_request(LegacyModels, {"name": "phone"}, 100)
    assert request.Offset == 100 and request.Filters[0].Name == "strategy-name"


def test_mutation_requests_serialize_normalized_users():
    created = mod.create_request(LegacyModels, legacy_target())
    updated = mod.update_request(LegacyModels, legacy_target())
    assert created.Strategy.Users == "10001;10002" and updated.Strategy.StrategyId == "mask-1"
    assert mod.delete_request(LegacyModels, "mask-1").StrategyId == "mask-1"
