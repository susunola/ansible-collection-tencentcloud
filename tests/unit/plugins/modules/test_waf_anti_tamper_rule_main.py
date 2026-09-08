"""Unit tests for the waf_anti_tamper_rule write module (run_module flows).

Drives ``run_module()`` end to end against an in-memory fake WAF client whose
write operations mutate the rule store, so the post-write describe refetch
converges immediately.

Scenario matrix:

* absent on a missing rule (idempotent no-op)
* absent with a matching rule (check-mode dry run and the real delete)
* creation when missing (name/uri guard, check-mode dry run and the happy
  path)
* no-op when nothing drifts
* name / uri / enable-state drift updates
* the ``refresh`` cache-refresh flag and its check mode
* the ambiguous-name guard and the required_one_of guard
* the blanket ``Tencent Cloud API request failed`` failure path
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import waf_anti_tamper_rule as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

DOMAIN = "www.example.com"
RULE_ID = 1

RULE = {
    "Id": RULE_ID,
    "Name": "protect-homepage",
    "Uri": "/index.html",
    "Status": 1,
    "Domain": DOMAIN,
}


def _rule(**overrides):
    item = copy.deepcopy(RULE)
    item.update(overrides)
    return item


def _base(**overrides):
    # NOTE: keys carrying ``choices`` (state) must not be pre-filled with
    # None. rule_id/name are a required_one_of pair so the _id_args/_name_args
    # helpers supply exactly one of them. domain is always required.
    params = {"domain": DOMAIN}
    params.update(overrides)
    return module_args(**params)


def _name_args(**overrides):
    params = {"domain": DOMAIN, "name": "protect-homepage"}
    params.update(overrides)
    return module_args(**params)


def _id_args(**overrides):
    params = {"domain": DOMAIN, "rule_id": RULE_ID}
    params.update(overrides)
    return module_args(**params)


class FakeWafClient(object):
    """In-memory WAF client mutating a small anti-tamper rule store."""

    def __init__(self, rules=None):
        self.rules = [copy.deepcopy(t) for t in (rules or [])]
        self.calls = []

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def _rule(self, rule_id):
        for item in self.rules:
            if item.get("Id") == rule_id:
                return item
        return None

    def DescribeAntiFakeRules(self, request):
        self._record("DescribeAntiFakeRules", request)
        page = [dict(t) for t in self.rules if t.get("Domain") == getattr(request, "Domain", None)]
        return SimpleNamespace(
            Data=[FakeResource(t) for t in page],
            Total=len(page),
        )

    def AddAntiFakeUrl(self, request):
        self._record("AddAntiFakeUrl", request)
        rule_id = max([t.get("Id", 0) for t in self.rules] or [0]) + 1
        self.rules.append(
            {
                "Id": rule_id,
                "Name": getattr(request, "Name", None),
                "Uri": getattr(request, "Uri", None),
                "Status": 1,
                "Domain": getattr(request, "Domain", None),
            }
        )
        return SimpleNamespace(Id=rule_id, RequestId="req-fake")

    def ModifyAntiFakeUrl(self, request):
        self._record("ModifyAntiFakeUrl", request)
        item = self._rule(getattr(request, "Id", None))
        if item is not None:
            item["Name"] = getattr(request, "Name", item.get("Name"))
            item["Uri"] = getattr(request, "Uri", item.get("Uri"))
        return SimpleNamespace(RequestId="req-fake")

    def ModifyAntiFakeUrlStatus(self, request):
        self._record("ModifyAntiFakeUrlStatus", request)
        for rule_id in (getattr(request, "Ids", None) or []):
            item = self._rule(rule_id)
            if item is not None:
                item["Status"] = getattr(request, "Status", item.get("Status"))
        return SimpleNamespace(RequestId="req-fake")

    def FreshAntiFakeUrl(self, request):
        self._record("FreshAntiFakeUrl", request)
        return SimpleNamespace(RequestId="req-fake")

    def DeleteAntiFakeUrl(self, request):
        self._record("DeleteAntiFakeUrl", request)
        self.rules = [t for t in self.rules if t.get("Id") != getattr(request, "Id", None)]
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake, models=None):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (models or FakeModels(), SimpleNamespace(WafClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


# ---------------------------------------------------------------------------
# absent flows
# ---------------------------------------------------------------------------


def test_absent_missing_rule_is_idempotent(monkeypatch):
    fake = FakeWafClient(rules=[])
    _make_module(monkeypatch, fake)
    _base(state="absent", rule_id=999)
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["rule"] is None
    assert [c for c, unused in fake.calls] == ["DescribeAntiFakeRules"]


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeWafClient(rules=[_rule()])
    _make_module(monkeypatch, fake)
    _id_args(_ansible_check_mode=True, state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["rule"]["Id"] == RULE_ID
    assert len(fake.rules) == 1
    assert "DeleteAntiFakeUrl" not in [c for c, unused in fake.calls]


def test_absent_deletes_rule(monkeypatch):
    fake = FakeWafClient(rules=[_rule()])
    _make_module(monkeypatch, fake)
    _id_args(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["rule"] is None
    assert fake.rules == []
    assert "DeleteAntiFakeUrl" in [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# creation flows
# ---------------------------------------------------------------------------


def test_present_requires_name_and_uri(monkeypatch):
    fake = FakeWafClient(rules=[_rule()])
    _make_module(monkeypatch, fake)
    _id_args(state="present")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "name and uri are required when state=present" in exc.value.args[0]["msg"]


def test_present_requires_uri(monkeypatch):
    fake = FakeWafClient(rules=[])
    _make_module(monkeypatch, fake)
    _name_args(state="present")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "name and uri are required when state=present" in exc.value.args[0]["msg"]


def test_create_check_mode_is_dry_run(monkeypatch):
    fake = FakeWafClient(rules=[])
    _make_module(monkeypatch, fake)
    _name_args(_ansible_check_mode=True, state="present", uri="/index.html")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["rule"] is None
    assert fake.rules == []
    assert "AddAntiFakeUrl" not in [c for c, unused in fake.calls]


def test_create_rule(monkeypatch):
    fake = FakeWafClient(rules=[])
    _make_module(monkeypatch, fake)
    _name_args(state="present", uri="/index.html", enabled=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    rule = result["rule"]
    assert rule["Name"] == "protect-homepage"
    assert rule["Uri"] == "/index.html"
    assert rule["Status"] == 1
    assert len(fake.rules) == 1
    ops = [c for c, unused in fake.calls]
    assert ops[0] == "DescribeAntiFakeRules"
    assert "AddAntiFakeUrl" in ops
    assert "ModifyAntiFakeUrlStatus" in ops


# ---------------------------------------------------------------------------
# existing-rule flows
# ---------------------------------------------------------------------------


def test_existing_no_drift_is_idempotent(monkeypatch):
    fake = FakeWafClient(rules=[_rule()])
    _make_module(monkeypatch, fake)
    _name_args(state="present", uri="/index.html")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["rule"]["Id"] == RULE_ID
    assert "ModifyAntiFakeUrl" not in [c for c, unused in fake.calls]
    assert "ModifyAntiFakeUrlStatus" not in [c for c, unused in fake.calls]


def test_rename_rule_via_id(monkeypatch):
    fake = FakeWafClient(rules=[_rule()])
    _make_module(monkeypatch, fake)
    _id_args(state="present", name="renamed-homepage", uri="/index.html")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["rule"]["Name"] == "renamed-homepage"
    assert fake.rules[0]["Name"] == "renamed-homepage"
    assert "ModifyAntiFakeUrl" in [c for c, unused in fake.calls]


def test_update_uri_and_disable(monkeypatch):
    fake = FakeWafClient(rules=[_rule()])
    _make_module(monkeypatch, fake)
    _id_args(state="present", name="protect-homepage", uri="/about.html", enabled=False)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["rule"]["Uri"] == "/about.html"
    assert result["rule"]["Status"] == 0
    assert fake.rules[0]["Uri"] == "/about.html"
    assert fake.rules[0]["Status"] == 0
    ops = [c for c, unused in fake.calls]
    assert "ModifyAntiFakeUrl" in ops
    assert "ModifyAntiFakeUrlStatus" in ops


def test_enable_rule(monkeypatch):
    fake = FakeWafClient(rules=[_rule(Status=0)])
    _make_module(monkeypatch, fake)
    _id_args(state="present", name="protect-homepage", uri="/index.html", enabled=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["rule"]["Status"] == 1
    assert fake.rules[0]["Status"] == 1
    assert "ModifyAntiFakeUrlStatus" in [c for c, unused in fake.calls]


def test_refresh_triggers_cache_refresh(monkeypatch):
    fake = FakeWafClient(rules=[_rule()])
    _make_module(monkeypatch, fake)
    _id_args(state="present", name="protect-homepage", uri="/index.html", refresh=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert "FreshAntiFakeUrl" in [c for c, unused in fake.calls]


def test_update_check_mode_is_dry_run(monkeypatch):
    fake = FakeWafClient(rules=[_rule()])
    _make_module(monkeypatch, fake)
    _id_args(_ansible_check_mode=True, state="present", name="renamed-homepage", uri="/about.html", enabled=False, refresh=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert fake.rules == [_rule()]
    assert "ModifyAntiFakeUrl" not in [c for c, unused in fake.calls]
    assert "ModifyAntiFakeUrlStatus" not in [c for c, unused in fake.calls]
    assert "FreshAntiFakeUrl" not in [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# guards / validation / failure paths
# ---------------------------------------------------------------------------


def test_multiple_rules_with_same_name_fail(monkeypatch):
    fake = FakeWafClient(rules=[_rule(), _rule(Id=2)])
    _make_module(monkeypatch, fake)
    _name_args(state="present", uri="/index.html")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "Multiple WAF anti-tamper rules matched; specify rule_id" in payload["msg"]


def test_missing_identity_fails(monkeypatch):
    fake = FakeWafClient(rules=[])
    _make_module(monkeypatch, fake)
    _base(state="absent")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "rule_id" in payload["msg"]
    assert "name" in payload["msg"]


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeAntiFakeRules(self, request):
            raise Boom("connection dropped")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    _id_args(state="present", name="protect-homepage", uri="/index.html")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]
