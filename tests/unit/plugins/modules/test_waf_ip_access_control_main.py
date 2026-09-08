"""Unit tests for the waf_ip_access_control write module (run_module flows).

Drives ``run_module()`` end to end against an in-memory fake WAF client
whose write operations mutate the IP-rule store, so the module's post-write
``find_rule`` refetch and waiter converge immediately.

Scenario matrix:

* absent on a missing rule (idempotent no-op)
* absent with a matching rule (check-mode dry run and the real delete)
* creation when missing (the ``required_if`` ip_list guard, check mode,
  happy path)
* no-op when nothing drifts
* drift updates by rule ID and check-mode dry runs
* the ``Tencent Cloud API request failed`` failure path
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import waf_ip_access_control as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

RULE = {
    "RuleId": 401,
    "ActionType": 42,
    "Domain": "api.example.com",
    "IpList": ["198.51.100.10", "203.0.113.0/24"],
    "Note": "Known abusive sources",
    "ValidTs": 0,
}


def _rule(**overrides):
    item = copy.deepcopy(RULE)
    item.update(overrides)
    item["IpList"] = sorted(item["IpList"])
    return item


def _base(**overrides):
    params = {}
    params.update(overrides)
    return module_args(**params)


class FakeWafClient(object):
    """In-memory WAF client mutating a small IP-rule store."""

    def __init__(self, rules=None):
        self.rules = [copy.deepcopy(t) for t in (rules or [])]
        self.calls = []
        self._next = 400

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def DescribeIpAccessControl(self, request):
        self._record("DescribeIpAccessControl", request)
        domain = getattr(request, "Domain", None)
        action_type = getattr(request, "ActionType", None)
        rule_id = getattr(request, "RuleId", None)
        matches = []
        for item in self.rules:
            if item.get("Domain") == domain and item.get("ActionType") == action_type:
                if rule_id is None or int(item.get("RuleId") or item.get("Id") or 0) == rule_id:
                    matches.append(dict(item))
        return SimpleNamespace(Data=SimpleNamespace(Res=[FakeResource(t) for t in matches]))

    def CreateIpAccessControl(self, request):
        self._record("CreateIpAccessControl", request)
        self._next += 1
        item = {
            "RuleId": self._next,
            "ActionType": getattr(request, "ActionType", None),
            "Domain": getattr(request, "Domain", None),
            "IpList": sorted(getattr(request, "IpList", None) or []),
            "Note": getattr(request, "Note", None),
            "ValidTs": getattr(request, "ValidTS", None),
        }
        self.rules.append(item)
        return SimpleNamespace(RuleId=self._next, RequestId="req-fake")

    def ModifyIpAccessControl(self, request):
        self._record("ModifyIpAccessControl", request)
        rule_id = getattr(request, "RuleId", None)
        for item in self.rules:
            if int(item.get("RuleId") or item.get("Id") or 0) == rule_id:
                item["ActionType"] = getattr(request, "ActionType", None)
                item["IpList"] = sorted(getattr(request, "IpList", None) or [])
                item["Note"] = getattr(request, "Note", None)
                item["ValidTs"] = getattr(request, "ValidTS", None)
        return SimpleNamespace(RequestId="req-fake")

    def DeleteIpAccessControl(self, request):
        self._record("DeleteIpAccessControl", request)
        items = getattr(request, "Items", None) or []
        is_id = getattr(request, "IsId", False)
        for raw in items:
            if is_id:
                self.rules = [t for t in self.rules if str(int(t.get("RuleId") or t.get("Id") or 0)) != raw]
            else:
                self.rules = [t for t in self.rules if t.get("IpList") not in (None, [raw])]
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake, models=None):
    """Wire the shared monkeypatches; returns the fake client."""
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load_waf", lambda: (models or FakeModels(), SimpleNamespace(WafClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


def _ops(fake):
    return [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# absent flows
# ---------------------------------------------------------------------------


def test_absent_missing_rule_is_idempotent(monkeypatch):
    fake = FakeWafClient(rules=[])
    _make_module(monkeypatch, fake)
    _base(state="absent", domain="api.example.com", action="block")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["rule"] is None
    assert _ops(fake) == ["DescribeIpAccessControl"]


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeWafClient(rules=[_rule()])
    _make_module(monkeypatch, fake)
    _base(_ansible_check_mode=True, state="absent", rule_id=401, domain="api.example.com", action="block")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["rule"]["RuleId"] == 401
    assert len(fake.rules) == 1
    assert "DeleteIpAccessControl" not in _ops(fake)


def test_absent_deletes_rule(monkeypatch):
    fake = FakeWafClient(rules=[_rule()])
    _make_module(monkeypatch, fake)
    _base(state="absent", domain="api.example.com", action="block", ip_list=["198.51.100.10", "203.0.113.0/24"], note="Known abusive sources")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["rule"] is None
    assert fake.rules == []
    ops = _ops(fake)
    assert "DeleteIpAccessControl" in ops
    delete_request = [r for c, r in fake.calls if c == "DeleteIpAccessControl"][0]
    assert delete_request.Items == ["401"]
    assert delete_request.IsId is True


# ---------------------------------------------------------------------------
# creation flows
# ---------------------------------------------------------------------------


def test_present_requires_ip_list(monkeypatch):
    fake = FakeWafClient(rules=[])
    _make_module(monkeypatch, fake)
    _base(state="present", domain="api.example.com", action="block")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "ip_list" in exc.value.args[0]["msg"]


def test_create_rule(monkeypatch):
    fake = FakeWafClient(rules=[])
    _make_module(monkeypatch, fake)
    _base(state="present", domain="api.example.com", action="block", ip_list=["198.51.100.10", "203.0.113.0/24"], note="Known abusive sources")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["rule"]["ActionType"] == 42
    assert result["rule"]["IpList"] == ["198.51.100.10", "203.0.113.0/24"]
    assert len(fake.rules) == 1
    ops = _ops(fake)
    assert ops[0] == "DescribeIpAccessControl"
    assert "CreateIpAccessControl" in ops


def test_create_allow_rule(monkeypatch):
    fake = FakeWafClient(rules=[])
    _make_module(monkeypatch, fake)
    _base(state="present", domain="api.example.com", action="allow", ip_list=["203.0.113.5"])
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["rule"]["ActionType"] == 40
    assert "CreateIpAccessControl" in _ops(fake)


def test_create_check_mode_is_dry_run(monkeypatch):
    fake = FakeWafClient(rules=[])
    _make_module(monkeypatch, fake)
    _base(
        _ansible_check_mode=True,
        state="present",
        domain="api.example.com",
        action="block",
        ip_list=["198.51.100.10"],
        note="Known abusive sources",
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert fake.rules == []
    assert "CreateIpAccessControl" not in _ops(fake)


# ---------------------------------------------------------------------------
# existing-rule flows
# ---------------------------------------------------------------------------


def test_existing_rule_no_drift_is_idempotent(monkeypatch):
    fake = FakeWafClient(rules=[_rule()])
    _make_module(monkeypatch, fake)
    _base(
        state="present",
        rule_id=401,
        domain="api.example.com",
        action="block",
        ip_list=["198.51.100.10", "203.0.113.0/24"],
        note="Known abusive sources",
    )
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["rule"]["RuleId"] == 401
    assert "ModifyIpAccessControl" not in _ops(fake)


def test_existing_rule_drift_updates(monkeypatch):
    fake = FakeWafClient(rules=[_rule()])
    _make_module(monkeypatch, fake)
    _base(
        state="present",
        rule_id=401,
        domain="api.example.com",
        action="block",
        ip_list=["198.51.100.10", "203.0.113.0/24", "192.0.2.9"],
        note="Known abusive sources",
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["rule"]["IpList"] == ["192.0.2.9", "198.51.100.10", "203.0.113.0/24"]
    ops = _ops(fake)
    assert "ModifyIpAccessControl" in ops
    modify_request = [r for c, r in fake.calls if c == "ModifyIpAccessControl"][0]
    assert modify_request.RuleId == 401


def test_existing_rule_update_check_mode_is_dry_run(monkeypatch):
    fake = FakeWafClient(rules=[_rule()])
    _make_module(monkeypatch, fake)
    _base(
        _ansible_check_mode=True,
        state="present",
        rule_id=401,
        domain="api.example.com",
        action="block",
        ip_list=["198.51.100.10", "203.0.113.0/24", "192.0.2.9"],
        note="Known abusive sources",
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert fake.rules[0]["IpList"] == ["198.51.100.10", "203.0.113.0/24"]
    assert "ModifyIpAccessControl" not in _ops(fake)


# ---------------------------------------------------------------------------
# failure path
# ---------------------------------------------------------------------------


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeIpAccessControl(self, request):
            raise Boom("connection dropped")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    _base(state="present", domain="api.example.com", action="block", ip_list=["198.51.100.10"])
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]
