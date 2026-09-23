"""Unit tests for the teo_security_bot_lite write module (run_module flows).

The module normalises the ``BotManagementLite`` section of an EdgeOne
security policy (CAPTCHA page + AI-crawler detection) into four booleans /
strings and reconciles it against the requested configuration via a single
``ModifySecurityPolicy``. The policy scope selects zone, template or host
and validation requires the matching id/host argument.

Scenario matrix:

* template/host scope require their key argument (validation, no SDK call)
* a default zone policy is idempotent; so is an identical template-scope
  policy with the scope carried on the request
* enabling CAPTCHA + AI-crawler Challenge writes the challenge parameters
* disabling CAPTCHA and switching the AI-crawler action each drive a modify
* host scope forwards the domain on the request
* check mode reports the diff without writing
* the blanket SDK failure path
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import teo_security_bot_lite as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

ZONE_ID = "zone-abc123"


def _policy(captcha=False, ai=False, action="Monitor", challenge="ManagedChallenge"):
    """Build the raw serialized ``BotManagementLite`` shape the module reads."""
    state = {"CAPTCHAPageChallenge": {"Enabled": "on" if captcha else "off"}}
    crawler = {"Enabled": "on" if ai else "off"}
    if ai:
        crawler["Action"] = {"Name": action}
        if action == "Challenge":
            crawler["Action"]["ChallengeActionParameters"] = {"ChallengeOption": challenge}
    state["AICrawlerDetection"] = crawler
    return state


def _normalized(captcha=False, ai=False, action="Monitor", challenge="ManagedChallenge"):
    return {
        "captcha_page_enabled": captcha,
        "ai_crawler_enabled": ai,
        "ai_crawler_action": action,
        "challenge_option": challenge,
    }


def _args(**overrides):
    params = {
        "zone_id": ZONE_ID,
        "scope": "zone",
        "captcha_page_enabled": False,
        "ai_crawler_enabled": False,
        "ai_crawler_action": "Monitor",
        "challenge_option": "ManagedChallenge",
    }
    params.update(overrides)
    return module_args(**params)


class FakeTeoClient(object):
    """In-memory EdgeOne client storing one security-policy BotManagementLite."""

    def __init__(self, policy=None):
        # policy=None represents "no BotManagementLite section".
        self.policy = copy.deepcopy(policy)
        self.calls = []

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def DescribeSecurityPolicy(self, request):
        self._record("DescribeSecurityPolicy", request)
        if self.policy is None:
            bot = None
        else:
            bot = FakeResource(copy.deepcopy(self.policy))
        policy = FakeResource({"BotManagementLite": bot})
        return SimpleNamespace(SecurityPolicy=policy)

    def ModifySecurityPolicy(self, request):
        self._record("ModifySecurityPolicy", request)
        bot = getattr(getattr(request, "SecurityPolicy", None), "BotManagementLite", None)
        if bot is None:
            return SimpleNamespace(RequestId="req-fake")
        captcha = getattr(bot, "CAPTCHAPageChallenge", None)
        crawler = getattr(bot, "AICrawlerDetection", None)
        state = {}
        if captcha is not None:
            state["CAPTCHAPageChallenge"] = {"Enabled": captcha.Enabled}
        if crawler is not None:
            crawler_state = {"Enabled": crawler.Enabled}
            action = getattr(crawler, "Action", None)
            if action is not None:
                action_state = {"Name": action.Name}
                params = getattr(action, "ChallengeActionParameters", None)
                if params is not None:
                    action_state["ChallengeActionParameters"] = {"ChallengeOption": params.ChallengeOption}
                crawler_state["Action"] = action_state
            state["AICrawlerDetection"] = crawler_state
        self.policy = state
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (FakeModels(), SimpleNamespace(TeoClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


# ---------------------------------------------------------------------------
# validation guards
# ---------------------------------------------------------------------------


def test_template_scope_requires_template_id(monkeypatch):
    fake = FakeTeoClient()
    _make_module(monkeypatch, fake)
    _args(scope="template")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "template_id is required for template scope" in exc.value.args[0]["msg"]
    assert fake.calls == []


def test_host_scope_requires_host(monkeypatch):
    fake = FakeTeoClient()
    _make_module(monkeypatch, fake)
    _args(scope="host")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "host is required for host scope" in exc.value.args[0]["msg"]
    assert fake.calls == []


# ---------------------------------------------------------------------------
# idempotent flows
# ---------------------------------------------------------------------------


def test_default_zone_policy_is_idempotent(monkeypatch):
    fake = FakeTeoClient(policy=None)
    _make_module(monkeypatch, fake)
    _args()
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["bot_lite"] == _normalized()
    assert [c for c, unused in fake.calls] == ["DescribeSecurityPolicy"]


def test_matching_policy_is_idempotent(monkeypatch):
    fake = FakeTeoClient(policy=_policy(captcha=True, ai=True))
    _make_module(monkeypatch, fake)
    _args(captcha_page_enabled=True, ai_crawler_enabled=True)
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["bot_lite"] == _normalized(captcha=True, ai=True)
    assert "ModifySecurityPolicy" not in [c for c, unused in fake.calls]


def test_template_scope_policy_is_idempotent(monkeypatch):
    fake = FakeTeoClient(policy=_policy())
    _make_module(monkeypatch, fake)
    _args(scope="template", template_id="temp-1001")
    result = run(mod.run_module)
    assert result["changed"] is False
    describe_call = dict((name, request) for name, request in fake.calls)["DescribeSecurityPolicy"]
    assert describe_call.Entity == "Template"
    assert describe_call.TemplateId == "temp-1001"
    assert describe_call.ZoneId == ZONE_ID


# ---------------------------------------------------------------------------
# drift flows
# ---------------------------------------------------------------------------


def test_enables_captcha_and_challenge(monkeypatch):
    fake = FakeTeoClient(policy=None)
    _make_module(monkeypatch, fake)
    _args(captcha_page_enabled=True, ai_crawler_enabled=True, ai_crawler_action="Challenge")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["bot_lite"] == _normalized(captcha=True, ai=True, action="Challenge")
    assert fake.policy["CAPTCHAPageChallenge"]["Enabled"] == "on"
    assert fake.policy["AICrawlerDetection"]["Enabled"] == "on"
    assert fake.policy["AICrawlerDetection"]["Action"]["Name"] == "Challenge"
    challenge = fake.policy["AICrawlerDetection"]["Action"]["ChallengeActionParameters"]["ChallengeOption"]
    assert challenge == "ManagedChallenge"
    ops = [c for c, unused in fake.calls]
    assert ops[0] == "DescribeSecurityPolicy"
    assert "ModifySecurityPolicy" in ops
    assert ops[-1] == "DescribeSecurityPolicy"


def test_disables_captcha_page(monkeypatch):
    fake = FakeTeoClient(policy=_policy(captcha=True))
    _make_module(monkeypatch, fake)
    _args(captcha_page_enabled=False)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["bot_lite"] == _normalized()
    assert fake.policy["CAPTCHAPageChallenge"]["Enabled"] == "off"


def test_ai_crawler_action_drift_switches_to_deny(monkeypatch):
    fake = FakeTeoClient(policy=_policy(ai=True))
    _make_module(monkeypatch, fake)
    _args(ai_crawler_enabled=True, ai_crawler_action="Deny")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["bot_lite"] == _normalized(ai=True, action="Deny")
    assert fake.policy["AICrawlerDetection"]["Action"]["Name"] == "Deny"
    assert "ChallengeActionParameters" not in fake.policy["AICrawlerDetection"]["Action"]


def test_host_scope_writes_for_domain(monkeypatch):
    fake = FakeTeoClient(policy=None)
    _make_module(monkeypatch, fake)
    _args(scope="host", host="app.example.com", captcha_page_enabled=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["bot_lite"] == _normalized(captcha=True)
    describe_call = dict((name, request) for name, request in fake.calls)["DescribeSecurityPolicy"]
    assert describe_call.Entity == "Host"
    assert describe_call.Host == "app.example.com"
    assert not hasattr(describe_call, "TemplateId")


def test_check_mode_reports_diff_without_writing(monkeypatch):
    fake = FakeTeoClient(policy=None)
    _make_module(monkeypatch, fake)
    _args(_ansible_check_mode=True, captcha_page_enabled=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert "diff" in result
    assert result["bot_lite"] == _normalized(captcha=True)
    assert "ModifySecurityPolicy" not in [c for c, unused in fake.calls]
    assert fake.policy is None


# ---------------------------------------------------------------------------
# failure paths
# ---------------------------------------------------------------------------


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeSecurityPolicy(self, request):
            raise Boom("connection dropped")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    _args()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]
