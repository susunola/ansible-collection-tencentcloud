"""Unit tests for the cdb_audit_rule_template write module (run_module flows).

Drives ``run_module()`` end to end against an in-memory fake CDB client that
mutates an audit-rule-template store keyed by name, so the module's
post-write ``DescribeAuditRuleTemplates`` refetch observes the new state
immediately.

Scenario matrix:

* create when missing (real Create + converged refetch)
* idempotent no-op when the template already exists
* absent when missing (no-op)
* delete when present (real Delete + converged refetch)
* check-mode dry run for create (no Create call)
* check-mode dry run for delete (no Delete call)
* missing rule_filters payload on present fails (required_if)
* SDK failure surfaces via fail_sdk_error
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from types import SimpleNamespace

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import cdb_audit_rule_template as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    FakeModels,
    FakeResource,
    module_args,
    run,
)


def _template(tid, name):
    return FakeResource({"RuleTemplateId": str(tid), "RuleTemplateName": name, "Description": ""})


RULE_FILTERS = [
    {"type": "host", "value": ["10.0.0.%"], "compare": "="},
]


class FakeCdbClient(object):
    """In-memory CDB client mutating an audit-rule-template store keyed by name."""

    def __init__(self, templates=None):
        self.templates = list(templates or [])
        self._seq = 0
        self.calls = []

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def DescribeAuditRuleTemplates(self, request):
        self._record("DescribeAuditRuleTemplates", request)
        wanted = list(getattr(request, "RuleTemplateNames", None) or [])
        if wanted:
            matched = [t for t in self.templates if t.RuleTemplateName in wanted]
        else:
            matched = list(self.templates)
        return SimpleNamespace(Items=[FakeResource(dict(t._data)) for t in matched],
                               TotalCount=len(matched), RequestId="req-fake")

    def CreateAuditRuleTemplate(self, request):
        self._record("CreateAuditRuleTemplate", request)
        self._seq += 1
        tid = "tmpl-%d" % self._seq
        item = _template(tid, getattr(request, "RuleTemplateName", ""))
        self.templates.append(item)
        return SimpleNamespace(RuleTemplateId=tid, RequestId="req-fake")

    def DeleteAuditRuleTemplates(self, request):
        self._record("DeleteAuditRuleTemplates", request)
        ids = list(getattr(request, "RuleTemplateIds", None) or [])
        self.templates = [t for t in self.templates if t.RuleTemplateId not in ids]
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake, models=None):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (models or FakeModels(), SimpleNamespace(CdbClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


# ---------------------------------------------------------------------------
# create / delete flows
# ---------------------------------------------------------------------------


def test_create_when_missing(monkeypatch):
    fake = FakeCdbClient(templates=[])
    _make_module(monkeypatch, fake)
    module_args(rule_template_name="tmpl-host-prod", rule_filters=list(RULE_FILTERS), state="present")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["exists"] is True
    assert result["rule_template_id"] is not None
    ops = [c for c, unused in fake.calls]
    assert ops[0] == "DescribeAuditRuleTemplates"
    assert "CreateAuditRuleTemplate" in ops
    assert "DeleteAuditRuleTemplates" not in ops
    created = [r for c, r in fake.calls if c == "CreateAuditRuleTemplate"][0]
    assert created.RuleTemplateName == "tmpl-host-prod"


def test_delete_when_present(monkeypatch):
    fake = FakeCdbClient(templates=[_template(1, "tmpl-host-prod")])
    _make_module(monkeypatch, fake)
    module_args(rule_template_name="tmpl-host-prod", state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["exists"] is False
    assert "DeleteAuditRuleTemplates" in [c for c, unused in fake.calls]
    assert "CreateAuditRuleTemplate" not in [c for c, unused in fake.calls]
    assert fake.templates == []


# ---------------------------------------------------------------------------
# idempotent no-op flows
# ---------------------------------------------------------------------------


def test_already_present_is_idempotent(monkeypatch):
    fake = FakeCdbClient(templates=[_template(1, "tmpl-host-prod")])
    _make_module(monkeypatch, fake)
    module_args(rule_template_name="tmpl-host-prod", rule_filters=list(RULE_FILTERS), state="present")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["rule_template_id"] == "1"
    assert [c for c, unused in fake.calls] == ["DescribeAuditRuleTemplates"]
    assert "CreateAuditRuleTemplate" not in [c for c, unused in fake.calls]


def test_absent_when_missing_is_idempotent(monkeypatch):
    fake = FakeCdbClient(templates=[])
    _make_module(monkeypatch, fake)
    module_args(rule_template_name="tmpl-host-prod", state="absent")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert "DeleteAuditRuleTemplates" not in [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# check-mode dry runs
# ---------------------------------------------------------------------------


def test_create_check_mode_is_dry_run(monkeypatch):
    fake = FakeCdbClient(templates=[])
    _make_module(monkeypatch, fake)
    module_args(rule_template_name="tmpl-host-prod", rule_filters=list(RULE_FILTERS),
                state="present", _ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert "CreateAuditRuleTemplate" not in [c for c, unused in fake.calls]
    assert fake.templates == []


def test_delete_check_mode_is_dry_run(monkeypatch):
    fake = FakeCdbClient(templates=[_template(1, "tmpl-host-prod")])
    _make_module(monkeypatch, fake)
    module_args(rule_template_name="tmpl-host-prod", state="absent", _ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert "DeleteAuditRuleTemplates" not in [c for c, unused in fake.calls]
    assert len(fake.templates) == 1


# ---------------------------------------------------------------------------
# error / validation paths
# ---------------------------------------------------------------------------


def test_missing_rule_filters_on_present_fails(monkeypatch):
    fake = FakeCdbClient(templates=[])
    _make_module(monkeypatch, fake)
    module_args(rule_template_name="tmpl-host-prod", state="present")
    try:
        run(mod.run_module)
    except SystemExit as exc:
        payload = getattr(exc, "args", [{}])[0]
        assert payload.get("failed")
    else:
        raise AssertionError("expected required_if rule_filters to fail the module")


def test_sdk_failure_fails(monkeypatch):
    fake = FakeCdbClient(templates=[])

    def _raise_error(request):
        raise RuntimeError("boom")
    fake.CreateAuditRuleTemplate = _raise_error
    _make_module(monkeypatch, fake)
    module_args(rule_template_name="tmpl-host-prod", rule_filters=list(RULE_FILTERS), state="present")
    try:
        run(mod.run_module)
    except SystemExit as exc:
        payload = getattr(exc, "args", [{}])[0]
        assert payload.get("failed")
    else:
        raise AssertionError("expected SDK failure to fail the module")
