"""Unit tests for the tse_gateway_autoscaler_binding write module (run_module flows).

Drives ``run_module()`` end to end against an in-memory fake TSE client whose
bind/unbind operations mutate a per-(gateway, strategy) binding store so the
post-write readback converges immediately.

Scenario matrix:

* absent on an unbound strategy (idempotent no-op)
* absent unbinding matched groups (real mutation + check-mode dry run)
* present binding missing groups (by id and by resolved strategy/group names)
* no-op when the binding already matches
* ``purge_unlisted`` removing groups absent from the task
* validation guards (duplicate/empty group lists, absent+purge)
* strategy-name and gateway-group-name resolution failures
* the blanket ``sdk_error_payload`` failure path
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import tse_gateway_autoscaler_binding as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

STRATEGIES = [{"StrategyId": "strategy-1", "StrategyName": "production-elasticity"}]

GATEWAY_GROUPS = [
    {"GroupId": "group-1", "Name": "grp-a"},
    {"GroupId": "group-2", "Name": "grp-b"},
]


def _bound(groups):
    return [{"GroupId": gid} for gid in groups]


def _base(**overrides):
    params = {"gateway_id": "gateway-abc"}
    params.update(overrides)
    return module_args(**params)


class FakeTseClient(object):
    """In-memory TSE autoscaler binding client."""

    def __init__(self, bound=None, strategies=None, gateway_groups=None):
        self.bound = {}  # (gateway_id, strategy_id) -> [{"GroupId": ...}]
        for (gateway_id, strategy_id), groups in (bound or {}).items():
            self.bound[(gateway_id, strategy_id)] = _bound(groups)
        self.strategies = [copy.deepcopy(t) for t in (strategies if strategies is not None else STRATEGIES)]
        self.gateway_groups = [copy.deepcopy(t) for t in (gateway_groups if gateway_groups is not None else GATEWAY_GROUPS)]
        self.calls = []

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def _key(self, request):
        return (getattr(request, "GatewayId", None), getattr(request, "StrategyId", None))

    def DescribeAutoScalerResourceStrategyBindingGroups(self, request):
        self._record("DescribeAutoScalerResourceStrategyBindingGroups", request)
        details = [dict(t) for t in self.bound.get(self._key(request), [])]
        return SimpleNamespace(
            Result=SimpleNamespace(GroupInfos=[FakeResource(t) for t in details], TotalCount=len(details))
        )

    def BindAutoScalerResourceStrategyToGroups(self, request):
        self._record("BindAutoScalerResourceStrategyToGroups", request)
        key = self._key(request)
        existing = {item.get("GroupId") for item in self.bound.get(key, [])}
        for group_id in getattr(request, "GroupIds", None) or []:
            if group_id not in existing:
                self.bound.setdefault(key, []).append({"GroupId": group_id})
        return SimpleNamespace(RequestId="req-fake")

    def UnbindAutoScalerResourceStrategyFromGroups(self, request):
        self._record("UnbindAutoScalerResourceStrategyFromGroups", request)
        key = self._key(request)
        remove = set(getattr(request, "GroupIds", None) or [])
        self.bound[key] = [t for t in self.bound.get(key, []) if t.get("GroupId") not in remove]
        return SimpleNamespace(RequestId="req-fake")

    def DescribeAutoScalerResourceStrategies(self, request):
        self._record("DescribeAutoScalerResourceStrategies", request)
        return SimpleNamespace(Result=SimpleNamespace(StrategyList=[FakeResource(t) for t in self.strategies]))

    def DescribeNativeGatewayServerGroups(self, request):
        self._record("DescribeNativeGatewayServerGroups", request)
        return SimpleNamespace(Result=SimpleNamespace(GatewayGroupList=[FakeResource(t) for t in self.gateway_groups]))


def _make_module(monkeypatch, fake, models=None):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (models or FakeModels(), SimpleNamespace(TseClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


# ---------------------------------------------------------------------------
# absent flows
# ---------------------------------------------------------------------------


def test_absent_unbound_is_idempotent(monkeypatch):
    fake = FakeTseClient(bound={})
    _make_module(monkeypatch, fake)
    _base(state="absent", strategy_id="strategy-1", group_ids=["group-1"])
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["binding"]["GroupIds"] == []
    ops = [c for c, unused in fake.calls]
    assert "UnbindAutoScalerResourceStrategyFromGroups" not in ops


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeTseClient(bound={("gateway-abc", "strategy-1"): ["group-1", "group-2"]})
    _make_module(monkeypatch, fake)
    _base(_ansible_check_mode=True, state="absent", strategy_id="strategy-1", group_ids=["group-1"])
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["binding"]["RemovedGroupIds"] == ["group-1"]
    assert "UnbindAutoScalerResourceStrategyFromGroups" not in [c for c, unused in fake.calls]


def test_absent_unbinds_matched_groups(monkeypatch):
    fake = FakeTseClient(bound={("gateway-abc", "strategy-1"): ["group-1", "group-2"]})
    _make_module(monkeypatch, fake)
    _base(state="absent", strategy_id="strategy-1", group_ids=["group-1"])
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["binding"]["RemovedGroupIds"] == ["group-1"]
    assert result["binding"]["GroupIds"] == ["group-2"]
    ops = [c for c, unused in fake.calls]
    assert "UnbindAutoScalerResourceStrategyFromGroups" in ops


def test_absent_resolves_strategy_by_name(monkeypatch):
    fake = FakeTseClient(bound={("gateway-abc", "strategy-1"): ["group-1"]})
    _make_module(monkeypatch, fake)
    _base(state="absent", strategy_name="production-elasticity", group_ids=["group-1"])
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["binding"]["RemovedGroupIds"] == ["group-1"]
    ops = [c for c, unused in fake.calls]
    assert "DescribeAutoScalerResourceStrategies" in ops


# ---------------------------------------------------------------------------
# present flows
# ---------------------------------------------------------------------------


def test_present_binds_new_groups(monkeypatch):
    fake = FakeTseClient(bound={})
    _make_module(monkeypatch, fake)
    _base(state="present", strategy_id="strategy-1", group_ids=["group-1", "group-2"])
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["binding"]["AddedGroupIds"] == ["group-1", "group-2"]
    assert result["binding"]["GroupIds"] == ["group-1", "group-2"]
    assert fake.bound[("gateway-abc", "strategy-1")] == [{"GroupId": "group-1"}, {"GroupId": "group-2"}]
    ops = [c for c, unused in fake.calls]
    assert "BindAutoScalerResourceStrategyToGroups" in ops


def test_present_binds_resolved_names(monkeypatch):
    fake = FakeTseClient(bound={})
    _make_module(monkeypatch, fake)
    _base(
        state="present",
        strategy_name="production-elasticity",
        group_names=["grp-a", "grp-b"],
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["binding"]["GroupIds"] == ["group-1", "group-2"]
    ops = [c for c, unused in fake.calls]
    assert "DescribeNativeGatewayServerGroups" in ops
    assert "DescribeAutoScalerResourceStrategies" in ops
    assert "BindAutoScalerResourceStrategyToGroups" in ops


def test_present_no_drift_is_idempotent(monkeypatch):
    fake = FakeTseClient(bound={("gateway-abc", "strategy-1"): ["group-1", "group-2"]})
    _make_module(monkeypatch, fake)
    _base(state="present", strategy_id="strategy-1", group_ids=["group-1", "group-2"])
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["binding"]["GroupIds"] == ["group-1", "group-2"]
    assert "BindAutoScalerResourceStrategyToGroups" not in [c for c, unused in fake.calls]
    assert "UnbindAutoScalerResourceStrategyFromGroups" not in [c for c, unused in fake.calls]


def test_present_check_mode_is_dry_run(monkeypatch):
    fake = FakeTseClient(bound={})
    _make_module(monkeypatch, fake)
    _base(_ansible_check_mode=True, state="present", strategy_id="strategy-1", group_ids=["group-1"])
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["binding"]["GroupIds"] == ["group-1"]
    assert result["binding"]["Groups"] == []
    assert "BindAutoScalerResourceStrategyToGroups" not in [c for c, unused in fake.calls]


def test_present_purges_unlisted_groups(monkeypatch):
    fake = FakeTseClient(bound={("gateway-abc", "strategy-1"): ["group-1", "group-2"]})
    _make_module(monkeypatch, fake)
    _base(state="present", strategy_id="strategy-1", group_ids=["group-1"], purge_unlisted=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["binding"]["RemovedGroupIds"] == ["group-2"]
    assert result["binding"]["GroupIds"] == ["group-1"]
    ops = [c for c, unused in fake.calls]
    assert "UnbindAutoScalerResourceStrategyFromGroups" in ops
    assert "BindAutoScalerResourceStrategyToGroups" not in ops


def test_present_purge_unlisted_noop_when_aligned(monkeypatch):
    fake = FakeTseClient(bound={("gateway-abc", "strategy-1"): ["group-1"]})
    _make_module(monkeypatch, fake)
    _base(state="present", strategy_id="strategy-1", group_ids=["group-1"], purge_unlisted=True)
    result = run(mod.run_module)
    assert result["changed"] is False


# ---------------------------------------------------------------------------
# validation guards
# ---------------------------------------------------------------------------


def test_group_names_duplicates_fail(monkeypatch):
    fake = FakeTseClient(bound={})
    _make_module(monkeypatch, fake)
    _base(state="present", strategy_id="strategy-1", group_names=["grp-a", "grp-a"])
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "group_names must not contain duplicates" in exc.value.args[0]["msg"]


def test_group_ids_required(monkeypatch):
    fake = FakeTseClient(bound={})
    _make_module(monkeypatch, fake)
    _base(state="present", strategy_id="strategy-1", group_ids=[])
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "group_ids must contain at least one entry" in exc.value.args[0]["msg"]


def test_group_ids_duplicates_fail(monkeypatch):
    fake = FakeTseClient(bound={})
    _make_module(monkeypatch, fake)
    _base(state="present", strategy_id="strategy-1", group_ids=["group-1", "group-1"])
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "group_ids must not contain duplicates" in exc.value.args[0]["msg"]


def test_absent_purge_unlisted_fails(monkeypatch):
    fake = FakeTseClient(bound={})
    _make_module(monkeypatch, fake)
    _base(state="absent", strategy_id="strategy-1", group_ids=["group-1"], purge_unlisted=True)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "purge_unlisted is only valid with state=present" in exc.value.args[0]["msg"]


def test_strategy_name_not_found_fails(monkeypatch):
    fake = FakeTseClient(bound={}, strategies=[])
    _make_module(monkeypatch, fake)
    _base(state="present", strategy_name="missing-strategy", group_ids=["group-1"])
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "TSE autoscaler strategy name was not found" in exc.value.args[0]["msg"]


def test_ambiguous_strategy_name_fails(monkeypatch):
    strategies = [
        {"StrategyId": "strategy-1", "StrategyName": "dup"},
        {"StrategyId": "strategy-2", "StrategyName": "dup"},
    ]
    fake = FakeTseClient(bound={}, strategies=strategies)
    _make_module(monkeypatch, fake)
    _base(state="present", strategy_name="dup", group_ids=["group-1"])
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "Multiple TSE autoscaler strategies matched the name" in exc.value.args[0]["msg"]


def test_group_name_not_found_fails(monkeypatch):
    fake = FakeTseClient(bound={})
    _make_module(monkeypatch, fake)
    _base(state="present", strategy_id="strategy-1", group_names=["missing-group"])
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "TSE gateway group names were not found" in exc.value.args[0]["msg"]


def test_ambiguous_group_name_fails(monkeypatch):
    groups = [
        {"GroupId": "group-1", "Name": "dup"},
        {"GroupId": "group-2", "Name": "dup"},
    ]
    fake = FakeTseClient(bound={}, gateway_groups=groups)
    _make_module(monkeypatch, fake)
    _base(state="present", strategy_id="strategy-1", group_names=["dup"])
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "Multiple TSE gateway groups matched names" in exc.value.args[0]["msg"]


# ---------------------------------------------------------------------------
# failure paths
# ---------------------------------------------------------------------------


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeAutoScalerResourceStrategyBindingGroups(self, request):
            raise Boom("connection dropped")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    _base(state="present", strategy_id="strategy-1", group_ids=["group-1"])
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]


# ---------------------------------------------------------------------------
# legacy helper regression tests (folded from test_tse_gateway_autoscaler.py)
# ---------------------------------------------------------------------------


class _Request(object):
    pass


def test_mutation_request_maps_group_delta():
    p = {"gateway_id": "g1", "strategy_id": "st1"}
    request = mod.mutation_request(_Request, p, ["group2"])
    assert request.GatewayId == "g1"
    assert request.StrategyId == "st1"
    assert request.GroupIds == ["group2"]


def test_strategy_and_groups_requests_map_identity():
    p = {"gateway_id": "g1", "strategy_id": "st1"}
    strategy = mod.strategy_request(FakeModels(), p)
    assert strategy.GatewayId == "g1"
    group_request = mod.groups_request(FakeModels(), p)
    assert group_request.GatewayId == "g1"
    assert group_request.Offset == 0
    assert group_request.Limit == 100
