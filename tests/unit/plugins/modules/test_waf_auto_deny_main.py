"""Unit tests for the waf_auto_deny write module (run_module flows).

Drives ``run_module()`` against an in-memory fake WAF client that returns
the current automatic-blocking thresholds/status and records modify
calls. There is no create/delete: the singleton policy is reconciled and
``enabled=false`` switches ``DefenseStatus`` off.

Scenario matrix:

* a matching policy is idempotent
* threshold drift triggers ModifyWafAutoDenyRules
* disabling/enabling flips DefenseStatus through the same modify call
* range guards reject out-of-bounds thresholds
* check-mode dry run and the blanket SDK failure path
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import waf_auto_deny as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    module_args,
    run,
)

POLICY = {
    "AttackThreshold": 10,
    "TimeThreshold": 5,
    "DenyTimeThreshold": 60,
    "DefenseStatus": 1,
}


def _args(enabled=True, **overrides):
    params = {
        "domain": "api.example.com",
        "enabled": enabled,
        "attack_threshold": 10,
        "time_threshold": 5,
        "deny_time_threshold": 60,
    }
    params.update(overrides)
    return module_args(**params)


class FakeWafClient(object):
    """In-memory WAF client serving one domain's auto-deny policy."""

    def __init__(self, policy=None):
        self.policy = copy.deepcopy(policy if policy is not None else POLICY)
        self.calls = []

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def DescribeWafAutoDenyRules(self, request):
        self._record("DescribeWafAutoDenyRules", request)
        return SimpleNamespace(**copy.deepcopy(self.policy))

    def ModifyWafAutoDenyRules(self, request):
        self._record("ModifyWafAutoDenyRules", request)
        self.policy = {
            "AttackThreshold": getattr(request, "AttackThreshold", self.policy.get("AttackThreshold")),
            "TimeThreshold": getattr(request, "TimeThreshold", self.policy.get("TimeThreshold")),
            "DenyTimeThreshold": getattr(request, "DenyTimeThreshold", self.policy.get("DenyTimeThreshold")),
            "DefenseStatus": getattr(request, "DefenseStatus", self.policy.get("DefenseStatus")),
        }
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake, models=None):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (models or FakeModels(), SimpleNamespace(WafClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


def test_no_drift_is_idempotent(monkeypatch):
    fake = FakeWafClient(policy=POLICY)
    _make_module(monkeypatch, fake)
    _args()
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["auto_deny"] == POLICY
    assert [c for c, unused in fake.calls] == ["DescribeWafAutoDenyRules"]


def test_attack_threshold_drift_updates(monkeypatch):
    fake = FakeWafClient(policy=POLICY)
    _make_module(monkeypatch, fake)
    _args(attack_threshold=20)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["auto_deny"]["AttackThreshold"] == 20
    ops = [c for c, unused in fake.calls]
    assert ops == ["DescribeWafAutoDenyRules", "ModifyWafAutoDenyRules"]
    modify_call = [r for c, r in fake.calls if c == "ModifyWafAutoDenyRules"][0]
    assert modify_call.AttackThreshold == 20
    assert modify_call.TimeThreshold == 5
    assert modify_call.Domain == "api.example.com"


def test_deny_time_threshold_drift_updates(monkeypatch):
    fake = FakeWafClient(policy=POLICY)
    _make_module(monkeypatch, fake)
    _args(deny_time_threshold=120)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["auto_deny"]["DenyTimeThreshold"] == 120


def test_disabling_turns_defense_off(monkeypatch):
    fake = FakeWafClient(policy=POLICY)
    _make_module(monkeypatch, fake)
    _args(enabled=False)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["auto_deny"]["DefenseStatus"] == 0
    modify_call = [r for c, r in fake.calls if c == "ModifyWafAutoDenyRules"][0]
    assert modify_call.DefenseStatus == 0


def test_enabling_turns_defense_on(monkeypatch):
    fake = FakeWafClient(policy=dict(POLICY, DefenseStatus=0))
    _make_module(monkeypatch, fake)
    _args(enabled=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["auto_deny"]["DefenseStatus"] == 1


def test_defaults_applied_when_api_reports_unset(monkeypatch):
    # An untouched domain can describe back all-zero thresholds/status; the
    # module then pushes its defaults.
    fake = FakeWafClient(policy={"AttackThreshold": 0, "TimeThreshold": 0, "DenyTimeThreshold": 0, "DefenseStatus": 0})
    _make_module(monkeypatch, fake)
    _args()
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["auto_deny"] == POLICY


def test_check_mode_is_dry_run(monkeypatch):
    fake = FakeWafClient(policy=POLICY)
    _make_module(monkeypatch, fake)
    _args(_ansible_check_mode=True, attack_threshold=50)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["auto_deny"]["AttackThreshold"] == 50
    assert not [c for c, unused in fake.calls if c != "DescribeWafAutoDenyRules"]


def test_attack_threshold_out_of_range_fails(monkeypatch):
    fake = FakeWafClient(policy=POLICY)
    _make_module(monkeypatch, fake)
    _args(attack_threshold=1)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "attack_threshold must be between 2 and 100" in exc.value.args[0]["msg"]


def test_time_threshold_out_of_range_fails(monkeypatch):
    fake = FakeWafClient(policy=POLICY)
    _make_module(monkeypatch, fake)
    _args(time_threshold=61)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "time_threshold must be between 1 and 60" in exc.value.args[0]["msg"]


def test_deny_time_threshold_out_of_range_fails(monkeypatch):
    fake = FakeWafClient(policy=POLICY)
    _make_module(monkeypatch, fake)
    _args(deny_time_threshold=4)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "deny_time_threshold must be between 5 and 360" in exc.value.args[0]["msg"]


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeWafAutoDenyRules(self, request):
            raise Boom("connection dropped")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    _args()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]
