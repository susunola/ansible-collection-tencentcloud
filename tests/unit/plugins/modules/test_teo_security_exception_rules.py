"""Unit tests for the teo_security_exception_rules write module (helpers + run_module).

``plugins/modules/teo_security_exception_rules.py`` exactly reconciles the
``SecurityPolicy.ExceptionRules`` section: the desired ``rules`` list is the
complete exception-rule set (an empty list clears the scope). Existing rules
are matched by ``rule_id`` when given, otherwise by a unique rule name, so
service-assigned Ids survive a reconcile. The fake EdgeOne client stores
API-shaped rule dicts and assigns synthetic Ids on create; the module's
post-write refetch normalizes the store back so idempotence holds.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import teo_security_exception_rules as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

# API-shaped exception rule matching the default param rule below, so a no-op
# run reports changed=False.
RULE = {
    "Id": "exc-1",
    "Name": "trusted_upload_payload",
    "Condition": "$http.request.uri.path eq '/upload'",
    "Enabled": "on",
    "SkipScope": "ManagedRules",
    "SkipOption": "SkipOnSpecifiedRequestFields",
    "WebSecurityModulesForException": [],
    "ManagedRulesForException": [],
    "ManagedRuleGroupsForException": ["OWASP"],
    "RequestFieldsForException": [{"Scope": "body", "Condition": "", "TargetField": "multipart"}],
}


def _rule(**overrides):
    item = copy.deepcopy(RULE)
    item.update(overrides)
    return item


def _param_rule(**overrides):
    """Param-shaped rule mirroring RULE (rule_id omitted when None)."""
    rule = {
        "name": "trusted_upload_payload",
        "condition": "$http.request.uri.path eq '/upload'",
        "enabled": True,
        "skip_scope": "ManagedRules",
        "skip_option": "SkipOnSpecifiedRequestFields",
        "web_security_modules": [],
        "managed_rule_ids": [],
        "managed_rule_group_ids": ["OWASP"],
        "request_fields": [{"field_scope": "body", "condition": "", "target_field": "multipart"}],
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
    """In-memory TeoClient for the ExceptionRules policy section."""

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
            SecurityPolicy=FakeResource({"ExceptionRules": section}),
            RequestId="req-fake",
        )

    def ModifySecurityPolicy(self, request):
        self._record("ModifySecurityPolicy", request)
        section = request.SecurityPolicy.ExceptionRules
        rules = list(getattr(section, "Rules", None) or [])
        stored = []
        for rule in rules:
            api = _to_api(rule)
            if not api.get("Id"):
                self._seq += 1
                api["Id"] = "exc-%d" % self._seq
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
    rule = request.SecurityPolicy.ExceptionRules.Rules[0]
    assert rule.Name == "trusted_upload_payload"
    assert rule.Condition == "$http.request.uri.path eq '/upload'"
    assert rule.Enabled == "on"
    assert rule.SkipScope == "ManagedRules"
    assert rule.SkipOption == "SkipOnSpecifiedRequestFields"
    assert rule.ManagedRuleGroupsForException == ["OWASP"]
    assert rule.ManagedRulesForException == []
    assert rule.WebSecurityModulesForException == []


def test_update_request_maps_request_fields():
    fields = [{"field_scope": "uri.query", "condition": "$arg ok", "target_field": "k"}]
    params = _params(rules=[_param_rule(request_fields=fields)])
    request = mod.update_request(FakeModels(), params)
    field = request.SecurityPolicy.ExceptionRules.Rules[0].RequestFieldsForException[0]
    assert field.Scope == "uri.query"
    assert field.Condition == "$arg ok"
    assert field.TargetField == "k"


def test_update_request_disabled_rule_maps_off():
    params = _params(rules=[_param_rule(enabled=False)])
    request = mod.update_request(FakeModels(), params)
    assert request.SecurityPolicy.ExceptionRules.Rules[0].Enabled == "off"


def test_update_request_matches_by_id():
    current = [_rule()]
    params = _params(rules=[_param_rule(rule_id="exc-1", condition="changed")])
    request = mod.update_request(FakeModels(), params, current)
    assert request.SecurityPolicy.ExceptionRules.Rules[0].Id == "exc-1"


def test_update_request_matches_unique_name_when_no_id():
    current = [_rule()]
    params = _params(rules=[_param_rule(condition="changed")])
    request = mod.update_request(FakeModels(), params, current)
    assert request.SecurityPolicy.ExceptionRules.Rules[0].Id == "exc-1"


def test_update_request_id_match_wins_over_name():
    current = [_rule(), _rule(Id="exc-2", Name="other")]
    params = _params(rules=[_param_rule(rule_id="exc-2", name="trusted_upload_payload")])
    request = mod.update_request(FakeModels(), params, current)
    assert request.SecurityPolicy.ExceptionRules.Rules[0].Id == "exc-2"


def test_update_request_ambiguous_name_gets_no_id():
    current = [_rule(), _rule(Id="exc-2")]
    params = _params(rules=[_param_rule(condition="changed")])
    request = mod.update_request(FakeModels(), params, current)
    assert not hasattr(request.SecurityPolicy.ExceptionRules.Rules[0], "Id")


def test_update_request_empty_rules_clears_section():
    params = _params(rules=[])
    request = mod.update_request(FakeModels(), params, [_rule()])
    assert request.SecurityPolicy.ExceptionRules.Rules == []


# ---------------------------------------------------------------------------
# normalization helpers
# ---------------------------------------------------------------------------


def test_normalize_sdk_side_maps_and_sorts():
    raw = [
        _rule(Id="exc-2", Name="zeta", ManagedRuleGroupsForException=["OWASP", "BOT"], RequestFieldsForException=[]),
        _rule(Id="exc-1", Name="alpha"),
    ]
    value = mod._normalize(raw, True)
    assert [item["name"] for item in value] == ["alpha", "zeta"]
    assert value[0]["enabled"] is True
    assert value[0]["skip_option"] == "SkipOnSpecifiedRequestFields"
    assert value[1]["managed_rule_group_ids"] == ["BOT", "OWASP"]


def test_normalize_sdk_defaults_skip_option_and_condition():
    raw = [_rule(SkipOption=None, RequestFieldsForException=[{"Scope": "header", "Condition": None, "TargetField": "ua"}])]
    value = mod._normalize(raw, True)
    assert value[0]["skip_option"] == "SkipOnAllRequestFields"
    assert value[0]["request_fields"][0] == {"field_scope": "header", "condition": "", "target_field": "ua"}


def test_normalize_param_side_uses_direct_keys():
    value = mod._normalize(_params()["rules"])
    assert value[0]["name"] == "trusted_upload_payload"
    assert value[0]["skip_scope"] == "ManagedRules"
    assert value[0]["managed_rule_group_ids"] == ["OWASP"]
    assert value[0]["request_fields"] == [{"field_scope": "body", "condition": "", "target_field": "multipart"}]


def test_normalize_sorts_request_fields():
    fields = [
        {"field_scope": "body", "condition": "", "target_field": "multipart"},
        {"field_scope": "header", "condition": "eq x", "target_field": "ua"},
    ]
    value = mod._normalize([_param_rule(request_fields=list(reversed(fields)))])
    assert [item["target_field"] for item in value[0]["request_fields"]] == ["multipart", "ua"]


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
    assert raw[0]["Id"] == "exc-1"
    assert normalized[0]["name"] == "trusted_upload_payload"


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
    rules = [_param_rule(), _param_rule(condition="$http.request.uri.path eq '/other'")]
    _run_args(rules=rules)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "exception rule names must be unique" in exc.value.args[0]["msg"]


def test_web_security_modules_scope_requires_modules():
    rule = _param_rule(skip_scope="WebSecurityModules", web_security_modules=[], managed_rule_ids=[], managed_rule_group_ids=[])
    _run_args(rules=[rule])
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "WebSecurityModules exceptions require web_security_modules" in exc.value.args[0]["msg"]


@pytest.mark.parametrize("rule", [
    {"skip_scope": "ManagedRules", "managed_rule_ids": ["r-1"], "managed_rule_group_ids": ["OWASP"]},
    {"skip_scope": "ManagedRules", "managed_rule_ids": [], "managed_rule_group_ids": []},
])
def test_managed_rules_scope_requires_exactly_one_target(rule):
    base = _param_rule()
    base.update(rule)
    _run_args(rules=[base])
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "ManagedRules exceptions require exactly one of managed_rule_ids or managed_rule_group_ids" in exc.value.args[0]["msg"]


def test_specified_request_fields_requires_fields():
    rule = _param_rule(skip_option="SkipOnSpecifiedRequestFields", request_fields=[])
    _run_args(rules=[rule])
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "SkipOnSpecifiedRequestFields requires request_fields" in exc.value.args[0]["msg"]


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
    assert len(fake.rules) == 1
    assert fake.rules[0]["Id"] == "exc-1"  # service-assigned on create
    write = [c for c in fake.calls if c[0] == "ModifySecurityPolicy"][0][1]
    assert write.SecurityPolicy.ExceptionRules.Rules[0].Name == "trusted_upload_payload"


def test_present_noop_when_in_sync(monkeypatch):
    fake = FakeTeoClient([_rule()])
    _make_module(monkeypatch, fake)
    _run_args()
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["rules"][0]["name"] == "trusted_upload_payload"
    assert [c[0] for c in fake.calls] == ["DescribeSecurityPolicy"]


def test_present_updates_by_unique_name(monkeypatch):
    fake = FakeTeoClient([_rule()])
    _make_module(monkeypatch, fake)
    _run_args(rules=[_param_rule(condition="$http.request.uri.path eq '/new'")])
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["rules"][0]["condition"] == "$http.request.uri.path eq '/new'"
    write = [c for c in fake.calls if c[0] == "ModifySecurityPolicy"][0][1]
    rule = write.SecurityPolicy.ExceptionRules.Rules[0]
    assert rule.Id == "exc-1"  # matched by name so the Id survives
    assert fake.rules[0]["Id"] == "exc-1"


def test_present_updates_by_rule_id(monkeypatch):
    fake = FakeTeoClient([_rule()])
    _make_module(monkeypatch, fake)
    _run_args(rules=[_param_rule(rule_id="exc-1", name="renamed", condition="$http.request.uri.path eq '/new'")])
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["rules"][0]["name"] == "renamed"
    write = [c for c in fake.calls if c[0] == "ModifySecurityPolicy"][0][1]
    assert write.SecurityPolicy.ExceptionRules.Rules[0].Id == "exc-1"


def test_present_web_security_modules_rule_round_trip(monkeypatch):
    rule = _param_rule(
        skip_scope="WebSecurityModules",
        skip_option="SkipOnAllRequestFields",
        web_security_modules=["websec-mod-bot", "websec-mod-rate-limiting"],
        managed_rule_ids=[],
        managed_rule_group_ids=[],
        request_fields=[],
    )
    fake = FakeTeoClient()
    _make_module(monkeypatch, fake)
    _run_args(rules=[rule])
    result = run(mod.run_module)
    assert result["changed"] is True
    normalized = result["rules"][0]
    assert normalized["web_security_modules"] == ["websec-mod-bot", "websec-mod-rate-limiting"]
    assert fake.rules[0]["WebSecurityModulesForException"] == ["websec-mod-bot", "websec-mod-rate-limiting"]


def test_present_clear_rules_removes_all(monkeypatch):
    fake = FakeTeoClient([_rule()])
    _make_module(monkeypatch, fake)
    _run_args(rules=[])
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["rules"] == []
    write = [c for c in fake.calls if c[0] == "ModifySecurityPolicy"][0][1]
    assert write.SecurityPolicy.ExceptionRules.Rules == []
    assert fake.rules == []


def test_second_run_is_noop_after_create(monkeypatch):
    fake = FakeTeoClient()
    _make_module(monkeypatch, fake)
    _run_args()
    run(mod.run_module)
    assert len([c for c in fake.calls if c[0] == "ModifySecurityPolicy"]) == 1
    run(mod.run_module)
    assert len([c for c in fake.calls if c[0] == "ModifySecurityPolicy"]) == 1  # no second write


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
    module_args(_ansible_check_mode=True, **_drop_none(_params(rules=[_param_rule(condition="$http.request.uri.path eq '/new'")])))
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["diff"]["after"][0]["condition"] == "$http.request.uri.path eq '/new'"
    assert [c[0] for c in fake.calls] == ["DescribeSecurityPolicy"]
    assert fake.rules[0]["Condition"] == "$http.request.uri.path eq '/upload'"  # untouched


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
