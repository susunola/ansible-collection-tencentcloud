"""Unit tests for the config_rule write module (run_module flows).

Drives ``run_module()`` end to end against an in-memory fake Config client
whose write operations mutate the rule store, so the module's post-write
``find_rule`` refetch and ``wait_for_rule`` convergence poll succeed on the
first iteration.

Scenario matrix:

* absent on a missing rule (idempotent no-op)
* absent with a matching rule (check-mode dry run and the real delete path,
  waiting for the rule to disappear)
* creation when missing (required_if guard, check mode and the happy path)
* no-op when nothing drifts and drift updates (risk level / input
  parameters / tags / regions) with check mode
* immutable identifier/identifier_type/resource_types guard and the
  multiple-match guard
* the blanket ``Tencent Cloud API request failed`` failure path
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import config_rule as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

RULE = {
    "ConfigRuleId": "cr-8b0a1c2d",
    "Identifier": "CBS_DISK_ENCRYPTED",
    "IdentifierType": "SYSTEM",
    "RuleName": "require-encrypted-disks",
    "ResourceType": ["QCS::CBS::Disk"],
    "TriggerType": [{"MessageType": "ConfigurationItemChangeNotification", "MaximumExecutionFrequency": None}],
    "RiskLevel": 2,
    "InputParameter": [],
    "Description": "",
    "RegionsScope": [],
    "TagsScope": [],
    "ExcludeResourceIdsScope": [],
}


def _rule(**overrides):
    item = copy.deepcopy(RULE)
    item.update(overrides)
    return item


def _base(**overrides):
    params = {
        "state": "present",
        "name": "require-encrypted-disks",
        "identifier": "CBS_DISK_ENCRYPTED",
        "resource_types": ["QCS::CBS::Disk"],
    }
    params.update(overrides)
    return module_args(**params)


def _trigger_items(values):
    return [
        {
            "MessageType": getattr(item, "MessageType", None),
            "MaximumExecutionFrequency": getattr(item, "MaximumExecutionFrequency", None),
        }
        for item in (values or [])
    ]


def _input_items(values):
    return [
        {"ParameterKey": item.ParameterKey, "Type": item.Type, "Value": item.Value}
        for item in (values or [])
    ]


def _tag_items(values):
    return [{"TagKey": item.TagKey, "TagValue": item.TagValue} for item in (values or [])]


class FakeConfigClient(object):
    """In-memory Config client mutating a small compliance-rule store."""

    def __init__(self, rules=None):
        self.rules = [copy.deepcopy(t) for t in (rules or [])]
        self.calls = []
        self._next = 0

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def _by_id(self, rule_id):
        for item in self.rules:
            if item.get("ConfigRuleId") == rule_id:
                return item
        return None

    def ListConfigRules(self, request):
        self._record("ListConfigRules", request)
        return SimpleNamespace(Items=[FakeResource(dict(t)) for t in self.rules], Total=len(self.rules))

    def DescribeConfigRule(self, request):
        self._record("DescribeConfigRule", request)
        item = self._by_id(getattr(request, "RuleId", None))
        return SimpleNamespace(ConfigRule=FakeResource(dict(item)) if item else None)

    def _build_record(self, request, rule_id):
        return {
            "ConfigRuleId": rule_id,
            "Identifier": getattr(request, "Identifier", None),
            "IdentifierType": getattr(request, "IdentifierType", None),
            "RuleName": getattr(request, "RuleName", None),
            "ResourceType": list(getattr(request, "ResourceType", None) or []),
            "RiskLevel": getattr(request, "RiskLevel", None),
            "Description": getattr(request, "Description", "") or "",
            "RegionsScope": list(getattr(request, "RegionsScope", None) or []),
            "TagsScope": _tag_items(getattr(request, "TagsScope", None) or []),
            "ExcludeResourceIdsScope": list(getattr(request, "ExcludeResourceIdsScope", None) or []),
            "InputParameter": _input_items(getattr(request, "InputParameter", None) or []),
            "TriggerType": _trigger_items(getattr(request, "TriggerType", None) or []),
        }

    def AddConfigRule(self, request):
        self._record("AddConfigRule", request)
        self._next += 1
        rule_id = "cr-new-%03d" % self._next
        self.rules.append(self._build_record(request, rule_id))
        return SimpleNamespace(RuleId=rule_id, RequestId="req-fake")

    def UpdateConfigRule(self, request):
        self._record("UpdateConfigRule", request)
        item = self._by_id(getattr(request, "RuleId", None))
        if item is None:
            return SimpleNamespace(RequestId="req-fake")
        for attr in ("RuleName", "RiskLevel", "Description", "RegionsScope", "ExcludeResourceIdsScope"):
            if hasattr(request, attr):
                item[attr] = getattr(request, attr)
        if hasattr(request, "TagsScope"):
            item["TagsScope"] = _tag_items(request.TagsScope or [])
        if hasattr(request, "InputParameter"):
            item["InputParameter"] = _input_items(request.InputParameter or [])
        if hasattr(request, "TriggerType"):
            item["TriggerType"] = _trigger_items(request.TriggerType or [])
        return SimpleNamespace(RequestId="req-fake")

    def DeleteConfigRule(self, request):
        self._record("DeleteConfigRule", request)
        self.rules = [t for t in self.rules if t.get("ConfigRuleId") != getattr(request, "RuleId", None)]
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake, models=None):
    """Wire the shared monkeypatches; returns the fake client."""
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load_config", lambda: (models or FakeModels(), SimpleNamespace(ConfigClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


# ---------------------------------------------------------------------------
# absent flows
# ---------------------------------------------------------------------------


def test_absent_missing_rule_is_idempotent(monkeypatch):
    fake = FakeConfigClient(rules=[])
    _make_module(monkeypatch, fake)
    _base(state="absent", name="ghost-rule")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["rule"] is None
    assert "Config rule is absent" in result["msg"]
    assert [c for c, unused in fake.calls] == ["ListConfigRules"]


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeConfigClient(rules=[_rule()])
    _make_module(monkeypatch, fake)
    _base(_ansible_check_mode=True, state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["rule"]["ConfigRuleId"] == "cr-8b0a1c2d"
    assert "Would delete" in result["msg"]
    assert len(fake.rules) == 1
    assert "DeleteConfigRule" not in [c for c, unused in fake.calls]


def test_absent_deletes_rule(monkeypatch):
    fake = FakeConfigClient(rules=[_rule()])
    _make_module(monkeypatch, fake)
    _base(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["rule"] is None
    assert fake.rules == []
    ops = [c for c, unused in fake.calls]
    assert "DeleteConfigRule" in ops
    delete_call = fake.calls[[c for c, unused in fake.calls].index("DeleteConfigRule")][1]
    assert delete_call.RuleId == "cr-8b0a1c2d"


# ---------------------------------------------------------------------------
# validation guards
# ---------------------------------------------------------------------------


def test_present_requires_identifier_and_resource_types(monkeypatch):
    fake = FakeConfigClient(rules=[])
    _make_module(monkeypatch, fake)
    module_args(state="present", name="require-encrypted-disks")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    message = exc.value.args[0]["msg"]
    assert "identifier" in message
    assert "resource_types" in message


def test_present_by_rule_id_still_requires_identity_fields(monkeypatch):
    fake = FakeConfigClient(rules=[])
    _make_module(monkeypatch, fake)
    module_args(state="present", rule_id="cr-unknown")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    message = exc.value.args[0]["msg"]
    assert "name" in message
    assert "identifier" in message


# ---------------------------------------------------------------------------
# creation flows
# ---------------------------------------------------------------------------


def test_create_rule(monkeypatch):
    fake = FakeConfigClient(rules=[])
    _make_module(monkeypatch, fake)
    _base(state="present", risk_level=1, description="encrypt all disks")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["msg"] == "Config rule created"
    assert result["rule"]["ConfigRuleId"].startswith("cr-new-")
    assert result["rule"]["RuleName"] == "require-encrypted-disks"
    assert result["rule"]["RiskLevel"] == 1
    assert result["rule"]["Description"] == "encrypt all disks"
    assert len(fake.rules) == 1
    ops = [c for c, unused in fake.calls]
    assert ops[0] == "ListConfigRules"
    assert "AddConfigRule" in ops
    add_call = fake.calls[[c for c, unused in fake.calls].index("AddConfigRule")][1]
    assert add_call.Identifier == "CBS_DISK_ENCRYPTED"
    assert add_call.IdentifierType == "SYSTEM"
    assert add_call.ResourceType == ["QCS::CBS::Disk"]
    assert add_call.RiskLevel == 1


def test_create_check_mode_is_dry_run(monkeypatch):
    fake = FakeConfigClient(rules=[])
    _make_module(monkeypatch, fake)
    _base(_ansible_check_mode=True, state="present", risk_level=1)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["rule"] is None
    assert "Would create" in result["msg"]
    assert fake.rules == []
    assert "AddConfigRule" not in [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# existing-rule flows
# ---------------------------------------------------------------------------


def test_existing_rule_no_drift_is_idempotent(monkeypatch):
    fake = FakeConfigClient(rules=[_rule()])
    _make_module(monkeypatch, fake)
    _base(state="present")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["msg"] == "Config rule is up to date"
    assert result["rule"]["ConfigRuleId"] == "cr-8b0a1c2d"
    assert "UpdateConfigRule" not in [c for c, unused in fake.calls]


def test_existing_rule_drift_updates(monkeypatch):
    fake = FakeConfigClient(rules=[_rule()])
    _make_module(monkeypatch, fake)
    _base(
        state="present",
        risk_level=1,
        input_parameters={"team": "security"},
        tags={"env": "prod"},
        regions=["ap-shanghai"],
        description="require disk encryption",
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["msg"] == "Config rule updated"
    assert result["rule"]["RiskLevel"] == 1
    assert result["rule"]["Description"] == "require disk encryption"
    assert result["rule"]["InputParameter"] == [
        {"ParameterKey": "team", "Type": "Optional", "Value": "security"}
    ]
    assert result["rule"]["TagsScope"] == [{"TagKey": "env", "TagValue": "prod"}]
    assert result["rule"]["RegionsScope"] == ["ap-shanghai"]
    ops = [c for c, unused in fake.calls]
    assert "UpdateConfigRule" in ops
    update_call = fake.calls[[c for c, unused in fake.calls].index("UpdateConfigRule")][1]
    assert update_call.RuleId == "cr-8b0a1c2d"
    assert update_call.RiskLevel == 1


def test_existing_rule_drift_check_mode_is_dry_run(monkeypatch):
    fake = FakeConfigClient(rules=[_rule()])
    _make_module(monkeypatch, fake)
    _base(_ansible_check_mode=True, state="present", risk_level=1)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["msg"] == "Would update Config rule"
    assert result["rule"]["RiskLevel"] == 2
    assert fake.rules[0]["RiskLevel"] == 2
    assert "UpdateConfigRule" not in [c for c, unused in fake.calls]


def test_identifier_change_is_rejected(monkeypatch):
    fake = FakeConfigClient(rules=[_rule()])
    _make_module(monkeypatch, fake)
    _base(state="present", identifier="CVM_DISK_ENCRYPTED")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "cannot be changed" in payload["msg"]
    assert payload["field"] == "Identifier"


def test_multiple_rules_with_same_name_fail(monkeypatch):
    fake = FakeConfigClient(rules=[_rule(), _rule(ConfigRuleId="cr-dup")])
    _make_module(monkeypatch, fake)
    _base(state="present")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "Multiple Config rules have the requested name" in exc.value.args[0]["msg"]


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def ListConfigRules(self, request):
            raise Boom("connection dropped")

    _make_module(monkeypatch, ExplodingClient())
    _base(state="present")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]
