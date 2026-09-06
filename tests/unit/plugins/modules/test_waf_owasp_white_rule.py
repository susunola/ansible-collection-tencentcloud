"""Unit tests for the waf_owasp_white_rule write module (helpers + run_module).

Covers the create / drift-update / destroy flows of
``plugins/modules/waf_owasp_white_rule.py`` with an in-memory fake WAF
client whose write operations mutate the rule store, so the module's
post-write ``find`` refetch converges immediately. Rules are matched by
``RuleId`` (int) or by name across the paged DescribeOwaspWhiteRules
(``response.List`` / ``response.Total``). ``Strategy`` entries round-trip
through ``_deserialize``. ``expire_time`` is sent on create/update but is
deliberately excluded from ``comparable``/``desired``, so drift on it is
ignored. There is no separate status-sync operation: ``Status`` rides
inside Create/Modify. In check mode a would-be create reports
``rule=None`` and a would-be update the pre-change rule.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import waf_owasp_white_rule as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

RULE = {
    "RuleId": 7,
    "Name": "allow-health-signatures",
    "Domain": "api.example.com",
    "Ids": [100001, 100002],
    "Type": 0,
    "Strategies": [{"Field": "URI", "Arg": "", "CompareFunc": "prefix", "Content": "/health"}],
    "LogicalOp": "and",
    "Status": 1,
    "ExpireTime": 0,
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
        "name": "allow-health-signatures",
        "allow_type": 0,
        "owasp_ids": [100001, 100002],
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
    """In-memory WafClient stand-in for OWASP allowlist rules.

    Stores API-shaped rule dicts keyed by integer RuleId. Describe pages
    over the store honouring Offset/Limit and reports Total at the top
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

    def DescribeOwaspWhiteRules(self, request):
        self._record("DescribeOwaspWhiteRules", request)
        page = self.rules[request.Offset : request.Offset + request.Limit]
        return SimpleNamespace(
            List=[FakeResource(dict(r)) for r in page],
            Total=len(self.rules),
            RequestId="req-fake",
        )

    def CreateOwaspWhiteRule(self, request):
        self._record("CreateOwaspWhiteRule", request)
        rule_id = self._next_id
        self._next_id += 1
        self.rules.append(
            {
                "RuleId": rule_id,
                "Name": request.Name,
                "Domain": request.Domain,
                "Ids": sorted(request.Ids or []),
                "Type": request.Type,
                "Strategies": self._store_strategies(request),
                "LogicalOp": request.LogicalOp,
                "Status": request.Status,
                "ExpireTime": request.ExpireTime,
            }
        )
        return SimpleNamespace(RuleId=rule_id, RequestId="req-fake")

    def ModifyOwaspWhiteRule(self, request):
        self._record("ModifyOwaspWhiteRule", request)
        for stored in self.rules:
            if stored.get("RuleId") != request.RuleId:
                continue
            stored["Name"] = request.Name
            stored["Domain"] = request.Domain
            stored["Ids"] = sorted(request.Ids or [])
            stored["Type"] = request.Type
            stored["Strategies"] = self._store_strategies(request)
            stored["LogicalOp"] = request.LogicalOp
            stored["Status"] = request.Status
            stored["ExpireTime"] = request.ExpireTime
        return SimpleNamespace(RequestId="req-fake")

    def DeleteOwaspWhiteRule(self, request):
        self._record("DeleteOwaspWhiteRule", request)
        self.rules = [r for r in self.rules if r.get("RuleId") not in request.Ids]
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


def test_strategies_builder_deserializes():
    items = mod._strategies(FakeWafModels(), [{"Field": "URI", "Arg": "", "CompareFunc": "prefix", "Content": "/health"}])
    assert items[0].Field == "URI"
    assert items[0].CompareFunc == "prefix"
    assert items[0].Content == "/health"


def test_create_request_fields():
    request = mod.create_request(FakeWafModels(), _params())
    assert request.Domain == "api.example.com"
    assert request.Name == "allow-health-signatures"
    assert request.Ids == [100001, 100002]
    assert request.Type == 0
    assert request.ExpireTime == 0
    assert request.Status == 1
    assert request.LogicalOp == "and"
    assert request.Strategies[0].Content == "/health"
    assert not hasattr(request, "RuleId")


def test_create_request_disabled_status_zero():
    request = mod.create_request(FakeWafModels(), _params(enabled=False))
    assert request.Status == 0


def test_update_request_fields():
    request = mod.update_request(FakeWafModels(), _params(name="renamed", allow_type=1, owasp_ids=[100003]), 7)
    assert request.RuleId == 7
    assert request.Name == "renamed"
    assert request.Type == 1
    assert request.Ids == [100003]


def test_delete_request_uses_ids_list():
    request = mod.delete_request(FakeWafModels(), _params(), 7)
    assert request.Domain == "api.example.com"
    assert request.Ids == [7]


def test_sorted_strategies_sort_order():
    unordered = [
        {"Field": "URI", "Arg": "", "CompareFunc": "contains", "Content": "/beta"},
        {"Field": "URI", "Arg": "", "CompareFunc": "prefix", "Content": "/health"},
        {"Field": "URI", "Arg": "", "CompareFunc": "contains", "Content": "/alpha"},
    ]
    ordered = mod._sorted(unordered)
    assert [s["Content"] for s in ordered] == ["/alpha", "/beta", "/health"]
    assert mod._sorted(None) == []


def test_comparable_normalises_defaults():
    value = mod.comparable({"Name": "x"})
    assert value["Ids"] == []
    assert value["Type"] == 0
    assert value["Strategies"] == []
    assert value["LogicalOp"] == "and"
    assert value["Status"] == 0


def test_comparable_sorts_and_int_coerces_ids():
    value = mod.comparable({"Name": "x", "Ids": ["2", 1], "LogicalOp": "or", "Status": "1"})
    assert value["Ids"] == [1, 2]
    assert value["LogicalOp"] == "or"
    assert value["Status"] == 1


def test_desired_maps_status_and_type():
    assert mod.desired(_params(enabled=True))["Status"] == 1
    assert mod.desired(_params(enabled=False))["Status"] == 0
    assert mod.desired(_params(allow_type=1))["Type"] == 1


def test_desired_and_comparable_exclude_expire_time():
    # expire_time is not compared, so a drift on it alone is a no-op
    assert "ExpireTime" not in mod.desired(_params(expire_time=12345))
    assert "ExpireTime" not in mod.comparable(_rule(ExpireTime=12345))


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
    module = FakeModule(_params(name="allow-health-signatures"))
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
    module = FakeModule(_params(name="allow-health-signatures"))
    with pytest.raises(AnsibleFailJson) as exc:
        mod.find(module, fake, FakeWafModels(), module.params)
    assert "Multiple WAF OWASP allowlist rules matched" in exc.value.args[0]["msg"]


def test_find_paginates_past_100(monkeypatch):
    rules = [_rule(RuleId=1000 + i, Name="bulk-%04d" % i) for i in range(101)]
    rules.append(_rule())
    fake = FakeWafClient(rules)
    _make_module(monkeypatch, fake)
    module = FakeModule(_params(name="allow-health-signatures"))
    value = mod.find(module, fake, FakeWafModels(), module.params)
    assert value["RuleId"] == 7
    list_calls = [c for c in fake.calls if c[0] == "DescribeOwaspWhiteRules"]
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
    module_args(domain="api.example.com", rule_id=7, state="present", owasp_ids=[100001])
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "name and owasp_ids are required when state=present" in exc.value.args[0]["msg"]


def test_present_requires_owasp_ids():
    module_args(domain="api.example.com", name="allow-health-signatures", state="present")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "name and owasp_ids are required when state=present" in exc.value.args[0]["msg"]


def test_present_creates_rule(monkeypatch):
    fake = FakeWafClient()
    _make_module(monkeypatch, fake)
    _run_args()
    result = run(mod.run_module)
    assert result["changed"] is True
    rule = result["rule"]
    assert rule["RuleId"] == 100
    assert rule["Name"] == "allow-health-signatures"
    assert rule["Status"] == 1
    assert rule["Ids"] == [100001, 100002]
    names = [c[0] for c in fake.calls]
    assert names.count("DescribeOwaspWhiteRules") == 2  # find + refetch
    assert names.count("CreateOwaspWhiteRule") == 1
    create = [c for c in fake.calls if c[0] == "CreateOwaspWhiteRule"][0][1]
    assert create.Type == 0
    assert create.Status == 1


def test_present_creates_disabled_rule(monkeypatch):
    fake = FakeWafClient()
    _make_module(monkeypatch, fake)
    _run_args(enabled=False)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["rule"]["Status"] == 0
    create = [c for c in fake.calls if c[0] == "CreateOwaspWhiteRule"][0][1]
    assert create.Status == 0


def test_present_noop_returns_unchanged(monkeypatch):
    fake = FakeWafClient([_rule()])
    _make_module(monkeypatch, fake)
    _run_args()
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["rule"]["RuleId"] == 7
    names = [c[0] for c in fake.calls]
    assert "ModifyOwaspWhiteRule" not in names
    assert "CreateOwaspWhiteRule" not in names


def test_present_expire_time_drift_is_ignored(monkeypatch):
    # expire_time is not part of comparable/desired -> no change reported
    fake = FakeWafClient([_rule(ExpireTime=0)])
    _make_module(monkeypatch, fake)
    _run_args(rule_id=7, expire_time=999999)
    result = run(mod.run_module)
    assert result["changed"] is False
    assert "ModifyOwaspWhiteRule" not in [c[0] for c in fake.calls]


def test_present_allow_type_drift_triggers_update(monkeypatch):
    fake = FakeWafClient([_rule()])
    _make_module(monkeypatch, fake)
    _run_args(rule_id=7, allow_type=1)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["rule"]["Type"] == 1
    modify = [c for c in fake.calls if c[0] == "ModifyOwaspWhiteRule"][0][1]
    assert modify.RuleId == 7
    assert modify.Type == 1


def test_present_owasp_ids_drift_triggers_update(monkeypatch):
    fake = FakeWafClient([_rule()])
    _make_module(monkeypatch, fake)
    _run_args(rule_id=7, owasp_ids=[100003])
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["rule"]["Ids"] == [100003]
    modify = [c for c in fake.calls if c[0] == "ModifyOwaspWhiteRule"][0][1]
    assert modify.Ids == [100003]


def test_present_strategy_drift_triggers_update(monkeypatch):
    fake = FakeWafClient([_rule()])
    _make_module(monkeypatch, fake)
    _run_args(rule_id=7, strategies=[{"Field": "URI", "Arg": "", "CompareFunc": "prefix", "Content": "/v2"}])
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["rule"]["Strategies"][0]["Content"] == "/v2"
    assert "ModifyOwaspWhiteRule" in [c[0] for c in fake.calls]


def test_present_logical_operator_drift_triggers_update(monkeypatch):
    fake = FakeWafClient([_rule()])
    _make_module(monkeypatch, fake)
    _run_args(rule_id=7, logical_operator="or")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["rule"]["LogicalOp"] == "or"
    modify = [c for c in fake.calls if c[0] == "ModifyOwaspWhiteRule"][0][1]
    assert modify.LogicalOp == "or"


def test_present_rename_by_id_triggers_update(monkeypatch):
    fake = FakeWafClient([_rule()])
    _make_module(monkeypatch, fake)
    _run_args(rule_id=7, name="renamed")  # identified by id, name drifts
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["rule"]["Name"] == "renamed"
    modify = [c for c in fake.calls if c[0] == "ModifyOwaspWhiteRule"][0][1]
    assert modify.RuleId == 7
    assert modify.Name == "renamed"


def test_present_enable_drift_triggers_update(monkeypatch):
    fake = FakeWafClient([_rule()])
    _make_module(monkeypatch, fake)
    _run_args(rule_id=7, enabled=False)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["rule"]["Status"] == 0
    names = [c[0] for c in fake.calls]
    assert names.count("ModifyOwaspWhiteRule") == 1
    assert "CreateOwaspWhiteRule" not in names
    modify = [c for c in fake.calls if c[0] == "ModifyOwaspWhiteRule"][0][1]
    assert modify.Status == 0


def test_check_mode_create_is_dry_run(monkeypatch):
    fake = FakeWafClient()
    _make_module(monkeypatch, fake)
    module_args(_ansible_check_mode=True, **{k: v for k, v in _params().items() if v is not None})
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["rule"] is None  # no refetch in check mode
    assert [c[0] for c in fake.calls] == ["DescribeOwaspWhiteRules"]  # find only
    assert not any("CreateOwaspWhiteRule" == c[0] for c in fake.calls)


def test_check_mode_update_is_dry_run(monkeypatch):
    fake = FakeWafClient([_rule()])
    _make_module(monkeypatch, fake)
    module_args(_ansible_check_mode=True, **{k: v for k, v in _params(rule_id=7, allow_type=1).items() if v is not None})
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["rule"]["RuleId"] == 7  # pre-change rule reported
    assert not any("ModifyOwaspWhiteRule" == c[0] for c in fake.calls)


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
    _run_args(state="absent", name="allow-health-signatures")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["rule"] is None
    delete = [c for c in fake.calls if c[0] == "DeleteOwaspWhiteRule"][0][1]
    assert delete.Domain == "api.example.com"
    assert delete.Ids == [7]
    assert fake.rules == []


def test_absent_not_found_is_noop(monkeypatch):
    fake = FakeWafClient([_rule()])
    _make_module(monkeypatch, fake)
    _run_args(state="absent", name="ghost")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["rule"] is None
    assert not any("DeleteOwaspWhiteRule" == c[0] for c in fake.calls)


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeWafClient([_rule()])
    _make_module(monkeypatch, fake)
    module_args(_ansible_check_mode=True, **{k: v for k, v in _params(state="absent").items() if v is not None})
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["rule"]["RuleId"] == 7  # pre-change rule reported
    assert not any("DeleteOwaspWhiteRule" == c[0] for c in fake.calls)
    assert len(fake.rules) == 1
