"""Unit tests for the waf_custom_white_rule write module (helpers + run_module).

Covers the create / drift-update / destroy flows of
``plugins/modules/waf_custom_white_rule.py`` with an in-memory fake WAF
client whose write operations mutate the rule store, so the module's
post-write ``find`` refetch converges immediately. Rules are matched by
``rule_id`` (int) or by name across the paged DescribeCustomWhiteRule; the
create/update operation is always followed by a ModifyCustomWhiteRuleStatus
call that syncs the enabled flag. ``Strategy`` entries round-trip through
``_deserialize`` (SDK model shape), and AddCustomWhiteRule returns the new
id on the bare response. In check mode the module reports ``rule=None`` for
a would-be create and the pre-change rule for a would-be update.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import waf_custom_white_rule as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

RULE = {
    "RuleId": 7,
    "Name": "allow-health-check",
    "Domain": "api.example.com",
    "SortId": 100,
    "Bypass": "owasp,acl",
    "Strategies": [{"Field": "URI", "Arg": "", "CompareFunc": "prefix", "Content": "/health"}],
    "LogicalOp": "and",
    "ExpireTime": 0,
    "Status": 1,
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
        "name": "allow-health-check",
        "priority": 100,
        "bypass_modules": "owasp,acl",
        "strategies": [{"Field": "URI", "Arg": "", "CompareFunc": "prefix", "Content": "/health"}],
        "logical_operator": "and",
        "expire_time": 0,
        "enabled": True,
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
    """In-memory WafClient stand-in for precision allowlist rules.

    Stores API-shaped rule dicts keyed by integer RuleId. Describe pages
    over the store honouring Offset/Limit and reports TotalCount at the top
    level (mirroring the SDK); write operations mutate the store so
    post-write refetches converge.
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

    def DescribeCustomWhiteRule(self, request):
        self._record("DescribeCustomWhiteRule", request)
        page = self.rules[request.Offset : request.Offset + request.Limit]
        return SimpleNamespace(
            RuleList=[FakeResource(dict(r)) for r in page],
            TotalCount=len(self.rules),
            RequestId="req-fake",
        )

    def AddCustomWhiteRule(self, request):
        self._record("AddCustomWhiteRule", request)
        rule_id = self._next_id
        self._next_id += 1
        self.rules.append(
            {
                "RuleId": rule_id,
                "Name": request.Name,
                "Domain": request.Domain,
                "SortId": request.SortId,
                "Bypass": request.Bypass,
                "Strategies": self._store_strategies(request),
                "LogicalOp": request.LogicalOp,
                "ExpireTime": request.ExpireTime,
                "Status": 0,
            }
        )
        return SimpleNamespace(RuleId=rule_id, RequestId="req-fake")

    def ModifyCustomWhiteRule(self, request):
        self._record("ModifyCustomWhiteRule", request)
        for stored in self.rules:
            if stored.get("RuleId") != request.RuleId:
                continue
            stored["Name"] = request.RuleName
            stored["Domain"] = request.Domain
            stored["SortId"] = request.SortId
            stored["Bypass"] = request.Bypass
            stored["Strategies"] = self._store_strategies(request)
            stored["LogicalOp"] = request.LogicalOp
            stored["ExpireTime"] = request.ExpireTime
        return SimpleNamespace(RequestId="req-fake")

    def ModifyCustomWhiteRuleStatus(self, request):
        self._record("ModifyCustomWhiteRuleStatus", request)
        for stored in self.rules:
            if stored.get("RuleId") != request.RuleId:
                continue
            stored["Status"] = request.Status
        return SimpleNamespace(RequestId="req-fake")

    def DeleteCustomWhiteRule(self, request):
        self._record("DeleteCustomWhiteRule", request)
        self.rules = [r for r in self.rules if r.get("RuleId") != request.RuleId]
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


def test_describe_request_fields():
    request = mod.describe_request(FakeWafModels(), _params())
    assert request.Domain == "api.example.com"
    assert request.Offset == 0
    assert request.Limit == 100


def test_describe_request_with_offset():
    request = mod.describe_request(FakeWafModels(), _params(), offset=100)
    assert request.Offset == 100


def test_strategies_builder_deserializes():
    items = mod._strategies(FakeWafModels(), [{"Field": "URI", "Arg": "", "CompareFunc": "prefix", "Content": "/health"}])
    assert items[0].Field == "URI"
    assert items[0].CompareFunc == "prefix"
    assert items[0].Content == "/health"


def test_apply_fills_shared_fields():
    request = mod._apply(FakeWafModels().AddCustomWhiteRuleRequest(), FakeWafModels(), _params(expire_time=123))
    assert request.Domain == "api.example.com"
    assert request.SortId == 100
    assert request.ExpireTime == 123
    assert request.LogicalOp == "and"
    assert request.Bypass == "owasp,acl"
    assert request.Strategies[0].Field == "URI"


def test_create_request_stringifies_sort_and_expiry():
    request = mod.create_request(FakeWafModels(), _params(expire_time=123))
    assert request.Name == "allow-health-check"
    assert request.SortId == "100"  # Add API expects strings
    assert request.ExpireTime == "123"


def test_update_request_fields():
    request = mod.update_request(FakeWafModels(), _params(priority=50), 7)
    assert request.RuleId == 7
    assert request.RuleName == "allow-health-check"
    assert request.SortId == 50  # Modify API keeps ints
    assert request.ExpireTime == 0


def test_status_request_enabled_and_disabled():
    request = mod.status_request(FakeWafModels(), _params(enabled=True), 7)
    assert request.Domain == "api.example.com"
    assert request.RuleId == 7
    assert request.Status == 1
    request = mod.status_request(FakeWafModels(), _params(enabled=False), 7)
    assert request.Status == 0


def test_delete_request_fields():
    request = mod.delete_request(FakeWafModels(), _params(), 7)
    assert request.Domain == "api.example.com"
    assert request.RuleId == 7


def test_sorted_normalises_and_orders_strategies():
    values = mod._sorted(
        [
            {"Field": "URI", "Arg": "", "CompareFunc": "prefix", "Content": "/health"},
            {"Field": "URI", "Arg": "", "CompareFunc": "prefix", "Content": "/admin"},
        ]
    )
    assert [v["Content"] for v in values] == ["/admin", "/health"]
    assert mod._sorted(None) == []


def test_comparable_normalises_and_sorts():
    value = mod.comparable(
        _rule(
            SortId="100",
            ExpireTime="0",
            Status=1,
            Strategies=[
                {"Field": "URI", "Arg": "", "CompareFunc": "prefix", "Content": "/admin"},
                {"Field": "URI", "Arg": "", "CompareFunc": "prefix", "Content": "/health"},
            ],
        )
    )
    assert value["SortId"] == 100
    assert value["ExpireTime"] == 0
    assert value["Status"] == 1
    assert [s["Content"] for s in value["Strategies"]] == ["/admin", "/health"]


def test_comparable_defaults():
    value = mod.comparable({"Name": "x", "SortId": None, "Bypass": None, "LogicalOp": None, "ExpireTime": None, "Strategies": None, "Status": None})
    assert value == {
        "Name": "x",
        "SortId": 0,
        "Bypass": "",
        "Strategies": [],
        "LogicalOp": "and",
        "ExpireTime": 0,
        "Status": 0,
    }


def test_desired_maps_enabled():
    assert mod.desired(_params(enabled=True))["Status"] == 1
    assert mod.desired(_params(enabled=False))["Status"] == 0
    assert mod.desired(_params(priority=5))["SortId"] == 5


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
    module = FakeModule(_params(name="allow-health-check"))
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
    module = FakeModule(_params(name="allow-health-check"))
    with pytest.raises(AnsibleFailJson) as exc:
        mod.find(module, fake, FakeWafModels(), module.params)
    assert "Multiple WAF precision allowlist rules matched" in exc.value.args[0]["msg"]


def test_find_paginates_past_100(monkeypatch):
    rules = [_rule(RuleId=1000 + i, Name="bulk-%04d" % i) for i in range(101)]
    rules.append(_rule())
    fake = FakeWafClient(rules)
    _make_module(monkeypatch, fake)
    module = FakeModule(_params(name="allow-health-check"))
    value = mod.find(module, fake, FakeWafModels(), module.params)
    assert value["RuleId"] == 7
    list_calls = [c for c in fake.calls if c[0] == "DescribeCustomWhiteRule"]
    assert len(list_calls) == 2  # pages of 100
    assert [c[1].Offset for c in list_calls] == [0, 100]


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
    assert rule["Name"] == "allow-health-check"
    assert rule["Status"] == 1
    names = [c[0] for c in fake.calls]
    assert names.count("DescribeCustomWhiteRule") == 2  # find + refetch
    assert names.count("AddCustomWhiteRule") == 1
    assert names.count("ModifyCustomWhiteRuleStatus") == 1
    add = [c for c in fake.calls if c[0] == "AddCustomWhiteRule"][0][1]
    assert add.SortId == "100"
    status = [c for c in fake.calls if c[0] == "ModifyCustomWhiteRuleStatus"][0][1]
    assert status.RuleId == 100
    assert status.Status == 1


def test_present_creates_disabled_rule(monkeypatch):
    fake = FakeWafClient()
    _make_module(monkeypatch, fake)
    _run_args(enabled=False)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["rule"]["Status"] == 0
    status = [c for c in fake.calls if c[0] == "ModifyCustomWhiteRuleStatus"][0][1]
    assert status.Status == 0


def test_present_noop_returns_unchanged(monkeypatch):
    fake = FakeWafClient([_rule()])
    _make_module(monkeypatch, fake)
    _run_args()
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["rule"]["RuleId"] == 7
    names = [c[0] for c in fake.calls]
    assert "ModifyCustomWhiteRule" not in names
    assert "AddCustomWhiteRule" not in names


def test_present_priority_drift_triggers_update(monkeypatch):
    fake = FakeWafClient([_rule()])
    _make_module(monkeypatch, fake)
    _run_args(rule_id=7, priority=50)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["rule"]["SortId"] == 50
    names = [c[0] for c in fake.calls]
    assert names.count("ModifyCustomWhiteRule") == 1
    assert names.count("ModifyCustomWhiteRuleStatus") == 1
    modify = [c for c in fake.calls if c[0] == "ModifyCustomWhiteRule"][0][1]
    assert modify.RuleId == 7
    assert modify.SortId == 50


def test_present_rename_by_id_triggers_update(monkeypatch):
    fake = FakeWafClient([_rule()])
    _make_module(monkeypatch, fake)
    _run_args(rule_id=7, name="renamed")  # identified by id, name drifts
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["rule"]["Name"] == "renamed"
    modify = [c for c in fake.calls if c[0] == "ModifyCustomWhiteRule"][0][1]
    assert modify.RuleId == 7
    assert modify.RuleName == "renamed"


def test_present_enable_drift_triggers_status_sync(monkeypatch):
    fake = FakeWafClient([_rule(Status=1)])
    _make_module(monkeypatch, fake)
    _run_args(rule_id=7, enabled=False)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["rule"]["Status"] == 0
    modify = [c for c in fake.calls if c[0] == "ModifyCustomWhiteRule"][0][1]
    assert modify.RuleId == 7
    status = [c for c in fake.calls if c[0] == "ModifyCustomWhiteRuleStatus"][0][1]
    assert status.Status == 0


def test_check_mode_create_is_dry_run(monkeypatch):
    fake = FakeWafClient()
    _make_module(monkeypatch, fake)
    module_args(_ansible_check_mode=True, **{k: v for k, v in _params().items() if v is not None})
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["rule"] is None  # no refetch in check mode
    assert [c[0] for c in fake.calls] == ["DescribeCustomWhiteRule"]  # find only
    assert not any("AddCustomWhiteRule" == c[0] for c in fake.calls)


def test_check_mode_update_is_dry_run(monkeypatch):
    fake = FakeWafClient([_rule()])
    _make_module(monkeypatch, fake)
    module_args(_ansible_check_mode=True, **{k: v for k, v in _params(rule_id=7, priority=50).items() if v is not None})
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["rule"]["RuleId"] == 7  # pre-change rule reported
    assert not any("ModifyCustomWhiteRule" == c[0] for c in fake.calls)


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
    _run_args(state="absent", name="allow-health-check")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["rule"] is None
    delete = [c for c in fake.calls if c[0] == "DeleteCustomWhiteRule"][0][1]
    assert delete.Domain == "api.example.com"
    assert delete.RuleId == 7
    assert fake.rules == []


def test_absent_not_found_is_noop(monkeypatch):
    fake = FakeWafClient([_rule()])
    _make_module(monkeypatch, fake)
    _run_args(state="absent", name="ghost")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["rule"] is None
    assert not any("DeleteCustomWhiteRule" == c[0] for c in fake.calls)


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeWafClient([_rule()])
    _make_module(monkeypatch, fake)
    module_args(_ansible_check_mode=True, **{k: v for k, v in _params(state="absent").items() if v is not None})
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["rule"]["RuleId"] == 7  # pre-change rule reported
    assert not any("DeleteCustomWhiteRule" == c[0] for c in fake.calls)
    assert len(fake.rules) == 1
