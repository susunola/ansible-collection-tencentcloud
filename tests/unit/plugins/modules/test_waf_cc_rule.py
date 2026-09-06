"""Unit tests for the waf_cc_rule write module (helpers + run_module).

Covers the create / drift-update / delete flows of
``plugins/modules/waf_cc_rule.py`` with an in-memory fake WAF client whose
write operations mutate the rule store, so the module's post-write ``find``
refetch converges immediately. Rules are matched by ``rule_id`` (int) or by
``name`` across the paged DescribeCCRuleList list; both create and update go
through the single UpsertCCRule call (``rule_id`` 0 for new rules, the
existing id otherwise), and value types are re-encoded to the API vocabulary
(Status 1/0, Advance ``"1"/"0"``, Limit/Interval/ActionType as strings, and
options as canonical JSON) before any comparison happens.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import waf_cc_rule as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

RULE = {
    "RuleId": 6001,
    "Name": "protect-login",
    "Status": 1,
    "Advance": "0",
    "Limit": "60",
    "Interval": "60",
    "ActionType": "22",
    "Priority": 50,
    "ValidTime": 600,
    "Url": "",
    "MatchFunc": 0,
    "Options": "[]",
    "SessionApplied": [],
    "LimitMethod": "only_limit",
    "LogicalOp": "and",
    "ActionRatio": 100,
}


def _rule_item(**overrides):
    """API-shaped rule dict isolated from the shared constant."""
    item = copy.deepcopy(RULE)
    item.update(overrides)
    return item


def _params(**overrides):
    """Module parameters pre-filled from the argument spec (base included)."""
    params = {
        "state": "present",
        "domain": "api.example.com",
        "rule_id": None,
        "name": "protect-login",
        "edition": "sparta-waf",
        "enabled": True,
        "threshold": 60,
        "interval": 60,
        "action": 22,
        "priority": 50,
        "valid_time": 600,
        "url": "",
        "match_function": 0,
        "advanced": False,
        "options": [],
        "session_ids": [],
        "limit_method": "only_limit",
        "logical_operator": "and",
        "action_ratio": 100,
        "retries": 5,
        "waiter_delay": 5,
        "waiter_timeout": 120,
    }
    params.update(overrides)
    return params


def _run_args(**extra):
    """module_args() pre-filled with every module parameter."""
    args = dict(_params())
    args.update(extra)
    return module_args(**args)


class FakeModule(object):
    """Minimal stand-in for helpers that need sdk_call / fail_json."""

    def __init__(self, params=None):
        self.params = params or _params()
        self.sdk_calls = []

    def sdk_call(self, operation, request):
        self.sdk_calls.append((operation, request))
        return operation(request)

    def fail_json(self, **kwargs):
        raise AnsibleFailJson(kwargs)


class FakeWafClient(object):
    """In-memory WafClient stand-in.

    Stores API-shaped rule dicts. DescribeCCRuleList pages over the store
    honouring Offset/Limit so find pagination is exercised; UpsertCCRule
    inserts (rule_id 0) or replaces (existing rule_id) a rule and returns the
    rule id, DeleteCCRule removes by id — post-write refetches converge.
    """

    def __init__(self, rules=None):
        self.rules = [copy.deepcopy(r) for r in (rules or [])]
        self.calls = []
        self._next_rule_id = 70000

    def _record(self, name, request):
        self.calls.append((name, request))
        return request

    def DescribeCCRuleList(self, request):
        self._record("DescribeCCRuleList", request)
        page = self.rules[request.Offset : request.Offset + request.Limit]
        return SimpleNamespace(
            Data=FakeResource(
                {
                    "Res": [FakeResource(dict(r)) for r in page],
                    "TotalCount": len(self.rules),
                }
            ),
            RequestId="req-fake",
        )

    def UpsertCCRule(self, request):
        self._record("UpsertCCRule", request)
        item = {
            "Name": request.Name,
            "Status": request.Status,
            "Advance": request.Advance,
            "Limit": request.Limit,
            "Interval": request.Interval,
            "ActionType": request.ActionType,
            "Priority": request.Priority,
            "ValidTime": request.ValidTime,
            "Url": request.Url,
            "MatchFunc": request.MatchFunc,
            "Options": request.OptionsArr,
            "SessionApplied": list(request.SessionApplied or []),
            "LimitMethod": request.LimitMethod,
            "LogicalOp": request.LogicalOp,
            "ActionRatio": request.ActionRatio,
        }
        if not request.RuleId:
            self._next_rule_id += 1
            item["RuleId"] = self._next_rule_id
            self.rules.append(item)
            return SimpleNamespace(RuleId=self._next_rule_id, RequestId="req-fake")
        for stored in self.rules:
            if stored.get("RuleId") == request.RuleId:
                stored.clear()
                stored.update(item)
                stored["RuleId"] = request.RuleId
        return SimpleNamespace(RuleId=request.RuleId, RequestId="req-fake")

    def DeleteCCRule(self, request):
        self._record("DeleteCCRule", request)
        self.rules = [r for r in self.rules if r.get("RuleId") != request.RuleId]
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake):
    """Wire the shared monkeypatches and return the fake client."""
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(
        mod,
        "_load",
        lambda: (FakeModels(), SimpleNamespace(WafClient=object)),
    )
    monkeypatch.setattr(
        TencentCloudModule,
        "create_client",
        lambda self, client_class, endpoint: fake,
    )
    return fake


class _BoomClient(object):
    """Every SDK call raises, so the module's wrapped error path is hit."""

    def __getattr__(self, name):
        def boom(*args, **kwargs):
            raise RuntimeError("service exploded")

        return boom


# ---------------------------------------------------------------------------
# canonical_options / request-builder helper tests
# ---------------------------------------------------------------------------


def test_canonical_options_empty_forms():
    assert mod.canonical_options(None) == "[]"
    assert mod.canonical_options([]) == "[]"
    assert mod.canonical_options("") == "[]"
    assert mod.canonical_options("[]") == "[]"


def test_canonical_options_compacts_and_sorts():
    assert mod.canonical_options([{"b": 1, "a": 2}]) == '[{"a":2,"b":1}]'
    assert mod.canonical_options('{"b":1,"a":2}') == '{"a":2,"b":1}'
    assert mod.canonical_options('[{"b":1,"a":2}]') == '[{"a":2,"b":1}]'
    assert mod.canonical_options([{"x": [3, 1, 2]}]) == '[{"x":[3,1,2]}]'


def test_describe_request_fields():
    request = mod.describe_request(FakeModels(), _params(), offset=7)
    assert request.Domain == "api.example.com"
    assert request.Offset == 7
    assert request.Limit == 100
    assert request.By == "ts_version"
    assert request.Order == "asc"


def test_upsert_request_encodes_api_values():
    request = mod.upsert_request(
        FakeModels(),
        _params(
            enabled=False,
            advanced=True,
            threshold=120,
            interval=30,
            action=26,
            url="/login",
            session_ids=[3, 1, 2],
            logical_operator="or",
        ),
    )
    assert request.Domain == "api.example.com"
    assert request.Name == "protect-login"
    assert request.Status == 0
    assert request.Advance == "1"
    assert request.Limit == "120"
    assert request.Interval == "30"
    assert request.ActionType == "26"
    assert request.Priority == 50
    assert request.ValidTime == 600
    assert request.Url == "/login"
    assert request.MatchFunc == 0
    assert request.OptionsArr == "[]"
    assert request.Edition == "sparta-waf"
    assert request.Type == 0
    assert request.RuleId == 0
    assert request.SessionApplied == [1, 2, 3]
    assert request.Length == len("/login")
    assert request.LimitMethod == "only_limit"
    assert request.LogicalOp == "or"
    assert request.ActionRatio == 100
    assert request.Source == ""
    assert request.JobType == "forever"
    assert request.ExpireTime == 0
    assert request.ValidStatus == 1


def test_upsert_request_options_canonicalised():
    request = mod.upsert_request(
        FakeModels(),
        _params(options=[{"op": "eq", "value": "x"}]),
        rule_id=6001,
    )
    assert request.OptionsArr == '[{"op":"eq","value":"x"}]'
    assert request.RuleId == 6001  # update keeps the existing id


def test_upsert_request_rule_id_defaults_zero():
    request = mod.upsert_request(FakeModels(), _params())
    assert request.RuleId == 0  # create


def test_delete_request_fields():
    request = mod.delete_request(FakeModels(), _params(name="protect-login"), 6001)
    assert request.Domain == "api.example.com"
    assert request.Name == "protect-login"
    assert request.Edition == "sparta-waf"
    assert request.RuleId == 6001


# ---------------------------------------------------------------------------
# comparable / desired tests
# ---------------------------------------------------------------------------


def test_comparable_normalises_api_dict():
    value = mod.comparable(_rule_item())
    assert value == {
        "Name": "protect-login",
        "Status": 1,
        "Advance": "0",
        "Limit": "60",
        "Interval": "60",
        "ActionType": "22",
        "Priority": 50,
        "ValidTime": 600,
        "Url": "",
        "MatchFunc": 0,
        "Options": "[]",
        "SessionApplied": [],
        "LimitMethod": "only_limit",
        "LogicalOp": "and",
        "ActionRatio": 100,
    }


def test_comparable_defaults_and_coercions():
    value = mod.comparable(
        {
            "Name": "x",
            "Advance": 1,
            "Limit": 30,
            "Interval": 10,
            "ActionType": "21",
            "SessionApplied": [2, 1],
        }
    )
    assert value["Status"] == 0
    assert value["Advance"] == "1"
    assert value["Limit"] == "30"
    assert value["Interval"] == "10"
    assert value["ActionType"] == "21"
    assert value["Priority"] == 0
    assert value["ValidTime"] == 0
    assert value["Url"] == ""
    assert value["MatchFunc"] == 0
    assert value["Options"] == "[]"
    assert value["SessionApplied"] == [1, 2]
    assert value["LimitMethod"] == "only_limit"
    assert value["LogicalOp"] == "and"
    assert value["ActionRatio"] == 100


def test_comparable_falls_back_to_options_arr():
    value = mod.comparable({"Name": "x", "OptionsArr": '[{"b":1,"a":2}]'})
    assert value["Options"] == '[{"a":2,"b":1}]'


def test_desired_matches_default_params():
    value = mod.desired(_params())
    assert value == {
        "Name": "protect-login",
        "Status": 1,
        "Advance": "0",
        "Limit": "60",
        "Interval": "60",
        "ActionType": "22",
        "Priority": 50,
        "ValidTime": 600,
        "Url": "",
        "MatchFunc": 0,
        "Options": "[]",
        "SessionApplied": [],
        "LimitMethod": "only_limit",
        "LogicalOp": "and",
        "ActionRatio": 100,
    }


def test_desired_encodes_disabled_and_advanced():
    value = mod.desired(_params(enabled=False, advanced=True, threshold=90, action=20, session_ids=[2, 1]))
    assert value["Status"] == 0
    assert value["Advance"] == "1"
    assert value["Limit"] == "90"
    assert value["ActionType"] == "20"
    assert value["SessionApplied"] == [1, 2]


# ---------------------------------------------------------------------------
# find tests
# ---------------------------------------------------------------------------


def test_find_no_match_returns_none(monkeypatch):
    fake = FakeWafClient([_rule_item()])
    _make_module(monkeypatch, fake)
    module = FakeModule(_params(name="no-such-rule"))
    assert mod.find(module, fake, FakeModels(), module.params) is None


def test_find_by_name(monkeypatch):
    fake = FakeWafClient([_rule_item(), _rule_item(RuleId=6002, Name="other")])
    _make_module(monkeypatch, fake)
    module = FakeModule(_params(name="protect-login"))
    value = mod.find(module, fake, FakeModels(), module.params)
    assert value["RuleId"] == 6001


def test_find_by_rule_id(monkeypatch):
    fake = FakeWafClient([_rule_item(), _rule_item(RuleId=6002, Name="other")])
    _make_module(monkeypatch, fake)
    module = FakeModule(_params(rule_id=6002, name=None))
    value = mod.find(module, fake, FakeModels(), module.params)
    assert value["RuleId"] == 6002


def test_find_multiple_matches_fails(monkeypatch):
    fake = FakeWafClient([_rule_item(), _rule_item(RuleId=6002)])
    _make_module(monkeypatch, fake)
    module = FakeModule(_params(name="protect-login"))
    with pytest.raises(AnsibleFailJson) as exc:
        mod.find(module, fake, FakeModels(), module.params)
    assert "Multiple WAF CC rules matched" in exc.value.args[0]["msg"]


def test_find_paginates_until_match(monkeypatch):
    rules = [_rule_item(RuleId=7000 + i, Name="bulk-%04d" % i) for i in range(250)]
    rules.append(_rule_item(RuleId=9999, Name="protect-login"))
    fake = FakeWafClient(rules)
    _make_module(monkeypatch, fake)
    module = FakeModule(_params(name="protect-login"))
    value = mod.find(module, fake, FakeModels(), module.params)
    assert value["RuleId"] == 9999
    list_calls = [c for c in fake.calls if c[0] == "DescribeCCRuleList"]
    assert len(list_calls) == 3  # pages of 100
    assert [c[1].Offset for c in list_calls] == [0, 100, 200]


# ---------------------------------------------------------------------------
# run_module main-path tests
# ---------------------------------------------------------------------------


def test_domain_is_required():
    module_args(state="present", name="protect-login")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "domain" in exc.value.args[0]["msg"]


def test_required_one_of_rule_id_or_name():
    module_args(state="present", domain="api.example.com")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "rule_id" in exc.value.args[0]["msg"]
    assert "name" in exc.value.args[0]["msg"]


def test_present_requires_name():
    module_args(state="present", domain="api.example.com", rule_id=6001)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert exc.value.args[0]["msg"] == "name is required when state=present"


def test_sdk_error_is_reported(monkeypatch):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(
        mod,
        "_load",
        lambda: (FakeModels(), SimpleNamespace(WafClient=object)),
    )
    monkeypatch.setattr(
        TencentCloudModule,
        "create_client",
        lambda self, client_class, endpoint: _BoomClient(),
    )
    _run_args()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert payload["error"] == "service exploded"


def test_present_creates_rule(monkeypatch):
    fake = FakeWafClient()
    _make_module(monkeypatch, fake)
    _run_args(url="/login", threshold=100)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["rule"]["RuleId"] == 70001
    assert result["rule"]["Name"] == "protect-login"
    assert result["rule"]["Limit"] == "100"
    names = [c[0] for c in fake.calls]
    assert names.count("DescribeCCRuleList") == 2  # find + refetch
    assert names.count("UpsertCCRule") == 1
    upsert = [c for c in fake.calls if c[0] == "UpsertCCRule"][0][1]
    assert upsert.RuleId == 0
    assert upsert.Status == 1
    assert upsert.Limit == "100"
    assert upsert.Length == len("/login")


def test_present_noop_returns_unchanged(monkeypatch):
    fake = FakeWafClient([_rule_item()])
    _make_module(monkeypatch, fake)
    _run_args()
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["rule"]["RuleId"] == 6001
    names = [c[0] for c in fake.calls]
    assert "UpsertCCRule" not in names
    assert "DeleteCCRule" not in names


def test_present_drift_triggers_update(monkeypatch):
    fake = FakeWafClient([_rule_item()])
    _make_module(monkeypatch, fake)
    _run_args(threshold=200)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["rule"]["RuleId"] == 6001
    assert result["rule"]["Limit"] == "200"
    upsert = [c for c in fake.calls if c[0] == "UpsertCCRule"][0][1]
    assert upsert.RuleId == 6001
    assert upsert.Limit == "200"
    assert len(fake.rules) == 1  # updated in place, no duplicate


def test_present_disable_toggle_triggers_update(monkeypatch):
    fake = FakeWafClient([_rule_item(Status=1)])
    _make_module(monkeypatch, fake)
    _run_args(enabled=False)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["rule"]["Status"] == 0
    upsert = [c for c in fake.calls if c[0] == "UpsertCCRule"][0][1]
    assert upsert.Status == 0


def test_present_rename_requires_rule_id(monkeypatch):
    fake = FakeWafClient([_rule_item(Name="old-name")])
    _make_module(monkeypatch, fake)
    _run_args(name="new-name", rule_id=6001)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["rule"]["Name"] == "new-name"
    assert result["rule"]["RuleId"] == 6001
    assert len(fake.rules) == 1  # renamed in place


def test_present_rename_by_name_alone_creates_duplicate(monkeypatch):
    # Matching happens by name alone, so an unknown name is treated as a
    # brand-new rule; renaming requires passing the existing rule_id.
    fake = FakeWafClient([_rule_item()])
    _make_module(monkeypatch, fake)
    _run_args(name="renamed-rule")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["rule"]["Name"] == "renamed-rule"
    assert len(fake.rules) == 2  # new rule added alongside the old one


def test_check_mode_create_is_dry_run(monkeypatch):
    fake = FakeWafClient()
    _make_module(monkeypatch, fake)
    module_args(_ansible_check_mode=True, **_params())
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["rule"] is None  # no real rule created in check mode
    assert not any("UpsertCCRule" == c[0] for c in fake.calls)


def test_check_mode_update_is_dry_run(monkeypatch):
    fake = FakeWafClient([_rule_item()])
    _make_module(monkeypatch, fake)
    module_args(_ansible_check_mode=True, **_params(threshold=300))
    result = run(mod.run_module)
    assert result["changed"] is True
    # No write happened, so the reported rule is the pre-change state.
    assert result["rule"]["Limit"] == "60"
    assert not any("UpsertCCRule" == c[0] for c in fake.calls)


def test_absent_removes_rule(monkeypatch):
    fake = FakeWafClient([_rule_item()])
    _make_module(monkeypatch, fake)
    _run_args(state="absent", name="protect-login")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["rule"] is None
    delete = [c for c in fake.calls if c[0] == "DeleteCCRule"][0][1]
    assert delete.RuleId == 6001
    assert fake.rules == []


def test_absent_by_rule_id_removes(monkeypatch):
    fake = FakeWafClient([_rule_item(), _rule_item(RuleId=6002, Name="other")])
    _make_module(monkeypatch, fake)
    _run_args(state="absent", rule_id=6002, name=None)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert [r["RuleId"] for r in fake.rules] == [6001]


def test_absent_not_found_is_noop(monkeypatch):
    fake = FakeWafClient([_rule_item()])
    _make_module(monkeypatch, fake)
    _run_args(state="absent", name="no-such-rule")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["rule"] is None
    assert not any("DeleteCCRule" == c[0] for c in fake.calls)


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeWafClient([_rule_item()])
    _make_module(monkeypatch, fake)
    module_args(_ansible_check_mode=True, **_params(state="absent", name="protect-login"))
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["rule"] is not None  # pre-change state reported
    assert not any("DeleteCCRule" == c[0] for c in fake.calls)
    assert len(fake.rules) == 1


def test_multiple_name_matches_fail(monkeypatch):
    fake = FakeWafClient([_rule_item(), _rule_item(RuleId=6002)])
    _make_module(monkeypatch, fake)
    _run_args()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "Multiple WAF CC rules matched" in exc.value.args[0]["msg"]
