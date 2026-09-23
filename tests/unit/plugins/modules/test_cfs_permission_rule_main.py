"""Unit tests for the cfs_permission_rule write module (run_module flows).

Creates, updates and deletes one client rule inside a CFS permission group.
Rules are matched by ``rule_id`` when given, otherwise by an exact
``AuthClientIp``; a single rule must match. ``absent`` deletes the matched
rule, ``present`` converges its client expression, priority, access and user
mapping. A missing rule under ``present`` with no ``rule_id`` creates one and
remembers the returned id for the follow-up describe.

Scenario matrix:

* absent on a missing rule is idempotent
* absent deletes the matched rule (check mode is a dry run)
* creation when missing (happy path and check mode)
* no-op when the existing rule matches
* drift triggers an update, identified by rule id or client ip
* an ambiguous client-ip match fails
* validation and SDK failure paths
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import cfs_permission_rule as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

RULE = {
    "PGroupId": "pgroup-abc123",
    "RuleId": 1001,
    "AuthClientIp": "10.0.0.0/16",
    "Priority": 1,
    "RWPermission": "RW",
    "UserPermission": "no_root_squash",
}


def _rule(**overrides):
    item = copy.deepcopy(RULE)
    item.update(overrides)
    return item


def _params(**overrides):
    params = {
        "permission_group_id": "pgroup-abc123",
        "client_ip": "10.0.0.0/16",
        "priority": 1,
        "access": "RW",
        "user_permission": "no_root_squash",
    }
    params.update(overrides)
    return params


def _run_args(**overrides):
    return module_args(**_params(**overrides))


class FakeCfsClient(object):
    """In-memory CFS client storing rules for one permission group."""

    def __init__(self, rules=None):
        self.rules = [copy.deepcopy(r) for r in (rules or [])]
        self.calls = []
        self._next = 2000

    def _by_id(self, rule_id):
        for item in self.rules:
            if str(item.get("RuleId")) == str(rule_id):
                return item
        return None

    def DescribeCfsRules(self, request):
        self.calls.append(("DescribeCfsRules", request))
        return SimpleNamespace(RuleList=[FakeResource(r) for r in self.rules])

    def CreateCfsRule(self, request):
        self.calls.append(("CreateCfsRule", request))
        self._next += 1
        item = {
            "PGroupId": request.PGroupId,
            "RuleId": self._next,
            "AuthClientIp": request.AuthClientIp,
            "Priority": request.Priority,
            "RWPermission": request.RWPermission,
            "UserPermission": request.UserPermission,
        }
        self.rules.append(item)
        return SimpleNamespace(RuleId=self._next, RequestId="req-fake")

    def UpdateCfsRule(self, request):
        self.calls.append(("UpdateCfsRule", request))
        item = self._by_id(request.RuleId)
        if item is not None:
            item["AuthClientIp"] = request.AuthClientIp
            item["Priority"] = request.Priority
            item["RWPermission"] = request.RWPermission
            item["UserPermission"] = request.UserPermission
        return SimpleNamespace(RequestId="req-fake")

    def DeleteCfsRule(self, request):
        self.calls.append(("DeleteCfsRule", request))
        self.rules = [r for r in self.rules if not (r.get("PGroupId") == request.PGroupId and str(r.get("RuleId")) == str(request.RuleId))]
        return SimpleNamespace(RequestId="req-fake")


class _BoomClient(object):
    """Every SDK call raises so the wrapped SDK failure path is reached."""

    def __getattr__(self, name):
        def boom(*args, **kwargs):
            raise RuntimeError("service exploded")

        return boom


def _make_module(monkeypatch, fake):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (FakeModels(), SimpleNamespace(CfsClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


# ---------------------------------------------------------------------------
# absent flows
# ---------------------------------------------------------------------------


def test_absent_missing_rule_is_idempotent(monkeypatch):
    fake = FakeCfsClient(rules=[_rule(RuleId=1002, AuthClientIp="10.99.0.0/16")])
    _make_module(monkeypatch, fake)
    _run_args(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["rule"] is None
    assert [name for name, unused in fake.calls] == ["DescribeCfsRules"]


def test_absent_deletes_rule(monkeypatch):
    fake = FakeCfsClient(rules=[_rule()])
    _make_module(monkeypatch, fake)
    _run_args(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["rule"] is None
    assert fake.rules == []
    ops = [name for name, unused in fake.calls]
    assert ops == ["DescribeCfsRules", "DeleteCfsRule"]
    delete = [request for name, request in fake.calls if name == "DeleteCfsRule"][0]
    assert delete.PGroupId == "pgroup-abc123"
    assert delete.RuleId == "1001"


def test_absent_by_rule_id_deletes(monkeypatch):
    fake = FakeCfsClient(rules=[_rule()])
    _make_module(monkeypatch, fake)
    module_args(state="absent", permission_group_id="pgroup-abc123", rule_id="1001", client_ip="10.0.0.0/16")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert fake.rules == []


def test_absent_in_check_mode_is_dry_run(monkeypatch):
    fake = FakeCfsClient(rules=[_rule()])
    _make_module(monkeypatch, fake)
    _run_args(_ansible_check_mode=True, state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["rule"]["RuleId"] == 1001  # matched rule shown as preview
    assert len(fake.rules) == 1
    assert "DeleteCfsRule" not in [name for name, unused in fake.calls]


# ---------------------------------------------------------------------------
# creation flows
# ---------------------------------------------------------------------------


def test_create_rule(monkeypatch):
    fake = FakeCfsClient(rules=[])
    _make_module(monkeypatch, fake)
    _run_args(state="present", access="RO", user_permission="root_squash", priority=10)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["rule"]["RuleId"] == 2001
    assert result["rule"]["AuthClientIp"] == "10.0.0.0/16"
    assert result["rule"]["RWPermission"] == "RO"
    assert len(fake.rules) == 1
    ops = [name for name, unused in fake.calls]
    assert ops[0] == "DescribeCfsRules"
    assert "CreateCfsRule" in ops


def test_create_check_mode_is_dry_run(monkeypatch):
    fake = FakeCfsClient(rules=[])
    _make_module(monkeypatch, fake)
    _run_args(_ansible_check_mode=True, state="present")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["rule"] is None
    assert fake.rules == []
    assert "CreateCfsRule" not in [name for name, unused in fake.calls]


def test_create_with_rule_id_not_found(monkeypatch):
    fake = FakeCfsClient(rules=[_rule(RuleId=1002, AuthClientIp="10.99.0.0/16")])
    _make_module(monkeypatch, fake)
    module_args(state="present", permission_group_id="pgroup-abc123", rule_id="9999", client_ip="10.0.0.0/16")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["rule"]["RuleId"] == 2001
    assert len(fake.rules) == 2


# ---------------------------------------------------------------------------
# existing-rule flows
# ---------------------------------------------------------------------------


def test_existing_rule_no_drift_is_idempotent(monkeypatch):
    fake = FakeCfsClient(rules=[_rule()])
    _make_module(monkeypatch, fake)
    _run_args(state="present")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["rule"]["RuleId"] == 1001
    assert "UpdateCfsRule" not in [name for name, unused in fake.calls]


def test_access_and_priority_drift_update(monkeypatch):
    fake = FakeCfsClient(rules=[_rule(Priority=50, RWPermission="RO")])
    _make_module(monkeypatch, fake)
    _run_args(state="present")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["rule"]["Priority"] == 1
    assert result["rule"]["RWPermission"] == "RW"
    ops = [name for name, unused in fake.calls]
    assert ops == ["DescribeCfsRules", "UpdateCfsRule", "DescribeCfsRules"]
    update = [request for name, request in fake.calls if name == "UpdateCfsRule"][0]
    assert update.RuleId == "1001"
    assert update.Priority == 1


def test_client_expression_drift_by_rule_id(monkeypatch):
    fake = FakeCfsClient(rules=[_rule()])
    _make_module(monkeypatch, fake)
    module_args(
        state="present",
        permission_group_id="pgroup-abc123",
        rule_id="1001",
        client_ip="10.1.0.0/16",
        access="RO",
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["rule"]["AuthClientIp"] == "10.1.0.0/16"
    assert result["rule"]["RWPermission"] == "RO"


def test_multiple_client_ip_matches_fail(monkeypatch):
    fake = FakeCfsClient(rules=[_rule(), _rule(RuleId=1002)])
    _make_module(monkeypatch, fake)
    _run_args(state="present")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "specify rule_id" in exc.value.args[0]["msg"]


# ---------------------------------------------------------------------------
# validation and failure paths
# ---------------------------------------------------------------------------


def test_present_without_client_ip_fails(monkeypatch):
    _make_module(monkeypatch, FakeCfsClient(rules=[_rule()]))
    module_args(state="present", permission_group_id="pgroup-abc123", rule_id="1001")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "client_ip is required when state=present" in exc.value.args[0]["msg"]


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    _make_module(monkeypatch, _BoomClient())
    _run_args(state="absent")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert payload["error"] == "service exploded"


def test_main_entrypoint_runs_module(monkeypatch):
    fake = FakeCfsClient(rules=[_rule()])
    _make_module(monkeypatch, fake)
    _run_args(state="present")
    result = run(mod.main)
    assert result["changed"] is False
    assert result["rule"]["RuleId"] == 1001
