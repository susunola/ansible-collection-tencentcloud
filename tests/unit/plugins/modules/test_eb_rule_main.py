"""Unit tests for the eb_rule write module (run_module flows).

Drives ``run_module()`` against an in-memory fake EventBridge client whose
create / update / delete operations mutate a per-bus rule store so
post-write describes converge immediately.

Scenario matrix:

* absent on a missing rule (idempotent no-op)
* absent with a matching rule (check-mode dry run, real delete)
* creation when missing (happy path, check mode, missing-parameter guard)
* no-op when the rule already matches (name/pattern/enabled/description)
* drift updates through UpdateRule, keeping remote name/pattern when omitted
* the ambiguous-match guard and the blanket SDK failure paths
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import eb_rule as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

RULE = {
    "EventBusId": "eb-l8q2abcd",
    "RuleId": "rule-1001",
    "RuleName": "order-created",
    "EventPattern": '{"source":["orders"]}',
    "Enable": True,
    "Description": "",
}


def _rule(**overrides):
    item = copy.deepcopy(RULE)
    item.update(overrides)
    return item


def _present_args(**overrides):
    params = {
        "state": "present",
        "event_bus_id": "eb-l8q2abcd",
        "name": "order-created",
        "event_pattern": '{"source":["orders"]}',
    }
    params.update(overrides)
    return module_args(**params)


class FakeEbClient(object):
    """In-memory EventBridge client mutating a small per-bus rule store."""

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

    def ListRules(self, request):
        self._record("ListRules", request)
        return SimpleNamespace(Rules=[FakeResource(copy.deepcopy(t)) for t in self.rules])

    def GetRule(self, request):
        self._record("GetRule", request)
        item = self._by_id(getattr(request, "RuleId", None))
        if item is None:
            return FakeResource({})
        value = copy.deepcopy(item)
        value["RequestId"] = "req-fake"
        return FakeResource(value)

    def CreateRule(self, request):
        self._record("CreateRule", request)
        self._next += 1
        item = {
            "EventBusId": getattr(request, "EventBusId", None),
            "RuleId": "rule-%04d" % self._next,
            "RuleName": getattr(request, "RuleName", None),
            "EventPattern": getattr(request, "EventPattern", None),
            "Enable": getattr(request, "Enable", True),
            "Description": getattr(request, "Description", None) or "",
        }
        self.rules.append(item)
        return SimpleNamespace(RuleId=item["RuleId"], RequestId="req-fake")

    def UpdateRule(self, request):
        self._record("UpdateRule", request)
        item = self._by_id(getattr(request, "RuleId", None))
        if item is not None:
            name = getattr(request, "RuleName", None)
            if name is not None:
                item["RuleName"] = name
            pattern = getattr(request, "EventPattern", None)
            if pattern is not None:
                item["EventPattern"] = pattern
            item["Enable"] = getattr(request, "Enable", item.get("Enable"))
            item["Description"] = getattr(request, "Description", item.get("Description"))
        return SimpleNamespace(RequestId="req-fake")

    def DeleteRule(self, request):
        self._record("DeleteRule", request)
        rule_id = getattr(request, "RuleId", None)
        self.rules = [t for t in self.rules if t.get("RuleId") != rule_id]
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake, models=None):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (models or FakeModels(), SimpleNamespace(EbClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


# ---------------------------------------------------------------------------
# absent flows
# ---------------------------------------------------------------------------


def test_absent_missing_rule_is_idempotent(monkeypatch):
    fake = FakeEbClient(rules=[])
    _make_module(monkeypatch, fake)
    module_args(state="absent", event_bus_id="eb-l8q2abcd", name="ghost-rule")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["rule"] is None
    assert [c for c, unused in fake.calls] == ["ListRules"]


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeEbClient(rules=[_rule()])
    _make_module(monkeypatch, fake)
    module_args(_ansible_check_mode=True, state="absent", event_bus_id="eb-l8q2abcd", name="order-created")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["rule"] is None
    assert len(fake.rules) == 1
    assert "DeleteRule" not in [c for c, unused in fake.calls]


def test_absent_deletes_rule(monkeypatch):
    fake = FakeEbClient(rules=[_rule()])
    _make_module(monkeypatch, fake)
    module_args(state="absent", event_bus_id="eb-l8q2abcd", name="order-created")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["rule"] is None
    assert fake.rules == []
    ops = [c for c, unused in fake.calls]
    assert "DeleteRule" in ops


# ---------------------------------------------------------------------------
# creation flows
# ---------------------------------------------------------------------------


def test_create_rule(monkeypatch):
    fake = FakeEbClient(rules=[])
    _make_module(monkeypatch, fake)
    _present_args()
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["rule"]["RuleId"] == "rule-0001"
    assert result["rule"]["RuleName"] == "order-created"
    assert result["rule"]["Enable"] is True
    assert len(fake.rules) == 1
    ops = [c for c, unused in fake.calls]
    assert ops[0] == "ListRules"
    assert "CreateRule" in ops
    assert ops[-1] == "GetRule"


def test_create_check_mode_returns_target(monkeypatch):
    fake = FakeEbClient(rules=[])
    _make_module(monkeypatch, fake)
    _present_args(_ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["rule"] == {
        "RuleName": "order-created",
        "EventPattern": '{"source":["orders"]}',
        "Enable": True,
        "Description": "",
    }
    assert "diff" in result
    assert fake.rules == []
    assert "CreateRule" not in [c for c, unused in fake.calls]


def test_create_missing_parameters_fails(monkeypatch):
    fake = FakeEbClient(rules=[])
    _make_module(monkeypatch, fake)
    module_args(state="present", event_bus_id="eb-l8q2abcd", rule_id="rule-9999")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "creation parameters are required" in payload["msg"]
    assert payload["missing"] == ["name", "event_pattern"]


# ---------------------------------------------------------------------------
# existing-rule flows
# ---------------------------------------------------------------------------


def test_existing_rule_no_drift_is_idempotent(monkeypatch):
    fake = FakeEbClient(rules=[_rule()])
    _make_module(monkeypatch, fake)
    _present_args()
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["rule"]["RuleId"] == "rule-1001"
    assert "UpdateRule" not in [c for c, unused in fake.calls]


def test_event_pattern_drift_updates(monkeypatch):
    fake = FakeEbClient(rules=[_rule()])
    _make_module(monkeypatch, fake)
    _present_args(event_pattern='{"source":["payments"]}')
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["rule"]["EventPattern"] == '{"source":["payments"]}'
    ops = [c for c, unused in fake.calls]
    assert "UpdateRule" in ops
    assert ops[-1] == "GetRule"


def test_rule_id_only_update_keeps_remote_name_and_pattern(monkeypatch):
    fake = FakeEbClient(rules=[_rule()])
    _make_module(monkeypatch, fake)
    module_args(state="present", event_bus_id="eb-l8q2abcd", rule_id="rule-1001", description="Audit trail rule")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["rule"]["RuleName"] == "order-created"
    assert result["rule"]["EventPattern"] == '{"source":["orders"]}'
    assert result["rule"]["Description"] == "Audit trail rule"


def test_update_check_mode_is_dry_run(monkeypatch):
    fake = FakeEbClient(rules=[_rule()])
    _make_module(monkeypatch, fake)
    _present_args(_ansible_check_mode=True, event_pattern='{"source":["preview"]}')
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["rule"]["EventPattern"] == '{"source":["orders"]}'
    assert "diff" in result
    assert "UpdateRule" not in [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# guards and failure paths
# ---------------------------------------------------------------------------


def test_multiple_name_matches_fail(monkeypatch):
    fake = FakeEbClient(rules=[_rule(), _rule(RuleId="rule-2002")])
    _make_module(monkeypatch, fake)
    _present_args()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "specify rule_id" in exc.value.args[0]["msg"]


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def ListRules(self, request):
            raise Boom("connection dropped")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    _present_args()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]


def test_delete_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def ListRules(self, request):
            return SimpleNamespace(Rules=[FakeResource(copy.deepcopy(_rule()))])

        def GetRule(self, request):
            value = copy.deepcopy(_rule())
            value["RequestId"] = "req-fake"
            return FakeResource(value)

        def DeleteRule(self, request):
            raise Boom("delete refused")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    module_args(state="absent", event_bus_id="eb-l8q2abcd", name="order-created")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "delete refused" in payload["error"]
