"""Unit tests for the teo_security_managed_rules write module (helpers + run_module).

``plugins/modules/teo_security_managed_rules.py`` exactly reconciles the
managed-WAF section of an EdgeOne security policy: the whole
``SecurityPolicy.ManagedRules`` subtree is compared (normalized) against the
desired param shape and rewritten wholesale through ``ModifySecurityPolicy``
when anything differs. Unlike the rule-list modules there is no per-rule Id
matching - groups and rule actions are replaced in place. The fake EdgeOne
client stores an API-shaped ManagedRules dict; ``ModifySecurityPolicy``
serializes the request tree back into that shape so the module's post-write
refetch converges. Check mode reports the desired state without writing.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import teo_security_managed_rules as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

# API-shaped managed-WAF config exactly matching the module's default params,
# so a no-op run reports changed=False. FrequentScanningProtection carries
# only Enabled because the module writes the remaining fields only when
# enabled and normalization default-fills them.
MANAGED = {
    "Enabled": "on",
    "DetectionOnly": "off",
    "SemanticAnalysis": "off",
    "AutoUpdate": {"AutoUpdateToLatestVersion": "on"},
    "ManagedRuleGroups": [],
    "FrequentScanningProtection": {"Enabled": "off"},
}


def _managed(**overrides):
    item = copy.deepcopy(MANAGED)
    item.update(overrides)
    return item


def _params(**overrides):
    """Module parameters pre-filled from the argument spec defaults."""
    params = {
        "zone_id": "zone-abc123",
        "scope": "zone",
        "template_id": None,
        "host": None,
        "enabled": True,
        "detection_only": False,
        "semantic_analysis": False,
        "auto_update": True,
        "groups": [],
        "frequent_scanning": {
            "enabled": False,
            "action": "Deny",
            "count_by": "http.request.ip",
            "block_threshold": 100,
            "counting_period": 60,
            "action_duration": 600,
        },
    }
    params.update(overrides)
    return params


def _run_args(**extra):
    args = dict(_params())
    args.update(extra)
    return module_args(**{k: v for k, v in args.items() if v is not None})


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
    """In-memory TeoClient for the ManagedRules policy section.

    ``managed`` is the API-shaped ManagedRules dict, or None when the zone
    has no managed-WAF configuration (DescribeSecurityPolicy then reports an
    empty policy section). ModifySecurityPolicy serializes the request tree
    back into the store so the module's post-write refetch converges.
    """

    def __init__(self, managed=None):
        self.managed = copy.deepcopy(managed) if managed is not None else None
        self.calls = []

    def _record(self, name, request):
        self.calls.append((name, request))
        return request

    def DescribeSecurityPolicy(self, request):
        self._record("DescribeSecurityPolicy", request)
        section = FakeResource(dict(self.managed)) if self.managed is not None else None
        return SimpleNamespace(
            SecurityPolicy=FakeResource({"ManagedRules": section}),
            RequestId="req-fake",
        )

    def ModifySecurityPolicy(self, request):
        self._record("ModifySecurityPolicy", request)
        managed = request.SecurityPolicy.ManagedRules
        self.managed = _to_api(managed)
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


def test_describe_request_zone_scope():
    request = mod.describe_request(FakeModels(), _params())
    assert request.ZoneId == "zone-abc123"
    assert request.Entity == "ZoneDefaultPolicy"
    assert not hasattr(request, "TemplateId")
    assert not hasattr(request, "Host")


def test_describe_request_template_scope_sets_template_id():
    request = mod.describe_request(FakeModels(), _params(scope="template", template_id="temp-1"))
    assert request.Entity == "Template"
    assert request.TemplateId == "temp-1"
    assert not hasattr(request, "Host")


def test_describe_request_host_scope_sets_host():
    request = mod.describe_request(FakeModels(), _params(scope="host", host="api.example.com"))
    assert request.Entity == "Host"
    assert request.Host == "api.example.com"
    assert not hasattr(request, "TemplateId")


def test_update_request_maps_bool_flags():
    request = mod.update_request(FakeModels(), _params(enabled=False, detection_only=True, semantic_analysis=True, auto_update=False))
    managed = request.SecurityPolicy.ManagedRules
    assert managed.Enabled == "off"
    assert managed.DetectionOnly == "on"
    assert managed.SemanticAnalysis == "on"
    assert managed.AutoUpdate.AutoUpdateToLatestVersion == "off"


def test_update_request_plain_group_action():
    groups = [{"group_id": "OWASP", "sensitivity": "strict", "action": "Monitor", "rule_actions": []}]
    request = mod.update_request(FakeModels(), _params(groups=groups))
    group = request.SecurityPolicy.ManagedRules.ManagedRuleGroups[0]
    assert group.GroupId == "OWASP"
    assert group.SensitivityLevel == "strict"
    assert group.Action.Name == "Monitor"
    assert not hasattr(group, "RuleActions")


def test_update_request_custom_group_builds_rule_actions():
    groups = [
        {
            "group_id": "OWASP",
            "sensitivity": "custom",
            "action": "Deny",
            "rule_actions": [
                {"rule_id": "r-1", "action": "Monitor"},
                {"rule_id": "r-2", "action": "Deny"},
            ],
        }
    ]
    request = mod.update_request(FakeModels(), _params(groups=groups))
    group = request.SecurityPolicy.ManagedRules.ManagedRuleGroups[0]
    assert not hasattr(group, "Action")
    actions = group.RuleActions
    assert [item.RuleId for item in actions] == ["r-1", "r-2"]
    assert [item.Action.Name for item in actions] == ["Monitor", "Deny"]


def test_update_request_scan_disabled_writes_only_enabled():
    request = mod.update_request(FakeModels(), _params())
    scan = request.SecurityPolicy.ManagedRules.FrequentScanningProtection
    assert scan.Enabled == "off"
    assert not hasattr(scan, "Action")
    assert not hasattr(scan, "BlockThreshold")


def test_update_request_scan_enabled_writes_periods_as_strings():
    scan = {
        "enabled": True,
        "action": "Monitor",
        "count_by": "http.request.xff_header_ip",
        "block_threshold": 250,
        "counting_period": 120,
        "action_duration": 900,
    }
    request = mod.update_request(FakeModels(), _params(frequent_scanning=scan))
    value = request.SecurityPolicy.ManagedRules.FrequentScanningProtection
    assert value.Enabled == "on"
    assert value.Action.Name == "Monitor"
    assert value.CountBy == "http.request.xff_header_ip"
    assert value.BlockThreshold == 250
    assert value.CountingPeriod == "120s"
    assert value.ActionDuration == "900s"


def test_update_request_sets_zone_id_and_policy_wrapper():
    request = mod.update_request(FakeModels(), _params())
    assert request.ZoneId == "zone-abc123"
    assert request.Entity == "ZoneDefaultPolicy"
    assert request.SecurityPolicy.ManagedRules is not None


# ---------------------------------------------------------------------------
# normalization helpers
# ---------------------------------------------------------------------------


def test_normalize_empty_raw_returns_defaults():
    value = mod._normalize({})
    assert value["enabled"] is False
    assert value["detection_only"] is False
    assert value["semantic_analysis"] is False
    assert value["auto_update"] is False
    assert value["groups"] == []
    assert value["frequent_scanning"] == {
        "enabled": False,
        "action": "Deny",
        "count_by": "http.request.ip",
        "block_threshold": 100,
        "counting_period": 60,
        "action_duration": 600,
    }


def test_normalize_none_raw_returns_defaults():
    value = mod._normalize(None)
    assert value["enabled"] is False
    assert value["frequent_scanning"]["action_duration"] == 600


def test_normalize_maps_on_off_flags():
    raw = _managed(Enabled="off", DetectionOnly="on", SemanticAnalysis="on", AutoUpdate={"AutoUpdateToLatestVersion": "off"})
    value = mod._normalize(raw)
    assert value["enabled"] is False
    assert value["detection_only"] is True
    assert value["semantic_analysis"] is True
    assert value["auto_update"] is False


def test_normalize_defaults_group_action_and_sorts():
    raw = _managed(
        ManagedRuleGroups=[
            {
                "GroupId": "G1",
                "SensitivityLevel": "normal",
                "RuleActions": [{"RuleId": "r-2", "Action": {"Name": "Deny"}}, {"RuleId": "r-1", "Action": {"Name": "Monitor"}}],
            }
        ]
    )
    value = mod._normalize(raw)
    assert value["groups"][0]["action"] == "Deny"  # no Action key -> default
    assert value["groups"][0]["rule_actions"] == [{"rule_id": "r-1", "action": "Monitor"}, {"rule_id": "r-2", "action": "Deny"}]


def test_normalize_parses_scan_periods_and_action():
    raw = _managed(
        FrequentScanningProtection={
            "Enabled": "on",
            "Action": {"Name": "Monitor"},
            "CountBy": "http.request.xff_header_ip",
            "BlockThreshold": 250,
            "CountingPeriod": "120s",
            "ActionDuration": "900s",
        }
    )
    scan = mod._normalize(raw)["frequent_scanning"]
    assert scan["enabled"] is True
    assert scan["action"] == "Monitor"
    assert scan["count_by"] == "http.request.xff_header_ip"
    assert scan["block_threshold"] == 250
    assert scan["counting_period"] == 120
    assert scan["action_duration"] == 900


def test_desired_matches_params_and_sorts():
    groups = [
        {"group_id": "G2", "sensitivity": "normal", "action": "Deny", "rule_actions": []},
        {
            "group_id": "G1",
            "sensitivity": "custom",
            "action": "Deny",
            "rule_actions": [{"rule_id": "r-2", "action": "Deny"}, {"rule_id": "r-1", "action": "Monitor"}],
        },
    ]
    value = mod.desired(_params(enabled=False, groups=groups))
    assert value["enabled"] is False
    assert [g["group_id"] for g in value["groups"]] == ["G1", "G2"]
    assert value["groups"][0]["rule_actions"] == [{"rule_id": "r-1", "action": "Monitor"}, {"rule_id": "r-2", "action": "Deny"}]


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


def test_duplicate_group_ids_fail():
    groups = [
        {"group_id": "OWASP", "sensitivity": "normal", "action": "Deny", "rule_actions": []},
        {"group_id": "OWASP", "sensitivity": "strict", "action": "Monitor", "rule_actions": []},
    ]
    _run_args(groups=groups)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "managed rule group IDs must be unique" in exc.value.args[0]["msg"]


def test_custom_sensitivity_requires_rule_actions():
    _run_args(groups=[{"group_id": "OWASP", "sensitivity": "custom", "action": "Deny", "rule_actions": []}])
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "custom sensitivity requires rule_actions" in exc.value.args[0]["msg"]


def test_duplicate_rule_ids_within_group_fail():
    rule_actions = [{"rule_id": "r-1", "action": "Deny"}, {"rule_id": "r-1", "action": "Monitor"}]
    _run_args(groups=[{"group_id": "OWASP", "sensitivity": "custom", "action": "Deny", "rule_actions": rule_actions}])
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "managed rule IDs must be unique within a group" in exc.value.args[0]["msg"]


@pytest.mark.parametrize(
    "overrides",
    [
        {"block_threshold": 0},
        {"block_threshold": 4294967295},
        {"counting_period": 4},
        {"counting_period": 1801},
        {"action_duration": 59},
        {"action_duration": 86401},
    ],
)
def test_scan_ranges_outside_supported_fail(overrides):
    scan = {"enabled": True, "action": "Deny", "count_by": "http.request.ip", "block_threshold": 100, "counting_period": 60, "action_duration": 600}
    scan.update(overrides)
    _run_args(frequent_scanning=scan)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "frequent_scanning thresholds or durations are outside supported ranges" in exc.value.args[0]["msg"]


# ---------------------------------------------------------------------------
# run_module main-path tests
# ---------------------------------------------------------------------------


def test_present_creates_configuration_when_none(monkeypatch):
    fake = FakeTeoClient()
    _make_module(monkeypatch, fake)
    _run_args()
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["managed_rules"] == mod.desired(_params())
    names = [c[0] for c in fake.calls]
    assert names == ["DescribeSecurityPolicy", "ModifySecurityPolicy", "DescribeSecurityPolicy"]
    write = [c for c in fake.calls if c[0] == "ModifySecurityPolicy"][0][1]
    managed = write.SecurityPolicy.ManagedRules
    assert managed.Enabled == "on"
    assert managed.FrequentScanningProtection.Enabled == "off"
    assert managed.ManagedRuleGroups == []
    assert "diff" not in result  # plain run without --diff omits the diff


def test_present_noop_when_in_sync(monkeypatch):
    fake = FakeTeoClient(_managed())
    _make_module(monkeypatch, fake)
    _run_args()
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["managed_rules"]["enabled"] is True
    assert [c[0] for c in fake.calls] == ["DescribeSecurityPolicy"]


def test_present_drift_disables_protection(monkeypatch):
    fake = FakeTeoClient(_managed())
    _make_module(monkeypatch, fake)
    _run_args(enabled=False)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["managed_rules"] == mod.desired(_params(enabled=False))
    write = [c for c in fake.calls if c[0] == "ModifySecurityPolicy"][0][1]
    assert write.SecurityPolicy.ManagedRules.Enabled == "off"


def test_present_group_drift_replaces_groups(monkeypatch):
    fake = FakeTeoClient(_managed())
    _make_module(monkeypatch, fake)
    groups = [
        {
            "group_id": "OWASP",
            "sensitivity": "custom",
            "action": "Deny",
            "rule_actions": [{"rule_id": "sqli", "action": "Monitor"}, {"rule_id": "xss", "action": "Disabled"}],
        }
    ]
    _run_args(groups=groups)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["managed_rules"] == mod.desired(_params(groups=groups))
    write = [c for c in fake.calls if c[0] == "ModifySecurityPolicy"][0][1]
    group = write.SecurityPolicy.ManagedRules.ManagedRuleGroups[0]
    assert group.SensitivityLevel == "custom"
    assert [item.RuleId for item in group.RuleActions] == ["sqli", "xss"]
    assert [item.Action.Name for item in group.RuleActions] == ["Monitor", "Disabled"]


def test_present_scan_drift_updates_protection(monkeypatch):
    fake = FakeTeoClient(_managed())
    _make_module(monkeypatch, fake)
    scan = {"enabled": True, "action": "Monitor", "count_by": "http.request.xff_header_ip", "block_threshold": 500, "counting_period": 300, "action_duration": 3600}
    _run_args(frequent_scanning=scan)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["managed_rules"] == mod.desired(_params(frequent_scanning=scan))
    write = [c for c in fake.calls if c[0] == "ModifySecurityPolicy"][0][1]
    value = write.SecurityPolicy.ManagedRules.FrequentScanningProtection
    assert value.Enabled == "on"
    assert value.CountingPeriod == "300s"
    assert value.ActionDuration == "3600s"


def test_second_run_is_noop_after_create(monkeypatch):
    fake = FakeTeoClient()
    _make_module(monkeypatch, fake)
    _run_args()
    run(mod.run_module)
    assert [c[0] for c in fake.calls] == ["DescribeSecurityPolicy", "ModifySecurityPolicy", "DescribeSecurityPolicy"]
    run(mod.run_module)
    assert [c[0] for c in fake.calls] == [
        "DescribeSecurityPolicy",
        "ModifySecurityPolicy",
        "DescribeSecurityPolicy",
        "DescribeSecurityPolicy",  # second run finds everything in sync
    ]


def test_check_mode_create_is_dry_run(monkeypatch):
    fake = FakeTeoClient()
    _make_module(monkeypatch, fake)
    module_args(_ansible_check_mode=True, **{k: v for k, v in _params().items() if v is not None})
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["managed_rules"] == mod.desired(_params())
    assert result["diff"]["after"]["enabled"] is True
    assert [c[0] for c in fake.calls] == ["DescribeSecurityPolicy"]


def test_check_mode_drift_reports_diff_without_writing(monkeypatch):
    fake = FakeTeoClient(_managed(Enabled="off"))
    _make_module(monkeypatch, fake)
    module_args(_ansible_check_mode=True, **{k: v for k, v in _params().items() if v is not None})
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["diff"]["before"]["enabled"] is False
    assert result["diff"]["after"]["enabled"] is True
    assert [c[0] for c in fake.calls] == ["DescribeSecurityPolicy"]


def test_run_with_diff_reports_payload(monkeypatch):
    fake = FakeTeoClient()
    _make_module(monkeypatch, fake)
    module_args(_ansible_diff=True, **{k: v for k, v in _params().items() if v is not None})
    result = run(mod.run_module)
    assert result["changed"] is True
    # an absent managed-WAF section normalizes to all-defaults (not None)
    assert result["diff"]["before"]["enabled"] is False
    assert result["diff"]["after"]["enabled"] is True


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
