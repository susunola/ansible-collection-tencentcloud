"""Unit tests for the clb_rule write module (run_module flows).

Drives ``run_module()`` end to end against an in-memory fake CLB client whose
write operations mutate the rule store so post-write ``find_rule`` refetches
see the new state immediately.

Scenario matrix:

* absent on a missing rule (idempotent no-op)
* absent with a matching rule (check-mode dry run, real delete)
* creation when missing (domain guard, check mode, happy path)
* no-op when nothing drifts
* drift updates (url, scheduler, session persistence, health check)
* identity validation guard, ambiguous-match guard and the blanket
  ``sdk_error_payload`` read path
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import clb_rule as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

RULE = {
    "LocationId": "loc-abc1",
    "Domain": "api.example.com",
    "Url": "/api",
    "Scheduler": "WRR",
    "SessionExpireTime": 0,
    "ForwardType": "TRADITIONAL",
    "CookieName": None,
    "HealthCheck": None,
}

HEALTH_CHECK_ATTRS = (
    "HealthSwitch", "IntervalTime", "HealthNum", "UnHealthNum", "TimeOut",
    "CheckType", "CheckPort", "HttpCheckPath", "HttpCheckDomain",
    "HttpCheckMethod", "HttpCode", "HttpVersion",
)


def _rule(**overrides):
    item = dict(RULE)
    item.update(overrides)
    return item


def _base(**overrides):
    params = {}
    params.update(overrides)
    return module_args(**params)


def _rule_args(location_id="loc-abc1", **overrides):
    params = {
        "load_balancer_id": "lb-aaaa",
        "listener_id": "lbl-bbbb",
        "location_id": location_id,
        "url": "/api",
    }
    params.update(overrides)
    return module_args(**params)


def _endpoint_args(domain="api.example.com", url="/api", **overrides):
    params = {
        "load_balancer_id": "lb-aaaa",
        "listener_id": "lbl-bbbb",
        "domain": domain,
        "url": url,
    }
    params.update(overrides)
    return module_args(**params)


class FakeClbClient(object):
    """In-memory CLB client mutating a small forwarding-rule store."""

    def __init__(self, rules=None):
        self.rules = [dict(t) for t in (rules or [])]
        self.calls = []
        self._next = 0

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def _hc(self, obj):
        if obj is None:
            return None
        result = {}
        for attr in HEALTH_CHECK_ATTRS:
            value = getattr(obj, attr, None)
            if value is not None:
                result[attr] = value
        return result or None

    def DescribeListeners(self, request):
        self._record("DescribeListeners", request)
        listener = {"Rules": [dict(r) for r in self.rules]}
        return SimpleNamespace(Listeners=[FakeResource(listener)], RequestId="req-describe")

    def CreateRule(self, request):
        self._record("CreateRule", request)
        self._next += 1
        location_id = "loc-new-%03d" % self._next
        rule = getattr(request, "Rules", [None])[0]
        item = {
            "LocationId": location_id,
            "Domain": getattr(rule, "Domain", None),
            "Url": getattr(rule, "Url", None),
            "Scheduler": getattr(rule, "Scheduler", None),
            "SessionExpireTime": getattr(rule, "SessionExpireTime", None),
            "ForwardType": getattr(rule, "ForwardType", None),
            "CookieName": getattr(rule, "CookieName", None),
            "HealthCheck": self._hc(getattr(rule, "HealthCheck", None)),
        }
        self.rules.append(item)
        return SimpleNamespace(LocationIds=[location_id], RequestId="req-create")

    def ModifyRule(self, request):
        self._record("ModifyRule", request)
        for item in self.rules:
            if item.get("LocationId") == getattr(request, "LocationId", None):
                item["Url"] = getattr(request, "Url", None)
                for source in ("Scheduler", "SessionExpireTime", "ForwardType", "CookieName"):
                    if getattr(request, source, None) is not None:
                        item[source] = getattr(request, source)
                if getattr(request, "HealthCheck", None) is not None:
                    item["HealthCheck"] = self._hc(request.HealthCheck)
        return SimpleNamespace(RequestId="req-modify")

    def DeleteRule(self, request):
        self._record("DeleteRule", request)
        doomed = set(getattr(request, "LocationIds", None) or [])
        self.rules = [r for r in self.rules if r.get("LocationId") not in doomed]
        return SimpleNamespace(RequestId="req-delete")


def _make_module(monkeypatch, fake, models=None):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load_clb", lambda: (models or FakeModels(), SimpleNamespace(ClbClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)


# ---------------------------------------------------------------------------
# absent flows
# ---------------------------------------------------------------------------


def test_absent_missing_rule_is_idempotent(monkeypatch):
    fake = FakeClbClient()
    _make_module(monkeypatch, fake)
    _endpoint_args(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert [c for c, unused in fake.calls] == ["DescribeListeners"]


def test_absent_deletes_rule(monkeypatch):
    fake = FakeClbClient(rules=[_rule()])
    _make_module(monkeypatch, fake)
    _rule_args(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["rule"] is None
    assert fake.rules == []
    assert "DeleteRule" in [c for c, unused in fake.calls]


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeClbClient(rules=[_rule()])
    _make_module(monkeypatch, fake)
    _rule_args(_ansible_check_mode=True, state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert len(fake.rules) == 1
    assert "DeleteRule" not in [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# creation flows
# ---------------------------------------------------------------------------


def test_create_with_location_id_requires_domain(monkeypatch):
    fake = FakeClbClient()
    _make_module(monkeypatch, fake)
    _rule_args(state="present")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "domain is required when creating" in exc.value.args[0]["msg"]


def test_create_rule(monkeypatch):
    fake = FakeClbClient()
    _make_module(monkeypatch, fake)
    _endpoint_args(state="present", scheduler="WRR", session_expire_time=300)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["rule"]["LocationId"].startswith("loc-new-")
    assert result["rule"]["Url"] == "/api"
    assert result["rule"]["Scheduler"] == "WRR"
    assert len(fake.rules) == 1
    ops = [c for c, unused in fake.calls]
    assert ops[0] == "DescribeListeners"
    assert "CreateRule" in ops


def test_create_rule_with_health_check(monkeypatch):
    fake = FakeClbClient()
    _make_module(monkeypatch, fake)
    _endpoint_args(
        state="present",
        scheduler="WRR",
        health_check={"health_switch": True, "http_check_path": "/healthz", "interval_time": 10},
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["rule"]["HealthCheck"]["HealthSwitch"] == 1
    assert result["rule"]["HealthCheck"]["HttpCheckPath"] == "/healthz"
    assert "CreateRule" in [c for c, unused in fake.calls]


def test_create_check_mode_is_dry_run(monkeypatch):
    fake = FakeClbClient()
    _make_module(monkeypatch, fake)
    _endpoint_args(_ansible_check_mode=True, state="present", scheduler="WRR")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert fake.rules == []
    assert "CreateRule" not in [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# existing-rule flows
# ---------------------------------------------------------------------------


def test_existing_rule_no_drift_is_idempotent(monkeypatch):
    fake = FakeClbClient(rules=[_rule()])
    _make_module(monkeypatch, fake)
    _rule_args(state="present", scheduler="WRR", domain="api.example.com")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["rule"]["LocationId"] == "loc-abc1"


def test_update_rule_url(monkeypatch):
    fake = FakeClbClient(rules=[_rule()])
    _make_module(monkeypatch, fake)
    _rule_args(state="present", url="/v2")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["rule"]["Url"] == "/v2"
    assert fake.rules[0]["Url"] == "/v2"
    assert "ModifyRule" in [c for c, unused in fake.calls]


def test_update_rule_scheduler(monkeypatch):
    fake = FakeClbClient(rules=[_rule()])
    _make_module(monkeypatch, fake)
    _rule_args(state="present", scheduler="LEAST_CONN")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["rule"]["Scheduler"] == "LEAST_CONN"
    assert "ModifyRule" in [c for c, unused in fake.calls]


def test_update_rule_health_check(monkeypatch):
    fake = FakeClbClient(rules=[_rule(HealthCheck={"HealthSwitch": 1, "HttpCheckPath": "/healthz"})])
    _make_module(monkeypatch, fake)
    _rule_args(state="present", health_check={"health_switch": False})
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["rule"]["HealthCheck"]["HealthSwitch"] == 0
    assert "ModifyRule" in [c for c, unused in fake.calls]


def test_update_check_mode_is_dry_run(monkeypatch):
    fake = FakeClbClient(rules=[_rule()])
    _make_module(monkeypatch, fake)
    _rule_args(_ansible_check_mode=True, state="present", url="/v2")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert fake.rules[0]["Url"] == "/api"
    assert "ModifyRule" not in [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# validation / failure paths
# ---------------------------------------------------------------------------


def test_missing_identity_fails(monkeypatch):
    fake = FakeClbClient()
    _make_module(monkeypatch, fake)
    _base(state="present", load_balancer_id="lb-aaaa", listener_id="lbl-bbbb", url="/api")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "location_id or domain is required" in exc.value.args[0]["msg"]


def test_ambiguous_rules_fail(monkeypatch):
    fake = FakeClbClient(rules=[_rule(), _rule(LocationId="loc-abc2")])
    _make_module(monkeypatch, fake)
    _endpoint_args(state="present")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "Ambiguous" in payload["msg"]
    assert payload["ambiguous"] is True


def test_invalid_scheduler_choice_fails(monkeypatch):
    fake = FakeClbClient()
    _make_module(monkeypatch, fake)
    _endpoint_args(state="present", scheduler="RANDOM")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "RANDOM" in exc.value.args[0]["msg"]


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeListeners(self, request):
            raise Boom("connection dropped")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    _endpoint_args(state="present")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]
