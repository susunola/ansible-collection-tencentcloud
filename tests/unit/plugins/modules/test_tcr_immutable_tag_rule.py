"""Unit tests for the tcr_immutable_tag_rule write module (run_module flows).

Drives ``run_module()`` end to end against an in-memory fake TCR client that
mutates an immutable-tag-rule store keyed by (registry, namespace, repository
pattern, tag pattern), so the module's post-write ``DescribeImmutableTagRules``
refetch observes the new state immediately.

Scenario matrix:

* create when missing (real Create + converged refetch)
* idempotent no-op when the rule already exists
* absent when missing (no-op)
* delete when present (real Delete + converged refetch)
* check-mode dry run for create (no Create call)
* check-mode dry run for delete (no Delete call)
* missing RepositoryPattern/TagPattern fails
* SDK failure surfaces via fail_sdk_error
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from types import SimpleNamespace

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import tcr_immutable_tag_rule as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    FakeModels,
    FakeResource,
    module_args,
    run,
)


def _rule(rule_id, ns, repo, tag, disabled=False):
    return FakeResource({
        "RuleId": rule_id,
        "NsName": ns,
        "RepositoryPattern": repo,
        "TagPattern": tag,
        "RepositoryDecoration": "repoMatches",
        "TagDecoration": "matches",
        "Disabled": disabled,
    })


class FakeTcrClient(object):
    """In-memory TCR client mutating an immutable-tag-rule store."""

    def __init__(self, rules=None):
        self.rules = list(rules or [])
        self._seq = 0
        self.calls = []

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def DescribeImmutableTagRules(self, request):
        self._record("DescribeImmutableTagRules", request)
        registry = getattr(request, "RegistryId", None)
        matched = [r for r in self.rules if r._data.get("RegistryId", registry) == registry]
        return SimpleNamespace(Rules=[FakeResource(dict(t._data)) for t in matched],
                               Total=len(matched), EmptyNs=False, RequestId="req-fake")

    def CreateImmutableTagRules(self, request):
        self._record("CreateImmutableTagRules", request)
        self._seq += 1
        rule = request.Rule if isinstance(getattr(request, "Rule", None), dict) else {}
        item = _rule(self._seq, getattr(request, "NamespaceName", ""), rule.get("RepositoryPattern"),
                     rule.get("TagPattern"), rule.get("Disabled", False))
        item._data["RegistryId"] = getattr(request, "RegistryId", None)
        self.rules.append(item)
        return SimpleNamespace(RequestId="req-fake")

    def DeleteImmutableTagRules(self, request):
        self._record("DeleteImmutableTagRules", request)
        registry = getattr(request, "RegistryId", None)
        ns = getattr(request, "NamespaceName", None)
        rid = getattr(request, "RuleId", None)
        self.rules = [r for r in self.rules
                      if not (r._data.get("RegistryId", registry) == registry
                              and r.NsName == ns and r.RuleId == rid)]
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake, models=None):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load_tcr", lambda: (models or FakeModels(), SimpleNamespace(TcrClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


RULE = {"RepositoryPattern": "web-*", "TagPattern": "latest", "RepositoryDecoration": "repoMatches", "TagDecoration": "matches"}


# ---------------------------------------------------------------------------
# create / delete flows
# ---------------------------------------------------------------------------


def test_create_when_missing(monkeypatch):
    fake = FakeTcrClient(rules=[])
    _make_module(monkeypatch, fake)
    module_args(registry_id="tcr-abc", namespace_name="prod", rule=dict(RULE), state="present")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["exists"] is True
    assert result["rule_id"] is not None
    ops = [c for c, unused in fake.calls]
    assert ops[0] == "DescribeImmutableTagRules"
    assert "CreateImmutableTagRules" in ops
    assert "DeleteImmutableTagRules" not in ops
    created = [r for c, r in fake.calls if c == "CreateImmutableTagRules"][0]
    assert created.Rule["RepositoryPattern"] == "web-*"
    assert created.NamespaceName == "prod"


def test_delete_when_present(monkeypatch):
    fake = FakeTcrClient(rules=[_rule(1, "prod", "web-*", "latest")])
    fake.rules[0]._data["RegistryId"] = "tcr-abc"
    _make_module(monkeypatch, fake)
    module_args(registry_id="tcr-abc", namespace_name="prod", rule=dict(RULE), state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["exists"] is False
    assert "DeleteImmutableTagRules" in [c for c, unused in fake.calls]
    assert "CreateImmutableTagRules" not in [c for c, unused in fake.calls]
    assert fake.rules == []


# ---------------------------------------------------------------------------
# idempotent no-op flows
# ---------------------------------------------------------------------------


def test_already_present_is_idempotent(monkeypatch):
    fake = FakeTcrClient(rules=[_rule(1, "prod", "web-*", "latest")])
    fake.rules[0]._data["RegistryId"] = "tcr-abc"
    _make_module(monkeypatch, fake)
    module_args(registry_id="tcr-abc", namespace_name="prod", rule=dict(RULE), state="present")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["rule_id"] == 1
    assert [c for c, unused in fake.calls] == ["DescribeImmutableTagRules"]
    assert "CreateImmutableTagRules" not in [c for c, unused in fake.calls]


def test_absent_when_missing_is_idempotent(monkeypatch):
    fake = FakeTcrClient(rules=[])
    _make_module(monkeypatch, fake)
    module_args(registry_id="tcr-abc", namespace_name="prod", rule=dict(RULE), state="absent")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert "DeleteImmutableTagRules" not in [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# check-mode dry runs
# ---------------------------------------------------------------------------


def test_create_check_mode_is_dry_run(monkeypatch):
    fake = FakeTcrClient(rules=[])
    _make_module(monkeypatch, fake)
    module_args(registry_id="tcr-abc", namespace_name="prod", rule=dict(RULE), state="present",
                _ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert "CreateImmutableTagRules" not in [c for c, unused in fake.calls]
    assert fake.rules == []


def test_delete_check_mode_is_dry_run(monkeypatch):
    fake = FakeTcrClient(rules=[_rule(1, "prod", "web-*", "latest")])
    fake.rules[0]._data["RegistryId"] = "tcr-abc"
    _make_module(monkeypatch, fake)
    module_args(registry_id="tcr-abc", namespace_name="prod", rule=dict(RULE), state="absent",
                _ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert "DeleteImmutableTagRules" not in [c for c, unused in fake.calls]
    assert len(fake.rules) == 1


# ---------------------------------------------------------------------------
# error / validation paths
# ---------------------------------------------------------------------------


def test_missing_patterns_fails(monkeypatch):
    fake = FakeTcrClient(rules=[])
    _make_module(monkeypatch, fake)
    module_args(registry_id="tcr-abc", namespace_name="prod", rule={"RepositoryDecoration": "repoMatches"},
                state="present")
    try:
        run(mod.run_module)
    except SystemExit as exc:
        payload = getattr(exc, "args", [{}])[0]
        assert payload.get("failed")
    else:
        raise AssertionError("expected missing-pattern validation to fail the module")


def test_sdk_failure_fails(monkeypatch):
    fake = FakeTcrClient(rules=[])
    fake.CreateImmutableTagRules = lambda request: (_ for _ in ()).throw(RuntimeError("boom"))
    _make_module(monkeypatch, fake)
    module_args(registry_id="tcr-abc", namespace_name="prod", rule=dict(RULE), state="present")
    try:
        run(mod.run_module)
    except SystemExit as exc:
        payload = getattr(exc, "args", [{}])[0]
        assert payload.get("failed")
    else:
        raise AssertionError("expected SDK failure to fail the module")
