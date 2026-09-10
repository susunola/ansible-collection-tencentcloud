"""Unit tests for the cdb_audit_rule write module (run_module flows).

Drives ``run_module()`` end to end against an in-memory fake CDB client that
mutates a rule-name keyed store, so the module's post-write
``DescribeAuditRules`` refetch observes the new state immediately.

Scenario matrix:

* create when missing (real Create + converged refetch)
* idempotent no-op when the rule already exists
* absent when missing (no-op)
* delete when present (real Delete + converged refetch)
* check-mode dry run for create (no Create call)
* check-mode dry run for delete (no Delete call)
* required_if guard (present without rule_filters fails)
* SDK failure surfaces via fail_sdk_error
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from types import SimpleNamespace

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import cdb_audit_rule as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    FakeModels,
    FakeResource,
    module_args,
    run,
)


def _rule(rule_id, rule_name):
    return FakeResource({"RuleId": rule_id, "RuleName": rule_name, "Description": "", "AuditAll": False})


class FakeCdbClient(object):
    """In-memory CDB client mutating an audit-rule store keyed by rule name."""

    def __init__(self, rules=None):
        self.rules = list(rules or [])
        self.calls = []

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def DescribeAuditRules(self, request):
        self._record("DescribeAuditRules", request)
        return SimpleNamespace(
            Items=[FakeResource(dict(t._data)) for t in self.rules],
            TotalCount=len(self.rules),
            RequestId="req-fake",
        )

    def CreateAuditRule(self, request):
        self._record("CreateAuditRule", request)
        rule_id = "rule-%d" % (len(self.rules) + 1)
        self.rules.append(_rule(rule_id, getattr(request, "RuleName", "")))
        return SimpleNamespace(RuleId=rule_id, RequestId="req-fake")

    def DeleteAuditRule(self, request):
        self._record("DeleteAuditRule", request)
        target = getattr(request, "RuleId", "")
        self.rules = [t for t in self.rules if t.RuleId != target]
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake, models=None):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (models or FakeModels(), SimpleNamespace(CdbClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


RF = [{"rule_filters": [{"type": "host", "value": ["10.0.0.%"], "compare": "="}]}]


# ---------------------------------------------------------------------------
# create / delete flows
# ---------------------------------------------------------------------------


def test_create_when_missing(monkeypatch):
    fake = FakeCdbClient(rules=[])
    _make_module(monkeypatch, fake)
    module_args(rule_name="rule-host-prod", rule_filters=RF, state="present")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["rule_name"] == "rule-host-prod"
    assert result["rule_id"].startswith("rule-")
    assert result["exists"] is True
    ops = [c for c, unused in fake.calls]
    assert ops[0] == "DescribeAuditRules"
    assert "CreateAuditRule" in ops
    assert "DeleteAuditRule" not in ops
    created = [r for c, r in fake.calls if c == "CreateAuditRule"][0]
    assert created.RuleFilters[0].RuleFilters[0].Type == "host"
    assert created.RuleFilters[0].RuleFilters[0].Value == ["10.0.0.%"]
    assert created.AuditAll is False


def test_delete_when_present(monkeypatch):
    fake = FakeCdbClient(rules=[_rule("rule-1", "rule-host-prod")])
    _make_module(monkeypatch, fake)
    module_args(rule_name="rule-host-prod", rule_filters=RF, state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["exists"] is False
    ops = [c for c, unused in fake.calls]
    assert "DeleteAuditRule" in ops
    assert "CreateAuditRule" not in ops
    assert fake.rules == []


# ---------------------------------------------------------------------------
# idempotent no-op flows
# ---------------------------------------------------------------------------


def test_already_present_is_idempotent(monkeypatch):
    fake = FakeCdbClient(rules=[_rule("rule-1", "rule-host-prod")])
    _make_module(monkeypatch, fake)
    module_args(rule_name="rule-host-prod", rule_filters=RF, state="present")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["rule_id"] == "rule-1"
    ops = [c for c, unused in fake.calls]
    assert ops == ["DescribeAuditRules"]
    assert "CreateAuditRule" not in ops


def test_absent_when_missing_is_idempotent(monkeypatch):
    fake = FakeCdbClient(rules=[])
    _make_module(monkeypatch, fake)
    module_args(rule_name="rule-host-prod", rule_filters=RF, state="absent")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert "DeleteAuditRule" not in [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# check-mode dry runs
# ---------------------------------------------------------------------------


def test_create_check_mode_is_dry_run(monkeypatch):
    fake = FakeCdbClient(rules=[])
    _make_module(monkeypatch, fake)
    module_args(rule_name="rule-host-prod", rule_filters=RF, state="present", _ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert "CreateAuditRule" not in [c for c, unused in fake.calls]
    assert fake.rules == []


def test_delete_check_mode_is_dry_run(monkeypatch):
    fake = FakeCdbClient(rules=[_rule("rule-1", "rule-host-prod")])
    _make_module(monkeypatch, fake)
    module_args(rule_name="rule-host-prod", rule_filters=RF, state="absent", _ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert "DeleteAuditRule" not in [c for c, unused in fake.calls]
    assert len(fake.rules) == 1


# ---------------------------------------------------------------------------
# guards / error paths
# ---------------------------------------------------------------------------


def test_required_if_guard(monkeypatch):
    fake = FakeCdbClient(rules=[])
    _make_module(monkeypatch, fake)
    module_args(rule_name="rule-host-prod", state="present")
    try:
        run(mod.run_module)
    except SystemExit as exc:
        payload = getattr(exc, "args", [{}])[0]
        assert payload.get("failed")
        assert "rule_filters" in payload.get("msg", "")
    else:
        raise AssertionError("expected required_if failure")


def test_sdk_failure_fails(monkeypatch):
    fake = FakeCdbClient(rules=[])
    fake.CreateAuditRule = lambda request: (_ for _ in ()).throw(RuntimeError("boom"))
    _make_module(monkeypatch, fake)
    module_args(rule_name="rule-host-prod", rule_filters=RF, state="present")
    try:
        run(mod.run_module)
    except SystemExit as exc:
        payload = getattr(exc, "args", [{}])[0]
        assert payload.get("failed")
    else:
        raise AssertionError("expected SDK failure to fail the module")
