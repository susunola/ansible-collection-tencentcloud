"""Unit tests for the waf_attack_white_rule write module (helpers + run_module).

Covers the create / drift-update / destroy flows of
``plugins/modules/waf_attack_white_rule.py`` with an in-memory fake WAF
client whose write operations mutate the rule store, so the module's
post-write ``find`` refetch converges immediately. Rules are matched by
``WhiteRuleId`` (int) or by name across the paged DescribeAttackWhiteRule
(``response.List`` / ``response.Total``); mode 0 matches signature IDs and
mode 1 matches signature-category IDs — the matching set is validated
pre-SDK (``signature_ids`` required in mode 0, ``type_ids`` in mode 1).
Unlike other WAF rule modules there is no separate status-sync operation:
``Status`` rides inside Add/Modify. Delete verifies the SDK ``FailIds``
response and fails when any id was not removed. ``UserWhiteRuleItem``
entries round-trip through ``_deserialize``. In check mode a would-be
create reports ``rule=None`` and a would-be update the pre-change rule.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import waf_attack_white_rule as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

RULE = {
    "WhiteRuleId": 7,
    "Name": "allow-health-check",
    "Domain": "api.example.com",
    "Status": 1,
    "Mode": 0,
    "SignatureIds": ["100001", "100002"],
    "TypeIds": [],
    "MatchInfo": [{"MatchField": "URI", "MatchParams": "", "MatchMethod": "prefix", "MatchContent": "/health"}],
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
        "enabled": True,
        "mode": 0,
        "signature_ids": ["100001", "100002"],
        "type_ids": [],
        "rules": [{"MatchField": "URI", "MatchMethod": "prefix", "MatchContent": "/health", "MatchParams": ""}],
    }
    params.update(overrides)
    return params


def _run_args(**extra):
    """module_args() pre-filled with every module parameter (None dropped)."""
    args = dict(_params())
    args.update(extra)
    return module_args(**{k: v for k, v in args.items() if v is not None})


class _ItemModel(object):
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
    """FakeModels whose UserWhiteRuleItem implements _deserialize."""

    def __getattr__(self, name):
        if name == "UserWhiteRuleItem":
            return _ItemModel
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
    """In-memory WafClient stand-in for attack-signature allow rules.

    Stores API-shaped rule dicts keyed by integer WhiteRuleId. Describe
    pages over the store honouring Offset/Limit and reports Total at the
    top level (mirroring the SDK); write operations mutate the store so
    post-write refetches converge.
    """

    def __init__(self, rules=None, fail_delete=False):
        self.rules = [copy.deepcopy(r) for r in (rules or [])]
        self.calls = []
        self._next_id = 100
        self.fail_delete = fail_delete

    def _record(self, name, request):
        self.calls.append((name, request))
        return request

    def _store_rules(self, request):
        return [s._serialize() if hasattr(s, "_serialize") else dict(s) for s in request.Rules]

    def DescribeAttackWhiteRule(self, request):
        self._record("DescribeAttackWhiteRule", request)
        page = self.rules[request.Offset : request.Offset + request.Limit]
        return SimpleNamespace(
            List=[FakeResource(dict(r)) for r in page],
            Total=len(self.rules),
            RequestId="req-fake",
        )

    def AddAttackWhiteRule(self, request):
        self._record("AddAttackWhiteRule", request)
        rule_id = self._next_id
        self._next_id += 1
        self.rules.append(
            {
                "WhiteRuleId": rule_id,
                "Name": request.Name,
                "Domain": request.Domain,
                "Status": request.Status,
                "Mode": request.Mode,
                "SignatureIds": list(request.SignatureIds or []),
                "TypeIds": list(request.TypeIds or []),
                "MatchInfo": self._store_rules(request),
            }
        )
        return SimpleNamespace(RuleId=rule_id, RequestId="req-fake")

    def ModifyAttackWhiteRule(self, request):
        self._record("ModifyAttackWhiteRule", request)
        for stored in self.rules:
            if stored.get("WhiteRuleId") != request.RuleId:
                continue
            stored["Name"] = request.Name
            stored["Domain"] = request.Domain
            stored["Status"] = request.Status
            stored["Mode"] = request.Mode
            stored["SignatureIds"] = list(request.SignatureIds or [])
            stored["TypeIds"] = list(request.TypeIds or [])
            stored["MatchInfo"] = self._store_rules(request)
        return SimpleNamespace(RequestId="req-fake")

    def DeleteAttackWhiteRule(self, request):
        self._record("DeleteAttackWhiteRule", request)
        self.rules = [r for r in self.rules if r.get("WhiteRuleId") not in request.Ids]
        if self.fail_delete:
            return SimpleNamespace(FailIds=list(request.Ids), RequestId="req-fake")
        return SimpleNamespace(FailIds=[], RequestId="req-fake")


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


def test_rules_builder_deserializes():
    items = mod._rules(FakeWafModels(), [{"MatchField": "URI", "MatchMethod": "prefix", "MatchContent": "/health"}])
    assert items[0].MatchField == "URI"
    assert items[0].MatchMethod == "prefix"
    assert items[0].MatchContent == "/health"


def test_create_request_mode0_fields():
    request = mod.create_request(FakeWafModels(), _params())
    assert request.Domain == "api.example.com"
    assert request.Name == "allow-health-check"
    assert request.Status == 1
    assert request.Mode == 0
    assert request.SignatureIds == ["100001", "100002"]
    assert request.TypeIds == []
    assert request.Rules[0].MatchContent == "/health"
    assert not hasattr(request, "RuleId")


def test_create_request_mode1_fields():
    request = mod.create_request(FakeWafModels(), _params(mode=1, type_ids=["200001", "200002"], signature_ids=[]))
    assert request.Mode == 1
    assert request.TypeIds == ["200001", "200002"]
    assert request.SignatureIds == []


def test_create_request_disabled_status_zero():
    request = mod.create_request(FakeWafModels(), _params(enabled=False))
    assert request.Status == 0


def test_update_request_fields():
    request = mod.update_request(FakeWafModels(), _params(name="renamed"), 7)
    assert request.RuleId == 7
    assert request.Name == "renamed"
    assert request.Domain == "api.example.com"
    assert request.Status == 1
    assert request.Mode == 0


def test_delete_request_uses_ids_list():
    request = mod.delete_request(FakeWafModels(), _params(), 7)
    assert request.Domain == "api.example.com"
    assert request.Ids == [7]


def test_sorted_rules_sort_order():
    unordered = [
        {"MatchField": "URI", "MatchParams": "", "MatchMethod": "contains", "MatchContent": "/beta"},
        {"MatchField": "URI", "MatchParams": "", "MatchMethod": "prefix", "MatchContent": "/health"},
        {"MatchField": "URI", "MatchParams": "", "MatchMethod": "contains", "MatchContent": "/alpha"},
    ]
    ordered = mod._sorted_rules(unordered)
    assert [r["MatchContent"] for r in ordered] == ["/alpha", "/beta", "/health"]
    assert mod._sorted_rules(None) == []


def test_comparable_single_signature_id_fallback():
    value = mod.comparable({"Name": "x", "Status": 1, "Mode": 0, "SignatureId": "100001", "TypeId": "200001"})
    assert value["SignatureIds"] == ["100001"]
    assert value["TypeIds"] == ["200001"]


def test_comparable_normalises_defaults():
    value = mod.comparable({"Name": "x", "MatchInfo": None})
    assert value["Status"] == 0
    assert value["Mode"] == 0
    assert value["SignatureIds"] == []
    assert value["TypeIds"] == []
    assert value["Rules"] == []


def test_desired_maps_status_and_mode():
    assert mod.desired(_params(enabled=True))["Status"] == 1
    assert mod.desired(_params(enabled=False))["Status"] == 0
    assert mod.desired(_params(mode=1))["Mode"] == 1
    assert mod.desired(_params())["SignatureIds"] == ["100001", "100002"]


# ---------------------------------------------------------------------------
# find tests
# ---------------------------------------------------------------------------


def test_find_by_rule_id(monkeypatch):
    fake = FakeWafClient([_rule(), _rule(WhiteRuleId=8, Name="other")])
    _make_module(monkeypatch, fake)
    module = FakeModule(_params(rule_id=8, name=None))
    value = mod.find(module, fake, FakeWafModels(), module.params)
    assert value["WhiteRuleId"] == 8


def test_find_by_name(monkeypatch):
    fake = FakeWafClient([_rule(Name="other"), _rule()])
    _make_module(monkeypatch, fake)
    module = FakeModule(_params(name="allow-health-check"))
    value = mod.find(module, fake, FakeWafModels(), module.params)
    assert value["WhiteRuleId"] == 7


def test_find_no_match_returns_none(monkeypatch):
    fake = FakeWafClient([_rule()])
    _make_module(monkeypatch, fake)
    module = FakeModule(_params(name="ghost"))
    assert mod.find(module, fake, FakeWafModels(), module.params) is None


def test_find_multiple_name_matches_fails(monkeypatch):
    fake = FakeWafClient([_rule(), _rule(WhiteRuleId=8)])
    _make_module(monkeypatch, fake)
    module = FakeModule(_params(name="allow-health-check"))
    with pytest.raises(AnsibleFailJson) as exc:
        mod.find(module, fake, FakeWafModels(), module.params)
    assert "Multiple WAF attack allow rules matched" in exc.value.args[0]["msg"]


def test_find_paginates_past_100(monkeypatch):
    rules = [_rule(WhiteRuleId=1000 + i, Name="bulk-%04d" % i) for i in range(101)]
    rules.append(_rule())
    fake = FakeWafClient(rules)
    _make_module(monkeypatch, fake)
    module = FakeModule(_params(name="allow-health-check"))
    value = mod.find(module, fake, FakeWafModels(), module.params)
    assert value["WhiteRuleId"] == 7
    list_calls = [c for c in fake.calls if c[0] == "DescribeAttackWhiteRule"]
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
    module_args(domain="api.example.com", rule_id=7, state="present", signature_ids=["100001"])
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "name is required when state=present" in exc.value.args[0]["msg"]


def test_present_mode0_requires_signature_ids():
    module_args(domain="api.example.com", name="allow-health-check", state="present", mode=0)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "signature_ids is required when mode=0" in exc.value.args[0]["msg"]


def test_present_mode1_requires_type_ids():
    module_args(domain="api.example.com", name="allow-health-check", state="present", mode=1, signature_ids=[])
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "type_ids is required when mode=1" in exc.value.args[0]["msg"]


def test_present_creates_rule(monkeypatch):
    fake = FakeWafClient()
    _make_module(monkeypatch, fake)
    _run_args()
    result = run(mod.run_module)
    assert result["changed"] is True
    rule = result["rule"]
    assert rule["WhiteRuleId"] == 100
    assert rule["Name"] == "allow-health-check"
    assert rule["Status"] == 1
    names = [c[0] for c in fake.calls]
    assert names.count("DescribeAttackWhiteRule") == 2  # find + refetch
    assert names.count("AddAttackWhiteRule") == 1
    assert "ModifyAttackWhiteRule" not in names
    add = [c for c in fake.calls if c[0] == "AddAttackWhiteRule"][0][1]
    assert add.Mode == 0
    assert add.SignatureIds == ["100001", "100002"]
    assert add.Status == 1


def test_present_creates_disabled_rule(monkeypatch):
    fake = FakeWafClient()
    _make_module(monkeypatch, fake)
    _run_args(enabled=False)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["rule"]["Status"] == 0
    add = [c for c in fake.calls if c[0] == "AddAttackWhiteRule"][0][1]
    assert add.Status == 0


def test_present_noop_returns_unchanged(monkeypatch):
    fake = FakeWafClient([_rule()])
    _make_module(monkeypatch, fake)
    _run_args()
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["rule"]["WhiteRuleId"] == 7
    names = [c[0] for c in fake.calls]
    assert "ModifyAttackWhiteRule" not in names
    assert "AddAttackWhiteRule" not in names


def test_present_mode_drift_triggers_update(monkeypatch):
    fake = FakeWafClient([_rule()])
    _make_module(monkeypatch, fake)
    _run_args(rule_id=7, mode=1, type_ids=["200001"])
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["rule"]["Mode"] == 1
    assert result["rule"]["TypeIds"] == ["200001"]
    names = [c[0] for c in fake.calls]
    assert names.count("ModifyAttackWhiteRule") == 1
    modify = [c for c in fake.calls if c[0] == "ModifyAttackWhiteRule"][0][1]
    assert modify.RuleId == 7
    assert modify.Mode == 1
    assert modify.TypeIds == ["200001"]


def test_present_signature_drift_triggers_update(monkeypatch):
    fake = FakeWafClient([_rule()])
    _make_module(monkeypatch, fake)
    _run_args(rule_id=7, signature_ids=["100003"])
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["rule"]["SignatureIds"] == ["100003"]
    modify = [c for c in fake.calls if c[0] == "ModifyAttackWhiteRule"][0][1]
    assert modify.SignatureIds == ["100003"]


def test_present_rename_by_id_triggers_update(monkeypatch):
    fake = FakeWafClient([_rule()])
    _make_module(monkeypatch, fake)
    _run_args(rule_id=7, name="renamed")  # identified by id, name drifts
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["rule"]["Name"] == "renamed"
    modify = [c for c in fake.calls if c[0] == "ModifyAttackWhiteRule"][0][1]
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
    assert names.count("ModifyAttackWhiteRule") == 1
    assert "AddAttackWhiteRule" not in names
    modify = [c for c in fake.calls if c[0] == "ModifyAttackWhiteRule"][0][1]
    assert modify.Status == 0


def test_check_mode_create_is_dry_run(monkeypatch):
    fake = FakeWafClient()
    _make_module(monkeypatch, fake)
    module_args(_ansible_check_mode=True, **{k: v for k, v in _params().items() if v is not None})
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["rule"] is None  # no refetch in check mode
    assert [c[0] for c in fake.calls] == ["DescribeAttackWhiteRule"]  # find only
    assert not any("AddAttackWhiteRule" == c[0] for c in fake.calls)


def test_check_mode_update_is_dry_run(monkeypatch):
    fake = FakeWafClient([_rule()])
    _make_module(monkeypatch, fake)
    module_args(_ansible_check_mode=True, **{k: v for k, v in _params(rule_id=7, mode=1, type_ids=["200001"]).items() if v is not None})
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["rule"]["WhiteRuleId"] == 7  # pre-change rule reported
    assert not any("ModifyAttackWhiteRule" == c[0] for c in fake.calls)


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
    delete = [c for c in fake.calls if c[0] == "DeleteAttackWhiteRule"][0][1]
    assert delete.Domain == "api.example.com"
    assert delete.Ids == [7]
    assert fake.rules == []


def test_absent_delete_failure_reported(monkeypatch):
    fake = FakeWafClient([_rule()], fail_delete=True)
    _make_module(monkeypatch, fake)
    _run_args(state="absent", name="allow-health-check")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "did not delete the attack allow rule" in payload["msg"]
    assert payload["failed_rule_ids"] == [7]


def test_absent_not_found_is_noop(monkeypatch):
    fake = FakeWafClient([_rule()])
    _make_module(monkeypatch, fake)
    _run_args(state="absent", name="ghost")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["rule"] is None
    assert not any("DeleteAttackWhiteRule" == c[0] for c in fake.calls)


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeWafClient([_rule()])
    _make_module(monkeypatch, fake)
    module_args(_ansible_check_mode=True, **{k: v for k, v in _params(state="absent").items() if v is not None})
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["rule"]["WhiteRuleId"] == 7  # pre-change rule reported
    assert not any("DeleteAttackWhiteRule" == c[0] for c in fake.calls)
    assert len(fake.rules) == 1
