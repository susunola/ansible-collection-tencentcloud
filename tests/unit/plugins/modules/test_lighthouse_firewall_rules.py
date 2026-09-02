"""Unit tests for the lighthouse_firewall_rules write module (helpers + run_module).

Covers the full reconcile flow of ``plugins/modules/lighthouse_firewall_rules.py``:
paginated describe, rule normalization / keying, and the remove-then-add
reconcile in ``run_module``, using an in-memory fake Lighthouse client whose
write operations mutate the rule store so re-describes converge (see harness.py).
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import lighthouse_firewall_rules as fw
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeRequest,
    FakeResource,
    module_args,
    run,
)

RULE_A = {"Protocol": "TCP", "Port": "22", "CidrBlock": "10.0.0.0/8", "Action": "ACCEPT", "FirewallRuleDescription": "administration"}
RULE_B = {"Protocol": "TCP", "Port": "443", "CidrBlock": "0.0.0.0/0", "Action": "ACCEPT", "FirewallRuleDescription": "HTTPS"}

WRITE_OPS = ("CreateFirewallRules", "DeleteFirewallRules")


class FirewallRuleModel(FakeRequest):
    """FirewallRule stand-in with the ``_deserialize`` the module calls."""

    def _deserialize(self, data):
        for key, value in (data or {}).items():
            setattr(self, key, value)


class FakeModels(object):
    FirewallRule = FirewallRuleModel
    DescribeFirewallRulesRequest = FakeRequest
    CreateFirewallRulesRequest = FakeRequest
    DeleteFirewallRulesRequest = FakeRequest


def _rule(**overrides):
    rule = {"Protocol": "", "Port": "", "CidrBlock": "", "Ipv6CidrBlock": "", "Action": "", "FirewallRuleDescription": ""}
    rule.update(overrides)
    return rule


class FakeFirewallClient(object):
    """In-memory Lighthouse firewall client with a normalized rule store."""

    def __init__(self, rules=None, version=1):
        self.rules = [copy.deepcopy(rule) for rule in (rules or [])]
        self.version = version
        self.calls = []

    def _record(self, name, request):
        self.calls.append((name, request))
        return request

    def _request_rule_dicts(self, rules):
        return [{key: getattr(item, key, "") for key in fw.FIELDS} for item in rules]

    def DescribeFirewallRules(self, request):
        self._record("DescribeFirewallRules", request)
        page = self.rules[request.Offset : request.Offset + request.Limit]
        return SimpleNamespace(
            FirewallRuleSet=[FakeResource(dict(rule)) for rule in page],
            TotalCount=len(self.rules),
            FirewallVersion=self.version,
        )

    def DeleteFirewallRules(self, request):
        self._record("DeleteFirewallRules", request)
        remove_keys = {fw.rule_key(rule) for rule in self._request_rule_dicts(request.FirewallRules)}
        self.rules = [rule for rule in self.rules if fw.rule_key(rule) not in remove_keys]
        return SimpleNamespace()

    def CreateFirewallRules(self, request):
        self._record("CreateFirewallRules", request)
        for rule in self._request_rule_dicts(request.FirewallRules):
            self.rules.append(rule)
        return SimpleNamespace()


class FakeModule(object):
    """Minimal stand-in for helpers that only need sdk_call."""

    def __init__(self):
        self.sdk_calls = []

    def sdk_call(self, operation, request):
        self.sdk_calls.append((operation, request))
        return operation(request)


@pytest.fixture
def client(monkeypatch):
    fake = FakeFirewallClient()
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(
        fw,
        "_load",
        lambda: (FakeModels(), SimpleNamespace(LighthouseClient=object)),
    )
    monkeypatch.setattr(
        TencentCloudModule,
        "create_client",
        lambda self, client_class, endpoint: fake,
    )
    return fake


# ---------------------------------------------------------------------------
# Helper-level tests
# ---------------------------------------------------------------------------


def test_rule_model_deserializes_only_present_fields():
    rule = fw._rule(FakeModels(), {"Protocol": "TCP", "Port": "22"})
    assert rule.Protocol == "TCP"
    assert rule.Port == "22"
    assert not hasattr(rule, "Action")


def test_normalize_rule_fills_missing_fields_with_empty_strings():
    normalized = fw.normalize_rule({"Protocol": "TCP", "Port": "22"})
    assert normalized == {"Protocol": "TCP", "Port": "22", "CidrBlock": "", "Ipv6CidrBlock": "", "Action": "", "FirewallRuleDescription": ""}


def test_rule_key_is_orderable_tuple():
    key = fw.rule_key({"Protocol": "TCP", "Port": "22", "Action": "ACCEPT"})
    assert isinstance(key, tuple)
    assert key == ("TCP", "22", "", "", "ACCEPT", "")


def test_normalize_rules_sorts_by_rule_key():
    rules = fw.normalize_rules([RULE_B, RULE_A])
    assert rules == [fw.normalize_rule(RULE_A), fw.normalize_rule(RULE_B)]


def test_normalize_rules_handles_none():
    assert fw.normalize_rules(None) == []
    assert fw.normalize_rules([]) == []


def test_describe_request_sets_instance_offset_limit():
    request = fw.describe_request(FakeModels(), "lhins-1", offset=100)
    assert request.InstanceId == "lhins-1"
    assert request.Offset == 100
    assert request.Limit == 100


def test_create_request_builds_rule_models():
    request = fw.create_request(FakeModels(), "lhins-1", [RULE_A, RULE_B], version=3)
    assert request.InstanceId == "lhins-1"
    assert request.FirewallVersion == 3
    assert len(request.FirewallRules) == 2
    assert request.FirewallRules[0].Protocol == "TCP"
    assert request.FirewallRules[0].FirewallRuleDescription == "administration"


def test_delete_request_builds_rule_models():
    request = fw.delete_request(FakeModels(), "lhins-1", [RULE_A], version=2)
    assert request.InstanceId == "lhins-1"
    assert request.FirewallVersion == 2
    assert request.FirewallRules[0].CidrBlock == "10.0.0.0/8"


def test_describe_returns_normalized_rules_and_version():
    module = FakeModule()
    client = FakeFirewallClient(rules=[RULE_A], version=7)
    current, version = fw.describe(module, client, FakeModels(), "lhins-1")
    assert current == [fw.normalize_rule(RULE_A)]
    assert version == 7


def test_describe_empty_returns_empty_list_and_version():
    module = FakeModule()
    client = FakeFirewallClient(rules=[], version=0)
    current, version = fw.describe(module, client, FakeModels(), "lhins-1")
    assert current == []
    assert version == 0


def test_describe_paginates_past_first_page():
    module = FakeModule()
    rules = [_rule(Protocol="TCP", Port=str(port)) for port in range(1, 151)]
    client = FakeFirewallClient(rules=rules, version=1)
    current, version = fw.describe(module, client, FakeModels(), "lhins-1")
    assert len(current) == 150
    assert version == 1
    offsets = [request.Offset for name, request in client.calls if name == "DescribeFirewallRules"]
    assert offsets == [0, 100]


# ---------------------------------------------------------------------------
# run_module main-path tests
# ---------------------------------------------------------------------------


def test_matching_rules_are_unchanged(client):
    client.rules = [RULE_A, RULE_B]
    module_args(instance_id="lhins-1", rules=[RULE_A, RULE_B])
    result = run(fw.run_module)
    assert result["changed"] is False
    assert not any(name in WRITE_OPS for name, request in client.calls)
    assert result["firewall_version"] == 1


def test_adds_missing_rules(client):
    module_args(instance_id="lhins-1", rules=[RULE_A, RULE_B])
    result = run(fw.run_module)
    assert result["changed"] is True
    assert any(name == "CreateFirewallRules" for name, request in client.calls)
    assert not any(name == "DeleteFirewallRules" for name, request in client.calls)
    assert len(client.rules) == 2
    assert result["rules"] == fw.normalize_rules([RULE_A, RULE_B])


def test_removes_extra_rules(client):
    client.rules = [RULE_A, RULE_B]
    module_args(instance_id="lhins-1", rules=[RULE_A])
    result = run(fw.run_module)
    assert result["changed"] is True
    assert any(name == "DeleteFirewallRules" for name, request in client.calls)
    assert not any(name == "CreateFirewallRules" for name, request in client.calls)
    assert len(client.rules) == 1
    assert client.rules[0]["Port"] == "22"


def test_reconcile_deletes_before_creating(client):
    client.rules = [RULE_A]
    module_args(instance_id="lhins-1", rules=[RULE_B])
    result = run(fw.run_module)
    assert result["changed"] is True
    call_names = [name for name, request in client.calls if name in WRITE_OPS]
    assert call_names == ["DeleteFirewallRules", "CreateFirewallRules"]
    assert len(client.rules) == 1
    assert client.rules[0]["Port"] == "443"


def test_check_mode_add_makes_no_writes(client):
    module_args(instance_id="lhins-1", rules=[RULE_A], _ansible_check_mode=True)
    result = run(fw.run_module)
    assert result["changed"] is True
    assert result["rules"] == fw.normalize_rules([RULE_A])
    assert not any(name in WRITE_OPS for name, request in client.calls)


def test_check_mode_remove_makes_no_writes(client):
    client.rules = [RULE_A, RULE_B]
    module_args(instance_id="lhins-1", rules=[RULE_A], _ansible_check_mode=True)
    result = run(fw.run_module)
    assert result["changed"] is True
    # build_diff strips empty values from both sides of the diff.
    def stripped(rules):
        return [{key: value for key, value in rule.items() if value}
                for rule in fw.normalize_rules(rules)]
    assert result["diff"]["before"] == stripped([RULE_A, RULE_B])
    assert result["diff"]["after"] == stripped([RULE_A])
    assert not any(name in WRITE_OPS for name, request in client.calls)


def test_sdk_error_on_describe_is_reported(client):
    def boom(request):
        raise RuntimeError("firewall api exploded")

    client.DescribeFirewallRules = boom
    module_args(instance_id="lhins-1", rules=[])
    with pytest.raises(AnsibleFailJson) as exc:
        run(fw.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "firewall api exploded" in payload["error"]
