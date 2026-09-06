"""Unit tests for the waf_custom_rule write module (helpers + run_module).

Covers the create / drift-update / destroy flows of
``plugins/modules/waf_custom_rule.py`` with an in-memory fake WAF client
whose write operations mutate the rule store, so the module's post-write
``find`` refetch converges immediately. Rules are matched by ``RuleId``
(int) or by name over a single DescribeCustomRuleList call
(``response.RuleList``). Create stringifies SortId/ExpireTime while
Modify keeps ints — each path is asserted. ``Strategy`` entries
round-trip through ``_deserialize``. In check mode a would-be create
reports ``rule=None`` and a would-be update the pre-change rule.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import waf_custom_rule as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

RULE = {
    "RuleId": 7,
    "Name": "block-admin",
    "Domain": "api.example.com",
    "SortId": 100,
    "ActionType": "1",
    "Strategies": [{"Field": "URI", "CompareFunc": "contains", "Content": "/admin", "CaseNotSensitive": 1}],
    "Redirect": "",
    "ExpireTime": 0,
    "Edition": "sparta-waf",
    "LogicalOp": "and",
    "ActionRatio": 100,
}


def _rule(**overrides):
    """API-shaped rule dict isolated from the shared constant."""
    item = copy.deepcopy(RULE)
    item.update(overrides)
    return item


def _params(**overrides):
    """Module parameters pre-filled from the argument spec defaults."""
    params = {
        "state": "present",
        "domain": "api.example.com",
        "rule_id": None,
        "name": "block-admin",
        "edition": "sparta-waf",
        "priority": 100,
        "action": "1",
        "strategies": [{"Field": "URI", "CompareFunc": "contains", "Content": "/admin", "CaseNotSensitive": 1}],
        "logical_operator": "and",
        "redirect": "",
        "expire_time": 0,
        "action_ratio": 100,
    }
    params.update(overrides)
    return params


def _run_args(**extra):
    """module_args() pre-filled with every module parameter (None dropped)."""
    args = dict(_params())
    args.update(extra)
    return module_args(**{k: v for k, v in args.items() if v is not None})


class _StrategyModel(object):
    """SDK model whose payload round-trips through _deserialize."""

    def __init__(self):
        self._data = {}

    def __getattr__(self, name):
        try:
            return self._data[name]
        except KeyError:
            raise AttributeError(name)

    def _deserialize(self, payload):
        self._data.update(payload or {})
        return self

    def _serialize(self, allow_none=True):
        return dict(self._data)


class FakeWafModels(FakeModels):
    """FakeModels whose Strategy implements _deserialize."""

    def __getattr__(self, name):
        if name == "Strategy":
            return _StrategyModel
        return super(FakeWafModels, self).__getattr__(name)


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
    """In-memory WafClient stand-in for custom rules.

    Stores API-shaped rule dicts keyed by integer RuleId. Describe returns
    the whole store in one page (the module issues a single call);
    write operations mutate the store so post-write refetches converge.
    """

    def __init__(self, rules=None):
        self.rules = [copy.deepcopy(r) for r in (rules or [])]
        self.calls = []
        self._next_id = 100

    def _record(self, name, request):
        self.calls.append((name, request))
        return request

    def _store_strategies(self, request):
        return [s._serialize() if hasattr(s, "_serialize") else dict(s) for s in request.Strategies]

    def DescribeCustomRuleList(self, request):
        self._record("DescribeCustomRuleList", request)
        return SimpleNamespace(RuleList=[FakeResource(dict(r)) for r in self.rules], RequestId="req-fake")

    def AddCustomRule(self, request):
        self._record("AddCustomRule", request)
        rule_id = self._next_id
        self._next_id += 1
        self.rules.append(
            {
                "RuleId": rule_id,
                "Name": request.Name,
                "Domain": request.Domain,
                "SortId": int(request.SortId),
                "ActionType": request.ActionType,
                "Strategies": self._store_strategies(request),
                "Redirect": request.Redirect or "",
                "ExpireTime": int(request.ExpireTime),
                "Edition": request.Edition,
                "LogicalOp": request.LogicalOp,
                "ActionRatio": request.ActionRatio,
            }
        )
        return SimpleNamespace(RuleId=rule_id, RequestId="req-fake")

    def ModifyCustomRule(self, request):
        self._record("ModifyCustomRule", request)
        for stored in self.rules:
            if stored.get("RuleId") != request.RuleId:
                continue
            stored["Name"] = request.RuleName
            stored["Domain"] = request.Domain
            stored["SortId"] = request.SortId
            stored["ActionType"] = request.RuleAction
            stored["Strategies"] = self._store_strategies(request)
            stored["Redirect"] = request.Redirect or ""
            stored["ExpireTime"] = request.ExpireTime
            stored["Edition"] = request.Edition
            stored["LogicalOp"] = request.LogicalOp
            stored["ActionRatio"] = request.ActionRatio
        return SimpleNamespace(RequestId="req-fake")

    def DeleteCustomRule(self, request):
        self._record("DeleteCustomRule", request)
        self.rules = [r for r in self.rules if r.get("RuleId") != int(request.RuleId)]
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake):
    """Wire the shared monkeypatches and return the fake client."""
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(
        mod,
        "_load",
        lambda: (FakeWafModels(), SimpleNamespace(WafClient=object)),
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
# request-builder / normalisation helper tests
# ---------------------------------------------------------------------------


def test_build_list_fields():
    request = mod.build_list(FakeWafModels(), _params())
    assert request.Domain == "api.example.com"
    assert request.Offset == 0
    assert request.Limit == 100


def test_strategies_builder_deserializes():
    items = mod._strategies(FakeWafModels(), [{"Field": "URI", "CompareFunc": "contains", "Content": "/admin"}])
    assert items[0].Field == "URI"
    assert items[0].Content == "/admin"


def test_create_request_stringifies_numeric_fields():
    request = mod.build_create(FakeWafModels(), _params(priority=50, expire_time=1000))
    assert request.Domain == "api.example.com"
    assert request.Name == "block-admin"
    assert request.SortId == "50"  # str on create
    assert request.ExpireTime == "1000"  # str on create
    assert request.ActionType == "1"
    assert request.Edition == "sparta-waf"
    assert request.LogicalOp == "and"
    assert request.ActionRatio == 100
    assert request.Strategies[0].Content == "/admin"
    assert not hasattr(request, "RuleId")


def test_update_request_keeps_int_fields():
    request = mod.build_update(FakeWafModels(), _params(priority=50, expire_time=1000), 7)
    assert request.RuleId == 7
    assert request.RuleName == "block-admin"
    assert request.Domain == "api.example.com"
    assert request.SortId == 50  # int on update
    assert request.ExpireTime == 1000  # int on update
    assert request.RuleAction == "1"


def test_delete_request_stringifies_rule_id():
    request = mod.build_delete(FakeWafModels(), _params(), 7)
    assert request.Domain == "api.example.com"
    assert request.RuleId == "7"  # str on delete
    assert request.Edition == "sparta-waf"


def test_desired_maps_fields():
    target = mod.desired(_params(priority=50, action="3", expire_time=1000))
    assert target["Name"] == "block-admin"
    assert target["SortId"] == 50
    assert target["ActionType"] == "3"
    assert target["ExpireTime"] == 1000


def test_comparable_normalises_defaults():
    value = mod.comparable({"Name": "x"})
    assert value["SortId"] == 0
    assert value["ActionType"] == "None"  # str(None)
    assert value["Strategies"] == []
    assert value["Redirect"] == ""
    assert value["ExpireTime"] == 0
    assert value["LogicalOp"] == "and"
    assert value["ActionRatio"] == 100


def test_comparable_coerces_action_type_string():
    value = mod.comparable({"Name": "x", "ActionType": 2, "SortId": "50", "ExpireTime": "1000"})
    assert value["ActionType"] == "2"
    assert value["SortId"] == 50
    assert value["ExpireTime"] == 1000


# ---------------------------------------------------------------------------
# find tests
# ---------------------------------------------------------------------------


def test_find_by_rule_id(monkeypatch):
    fake = FakeWafClient([_rule(), _rule(RuleId=8, Name="other")])
    _make_module(monkeypatch, fake)
    module = FakeModule(_params(rule_id=8, name=None))
    value = mod.find(module, fake, FakeWafModels(), module.params)
    assert value["RuleId"] == 8


def test_find_by_name(monkeypatch):
    fake = FakeWafClient([_rule(Name="other"), _rule()])
    _make_module(monkeypatch, fake)
    module = FakeModule(_params(name="block-admin"))
    value = mod.find(module, fake, FakeWafModels(), module.params)
    assert value["RuleId"] == 7


def test_find_no_match_returns_none(monkeypatch):
    fake = FakeWafClient([_rule()])
    _make_module(monkeypatch, fake)
    module = FakeModule(_params(name="ghost"))
    assert mod.find(module, fake, FakeWafModels(), module.params) is None


def test_find_multiple_name_matches_fails(monkeypatch):
    fake = FakeWafClient([_rule(), _rule(RuleId=8)])
    _make_module(monkeypatch, fake)
    module = FakeModule(_params(name="block-admin"))
    with pytest.raises(AnsibleFailJson) as exc:
        mod.find(module, fake, FakeWafModels(), module.params)
    payload = exc.value.args[0]
    assert "Multiple WAF custom rules have the requested name" in payload["msg"]
    assert payload["name"] == "block-admin"


# ---------------------------------------------------------------------------
# run_module main-path tests
# ---------------------------------------------------------------------------


def test_required_one_of_enforced():
    module_args(domain="api.example.com")  # neither rule_id nor name
    with pytest.raises(AnsibleFailJson):
        run(mod.run_module)


def test_present_requires_name():
    module_args(domain="api.example.com", rule_id=7, state="present")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "name is required when state=present" in exc.value.args[0]["msg"]


def test_present_creates_rule(monkeypatch):
    fake = FakeWafClient()
    _make_module(monkeypatch, fake)
    _run_args()
    result = run(mod.run_module)
    assert result["changed"] is True
    rule = result["rule"]
    assert rule["RuleId"] == 100
    assert rule["Name"] == "block-admin"
    assert rule["ActionType"] == "1"
    assert rule["SortId"] == 100
    names = [c[0] for c in fake.calls]
    assert names.count("DescribeCustomRuleList") == 2  # find + refetch
    assert names.count("AddCustomRule") == 1
    add = [c for c in fake.calls if c[0] == "AddCustomRule"][0][1]
    assert add.SortId == "100"
    assert add.ExpireTime == "0"


def test_present_noop_returns_unchanged(monkeypatch):
    fake = FakeWafClient([_rule()])
    _make_module(monkeypatch, fake)
    _run_args()
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["rule"]["RuleId"] == 7
    names = [c[0] for c in fake.calls]
    assert "ModifyCustomRule" not in names
    assert "AddCustomRule" not in names


def test_present_priority_drift_triggers_update(monkeypatch):
    fake = FakeWafClient([_rule()])
    _make_module(monkeypatch, fake)
    _run_args(rule_id=7, priority=50)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["rule"]["SortId"] == 50
    names = [c[0] for c in fake.calls]
    assert names.count("ModifyCustomRule") == 1
    modify = [c for c in fake.calls if c[0] == "ModifyCustomRule"][0][1]
    assert modify.RuleId == 7
    assert modify.SortId == 50  # int on update


def test_present_action_drift_triggers_update(monkeypatch):
    fake = FakeWafClient([_rule()])
    _make_module(monkeypatch, fake)
    _run_args(rule_id=7, action="3")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["rule"]["ActionType"] == "3"
    modify = [c for c in fake.calls if c[0] == "ModifyCustomRule"][0][1]
    assert modify.RuleAction == "3"


def test_present_strategy_drift_triggers_update(monkeypatch):
    fake = FakeWafClient([_rule()])
    _make_module(monkeypatch, fake)
    new_strategy = [{"Field": "URI", "CompareFunc": "contains", "Content": "/v2", "CaseNotSensitive": 1}]
    _run_args(rule_id=7, strategies=new_strategy)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["rule"]["Strategies"][0]["Content"] == "/v2"
    modify = [c for c in fake.calls if c[0] == "ModifyCustomRule"][0][1]
    assert modify.Strategies[0].Content == "/v2"


def test_present_rename_by_id_triggers_update(monkeypatch):
    fake = FakeWafClient([_rule()])
    _make_module(monkeypatch, fake)
    _run_args(rule_id=7, name="renamed")  # identified by id, name drifts
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["rule"]["Name"] == "renamed"
    modify = [c for c in fake.calls if c[0] == "ModifyCustomRule"][0][1]
    assert modify.RuleName == "renamed"


def test_present_redirect_drift_triggers_update(monkeypatch):
    fake = FakeWafClient([_rule()])
    _make_module(monkeypatch, fake)
    _run_args(rule_id=7, redirect="https://blocked.example.com")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["rule"]["Redirect"] == "https://blocked.example.com"
    assert "ModifyCustomRule" in [c[0] for c in fake.calls]


def test_present_logical_op_drift_triggers_update(monkeypatch):
    fake = FakeWafClient([_rule()])
    _make_module(monkeypatch, fake)
    _run_args(rule_id=7, logical_operator="or")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["rule"]["LogicalOp"] == "or"


def test_present_expire_time_drift_triggers_update(monkeypatch):
    fake = FakeWafClient([_rule()])
    _make_module(monkeypatch, fake)
    _run_args(rule_id=7, expire_time=4102444800)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["rule"]["ExpireTime"] == 4102444800
    modify = [c for c in fake.calls if c[0] == "ModifyCustomRule"][0][1]
    assert modify.ExpireTime == 4102444800  # int on update


def test_check_mode_create_is_dry_run(monkeypatch):
    fake = FakeWafClient()
    _make_module(monkeypatch, fake)
    module_args(_ansible_check_mode=True, **{k: v for k, v in _params().items() if v is not None})
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["rule"] is None  # no refetch in check mode
    assert [c[0] for c in fake.calls] == ["DescribeCustomRuleList"]  # find only
    assert not any("AddCustomRule" == c[0] for c in fake.calls)


def test_check_mode_update_is_dry_run(monkeypatch):
    fake = FakeWafClient([_rule()])
    _make_module(monkeypatch, fake)
    module_args(_ansible_check_mode=True, **{k: v for k, v in _params(rule_id=7, priority=50).items() if v is not None})
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["rule"]["RuleId"] == 7  # pre-change rule reported
    assert not any("ModifyCustomRule" == c[0] for c in fake.calls)


def test_sdk_error_is_reported(monkeypatch):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(
        mod,
        "_load",
        lambda: (FakeWafModels(), SimpleNamespace(WafClient=object)),
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


def test_absent_deletes_rule(monkeypatch):
    fake = FakeWafClient([_rule()])
    _make_module(monkeypatch, fake)
    _run_args(state="absent", name="block-admin")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["rule"] is None
    delete = [c for c in fake.calls if c[0] == "DeleteCustomRule"][0][1]
    assert delete.Domain == "api.example.com"
    assert delete.RuleId == "7"  # str on delete
    assert fake.rules == []


def test_absent_not_found_is_noop(monkeypatch):
    fake = FakeWafClient([_rule()])
    _make_module(monkeypatch, fake)
    _run_args(state="absent", name="ghost")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["rule"] is None
    assert not any("DeleteCustomRule" == c[0] for c in fake.calls)


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeWafClient([_rule()])
    _make_module(monkeypatch, fake)
    module_args(_ansible_check_mode=True, **{k: v for k, v in _params(state="absent").items() if v is not None})
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["rule"]["RuleId"] == 7  # pre-change rule reported
    assert not any("DeleteCustomRule" == c[0] for c in fake.calls)
    assert len(fake.rules) == 1
