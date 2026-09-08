"""Unit tests for the tsf_lane_rule write module (run_module flows).

Drives ``run_module()`` end to end against an in-memory fake TSF client
whose write operations mutate the lane-rule store, so the module's
post-write ``find`` refetch converges immediately.

Scenario matrix:

* absent on a missing rule (idempotent no-op), rejected-deletion guard and
  the real delete path
* tags required when creating, no-drift idempotency
* creation (enabled and disabled) and update (remark / tags / enable)
  flows, including the enable/disable call after creation
* multiple-match guard and the blanket ``sdk_error_payload`` failure path
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import tsf_lane_rule as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

LANE_RULE = {
    "RuleId": "lane-rule-1",
    "RuleName": "checkout-canary-header",
    "LaneId": "lane-xxx",
    "Enable": True,
    "RuleTagRelationship": "RELEATION_AND",
    "Remark": "checkout canary",
    "RuleTagList": [{"TagName": "x-canary", "TagOperator": "EQUAL", "TagValue": "true"}],
}

TAGS = [{"name": "x-canary", "operator": "EQUAL", "value": "true"}]


def _lane_rule(**overrides):
    item = copy.deepcopy(LANE_RULE)
    item.update(overrides)
    return item


def _plain(value):
    """Recursively unwrap FakeRequest/model stand-ins into plain data."""
    if value is None or isinstance(value, bool) or isinstance(value, (str, int, float)):
        return value
    if isinstance(value, list):
        return [_plain(item) for item in value]
    if isinstance(value, tuple):
        return [_plain(item) for item in value]
    if isinstance(value, dict):
        return {key: _plain(item) for key, item in value.items()}
    return {key: _plain(item) for key, item in vars(value).items()}


class FakeTsfLaneClient(object):
    """In-memory TSF client mutating a lane-rule store."""

    def __init__(self, rules=None):
        self.rules = [copy.deepcopy(t) for t in (rules or [])]
        self.calls = []
        self._next = 0

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def _by_id(self, rule_id):
        for item in self.rules:
            if item.get("RuleId") == rule_id:
                return item
        return None

    def _matches(self, request):
        rule_id = getattr(request, "RuleId", None)
        if rule_id:
            return [item for item in self.rules if item.get("RuleId") == rule_id]
        search = getattr(request, "SearchWord", None)
        return [item for item in self.rules if item.get("RuleName") == search]

    def DescribeLaneRules(self, request):
        self._record("DescribeLaneRules", request)
        return SimpleNamespace(
            Result=SimpleNamespace(Content=[FakeResource(item) for item in self._matches(request)], TotalCount=len(self._matches(request)))
        )

    def DeleteLaneRule(self, request):
        self._record("DeleteLaneRule", request)
        rule_id = getattr(request, "RuleId", None)
        self.rules = [item for item in self.rules if item.get("RuleId") != rule_id]
        return SimpleNamespace(Result=True, RequestId="req-fake")

    def CreateLaneRule(self, request):
        self._record("CreateLaneRule", request)
        self._next += 1
        item = {"RuleId": "lane-rule-new-%03d" % self._next}
        for key, value in vars(request).items():
            item[key] = _plain(value)
        self.rules.append(item)
        return SimpleNamespace(Result=item["RuleId"], RequestId="req-fake")

    def ModifyLaneRule(self, request):
        self._record("ModifyLaneRule", request)
        rule = self._by_id(getattr(request, "RuleId", None))
        if rule is not None:
            for key, value in vars(request).items():
                if key != "RuleId":
                    rule[key] = _plain(value)
        return SimpleNamespace(Result=True, RequestId="req-fake")

    def EnableLaneRule(self, request):
        self._record("EnableLaneRule", request)
        rule = self._by_id(getattr(request, "RuleId", None))
        if rule is not None:
            rule["Enable"] = True
        return SimpleNamespace(Result=True, RequestId="req-fake")

    def DisableLaneRule(self, request):
        self._record("DisableLaneRule", request)
        rule = self._by_id(getattr(request, "RuleId", None))
        if rule is not None:
            rule["Enable"] = False
        return SimpleNamespace(Result=True, RequestId="req-fake")


def _make_module(monkeypatch, fake, models=None):
    """Wire the shared monkeypatches; returns the fake client."""
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (models or FakeModels(), SimpleNamespace(TsfClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


def _rule_args(**overrides):
    params = {
        "name": "checkout-canary-header",
        "lane_id": "lane-xxx",
        "remark": "checkout canary",
        "tags": copy.deepcopy(TAGS),
    }
    params.update(overrides)
    return module_args(**params)


# ---------------------------------------------------------------------------
# absent flows
# ---------------------------------------------------------------------------


def test_absent_missing_rule_is_idempotent(monkeypatch):
    fake = FakeTsfLaneClient(rules=[])
    _make_module(monkeypatch, fake)
    module_args(state="absent", name="ghost", lane_id="lane-xxx")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["lane_rule"] is None


def test_absent_deletes_rule(monkeypatch):
    fake = FakeTsfLaneClient(rules=[_lane_rule()])
    _make_module(monkeypatch, fake)
    module_args(state="absent", name="checkout-canary-header", lane_id="lane-xxx")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert fake.rules == []
    assert "DeleteLaneRule" in [c for c, unused in fake.calls]


def test_absent_deletion_rejected(monkeypatch):
    class RejectingClient(FakeTsfLaneClient):
        def DeleteLaneRule(self, request):
            self._record("DeleteLaneRule", request)
            return SimpleNamespace(Result=False, RequestId="req-fake")

    fake = RejectingClient(rules=[_lane_rule()])
    _make_module(monkeypatch, fake)
    module_args(state="absent", name="checkout-canary-header", lane_id="lane-xxx")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "rejected the TSF lane rule deletion" in exc.value.args[0]["msg"]


# ---------------------------------------------------------------------------
# creation flows
# ---------------------------------------------------------------------------


def test_create_requires_tags(monkeypatch):
    fake = FakeTsfLaneClient(rules=[])
    _make_module(monkeypatch, fake)
    module_args(name="checkout-canary-header", lane_id="lane-xxx")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "tags is required when creating a TSF lane rule" in exc.value.args[0]["msg"]


def test_create_enabled_rule(monkeypatch):
    fake = FakeTsfLaneClient(rules=[])
    _make_module(monkeypatch, fake)
    _rule_args()
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["lane_rule"]["RuleName"] == "checkout-canary-header"
    assert result["lane_rule"]["Enable"] is True
    assert len(fake.rules) == 1
    ops = [c for c, unused in fake.calls]
    assert "CreateLaneRule" in ops
    assert "EnableLaneRule" in ops
    assert "DisableLaneRule" not in ops


def test_create_disabled_rule(monkeypatch):
    fake = FakeTsfLaneClient(rules=[])
    _make_module(monkeypatch, fake)
    _rule_args(enabled=False)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["lane_rule"]["Enable"] is False
    ops = [c for c, unused in fake.calls]
    assert "DisableLaneRule" in ops


def test_create_check_mode_is_dry_run(monkeypatch):
    fake = FakeTsfLaneClient(rules=[])
    _make_module(monkeypatch, fake)
    _rule_args(_ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["lane_rule"]["RuleName"] == "checkout-canary-header"
    assert fake.rules == []
    assert "CreateLaneRule" not in [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# existing-rule flows
# ---------------------------------------------------------------------------


def test_existing_rule_no_drift_is_idempotent(monkeypatch):
    fake = FakeTsfLaneClient(rules=[_lane_rule()])
    _make_module(monkeypatch, fake)
    _rule_args()
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["lane_rule"]["RuleId"] == "lane-rule-1"
    assert "ModifyLaneRule" not in [c for c, unused in fake.calls]


def test_update_rule_drift(monkeypatch):
    fake = FakeTsfLaneClient(rules=[_lane_rule()])
    _make_module(monkeypatch, fake)
    _rule_args(remark="updated remark", enabled=False)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["lane_rule"]["Remark"] == "updated remark"
    assert result["lane_rule"]["Enable"] is False
    ops = [c for c, unused in fake.calls]
    assert "ModifyLaneRule" in ops


# ---------------------------------------------------------------------------
# guards / failure paths
# ---------------------------------------------------------------------------


def test_multiple_matches_fail(monkeypatch):
    fake = FakeTsfLaneClient(rules=[_lane_rule(), _lane_rule(RuleId="lane-rule-dup")])
    _make_module(monkeypatch, fake)
    _rule_args()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "Multiple TSF lane rules matched" in exc.value.args[0]["msg"]


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeLaneRules(self, request):
            raise Boom("tsf control plane down")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    _rule_args()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "tsf control plane down" in payload["error"]
