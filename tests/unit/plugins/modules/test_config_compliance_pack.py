"""Unit tests for the config_compliance_pack write module (roadmap #57 lever 1).

Hand-finished after scripts/generate_module_test_skeleton.py: covers every
request builder, the rule normalizer (both API and parameter shapes), the
paginated finder, and all present/absent/check-mode reconcile paths.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import config_compliance_pack as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

PACK = {
    "CompliancePackId": "cp-8b0a1c2d",
    "CompliancePackName": "production-security",
    "Description": "Production baseline",
    "RiskLevel": 1,
    "ConfigRules": [
        {
            "RuleName": "public-bucket-denied",
            "RiskLevel": 1,
            "Identifier": "cos-public-read-prohibited",
            "ConfigRuleId": "cr-9f6e5d4c",
            "ManagedRuleIdentifier": "cos-public-read-prohibited",
            "Description": "Deny public reads",
            "InputParameter": [{"ParameterKey": "region", "Type": "string", "Value": "ap-guangzhou"}],
        }
    ],
    "Status": "ACTIVE",
}

WRITE_OPS = (
    "AddCompliancePack",
    "UpdateCompliancePack",
    "UpdateCompliancePackStatus",
    "DeleteCompliancePack",
)


def _pack(**overrides):
    """Return a compliance-pack fixture isolated from the shared constant."""
    pack = copy.deepcopy(PACK)
    pack.update(overrides)
    return pack


def _rule_param(**overrides):
    """Module-side rule dict (parameter shape) matching PACK's ConfigRules[0]."""
    rule = {
        "name": "public-bucket-denied",
        "risk_level": 1,
        "identifier": "cos-public-read-prohibited",
        "config_rule_id": "cr-9f6e5d4c",
        "managed_rule_identifier": "cos-public-read-prohibited",
        "description": "Deny public reads",
        "input_parameters": [{"parameter_name": "region", "type": "string", "value": "ap-guangzhou"}],
    }
    rule.update(overrides)
    return rule


def _params(**overrides):
    """Module parameters pre-filled from the argument spec (base params included)."""
    params = {
        "state": "present",
        "compliance_pack_id": None,
        "name": None,
        "description": "",
        "risk_level": 2,
        "enabled": True,
        "rules": [],
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


class FakeConfigClient(object):
    """In-memory ConfigClient stand-in.

    Stores API-shaped pack dicts; write ops mutate the store so the module's
    post-write find_pack() refetch converges on the first retry.
    """

    def __init__(self, items=None):
        self.items = [dict(item) for item in (items or [])]
        self.calls = []
        self._next_id = 1

    def _record(self, name, request):
        self.calls.append((name, request))
        return request

    @staticmethod
    def _rule_to_dict(rule):
        result = {
            "RuleName": rule.RuleName,
            "RiskLevel": rule.RiskLevel,
            "Identifier": rule.Identifier,
            "ConfigRuleId": rule.ConfigRuleId,
            "Description": rule.Description,
            "InputParameter": [{"ParameterKey": x.ParameterKey, "Type": x.Type, "Value": x.Value} for x in rule.InputParameter],
        }
        if getattr(rule, "ManagedRuleIdentifier", None):
            result["ManagedRuleIdentifier"] = rule.ManagedRuleIdentifier
        return result

    def AddCompliancePack(self, request):
        self._record("AddCompliancePack", request)
        pack_id = "cp-fake-%d" % self._next_id
        self._next_id += 1
        self.items.append(
            {
                "CompliancePackId": pack_id,
                "CompliancePackName": request.CompliancePackName,
                "Description": request.Description,
                "RiskLevel": request.RiskLevel,
                "ConfigRules": [self._rule_to_dict(r) for r in (request.ConfigRules or [])],
                "Status": "UN_ACTIVE",
            }
        )
        return SimpleNamespace(CompliancePackId=pack_id, RequestId="req-fake")

    def DeleteCompliancePack(self, request):
        self._record("DeleteCompliancePack", request)
        self.items = [i for i in self.items if i["CompliancePackId"] != request.CompliancePackId]
        return SimpleNamespace(RequestId="req-fake")

    def DescribeCompliancePack(self, request):
        self._record("DescribeCompliancePack", request)
        for item in self.items:
            if item["CompliancePackId"] == request.CompliancePackId:
                return FakeResource(dict(item, RequestId="req-fake"))
        return FakeResource({})

    def ListCompliancePacks(self, request):
        self._record("ListCompliancePacks", request)
        return SimpleNamespace(
            Items=[FakeResource(dict(item)) for item in self.items],
            Total=len(self.items),
            RequestId="req-fake",
        )

    def UpdateCompliancePack(self, request):
        self._record("UpdateCompliancePack", request)
        for item in self.items:
            if item["CompliancePackId"] == request.CompliancePackId:
                item["CompliancePackName"] = request.CompliancePackName
                item["Description"] = request.Description
                item["RiskLevel"] = request.RiskLevel
                item["ConfigRules"] = [self._rule_to_dict(r) for r in (request.ConfigRules or [])]
                break
        return SimpleNamespace(RequestId="req-fake")

    def UpdateCompliancePackStatus(self, request):
        self._record("UpdateCompliancePackStatus", request)
        for item in self.items:
            if item["CompliancePackId"] == request.CompliancePackId:
                item["Status"] = request.Status
                break
        return SimpleNamespace(RequestId="req-fake")

    def written(self):
        return [name for name, _ in self.calls if name in WRITE_OPS]


def _patch_env(monkeypatch, fake):
    """Wire the module's SDK boundary to the in-memory client."""
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(
        mod,
        "_load",
        lambda: (FakeModels(), SimpleNamespace(ConfigClient=object)),
    )
    monkeypatch.setattr(
        TencentCloudModule,
        "create_client",
        lambda self, client_class, endpoint: fake,
    )
    return fake


# ---------------------------------------------------------------------------
# Request-builder helpers
# ---------------------------------------------------------------------------


def test_list_request_without_name():
    request = mod.list_request(FakeModels(), _params())
    assert request.Offset == 0
    assert request.Limit == 100
    assert not hasattr(request, "CompliancePackName")


def test_list_request_with_name_and_offset():
    request = mod.list_request(FakeModels(), _params(name="production-security"), offset=200)
    assert request.Offset == 200
    assert request.CompliancePackName == "production-security"


def test_describe_request():
    request = mod.describe_request(FakeModels(), "cp-8b0a1c2d")
    assert request.CompliancePackId == "cp-8b0a1c2d"


def test_rules_full_and_minimal():
    rules = mod._rules(
        FakeModels(),
        [
            _rule_param(),
            _rule_param(
                name="eip-unbound",
                risk_level=2,
                identifier="eip-unbound-check",
                config_rule_id="cr-11223344",
                description="",
                managed_rule_identifier=None,
                input_parameters=[],
            ),
        ],
    )
    assert len(rules) == 2
    full, minimal = rules
    assert full.RuleName == "public-bucket-denied"
    assert full.RiskLevel == 1
    assert full.ManagedRuleIdentifier == "cos-public-read-prohibited"
    assert full.Description == "Deny public reads"
    assert [x.ParameterKey for x in full.InputParameter] == ["region"]
    assert [x.Type for x in full.InputParameter] == ["string"]
    assert minimal.RuleName == "eip-unbound"
    assert minimal.RiskLevel == 2
    assert minimal.InputParameter == []
    assert not hasattr(minimal, "ManagedRuleIdentifier")


def test_create_request():
    p = _params(name="production-security", description="Production baseline", risk_level=1, rules=[_rule_param()])
    request = mod.create_request(FakeModels(), p)
    assert request.CompliancePackName == "production-security"
    assert request.Description == "Production baseline"
    assert request.RiskLevel == 1
    assert [x.RuleName for x in request.ConfigRules] == ["public-bucket-denied"]


def test_update_request():
    p = _params(name="renamed", description="Production baseline", risk_level=1, rules=[_rule_param()])
    request = mod.update_request(FakeModels(), p, "cp-8b0a1c2d")
    assert request.CompliancePackId == "cp-8b0a1c2d"
    assert request.CompliancePackName == "renamed"
    assert request.RiskLevel == 1
    assert [x.RuleName for x in request.ConfigRules] == ["public-bucket-denied"]


def test_status_request_enabled_and_disabled():
    active = mod.status_request(FakeModels(), "cp-8b0a1c2d", True)
    assert active.CompliancePackId == "cp-8b0a1c2d"
    assert active.Status == "ACTIVE"
    inactive = mod.status_request(FakeModels(), "cp-8b0a1c2d", False)
    assert inactive.Status == "UN_ACTIVE"


def test_delete_request():
    request = mod.delete_request(FakeModels(), "cp-8b0a1c2d")
    assert request.CompliancePackId == "cp-8b0a1c2d"


# ---------------------------------------------------------------------------
# _normalized_rules
# ---------------------------------------------------------------------------


def test_normalized_rules_api_shape_sorted_by_config_rule_id():
    rules = [
        {
            "RuleName": "second",
            "RiskLevel": 2,
            "Identifier": "i2",
            "ConfigRuleId": "cr-2",
            "Description": "second pack rule",
            "InputParameter": [{"ParameterKey": "k2", "Type": "str", "Value": "v2"}],
        },
        {
            "RuleName": "first",
            "RiskLevel": 1,
            "Identifier": "i1",
            "ConfigRuleId": "cr-1",
            "ManagedRuleIdentifier": "m1",
            "Description": "",
            "InputParameter": [
                {"ParameterKey": "k1", "Type": "str", "Value": "v1"},
                {"ParameterKey": "k0", "Type": "int", "Value": "0"},
            ],
        },
    ]
    normalized = mod._normalized_rules(rules)
    assert [x["ConfigRuleId"] for x in normalized] == ["cr-1", "cr-2"]
    assert normalized[0]["ManagedRuleIdentifier"] == "m1"
    assert [x["ParameterKey"] for x in normalized[0]["InputParameter"]] == ["k0", "k1"]
    assert normalized[0]["InputParameter"][0] == {"ParameterKey": "k0", "Type": "int", "Value": "0"}
    assert normalized[1]["ManagedRuleIdentifier"] is None
    assert normalized[1]["InputParameter"] == [{"ParameterKey": "k2", "Type": "str", "Value": "v2"}]


def test_normalized_rules_param_shape():
    rules = [
        _rule_param(),
        _rule_param(
            name="eip-unbound",
            risk_level=2,
            identifier="eip-unbound-check",
            config_rule_id="cr-00000000",
            description="",
            managed_rule_identifier=None,
            input_parameters=[],
        ),
    ]
    normalized = mod._normalized_rules(rules)
    assert [x["ConfigRuleId"] for x in normalized] == ["cr-00000000", "cr-9f6e5d4c"]
    assert normalized[0]["RuleName"] == "eip-unbound"
    assert normalized[0]["RiskLevel"] == 2
    assert normalized[0]["InputParameter"] == []
    assert normalized[1]["ManagedRuleIdentifier"] == "cos-public-read-prohibited"
    assert normalized[1]["Description"] == "Deny public reads"
    assert normalized[1]["InputParameter"] == [{"ParameterKey": "region", "Type": "string", "Value": "ap-guangzhou"}]


def test_normalized_rules_none_is_empty():
    assert mod._normalized_rules(None) == []


# ---------------------------------------------------------------------------
# find_pack()
# ---------------------------------------------------------------------------


def test_find_pack_by_id():
    fake = FakeConfigClient(items=[_pack()])
    module = FakeModule()
    found = mod.find_pack(module, fake, FakeModels(), _params(compliance_pack_id="cp-8b0a1c2d"))
    assert found["CompliancePackName"] == "production-security"
    assert found["Status"] == "ACTIVE"
    assert "RequestId" not in found
    assert [name for name, _ in fake.calls] == ["ListCompliancePacks", "DescribeCompliancePack"]


def test_find_pack_by_name():
    fake = FakeConfigClient(items=[_pack()])
    module = FakeModule()
    found = mod.find_pack(module, fake, FakeModels(), _params(name="production-security"))
    assert found["CompliancePackId"] == "cp-8b0a1c2d"


def test_find_pack_returns_none_when_absent():
    fake = FakeConfigClient()
    module = FakeModule()
    found = mod.find_pack(module, fake, FakeModels(), _params(name="missing"))
    assert found is None
    assert [name for name, _ in fake.calls] == ["ListCompliancePacks"]


def test_find_pack_fails_on_multiple_matches():
    fake = FakeConfigClient(
        items=[
            _pack(CompliancePackId="cp-1", CompliancePackName="dup"),
            _pack(CompliancePackId="cp-2", CompliancePackName="dup"),
        ]
    )
    module = FakeModule()
    with pytest.raises(AnsibleFailJson) as exc:
        mod.find_pack(module, fake, FakeModels(), _params(name="dup"))
    assert "Multiple compliance packs matched" in exc.value.args[0]["msg"]


# ---------------------------------------------------------------------------
# run_module main paths
# ---------------------------------------------------------------------------


def test_required_one_of_enforced(monkeypatch):
    _patch_env(monkeypatch, FakeConfigClient())
    module_args()
    with pytest.raises(AnsibleFailJson):
        run(mod.run_module)


def test_present_without_name_fails(monkeypatch):
    _patch_env(monkeypatch, FakeConfigClient())
    _run_args(compliance_pack_id="cp-8b0a1c2d")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "name is required when state=present" in exc.value.args[0]["msg"]


def test_sdk_error_is_reported(monkeypatch):
    _patch_env(monkeypatch, _BoomClient())
    _run_args(compliance_pack_id="cp-8b0a1c2d", name="production-security")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["failed"] is True
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert payload["error"] == "service exploded"


def test_absent_noop_when_not_found(monkeypatch):
    fake = _patch_env(monkeypatch, FakeConfigClient())
    _run_args(state="absent", compliance_pack_id="cp-8b0a1c2d")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["compliance_pack"] is None
    assert fake.written() == []


def test_absent_removes_existing(monkeypatch):
    fake = _patch_env(monkeypatch, FakeConfigClient(items=[_pack()]))
    _run_args(state="absent", compliance_pack_id="cp-8b0a1c2d")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["compliance_pack"] is None
    assert fake.written() == ["DeleteCompliancePack"]
    assert fake.items == []


def test_absent_check_mode_does_not_delete(monkeypatch):
    fake = _patch_env(monkeypatch, FakeConfigClient(items=[_pack()]))
    _run_args(_ansible_check_mode=True, state="absent", compliance_pack_id="cp-8b0a1c2d")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["compliance_pack"]["CompliancePackId"] == "cp-8b0a1c2d"
    assert fake.written() == []
    assert len(fake.items) == 1


def test_present_creates_missing_pack(monkeypatch):
    fake = _patch_env(monkeypatch, FakeConfigClient())
    _run_args(
        name="production-security",
        description="Production baseline",
        risk_level=1,
        enabled=True,
        rules=[_rule_param()],
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert fake.written() == ["AddCompliancePack", "UpdateCompliancePackStatus"]
    pack = result["compliance_pack"]
    assert pack["CompliancePackId"].startswith("cp-fake-")
    assert pack["CompliancePackName"] == "production-security"
    assert pack["Description"] == "Production baseline"
    assert pack["Status"] == "ACTIVE"
    assert pack["ConfigRules"][0]["RuleName"] == "public-bucket-denied"


def test_present_up_to_date_noop(monkeypatch):
    fake = _patch_env(monkeypatch, FakeConfigClient(items=[_pack()]))
    _run_args(
        name="production-security",
        description="Production baseline",
        risk_level=1,
        enabled=True,
        rules=[_rule_param()],
    )
    result = run(mod.run_module)
    assert result["changed"] is False
    assert fake.written() == []


def test_present_updates_content_drift(monkeypatch):
    fake = _patch_env(monkeypatch, FakeConfigClient(items=[_pack(Description="Stale baseline")]))
    _run_args(
        name="production-security",
        description="Production baseline",
        risk_level=1,
        enabled=True,
        rules=[_rule_param()],
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert fake.written() == ["UpdateCompliancePack"]
    assert result["compliance_pack"]["Description"] == "Production baseline"


def test_present_updates_status_only_drift(monkeypatch):
    fake = _patch_env(monkeypatch, FakeConfigClient(items=[_pack(Status="UN_ACTIVE")]))
    _run_args(
        name="production-security",
        description="Production baseline",
        risk_level=1,
        enabled=True,
        rules=[_rule_param()],
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert fake.written() == ["UpdateCompliancePackStatus"]
    assert result["compliance_pack"]["Status"] == "ACTIVE"


def test_present_disables_when_enabled_false(monkeypatch):
    fake = _patch_env(monkeypatch, FakeConfigClient(items=[_pack()]))
    _run_args(
        name="production-security",
        description="Production baseline",
        risk_level=1,
        enabled=False,
        rules=[_rule_param()],
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert fake.written() == ["UpdateCompliancePackStatus"]
    assert result["compliance_pack"]["Status"] == "UN_ACTIVE"


def test_present_check_mode_create_does_not_write(monkeypatch):
    fake = _patch_env(monkeypatch, FakeConfigClient())
    _run_args(
        _ansible_check_mode=True,
        name="production-security",
        description="Production baseline",
        risk_level=1,
        enabled=True,
        rules=[_rule_param()],
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["compliance_pack"] is None
    assert fake.written() == []
    assert fake.items == []


def test_present_check_mode_update_does_not_write(monkeypatch):
    fake = _patch_env(monkeypatch, FakeConfigClient(items=[_pack(Description="Stale baseline")]))
    _run_args(
        _ansible_check_mode=True,
        name="production-security",
        description="Production baseline",
        risk_level=1,
        enabled=True,
        rules=[_rule_param()],
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["compliance_pack"]["Description"] == "Stale baseline"
    assert fake.written() == []


class _BoomClient(object):
    """Every SDK call raises, so the module's wrapped error path is hit."""

    def __getattr__(self, name):
        def boom(*args, **kwargs):
            raise RuntimeError("service exploded")

        return boom
