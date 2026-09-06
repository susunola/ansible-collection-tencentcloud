"""Unit tests for the ckafka_acl_rule write module (helpers + run_module).

Covers the create / update / delete flows of
``plugins/modules/ckafka_acl_rule.py`` with an in-memory fake CKafka client
whose write operations mutate the rule store, so the module's post-write
``find`` refetch converges immediately. Rules are matched by ``RuleName``
against DescribeAclRule; PatternType / Pattern / Comment / AclList are
immutable after creation and drift on them fails with a
replacement-required error, while the IsApplied (apply-to-new-topics) flag
is reconciled in place.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import ckafka_acl_rule as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

RULE = {
    "RuleName": "orders-producers",
    "PatternType": "PREFIXED",
    "Pattern": "orders-",
    "Comment": "",
    "IsApplied": 0,
    "AclList": [{"Operation": "Write", "PermissionType": "Allow", "Host": "*", "Principal": "User:producer"}],
}


def _rule(**overrides):
    """API-shaped rule dict isolated from the shared constant."""
    item = copy.deepcopy(RULE)
    item.update(overrides)
    return item


def _params(**overrides):
    """Module parameters pre-filled from the argument spec."""
    params = {
        "state": "present",
        "instance_id": "ckafka-1",
        "name": "orders-producers",
        "pattern_type": "PREFIXED",
        "pattern": "orders-",
        "apply_to_new_topics": False,
        "comment": "",
        "rules": [{"operation": "Write", "permission": "Allow", "host": "*", "principal": "User:producer"}],
    }
    params.update(overrides)
    return params


def _run_args(**extra):
    """module_args() pre-filled with every module parameter (None dropped)."""
    args = dict(_params())
    args.update(extra)
    return module_args(**{k: v for k, v in args.items() if v is not None})


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


class FakeCkafkaClient(object):
    """In-memory CkafkaClient stand-in.

    Stores API-shaped rule dicts keyed by RuleName. DescribeAclRule returns
    the whole store; write operations mutate the store so the module's
    post-write find refetch converges.
    """

    def __init__(self, rules=None):
        self.rules = [copy.deepcopy(r) for r in (rules or [])]
        self.calls = []

    def _record(self, name, request):
        self.calls.append((name, request))
        return request

    def _get(self, rule_name):
        for stored in self.rules:
            if stored.get("RuleName") == rule_name:
                return stored
        return None

    @staticmethod
    def _acl_list(request):
        return [
            {
                "Operation": entry.Operation,
                "PermissionType": entry.PermissionType,
                "Host": entry.Host,
                "Principal": entry.Principal,
            }
            for entry in (getattr(request, "RuleList", None) or [])
        ]

    def DescribeAclRule(self, request):
        self._record("DescribeAclRule", request)
        return SimpleNamespace(
            Result=SimpleNamespace(AclRuleList=[FakeResource(dict(r)) for r in self.rules]),
            RequestId="req-fake",
        )

    def CreateAclRule(self, request):
        self._record("CreateAclRule", request)
        self.rules.append(
            {
                "RuleName": request.RuleName,
                "PatternType": request.PatternType,
                "Pattern": getattr(request, "Pattern", None),
                "Comment": request.Comment,
                "IsApplied": request.IsApplied,
                "AclList": self._acl_list(request),
            }
        )
        return SimpleNamespace(RequestId="req-fake")

    def ModifyAclRule(self, request):
        self._record("ModifyAclRule", request)
        stored = self._get(request.RuleName)
        if stored is not None:
            stored["IsApplied"] = request.IsApplied
        return SimpleNamespace(RequestId="req-fake")

    def DeleteAclRule(self, request):
        self._record("DeleteAclRule", request)
        self.rules = [r for r in self.rules if r.get("RuleName") != request.RuleName]
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake):
    """Wire the shared monkeypatches and return the fake client."""
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(
        mod,
        "_load",
        lambda: (FakeModels(), SimpleNamespace(CkafkaClient=object)),
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
    request = mod.describe_request(FakeModels(), _params())
    assert request.InstanceId == "ckafka-1"
    assert request.RuleName == "orders-producers"
    assert request.PatternType == "PREFIXED"


def test_acl_entries_maps_fields():
    entries = mod.acl_entries(FakeModels(), _params()["rules"])
    assert len(entries) == 1
    assert entries[0].Operation == "Write"
    assert entries[0].PermissionType == "Allow"
    assert entries[0].Host == "*"
    assert entries[0].Principal == "User:producer"


def test_create_request_fields():
    request = mod.create_request(FakeModels(), _params())
    assert request.InstanceId == "ckafka-1"
    assert request.ResourceType == "Topic"
    assert request.PatternType == "PREFIXED"
    assert request.RuleName == "orders-producers"
    assert request.Pattern == "orders-"
    assert request.IsApplied == 0
    assert request.Comment == ""
    assert [e.Principal for e in request.RuleList] == ["User:producer"]


def test_create_request_preset_omits_pattern():
    request = mod.create_request(FakeModels(), _params(pattern_type="PRESET", pattern=None))
    assert request.PatternType == "PRESET"
    assert request.Pattern is None
    assert request.IsApplied == 0


def test_create_request_applies_to_new_topics_flag():
    request = mod.create_request(FakeModels(), _params(apply_to_new_topics=True))
    assert request.IsApplied == 1


def test_update_request_fields():
    request = mod.update_request(FakeModels(), _params(apply_to_new_topics=True))
    assert request.InstanceId == "ckafka-1"
    assert request.RuleName == "orders-producers"
    assert request.IsApplied == 1


def test_delete_request_fields():
    request = mod.delete_request(FakeModels(), _params())
    assert request.InstanceId == "ckafka-1"
    assert request.RuleName == "orders-producers"


def test_normalized_rules_sorts_and_defaults_host():
    values = mod.normalized_rules(
        [
            {"Operation": "Read", "PermissionType": "Allow", "Host": "10.0.0.1", "Principal": "User:a"},
            {"Operation": "Write", "PermissionType": "Allow", "Host": None, "Principal": "User:a"},
            {"Operation": "Read", "PermissionType": "Deny", "Host": "*", "Principal": "User:b"},
        ]
    )
    # Sorted by (principal, host, operation, permission); "*" < "10.0.0.1".
    assert values == [
        {"operation": "Write", "permission": "Allow", "host": "*", "principal": "User:a"},  # None host -> "*"
        {"operation": "Read", "permission": "Allow", "host": "10.0.0.1", "principal": "User:a"},
        {"operation": "Read", "permission": "Deny", "host": "*", "principal": "User:b"},
    ]


def test_normalized_rules_handles_sdk_objects():
    values = mod.normalized_rules(
        [
            SimpleNamespace(
                Operation="Write",
                PermissionType="Allow",
                Host="*",
                Principal="User:x",
                _serialize=lambda allow_none=True: {
                    "Operation": "Write",
                    "PermissionType": "Allow",
                    "Host": "*",
                    "Principal": "User:x",
                },
            )
        ]
    )
    assert values == [{"operation": "Write", "permission": "Allow", "host": "*", "principal": "User:x"}]


def test_comparable_normalises_fields():
    value = mod.comparable(_rule(IsApplied="1"))
    assert value["PatternType"] == "PREFIXED"
    assert value["Pattern"] == "orders-"
    assert value["Comment"] == ""
    assert value["IsApplied"] == 1
    assert value["AclList"] == [{"operation": "Write", "permission": "Allow", "host": "*", "principal": "User:producer"}]


def test_desired_matches_params():
    value = mod.desired(_params(apply_to_new_topics=True))
    assert value["PatternType"] == "PREFIXED"
    assert value["Pattern"] == "orders-"
    assert value["Comment"] == ""
    assert value["IsApplied"] == 1
    assert value["AclList"] == [{"operation": "Write", "permission": "Allow", "host": "*", "principal": "User:producer"}]


# ---------------------------------------------------------------------------
# find tests
# ---------------------------------------------------------------------------


def test_find_matching_rule(monkeypatch):
    fake = FakeCkafkaClient([_rule(RuleName="other"), _rule()])
    _make_module(monkeypatch, fake)
    module = FakeModule(_params())
    value = mod.find(module, fake, FakeModels(), module.params)
    assert value["RuleName"] == "orders-producers"


def test_find_no_match_returns_none(monkeypatch):
    fake = FakeCkafkaClient([_rule(RuleName="other")])
    _make_module(monkeypatch, fake)
    module = FakeModule(_params(name="ghost"))
    assert mod.find(module, fake, FakeModels(), module.params) is None


# ---------------------------------------------------------------------------
# run_module main-path tests
# ---------------------------------------------------------------------------


def test_instance_id_and_name_required():
    module_args(state="present", rules=_params()["rules"])  # no instance_id / name
    with pytest.raises(AnsibleFailJson):
        run(mod.run_module)


def test_rules_required_when_present():
    module_args(instance_id="ckafka-1", name="orders-producers")  # state present without rules
    with pytest.raises(AnsibleFailJson):
        run(mod.run_module)


def test_pattern_required_for_prefixed(monkeypatch):
    fake = FakeCkafkaClient()
    _make_module(monkeypatch, fake)
    _run_args(pattern=None)  # PREFIXED without pattern
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "pattern is required for PREFIXED ACL rules" in exc.value.args[0]["msg"]
    assert not fake.calls  # validation precedes any SDK call


def test_present_creates_rule(monkeypatch):
    fake = FakeCkafkaClient()
    _make_module(monkeypatch, fake)
    _run_args()
    result = run(mod.run_module)
    assert result["changed"] is True
    rule = result["acl_rule"]
    assert rule["RuleName"] == "orders-producers"
    assert rule["PatternType"] == "PREFIXED"
    names = [c[0] for c in fake.calls]
    assert names.count("DescribeAclRule") == 2  # find + refetch
    assert names.count("CreateAclRule") == 1
    create = [c for c in fake.calls if c[0] == "CreateAclRule"][0][1]
    assert create.InstanceId == "ckafka-1"
    assert create.Pattern == "orders-"


def test_present_creates_preset_rule(monkeypatch):
    fake = FakeCkafkaClient()
    _make_module(monkeypatch, fake)
    _run_args(pattern_type="PRESET", pattern=None)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["acl_rule"]["PatternType"] == "PRESET"


def test_present_noop_returns_unchanged(monkeypatch):
    fake = FakeCkafkaClient([_rule()])
    _make_module(monkeypatch, fake)
    _run_args()
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["acl_rule"]["RuleName"] == "orders-producers"
    names = [c[0] for c in fake.calls]
    assert "CreateAclRule" not in names
    assert "ModifyAclRule" not in names


def test_present_apply_flag_drift_triggers_update(monkeypatch):
    fake = FakeCkafkaClient([_rule()])
    _make_module(monkeypatch, fake)
    _run_args(apply_to_new_topics=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["acl_rule"]["IsApplied"] == 1
    modify = [c for c in fake.calls if c[0] == "ModifyAclRule"][0][1]
    assert modify.RuleName == "orders-producers"
    assert modify.IsApplied == 1


def test_present_immutable_pattern_drift_fails(monkeypatch):
    fake = FakeCkafkaClient([_rule()])
    _make_module(monkeypatch, fake)
    _run_args(pattern="customers-")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "Immutable fields cannot be changed" in payload["msg"]
    assert payload["replacement_required"] is True
    assert payload["immutable_changes"]["Pattern"]["before"] == "orders-"
    assert payload["immutable_changes"]["Pattern"]["after"] == "customers-"
    assert not any("ModifyAclRule" == c[0] for c in fake.calls)


def test_present_immutable_comment_drift_fails(monkeypatch):
    fake = FakeCkafkaClient([_rule()])
    _make_module(monkeypatch, fake)
    _run_args(comment="changed")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "Immutable fields cannot be changed" in exc.value.args[0]["msg"]


def test_present_immutable_acl_list_drift_fails(monkeypatch):
    fake = FakeCkafkaClient([_rule()])
    _make_module(monkeypatch, fake)
    _run_args(rules=[{"operation": "Read", "permission": "Allow", "host": "*", "principal": "User:consumer"}])
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "Immutable fields cannot be changed" in payload["msg"]
    assert "AclList" in payload["immutable_changes"]
    assert not any("ModifyAclRule" == c[0] for c in fake.calls)


def test_sdk_error_is_reported(monkeypatch):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(
        mod,
        "_load",
        lambda: (FakeModels(), SimpleNamespace(CkafkaClient=object)),
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


def test_check_mode_create_is_dry_run(monkeypatch):
    fake = FakeCkafkaClient()
    _make_module(monkeypatch, fake)
    module_args(_ansible_check_mode=True, **{k: v for k, v in _params().items() if v is not None})
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["acl_rule"] is None  # nothing to report for a dry-run create
    assert not any("CreateAclRule" == c[0] for c in fake.calls)


def test_check_mode_update_is_dry_run(monkeypatch):
    fake = FakeCkafkaClient([_rule()])
    _make_module(monkeypatch, fake)
    module_args(_ansible_check_mode=True, **{k: v for k, v in _params(apply_to_new_topics=True).items() if v is not None})
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["acl_rule"]["IsApplied"] == 0  # pre-change state reported
    assert not any("ModifyAclRule" == c[0] for c in fake.calls)


def test_absent_removes_rule(monkeypatch):
    fake = FakeCkafkaClient([_rule()])
    _make_module(monkeypatch, fake)
    _run_args(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["acl_rule"] is None
    delete = [c for c in fake.calls if c[0] == "DeleteAclRule"][0][1]
    assert delete.RuleName == "orders-producers"
    assert fake.rules == []


def test_absent_not_found_is_noop(monkeypatch):
    fake = FakeCkafkaClient([_rule()])
    _make_module(monkeypatch, fake)
    _run_args(state="absent", name="ghost")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["acl_rule"] is None
    assert not any("DeleteAclRule" == c[0] for c in fake.calls)


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeCkafkaClient([_rule()])
    _make_module(monkeypatch, fake)
    module_args(_ansible_check_mode=True, **{k: v for k, v in _params(state="absent").items() if v is not None})
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["acl_rule"]["RuleName"] == "orders-producers"  # pre-change state reported
    assert not any("DeleteAclRule" == c[0] for c in fake.calls)
    assert len(fake.rules) == 1
