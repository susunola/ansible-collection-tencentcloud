"""Unit tests for the teo_security_rate_limiting_rules write module.

``plugins/modules/teo_security_rate_limiting_rules.py`` exactly reconciles
the ``SecurityPolicy.RateLimitingRules`` section. Existing rules are matched
by ``rule_id`` or unique name (like the exception/custom siblings), the
enforcement ``action`` maps onto a nested ``SecurityAction`` carrying
Challenge/Redirect parameter objects, and ``action_duration`` is validated
against per-unit ceilings (s 120 / m 120 / h 48 / d 30) before the SDK is
reached. The fake client stores API-shaped rule dicts and round-trips the
request tree through ``ModifySecurityPolicy`` so refetches converge.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import teo_security_rate_limiting_rules as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

# API-shaped rate-limiting rule matching the default param rule below.
RULE = {
    "Id": "rl-1",
    "Name": "login_limit",
    "Condition": "$http.request.uri.path eq '/login'",
    "Mode": "Block",
    "CountBy": ["http.request.ip"],
    "MaxRequestThreshold": 30,
    "CountingPeriod": "1m",
    "ActionDuration": "10m",
    "Action": {"Name": "Deny"},
    "Priority": 0,
    "Enabled": "on",
}


def _rule(**overrides):
    item = copy.deepcopy(RULE)
    item.update(overrides)
    return item


def _param_rule(**overrides):
    """Param-shaped rule mirroring RULE (None optionals omitted)."""
    rule = {
        "name": "login_limit",
        "condition": "$http.request.uri.path eq '/login'",
        "mode": "Block",
        "count_by": ["http.request.ip"],
        "threshold": 30,
        "counting_period": "1m",
        "action_duration": "10m",
        "action": "Deny",
        "challenge_option": "ManagedChallenge",
        "priority": 0,
        "enabled": True,
    }
    rule.update(overrides)
    return rule


def _params(**overrides):
    params = {
        "zone_id": "zone-abc123",
        "scope": "zone",
        "template_id": None,
        "host": None,
        "rules": [_param_rule()],
    }
    params.update(overrides)
    return params


def _drop_none(values):
    """Recursively drop None values so real-args parsing matches fixtures."""
    if isinstance(values, dict):
        return {k: _drop_none(v) for k, v in values.items() if v is not None}
    if isinstance(values, list):
        return [_drop_none(v) for v in values]
    return values


def _run_args(**extra):
    args = dict(_params())
    args.update(extra)
    return module_args(**_drop_none(args))


def _to_api(value):
    """Serialize a request/object tree into plain API-shaped dicts/lists."""
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, (list, tuple)):
        return [_to_api(v) for v in value]
    data = getattr(value, "__dict__", None)
    if data:
        return {key: _to_api(val) for key, val in data.items()}
    return value


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


class FakeTeoClient(object):
    """In-memory TeoClient for the RateLimitingRules policy section."""

    def __init__(self, rules=None):
        self.rules = [copy.deepcopy(r) for r in (rules or [])]
        self.calls = []
        self._seq = 0

    def _record(self, name, request):
        self.calls.append((name, request))
        return request

    def DescribeSecurityPolicy(self, request):
        self._record("DescribeSecurityPolicy", request)
        if not self.rules:
            section = None
        else:
            section = FakeResource({"Rules": [FakeResource(dict(r)) for r in self.rules]})
        return SimpleNamespace(
            SecurityPolicy=FakeResource({"RateLimitingRules": section}),
            RequestId="req-fake",
        )

    def ModifySecurityPolicy(self, request):
        self._record("ModifySecurityPolicy", request)
        section = request.SecurityPolicy.RateLimitingRules
        rules = list(getattr(section, "Rules", None) or [])
        stored = []
        for rule in rules:
            api = _to_api(rule)
            if not api.get("Id"):
                self._seq += 1
                api["Id"] = "rl-%d" % self._seq
            stored.append(api)
        self.rules = stored
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(
        mod,
        "_load",
        lambda: (FakeModels(), SimpleNamespace(TeoClient=object)),
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
# request-builder helpers
# ---------------------------------------------------------------------------


def test_describe_request_maps_scope():
    request = mod.describe_request(FakeModels(), _params())
    assert request.ZoneId == "zone-abc123"
    assert request.Entity == "ZoneDefaultPolicy"
    request = mod.describe_request(FakeModels(), _params(scope="template", template_id="temp-1"))
    assert request.Entity == "Template"
    assert request.TemplateId == "temp-1"
    request = mod.describe_request(FakeModels(), _params(scope="host", host="api.example.com"))
    assert request.Entity == "Host"
    assert request.Host == "api.example.com"


def test_update_request_maps_core_fields():
    request = mod.update_request(FakeModels(), _params())
    rule = request.SecurityPolicy.RateLimitingRules.Rules[0]
    assert rule.Name == "login_limit"
    assert rule.Condition == "$http.request.uri.path eq '/login'"
    assert rule.Mode == "Block"
    assert rule.CountBy == ["http.request.ip"]
    assert rule.MaxRequestThreshold == 30
    assert rule.CountingPeriod == "1m"
    assert rule.ActionDuration == "10m"
    assert rule.Priority == 0
    assert rule.Enabled == "on"


def test_update_request_disabled_rule_maps_off():
    params = _params(rules=[_param_rule(enabled=False)])
    request = mod.update_request(FakeModels(), params)
    assert request.SecurityPolicy.RateLimitingRules.Rules[0].Enabled == "off"


def test_update_request_plain_action_has_no_parameters():
    request = mod.update_request(FakeModels(), _params())
    action = request.SecurityPolicy.RateLimitingRules.Rules[0].Action
    assert action.Name == "Deny"
    assert not hasattr(action, "ChallengeActionParameters")
    assert not hasattr(action, "RedirectActionParameters")


def test_update_request_challenge_action_attaches_option():
    params = _params(rules=[_param_rule(action="Challenge", challenge_option="JSChallenge")])
    request = mod.update_request(FakeModels(), params)
    action = request.SecurityPolicy.RateLimitingRules.Rules[0].Action
    assert action.Name == "Challenge"
    assert action.ChallengeActionParameters.ChallengeOption == "JSChallenge"


def test_update_request_redirect_action_attaches_url():
    params = _params(rules=[_param_rule(action="Redirect", redirect_url="https://verify.example.com")])
    request = mod.update_request(FakeModels(), params)
    action = request.SecurityPolicy.RateLimitingRules.Rules[0].Action
    assert action.Name == "Redirect"
    assert action.RedirectActionParameters.URL == "https://verify.example.com"


def test_update_request_matches_by_id_and_unique_name():
    current = [_rule()]
    params = _params(rules=[_param_rule(rule_id="rl-1", threshold=99)])
    request = mod.update_request(FakeModels(), params, current)
    assert request.SecurityPolicy.RateLimitingRules.Rules[0].Id == "rl-1"
    params = _params(rules=[_param_rule(threshold=99)])
    request = mod.update_request(FakeModels(), params, current)
    assert request.SecurityPolicy.RateLimitingRules.Rules[0].Id == "rl-1"


def test_update_request_ambiguous_name_gets_no_id():
    current = [_rule(), _rule(Id="rl-2")]
    params = _params(rules=[_param_rule(threshold=99)])
    request = mod.update_request(FakeModels(), params, current)
    assert not hasattr(request.SecurityPolicy.RateLimitingRules.Rules[0], "Id")


def test_update_request_empty_rules_clears_section():
    request = mod.update_request(FakeModels(), _params(rules=[]), [_rule()])
    assert request.SecurityPolicy.RateLimitingRules.Rules == []


# ---------------------------------------------------------------------------
# normalization helpers
# ---------------------------------------------------------------------------


def test_normalize_sdk_side_maps_threshold_and_action():
    raw = [_rule(Mode=None, Priority=None, Enabled="off")]
    value = mod._normalize(raw, True)
    assert value[0]["mode"] == "Block"
    assert value[0]["threshold"] == 30
    assert value[0]["priority"] == 0
    assert value[0]["enabled"] is False


def test_normalize_sdk_challenge_option_and_default_duration():
    raw = [_rule(Action={"Name": "Challenge", "ChallengeActionParameters": {"ChallengeOption": "JSChallenge"}})]
    value = mod._normalize(raw, True)
    assert value[0]["action"] == "Challenge"
    assert value[0]["challenge_option"] == "JSChallenge"
    assert value[0]["redirect_url"] == ""


def test_normalize_sdk_redirect_url():
    raw = [_rule(Action={"Name": "Redirect", "RedirectActionParameters": {"URL": "https://verify.example.com"}})]
    value = mod._normalize(raw, True)
    assert value[0]["redirect_url"] == "https://verify.example.com"


def test_normalize_sorts_by_priority_then_name():
    raw = [
        _rule(Id="rl-2", Name="zeta", Priority=1),
        _rule(Id="rl-3", Name="alpha", Priority=1),
        _rule(Id="rl-1", Name="login_limit", Priority=0),
    ]
    value = mod._normalize(raw, True)
    assert [item["name"] for item in value] == ["login_limit", "alpha", "zeta"]


def test_normalize_sorts_count_by():
    raw = [_rule(CountBy=["http.request.xff_header_ip", "http.request.ip"])]
    value = mod._normalize(raw, True)
    assert value[0]["count_by"] == ["http.request.ip", "http.request.xff_header_ip"]


def test_normalize_param_side_uses_direct_keys():
    value = mod._normalize(_params()["rules"])
    assert value[0]["name"] == "login_limit"
    assert value[0]["threshold"] == 30
    assert value[0]["action"] == "Deny"
    assert value[0]["action_duration"] == "10m"


# ---------------------------------------------------------------------------
# get_rules helper
# ---------------------------------------------------------------------------


def test_get_rules_empty_policy_returns_empty(monkeypatch):
    fake = FakeTeoClient()
    _make_module(monkeypatch, fake)
    module = FakeModule(_params())
    raw, normalized = mod.get_rules(module, fake, FakeModels(), module.params)
    assert raw == []
    assert normalized == []


def test_get_rules_returns_raw_and_normalized(monkeypatch):
    fake = FakeTeoClient([_rule()])
    _make_module(monkeypatch, fake)
    module = FakeModule(_params())
    raw, normalized = mod.get_rules(module, fake, FakeModels(), module.params)
    assert raw[0]["Id"] == "rl-1"
    assert normalized[0]["name"] == "login_limit"
    assert normalized[0]["threshold"] == 30


# ---------------------------------------------------------------------------
# pre-SDK validation
# ---------------------------------------------------------------------------


def test_template_scope_requires_template_id():
    _run_args(scope="template", template_id=None)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "template_id is required for template scope" in exc.value.args[0]["msg"]


def test_host_scope_requires_host():
    _run_args(scope="host", host=None)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "host is required for host scope" in exc.value.args[0]["msg"]


def test_duplicate_rule_names_fail():
    _run_args(rules=[_param_rule(), _param_rule(condition="$http.request.uri.path eq '/other'")])
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "rate-limiting rule names must be unique" in exc.value.args[0]["msg"]


@pytest.mark.parametrize("count_by", [[], ["http.request.ip"] * 6, ["http.request.ip", "http.request.ip"]])
def test_count_by_must_be_one_to_five_unique(count_by):
    _run_args(rules=[_param_rule(count_by=count_by)])
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "count_by requires one through five unique characteristics" in exc.value.args[0]["msg"]


@pytest.mark.parametrize("overrides", [{"threshold": 0}, {"threshold": 100001}, {"priority": -1}, {"priority": 101}])
def test_threshold_and_priority_range_validation(overrides):
    rule = _param_rule()
    rule.update(overrides)
    _run_args(rules=[rule])
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "rate threshold or priority is outside the supported range" in exc.value.args[0]["msg"]


@pytest.mark.parametrize("action_duration", ["0s", "121s", "121m", "49h", "31d", "1x", "2"])
def test_action_duration_outside_supported_range_fails(action_duration):
    _run_args(rules=[_param_rule(action_duration=action_duration)])
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "action_duration is outside the supported range" in exc.value.args[0]["msg"]


def test_redirect_action_requires_redirect_url():
    _run_args(rules=[_param_rule(action="Redirect")])
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "redirect_url is required when action=Redirect" in exc.value.args[0]["msg"]


# ---------------------------------------------------------------------------
# run_module main-path tests
# ---------------------------------------------------------------------------


def test_present_creates_rule_when_none(monkeypatch):
    fake = FakeTeoClient()
    _make_module(monkeypatch, fake)
    _run_args()
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["rules"] == mod._normalize(_params()["rules"])
    names = [c[0] for c in fake.calls]
    assert names == ["DescribeSecurityPolicy", "ModifySecurityPolicy", "DescribeSecurityPolicy"]
    assert fake.rules[0]["Id"] == "rl-1"
    assert fake.rules[0]["MaxRequestThreshold"] == 30
    write = [c for c in fake.calls if c[0] == "ModifySecurityPolicy"][0][1]
    assert write.SecurityPolicy.RateLimitingRules.Rules[0].Action.Name == "Deny"


def test_present_noop_when_in_sync(monkeypatch):
    fake = FakeTeoClient([_rule()])
    _make_module(monkeypatch, fake)
    _run_args()
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["rules"][0]["threshold"] == 30
    assert [c[0] for c in fake.calls] == ["DescribeSecurityPolicy"]


def test_present_drift_updates_by_unique_name(monkeypatch):
    fake = FakeTeoClient([_rule()])
    _make_module(monkeypatch, fake)
    _run_args(rules=[_param_rule(threshold=90, action_duration="1h")])
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["rules"][0]["threshold"] == 90
    assert result["rules"][0]["action_duration"] == "1h"
    write = [c for c in fake.calls if c[0] == "ModifySecurityPolicy"][0][1]
    assert write.SecurityPolicy.RateLimitingRules.Rules[0].Id == "rl-1"
    assert write.SecurityPolicy.RateLimitingRules.Rules[0].ActionDuration == "1h"


def test_present_challenge_rule_round_trip(monkeypatch):
    fake = FakeTeoClient()
    _make_module(monkeypatch, fake)
    _run_args(rules=[_param_rule(action="Challenge", challenge_option="JSChallenge")])
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["rules"][0]["action"] == "Challenge"
    assert result["rules"][0]["challenge_option"] == "JSChallenge"
    assert fake.rules[0]["Action"]["Name"] == "Challenge"
    assert fake.rules[0]["Action"]["ChallengeActionParameters"]["ChallengeOption"] == "JSChallenge"


def test_present_redirect_rule_round_trip(monkeypatch):
    fake = FakeTeoClient()
    _make_module(monkeypatch, fake)
    _run_args(rules=[_param_rule(action="Redirect", redirect_url="https://verify.example.com")])
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["rules"][0]["action"] == "Redirect"
    assert result["rules"][0]["redirect_url"] == "https://verify.example.com"
    assert fake.rules[0]["Action"]["RedirectActionParameters"]["URL"] == "https://verify.example.com"


def test_present_multiple_rules_reconcile_together(monkeypatch):
    fake = FakeTeoClient()
    _make_module(monkeypatch, fake)
    rules = [
        _param_rule(name="high_prio", threshold=5, priority=100),
        _param_rule(name="login_limit", threshold=30),
    ]
    _run_args(rules=rules)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert [item["name"] for item in result["rules"]] == ["login_limit", "high_prio"]  # (priority, name)
    assert len(fake.rules) == 2


def test_present_clear_rules_removes_all(monkeypatch):
    fake = FakeTeoClient([_rule()])
    _make_module(monkeypatch, fake)
    _run_args(rules=[])
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["rules"] == []
    assert fake.rules == []


def test_check_mode_create_is_dry_run(monkeypatch):
    fake = FakeTeoClient()
    _make_module(monkeypatch, fake)
    module_args(_ansible_check_mode=True, **_drop_none(_params()))
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["rules"] == mod._normalize(_params()["rules"])
    assert [c[0] for c in fake.calls] == ["DescribeSecurityPolicy"]
    assert fake.rules == []


def test_check_mode_update_reports_diff_without_writing(monkeypatch):
    fake = FakeTeoClient([_rule()])
    _make_module(monkeypatch, fake)
    module_args(_ansible_check_mode=True, **_drop_none(_params(rules=[_param_rule(threshold=90)])))
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["diff"]["before"][0]["threshold"] == 30
    assert result["diff"]["after"][0]["threshold"] == 90
    assert [c[0] for c in fake.calls] == ["DescribeSecurityPolicy"]


def test_sdk_error_is_reported(monkeypatch):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(
        mod,
        "_load",
        lambda: (FakeModels(), SimpleNamespace(TeoClient=object)),
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
