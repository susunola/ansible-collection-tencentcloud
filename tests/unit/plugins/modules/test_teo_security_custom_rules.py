"""Unit tests for the teo_security_custom_rules write module (helpers + run_module).

``plugins/modules/teo_security_custom_rules.py`` exactly reconciles the
``SecurityPolicy.CustomRules`` section. Rules are matched by ``rule_id`` or
unique name; ``BasicAccessRule`` rules must keep the default priority 0
(priority only applies to ``PreciseMatchRule``). The fake client stores
API-shaped rule dicts and round-trips ``ModifySecurityPolicy`` so refetches
converge and idempotence holds.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import teo_security_custom_rules as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

# API-shaped custom rule matching the default param rule below.
RULE = {
    "Id": "cr-1",
    "Name": "block_known_attackers",
    "Condition": "$http.request.ip in '1234'",
    "Action": {"Name": "Deny"},
    "Enabled": "on",
    "RuleType": "PreciseMatchRule",
    "Priority": 10,
}


def _rule(**overrides):
    item = copy.deepcopy(RULE)
    item.update(overrides)
    return item


def _param_rule(**overrides):
    """Param-shaped rule mirroring RULE (None optionals omitted)."""
    rule = {
        "name": "block_known_attackers",
        "condition": "$http.request.ip in '1234'",
        "action": "Deny",
        "enabled": True,
        "rule_type": "PreciseMatchRule",
        "priority": 10,
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
    """In-memory TeoClient for the CustomRules policy section."""

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
            SecurityPolicy=FakeResource({"CustomRules": section}),
            RequestId="req-fake",
        )

    def ModifySecurityPolicy(self, request):
        self._record("ModifySecurityPolicy", request)
        section = request.SecurityPolicy.CustomRules
        rules = list(getattr(section, "Rules", None) or [])
        stored = []
        for rule in rules:
            api = _to_api(rule)
            if not api.get("Id"):
                self._seq += 1
                api["Id"] = "cr-%d" % self._seq
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


def test_update_request_maps_rule_fields():
    request = mod.update_request(FakeModels(), _params())
    rule = request.SecurityPolicy.CustomRules.Rules[0]
    assert rule.Name == "block_known_attackers"
    assert rule.Condition == "$http.request.ip in '1234'"
    assert rule.Action.Name == "Deny"
    assert rule.Enabled == "on"
    assert rule.RuleType == "PreciseMatchRule"
    assert rule.Priority == 10


def test_update_request_disabled_monitor_rule():
    params = _params(rules=[_param_rule(action="Monitor", enabled=False, priority=0)])
    request = mod.update_request(FakeModels(), params)
    rule = request.SecurityPolicy.CustomRules.Rules[0]
    assert rule.Action.Name == "Monitor"
    assert rule.Enabled == "off"


def test_update_request_matches_by_id_and_unique_name():
    current = [_rule()]
    params = _params(rules=[_param_rule(rule_id="cr-1", condition="changed")])
    request = mod.update_request(FakeModels(), params, current)
    assert request.SecurityPolicy.CustomRules.Rules[0].Id == "cr-1"
    params = _params(rules=[_param_rule(condition="changed")])
    request = mod.update_request(FakeModels(), params, current)
    assert request.SecurityPolicy.CustomRules.Rules[0].Id == "cr-1"


def test_update_request_ambiguous_name_gets_no_id():
    current = [_rule(), _rule(Id="cr-2")]
    params = _params(rules=[_param_rule(condition="changed")])
    request = mod.update_request(FakeModels(), params, current)
    assert not hasattr(request.SecurityPolicy.CustomRules.Rules[0], "Id")


def test_update_request_empty_rules_clears_section():
    request = mod.update_request(FakeModels(), _params(rules=[]), [_rule()])
    assert request.SecurityPolicy.CustomRules.Rules == []


# ---------------------------------------------------------------------------
# normalization helpers
# ---------------------------------------------------------------------------


def test_normalize_sdk_side_maps_and_defaults():
    raw = [_rule(RuleType=None, Priority=None, Enabled="off", Action={"Name": "Monitor"})]
    value = mod._normalize(raw, True)
    assert value[0]["rule_type"] == "PreciseMatchRule"
    assert value[0]["priority"] == 0
    assert value[0]["enabled"] is False
    assert value[0]["action"] == "Monitor"


def test_normalize_sorts_by_priority_then_name():
    raw = [
        _rule(Id="cr-2", Name="zeta", Priority=5),
        _rule(Id="cr-3", Name="alpha", Priority=5),
        _rule(Id="cr-1", Name="block_known_attackers", Priority=10),
    ]
    value = mod._normalize(raw, True)
    assert [item["name"] for item in value] == ["alpha", "zeta", "block_known_attackers"]


def test_normalize_param_side_uses_direct_keys():
    value = mod._normalize(_params()["rules"])
    assert value[0]["name"] == "block_known_attackers"
    assert value[0]["action"] == "Deny"
    assert value[0]["rule_type"] == "PreciseMatchRule"
    assert value[0]["priority"] == 10
    assert value[0]["enabled"] is True


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
    assert raw[0]["Id"] == "cr-1"
    assert normalized[0]["action"] == "Deny"


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
    assert "rule names must be unique" in exc.value.args[0]["msg"]


@pytest.mark.parametrize("priority", [-1, 101])
def test_priority_outside_range_fails(priority):
    _run_args(rules=[_param_rule(priority=priority)])
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "rule priority must be between 0 and 100" in exc.value.args[0]["msg"]


def test_basic_access_rule_rejects_priority():
    _run_args(rules=[_param_rule(rule_type="BasicAccessRule", priority=5)])
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "priority is only supported for PreciseMatchRule" in exc.value.args[0]["msg"]


# ---------------------------------------------------------------------------
# run_module main-path tests
# ---------------------------------------------------------------------------


def test_present_creates_rules_when_none(monkeypatch):
    fake = FakeTeoClient()
    _make_module(monkeypatch, fake)
    _run_args()
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["rules"] == mod._normalize(_params()["rules"])
    names = [c[0] for c in fake.calls]
    assert names == ["DescribeSecurityPolicy", "ModifySecurityPolicy", "DescribeSecurityPolicy"]
    assert fake.rules[0]["Id"] == "cr-1"
    assert fake.rules[0]["Action"] == {"Name": "Deny"}
    write = [c for c in fake.calls if c[0] == "ModifySecurityPolicy"][0][1]
    assert write.SecurityPolicy.CustomRules.Rules[0].Name == "block_known_attackers"


def test_present_noop_when_in_sync(monkeypatch):
    fake = FakeTeoClient([_rule()])
    _make_module(monkeypatch, fake)
    _run_args()
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["rules"][0]["name"] == "block_known_attackers"
    assert [c[0] for c in fake.calls] == ["DescribeSecurityPolicy"]


def test_present_updates_by_unique_name(monkeypatch):
    fake = FakeTeoClient([_rule()])
    _make_module(monkeypatch, fake)
    _run_args(rules=[_param_rule(condition="$http.request.uri.path eq '/admin'")])
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["rules"][0]["condition"] == "$http.request.uri.path eq '/admin'"
    write = [c for c in fake.calls if c[0] == "ModifySecurityPolicy"][0][1]
    assert write.SecurityPolicy.CustomRules.Rules[0].Id == "cr-1"
    assert fake.rules[0]["Id"] == "cr-1"


def test_present_priority_drift_updates(monkeypatch):
    fake = FakeTeoClient([_rule()])
    _make_module(monkeypatch, fake)
    _run_args(rules=[_param_rule(priority=1)])
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["rules"][0]["priority"] == 1
    write = [c for c in fake.calls if c[0] == "ModifySecurityPolicy"][0][1]
    assert write.SecurityPolicy.CustomRules.Rules[0].Priority == 1


def test_present_basic_access_rule_round_trip(monkeypatch):
    fake = FakeTeoClient()
    _make_module(monkeypatch, fake)
    _run_args(rules=[_param_rule(rule_type="BasicAccessRule", priority=0)])
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["rules"][0]["rule_type"] == "BasicAccessRule"
    assert fake.rules[0]["RuleType"] == "BasicAccessRule"
    assert fake.rules[0]["Priority"] == 0


def test_present_clear_rules_removes_all(monkeypatch):
    fake = FakeTeoClient([_rule()])
    _make_module(monkeypatch, fake)
    _run_args(rules=[])
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["rules"] == []
    write = [c for c in fake.calls if c[0] == "ModifySecurityPolicy"][0][1]
    assert write.SecurityPolicy.CustomRules.Rules == []
    assert fake.rules == []


def test_second_run_is_noop_after_create(monkeypatch):
    fake = FakeTeoClient()
    _make_module(monkeypatch, fake)
    _run_args()
    run(mod.run_module)
    assert len([c for c in fake.calls if c[0] == "ModifySecurityPolicy"]) == 1
    run(mod.run_module)
    assert len([c for c in fake.calls if c[0] == "ModifySecurityPolicy"]) == 1


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
    module_args(_ansible_check_mode=True, **_drop_none(_params(rules=[_param_rule(action="Monitor")])))
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["diff"]["before"][0]["action"] == "Deny"
    assert result["diff"]["after"][0]["action"] == "Monitor"
    assert [c[0] for c in fake.calls] == ["DescribeSecurityPolicy"]
    assert fake.rules[0]["Action"] == {"Name": "Deny"}


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
