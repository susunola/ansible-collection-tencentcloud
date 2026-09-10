"""Unit tests for the tse_gateway_canary_rule write module (run_module flows).

``run_module()`` creates, updates and deletes a priority-addressed TSE
gateway canary rule. It is driven end to end against an in-memory fake
client whose create/modify/delete operations mutate a rule store, so the
post-write ``DescribeCloudNativeAPIGatewayCanaryRules`` refetch converges
immediately.

Scenario matrix:

* absent without a rule (idempotent) / check-mode delete / real delete
* creation when missing, with config required (check mode and real)
* idempotent no-op when the live rule already satisfies the desired shape
* drift updates through the modify API (check mode and real)
* distinct Standard/Lane rule sets addressed by the same priority
* priority range and config/rule_type validation before mutation
* duplicate matching rules fail before any write
* blanket ``sdk_error_payload`` failure path
* legacy helper regression tests (folded from test_tse_gateway_canary_rule.py)
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
import json
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import tse_gateway_canary_rule as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

GATEWAY_ID = "gateway-abc"
SERVICE_ID = "service-orders"
PRIORITY = 90
CONDITIONS = [{"Type": "header", "Key": "X-Canary", "Operator": "exact", "Value": "beta"}]
BALANCED = [
    {"ServiceID": "service-stable", "Percent": 90},
    {"ServiceID": "service-canary", "Percent": 10},
]
CONFIG = {"Enabled": True, "ConditionList": CONDITIONS, "BalancedServiceList": BALANCED}


def _base(**overrides):
    params = {
        "gateway_id": GATEWAY_ID,
        "service_id": SERVICE_ID,
        "priority": PRIORITY,
        "config": dict(CONFIG),
    }
    params.update(overrides)
    return module_args(**params)


def _rule(**overrides):
    value = {
        "Priority": PRIORITY,
        "RuleType": "Standard",
        "Enabled": True,
        "ConditionList": CONDITIONS,
        "BalancedServiceList": BALANCED,
    }
    value.update(overrides)
    return value


class FakeCanaryClient(object):
    """In-memory TSE canary-rule client keyed by identity plus rule type."""

    def __init__(self, rules=None):
        self.rules = {}
        for value in (rules or []):
            self._store(copy.deepcopy(value))
        self.calls = []

    def _record(self, name, request=None):
        self.calls.append((name, request))

    @staticmethod
    def _key(value):
        return (value["GatewayId"], value["ServiceId"], value["RuleType"], value["Priority"])

    def _store(self, value):
        self.rules[self._key(value)] = value

    def DescribeCloudNativeAPIGatewayCanaryRules(self, request):
        self._record("DescribeCloudNativeAPIGatewayCanaryRules", request)
        matches = sorted(
            [
                copy.deepcopy(value)
                for key, value in self.rules.items()
                if key[0] == request.GatewayId
                and key[1] == request.ServiceId
                and key[2] == request.RuleType
            ],
            key=lambda item: item["Priority"],
        )
        page = matches[request.Offset: request.Offset + request.Limit]
        return SimpleNamespace(
            Result=SimpleNamespace(
                CanaryRuleList=[FakeResource(item) for item in page],
                TotalCount=len(matches),
            ),
            RequestId="req-fake",
        )

    def CreateCloudNativeAPIGatewayCanaryRule(self, request):
        self._record("CreateCloudNativeAPIGatewayCanaryRule", request)
        value = copy.deepcopy(request.CanaryRule)
        value["GatewayId"] = request.GatewayId
        value["ServiceId"] = request.ServiceId
        self._store(value)
        return SimpleNamespace(RequestId="req-fake")

    def ModifyCloudNativeAPIGatewayCanaryRule(self, request):
        self._record("ModifyCloudNativeAPIGatewayCanaryRule", request)
        value = copy.deepcopy(request.CanaryRule)
        value["GatewayId"] = request.GatewayId
        value["ServiceId"] = request.ServiceId
        self._store(value)
        return SimpleNamespace(RequestId="req-fake")

    def DeleteCloudNativeAPIGatewayCanaryRule(self, request):
        self._record("DeleteCloudNativeAPIGatewayCanaryRule", request)
        for key in [k for k in self.rules if k[0] == request.GatewayId and k[1] == request.ServiceId and k[3] == request.Priority]:
            self.rules.pop(key, None)
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (FakeModels(), SimpleNamespace(TseClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


def _ops(fake):
    return [name for name, unused in fake.calls]


# ---------------------------------------------------------------------------
# absent flows
# ---------------------------------------------------------------------------


def test_absent_without_rule_is_idempotent(monkeypatch):
    fake = _make_module(monkeypatch, FakeCanaryClient())
    _base(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["canary_rule"] is None
    assert _ops(fake) == ["DescribeCloudNativeAPIGatewayCanaryRules"]


def test_absent_deletes_existing_rule(monkeypatch):
    fake = _make_module(monkeypatch, FakeCanaryClient(rules=[_rule(GatewayId=GATEWAY_ID, ServiceId=SERVICE_ID)]))
    _base(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["canary_rule"] is None
    assert fake.rules == {}
    assert _ops(fake) == [
        "DescribeCloudNativeAPIGatewayCanaryRules",
        "DeleteCloudNativeAPIGatewayCanaryRule",
    ]


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = _make_module(monkeypatch, FakeCanaryClient(rules=[_rule(GatewayId=GATEWAY_ID, ServiceId=SERVICE_ID)]))
    _base(state="absent", _ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert len(fake.rules) == 1
    assert "DeleteCloudNativeAPIGatewayCanaryRule" not in _ops(fake)


# ---------------------------------------------------------------------------
# creation flows
# ---------------------------------------------------------------------------


def test_present_creates_missing_rule(monkeypatch):
    fake = _make_module(monkeypatch, FakeCanaryClient())
    _base()
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["canary_rule"]["Priority"] == PRIORITY
    assert result["canary_rule"]["RuleType"] == "Standard"
    assert result["canary_rule"]["Enabled"] is True
    assert len(fake.rules) == 1
    stored = fake.rules[(GATEWAY_ID, SERVICE_ID, "Standard", PRIORITY)]
    assert stored["Enabled"] is True
    assert stored["Priority"] == PRIORITY
    assert _ops(fake) == [
        "DescribeCloudNativeAPIGatewayCanaryRules",
        "CreateCloudNativeAPIGatewayCanaryRule",
        "DescribeCloudNativeAPIGatewayCanaryRules",
    ]


def test_present_create_check_mode_is_dry_run(monkeypatch):
    fake = _make_module(monkeypatch, FakeCanaryClient())
    _base(_ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["canary_rule"]["RuleType"] == "Standard"
    assert result["canary_rule"]["Priority"] == PRIORITY
    assert "diff" in result
    assert fake.rules == {}
    assert "CreateCloudNativeAPIGatewayCanaryRule" not in _ops(fake)


def test_present_create_requires_config(monkeypatch):
    fake = _make_module(monkeypatch, FakeCanaryClient())
    params = {
        "gateway_id": GATEWAY_ID,
        "service_id": SERVICE_ID,
        "priority": PRIORITY,
        "state": "present",
    }
    module_args(**params)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "config" in payload["msg"]
    assert fake.rules == {}


# ---------------------------------------------------------------------------
# idempotent and drift flows
# ---------------------------------------------------------------------------


def test_converged_rule_is_idempotent(monkeypatch):
    current = _rule(GatewayId=GATEWAY_ID, ServiceId=SERVICE_ID, CreateTime="2026-01-01")
    fake = _make_module(monkeypatch, FakeCanaryClient(rules=[current]))
    _base()
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["canary_rule"]["CreateTime"] == "2026-01-01"
    assert _ops(fake) == ["DescribeCloudNativeAPIGatewayCanaryRules"]


def test_rule_type_filters_same_priority_rules(monkeypatch):
    standard = _rule(GatewayId=GATEWAY_ID, ServiceId=SERVICE_ID)
    lane = _rule(GatewayId=GATEWAY_ID, ServiceId=SERVICE_ID, RuleType="Lane", Enabled=False)
    _make_module(monkeypatch, FakeCanaryClient(rules=[standard, lane]))
    _base()
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["canary_rule"]["RuleType"] == "Standard"


def test_enabled_drift_updates_existing_rule(monkeypatch):
    current = _rule(GatewayId=GATEWAY_ID, ServiceId=SERVICE_ID, Enabled=False)
    fake = _make_module(monkeypatch, FakeCanaryClient(rules=[current]))
    _base()
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["canary_rule"]["Enabled"] is True
    stored = fake.rules[(GATEWAY_ID, SERVICE_ID, "Standard", PRIORITY)]
    assert stored["Enabled"] is True
    assert _ops(fake) == [
        "DescribeCloudNativeAPIGatewayCanaryRules",
        "ModifyCloudNativeAPIGatewayCanaryRule",
        "DescribeCloudNativeAPIGatewayCanaryRules",
    ]


def test_drift_check_mode_is_dry_run(monkeypatch):
    current = _rule(GatewayId=GATEWAY_ID, ServiceId=SERVICE_ID, Enabled=False)
    fake = _make_module(monkeypatch, FakeCanaryClient(rules=[current]))
    _base(_ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["canary_rule"]["Enabled"] is True
    assert "diff" in result
    assert fake.rules[(GATEWAY_ID, SERVICE_ID, "Standard", PRIORITY)]["Enabled"] is False
    assert "ModifyCloudNativeAPIGatewayCanaryRule" not in _ops(fake)


# ---------------------------------------------------------------------------
# validation guards
# ---------------------------------------------------------------------------


def test_priority_above_range_fails_before_sdk(monkeypatch):
    class NeverClient(object):
        def DescribeCloudNativeAPIGatewayCanaryRules(self, request):
            raise AssertionError("sdk must not be reached")

    _make_module(monkeypatch, NeverClient())
    _base(priority=101)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert exc.value.args[0]["msg"] == "priority must be between 0 and 100"


def test_negative_priority_fails_before_sdk(monkeypatch):
    class NeverClient(object):
        def DescribeCloudNativeAPIGatewayCanaryRules(self, request):
            raise AssertionError("sdk must not be reached")

    _make_module(monkeypatch, NeverClient())
    _base(priority=-1)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert exc.value.args[0]["msg"] == "priority must be between 0 and 100"


def test_config_rule_type_mismatch_fails(monkeypatch):
    fake = _make_module(monkeypatch, FakeCanaryClient())
    _base(config={"Enabled": True, "RuleType": "Lane"})
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "config.RuleType must match rule_type"
    assert fake.rules == {}
    assert _ops(fake) == ["DescribeCloudNativeAPIGatewayCanaryRules"]


def test_duplicate_matching_rules_fail(monkeypatch):
    class DuplicateClient(object):
        def DescribeCloudNativeAPIGatewayCanaryRules(self, request):
            values = [
                FakeResource(_rule(GatewayId=GATEWAY_ID, ServiceId=SERVICE_ID)),
                FakeResource(_rule(GatewayId=GATEWAY_ID, ServiceId=SERVICE_ID)),
            ]
            return SimpleNamespace(Result=SimpleNamespace(CanaryRuleList=values, TotalCount=2), RequestId="req-fake")

    _make_module(monkeypatch, DuplicateClient())
    _base()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "Multiple TSE canary rules matched" in exc.value.args[0]["msg"]


# ---------------------------------------------------------------------------
# failure paths
# ---------------------------------------------------------------------------


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeCloudNativeAPIGatewayCanaryRules(self, request):
            raise Boom("tse endpoint unreachable")

    _make_module(monkeypatch, ExplodingClient())
    _base()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "tse endpoint unreachable" in payload["error"]


# ---------------------------------------------------------------------------
# legacy helper regression tests (folded from test_tse_gateway_canary_rule.py)
# ---------------------------------------------------------------------------


class _CanaryRequest(object):
    def from_json_string(self, value):
        for key, item in json.loads(value).items():
            setattr(self, key, item)


def test_canary_request_injects_stable_priority():
    p = {"gateway_id": "g1", "service_id": "s1", "priority": 90}
    request = mod.mutation_request(_CanaryRequest, p, {"Enabled": True})
    assert request.Priority == 90
    assert request.CanaryRule["Priority"] == 90


def test_canary_delete_request_maps_identity_only():
    p = {"gateway_id": "g1", "service_id": "s1", "priority": 10}
    request = mod.mutation_request(_CanaryRequest, p)
    assert request.GatewayId == "g1"
    assert request.ServiceId == "s1"
    assert request.Priority == 10
    assert not hasattr(request, "CanaryRule")


def test_contains_allows_server_enriched_rule():
    actual = {"Priority": 90, "Enabled": True, "ServiceName": "orders"}
    expected = {"Priority": 90, "Enabled": True}
    assert mod.contains(actual, expected)


def test_contains_rejects_drifted_values():
    actual = {"Priority": 90, "Enabled": False}
    expected = {"Priority": 90, "Enabled": True}
    assert not mod.contains(actual, expected)
