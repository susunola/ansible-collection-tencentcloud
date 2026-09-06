"""Unit tests for the tcr_replication_rule write module (helpers + run_module).

Creates, updates, enables/disables and deletes Enterprise TCR replication
policies. Lookup walks DescribeReplicationPolicies page by page (Page /
PageSize 100) and matches the raw policy's ``Name`` before serializing;
the fake list items are :class:`FakeResource` so both ``.Name`` attribute
access and ``_serialize`` work. ``desired``/``normalize`` compare on
sorted lowercase ``Filters`` with bool-cast flags, so drift updates
route through ModifyReplication (with a ``ModifyReplicationRule`` that
carries ``Enabled`` but no ``Name``); a brand-new rule is created through
ManageReplication, followed by an extra disable call when ``enabled`` is
false.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import tcr_replication_rule as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)


def _rule(**overrides):
    """API-shaped replication rule dict isolated from the shared constant."""
    item = {
        "RegistryId": "tcr-abc",
        "Name": "production-images",
        "DestNamespace": "prod",
        "Override": True,
        "Deletion": False,
        "Enabled": True,
        "Description": "",
        "Filters": [{"Type": "namespace", "Value": "production"}],
    }
    item.update(overrides)
    return item


def _params(**overrides):
    """Module parameters pre-filled from the argument spec defaults."""
    params = {
        "state": "present",
        "registry_id": "tcr-abc",
        "destination_registry_id": "tcr-dst",
        "destination_region_id": 4,
        "name": "production-images",
        "destination_namespace": "prod",
        "filters": [{"type": "namespace", "value": "production"}],
        "override": True,
        "deletion": False,
        "enabled": True,
        "description": "",
    }
    params.update(overrides)
    return params


def _run_args(**extra):
    """module_args() pre-filled with every non-None module parameter."""
    return module_args(**dict(_params(), **extra))


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


class FakeTcrClient(object):
    """In-memory TcrClient stand-in storing replication rule dicts.

    DescribeReplicationPolicies honours RegistryId/Page/PageSize so the
    module's pagination walk can be exercised; items are returned as
    :class:`FakeResource` (raw ``.Name`` attribute plus ``_serialize``).
    ManageReplication seeds a rule from the request's rule object (filters
    are SDK objects converted to ``Type``/``Value`` dicts), and
    ModifyReplication updates a rule by source registry + rule name,
    carrying ``Enabled`` only when the rule model exposes it.
    """

    def __init__(self, rules=None):
        self.rules = [copy.deepcopy(r) for r in (rules or [])]
        self.calls = []

    def _record(self, name, request):
        self.calls.append((name, request))
        return request

    def DescribeReplicationPolicies(self, request):
        self._record("DescribeReplicationPolicies", request)
        rules = [r for r in self.rules if r.get("RegistryId") == request.RegistryId]
        offset = (request.Page - 1) * request.PageSize
        page = rules[offset : offset + request.PageSize]
        return SimpleNamespace(
            ReplicationPolicyInfoList=[FakeResource(dict(r)) for r in page],
            TotalCount=len(rules),
            RequestId="req-fake",
        )

    def ManageReplication(self, request):
        self._record("ManageReplication", request)
        rule = request.Rule
        self.rules.append(
            {
                "RegistryId": request.SourceRegistryId,
                "Name": rule.Name,
                "DestNamespace": rule.DestNamespace,
                "Override": rule.Override,
                "Deletion": rule.Deletion,
                "Filters": [{"Type": f.Type, "Value": f.Value} for f in rule.Filters],
                "Enabled": True,
                "Description": request.Description,
                "DestinationRegistryId": request.DestinationRegistryId,
                "DestinationRegionId": request.DestinationRegionId,
            }
        )
        return SimpleNamespace(RequestId="req-fake")

    def ModifyReplication(self, request):
        self._record("ModifyReplication", request)
        rule = request.Rule
        for stored in self.rules:
            if stored.get("RegistryId") == request.SourceRegistryId and stored.get("Name") == request.RuleName:
                stored["DestNamespace"] = rule.DestNamespace
                stored["Override"] = rule.Override
                stored["Deletion"] = rule.Deletion
                stored["Filters"] = [{"Type": f.Type, "Value": f.Value} for f in rule.Filters]
                if hasattr(rule, "Enabled"):
                    stored["Enabled"] = rule.Enabled
                stored["Description"] = request.Description
        return SimpleNamespace(RequestId="req-fake")

    def DeleteReplicationRule(self, request):
        self._record("DeleteReplicationRule", request)
        self.rules = [
            r for r in self.rules
            if not (r.get("RegistryId") == request.SourceRegistryId and r.get("Name") == request.RuleName)
        ]
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake):
    """Wire the shared monkeypatches and return the fake client."""
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(
        mod,
        "_load",
        lambda: (FakeModels(), SimpleNamespace(TcrClient=object)),
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


def test_filter_models_builds_typed_items():
    items = mod.filter_models(FakeModels(), [{"type": "namespace", "value": "production"}, {"type": "repository", "value": "api"}])
    assert [(item.Type, item.Value) for item in items] == [("namespace", "production"), ("repository", "api")]
    assert mod.filter_models(FakeModels(), []) == []


def test_desired_maps_and_sorts_filters():
    target = mod.desired(_params(filters=[{"type": "repository", "value": "api"}, {"type": "namespace", "value": "production"}]))
    assert target["Name"] == "production-images"
    assert target["Description"] == ""
    assert target["Override"] is True
    assert target["Enabled"] is True
    assert target["Filters"] == [{"type": "namespace", "value": "production"}, {"type": "repository", "value": "api"}]


def test_normalize_bool_casts_and_sorts():
    norm = mod.normalize(
        {
            "Name": "production-images",
            "Description": "note",
            "Override": 1,
            "Enabled": 0,
            "Filters": [{"Type": "repository", "Value": "api"}, {"Type": "namespace", "Value": "production"}],
        }
    )
    assert norm["Override"] is True
    assert norm["Enabled"] is False
    assert norm["Filters"] == [{"type": "namespace", "value": "production"}, {"type": "repository", "value": "api"}]


def test_normalize_defaults_description_and_flags():
    norm = mod.normalize({"Name": "x", "Filters": []})
    assert norm["Description"] == ""
    assert norm["Override"] is False
    assert norm["Enabled"] is False
    assert norm["Filters"] == []


def test_rule_model_create_has_name_no_enabled():
    rule = mod.rule_model(FakeModels(), _params())
    assert rule.Name == "production-images"
    assert rule.DestNamespace == "prod"
    assert rule.Override is True
    assert rule.Deletion is False
    assert [(f.Type, f.Value) for f in rule.Filters] == [("namespace", "production")]
    assert not hasattr(rule, "Enabled")


def test_rule_model_modify_has_enabled_no_name():
    rule = mod.rule_model(FakeModels(), _params(enabled=False), modifying=True)
    assert not hasattr(rule, "Name")
    assert rule.Enabled is False
    assert rule.DestNamespace == "prod"
    assert [(f.Type, f.Value) for f in rule.Filters] == [("namespace", "production")]


# ---------------------------------------------------------------------------
# find tests
# ---------------------------------------------------------------------------


def test_find_matches_rule_by_name(monkeypatch):
    fake = FakeTcrClient([_rule(Name="other-rule"), _rule()])
    _make_module(monkeypatch, fake)
    module = FakeModule(_params())
    value = mod.find(module, fake, FakeModels(), "tcr-abc", "production-images")
    assert value["Name"] == "production-images"
    assert value["Override"] is True


def test_find_no_match_returns_none(monkeypatch):
    fake = FakeTcrClient([_rule()])
    _make_module(monkeypatch, fake)
    module = FakeModule(_params())
    assert mod.find(module, fake, FakeModels(), "tcr-abc", "ghost") is None


def test_find_paginates_past_first_page(monkeypatch):
    rules = [_rule(Name="rule-%03d" % i, RegistryId="tcr-abc") for i in range(150)]
    rules.append(_rule(Name="production-images", RegistryId="tcr-abc", Description="deep"))
    fake = FakeTcrClient(rules)
    _make_module(monkeypatch, fake)
    module = FakeModule(_params())
    value = mod.find(module, fake, FakeModels(), "tcr-abc", "production-images")
    assert value["Name"] == "production-images"
    assert value["Description"] == "deep"
    describes = [c for c in fake.calls if c[0] == "DescribeReplicationPolicies"]
    assert len(describes) == 2
    assert describes[0][1].Page == 1
    assert describes[1][1].Page == 2
    assert describes[0][1].PageSize == 100


def test_find_ignores_other_registries(monkeypatch):
    fake = FakeTcrClient([_rule(RegistryId="tcr-other")])
    _make_module(monkeypatch, fake)
    module = FakeModule(_params())
    assert mod.find(module, fake, FakeModels(), "tcr-abc", "production-images") is None


# ---------------------------------------------------------------------------
# run_module main-path tests
# ---------------------------------------------------------------------------


def test_present_creates_rule(monkeypatch):
    fake = FakeTcrClient()
    _make_module(monkeypatch, fake)
    _run_args()
    result = run(mod.run_module)
    assert result["changed"] is True
    rule = result["replication_rule"]
    assert rule["Name"] == "production-images"
    assert rule["Enabled"] is True
    assert [c[0] for c in fake.calls].count("ManageReplication") == 1
    assert "ModifyReplication" not in [c[0] for c in fake.calls]
    manage = [c for c in fake.calls if c[0] == "ManageReplication"][0][1]
    assert manage.SourceRegistryId == "tcr-abc"
    assert manage.DestinationRegistryId == "tcr-dst"
    assert manage.DestinationRegionId == 4
    assert manage.Rule.Name == "production-images"


def test_present_create_disabled_runs_extra_modify(monkeypatch):
    fake = FakeTcrClient()
    _make_module(monkeypatch, fake)
    _run_args(enabled=False)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["replication_rule"]["Enabled"] is False
    modifies = [c for c in fake.calls if c[0] == "ModifyReplication"]
    assert len(modifies) == 1
    assert modifies[0][1].RuleName == "production-images"
    assert modifies[0][1].Rule.Enabled is False


def test_present_noop_returns_unchanged(monkeypatch):
    fake = FakeTcrClient([_rule()])
    _make_module(monkeypatch, fake)
    _run_args()
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["replication_rule"]["Name"] == "production-images"
    assert [c[0] for c in fake.calls] == ["DescribeReplicationPolicies"]  # find only


def test_present_description_drift_triggers_modify(monkeypatch):
    fake = FakeTcrClient([_rule()])
    _make_module(monkeypatch, fake)
    _run_args(description="replication for production")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["replication_rule"]["Description"] == "replication for production"
    modify = [c for c in fake.calls if c[0] == "ModifyReplication"][0][1]
    assert modify.SourceRegistryId == "tcr-abc"
    assert modify.RuleName == "production-images"
    assert modify.Description == "replication for production"
    assert modify.Rule.Enabled is True  # enabled carried on the modify model
    assert "ManageReplication" not in [c[0] for c in fake.calls]


def test_present_enabled_drift_triggers_modify(monkeypatch):
    fake = FakeTcrClient([_rule()])
    _make_module(monkeypatch, fake)
    _run_args(enabled=False)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["replication_rule"]["Enabled"] is False
    modify = [c for c in fake.calls if c[0] == "ModifyReplication"][0][1]
    assert modify.Rule.Enabled is False


def test_present_override_drift_triggers_modify(monkeypatch):
    fake = FakeTcrClient([_rule()])
    _make_module(monkeypatch, fake)
    _run_args(override=False)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["replication_rule"]["Override"] is False
    modify = [c for c in fake.calls if c[0] == "ModifyReplication"][0][1]
    assert modify.Rule.Override is False


def test_present_filter_drift_triggers_modify(monkeypatch):
    fake = FakeTcrClient([_rule()])
    _make_module(monkeypatch, fake)
    _run_args(filters=[{"type": "repository", "value": "api"}])
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["replication_rule"]["Filters"] == [{"Type": "repository", "Value": "api"}]
    modify = [c for c in fake.calls if c[0] == "ModifyReplication"][0][1]
    assert [(f.Type, f.Value) for f in modify.Rule.Filters] == [("repository", "api")]


def test_check_mode_create_is_dry_run(monkeypatch):
    fake = FakeTcrClient()
    _make_module(monkeypatch, fake)
    module_args(_ansible_check_mode=True, **dict(_params()))
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["replication_rule"] is None  # no refetch in check mode
    assert not any(c[0] == "ManageReplication" for c in fake.calls)


def test_check_mode_update_is_dry_run(monkeypatch):
    fake = FakeTcrClient([_rule()])
    _make_module(monkeypatch, fake)
    module_args(_ansible_check_mode=True, **dict(_params(description="new note")))
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["replication_rule"]["Name"] == "production-images"  # pre-change rule
    assert not any(c[0] == "ModifyReplication" for c in fake.calls)


def test_absent_not_found_is_noop(monkeypatch):
    fake = FakeTcrClient([_rule(Name="other")])
    _make_module(monkeypatch, fake)
    _run_args(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["replication_rule"] is None
    assert not any(c[0] == "DeleteReplicationRule" for c in fake.calls)


def test_absent_deletes_rule(monkeypatch):
    fake = FakeTcrClient([_rule(), _rule(Name="keep-me")])
    _make_module(monkeypatch, fake)
    _run_args(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["replication_rule"] is None
    delete = [c for c in fake.calls if c[0] == "DeleteReplicationRule"][0][1]
    assert delete.SourceRegistryId == "tcr-abc"
    assert delete.RuleName == "production-images"
    assert [r["Name"] for r in fake.rules] == ["keep-me"]


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeTcrClient([_rule()])
    _make_module(monkeypatch, fake)
    module_args(_ansible_check_mode=True, **dict(_params(state="absent")))
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["replication_rule"]["Name"] == "production-images"  # pre-change rule reported
    assert not any(c[0] == "DeleteReplicationRule" for c in fake.calls)
    assert len(fake.rules) == 1


def test_sdk_error_is_reported(monkeypatch):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(
        mod,
        "_load",
        lambda: (FakeModels(), SimpleNamespace(TcrClient=object)),
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
