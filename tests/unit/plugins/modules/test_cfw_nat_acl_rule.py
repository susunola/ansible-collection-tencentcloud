"""Unit tests for the cfw_nat_acl_rule write module (helpers + run_module).

Covers the create / drift-update / delete flows of
``plugins/modules/cfw_nat_acl_rule.py`` with an in-memory fake Cloud Firewall
client whose write operations mutate the rule store, so the module's
post-write ``find_rule`` refetch converges immediately. Rules are matched by
``rule_uuid`` or by ``description`` (both across the paged DescribeNatAcRule
list); value types are re-encoded to the API vocabulary (``net``/``ip``/
``domain``/``template``), actions to ``log``/``drop``/``accept`` and
directions to 0/1 before any comparison happens.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import cfw_nat_acl_rule as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

RULE = {
    "Uuid": 9001,
    "SourceContent": "10.0.0.0/8",
    "SourceType": "net",
    "TargetContent": "203.0.113.0/24",
    "TargetType": "net",
    "Protocol": "TCP",
    "Port": "443",
    "RuleAction": "accept",
    "Direction": 0,
    "Enable": "true",
    "Description": "allow-trusted-https",
    "OrderIndex": -1,
}


def _rule_item(**overrides):
    """API-shaped rule dict isolated from the shared constant."""
    item = copy.deepcopy(RULE)
    item.update(overrides)
    return item


def _params(**overrides):
    """Module parameters pre-filled from the argument spec (base included)."""
    params = {
        "state": "present",
        "rule_uuid": None,
        "description": "allow-trusted-https",
        "source": "10.0.0.0/8",
        "source_type": "ip",
        "destination": "203.0.113.0/24",
        "destination_type": "ip",
        "protocol": "TCP",
        "ports": "443",
        "action": "accept",
        "direction": "outbound",
        "enabled": True,
        "order_index": None,
        "scope": None,
        "parameter_template_id": None,
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


class FakeCfwClient(object):
    """In-memory CfwClient stand-in.

    Stores API-shaped rule dicts. DescribeNatAcRule pages over the store
    honouring Offset/Limit so find_rule pagination is exercised; write ops
    mutate the store so post-write refetches converge.
    """

    def __init__(self, rules=None):
        self.rules = [copy.deepcopy(r) for r in (rules or [])]
        self.calls = []
        self._next_uuid = 10000

    def _record(self, name, request):
        self.calls.append((name, request))
        return request

    @staticmethod
    def _plain(rule):
        """Convert an attribute-bag rule model back to a plain dict."""
        return {k: v for k, v in vars(rule).items() if not k.startswith("_")}

    def DescribeNatAcRule(self, request):
        self._record("DescribeNatAcRule", request)
        page = self.rules[request.Offset : request.Offset + request.Limit]
        return SimpleNamespace(
            Data=[FakeResource(dict(r)) for r in page],
            Total=len(self.rules),
            RequestId="req-fake",
        )

    def AddNatAcRule(self, request):
        self._record("AddNatAcRule", request)
        uuids = []
        for rule in request.Rules:
            self._next_uuid += 1
            uuids.append(self._next_uuid)
            item = self._plain(rule)
            item["Uuid"] = self._next_uuid
            self.rules.append(item)
        return SimpleNamespace(RuleUuid=uuids, RequestId="req-fake")

    def ModifyNatAcRule(self, request):
        self._record("ModifyNatAcRule", request)
        for rule in request.Rules:
            item = self._plain(rule)
            uuid = item.pop("Uuid")
            for stored in self.rules:
                if stored.get("Uuid") == uuid:
                    stored.clear()
                    stored.update(item)
                    stored["Uuid"] = uuid
        return SimpleNamespace(RequestId="req-fake")

    def RemoveNatAcRule(self, request):
        self._record("RemoveNatAcRule", request)
        uuids = list(request.RuleUuid or [])
        self.rules = [r for r in self.rules if r.get("Uuid") not in uuids]
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake):
    """Wire the shared monkeypatches and return the fake client."""
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(
        mod,
        "_load",
        lambda: (FakeModels(), SimpleNamespace(CfwClient=object)),
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
# Value-type / request-builder helper tests
# ---------------------------------------------------------------------------


def test_api_value_type_mapping():
    assert mod._api_value_type("ip", "1.2.3.4") == "ip"
    assert mod._api_value_type("ip", "10.0.0.0/8") == "net"
    assert mod._api_value_type("domain", "example.com") == "domain"
    assert mod._api_value_type("ip_template", "tpl-x") == "template"
    assert mod._api_value_type("domain_template", "tpl-y") == "template"


def test_describe_request_fields():
    request = mod.describe_request(FakeModels(), offset=7)
    assert request.Offset == 7
    assert request.Limit == 100


def test_rule_builder_maps_encodings():
    rule = mod._rule(FakeModels(), _params(source_type="domain", destination_type="ip_template",
                                                source="example.com", destination="tpl-abc",
                                                action="block", direction="inbound", enabled=False))
    assert rule.SourceType == "domain"
    assert rule.TargetType == "template"
    assert rule.RuleAction == "drop"
    assert rule.Direction == 1
    assert rule.Enable == "false"
    assert rule.OrderIndex == -1  # append-by-default
    assert rule.Description == "allow-trusted-https"


def test_rule_builder_optional_fields():
    rule = mod._rule(FakeModels(), _params(order_index=4, scope="internet-1", parameter_template_id="pmt-9"), rule_uuid=77)
    assert rule.OrderIndex == 4
    assert rule.Scope == "internet-1"
    assert rule.ParamTemplateId == "pmt-9"
    assert rule.Uuid == 77


def test_rule_builder_omits_uuid_when_absent():
    rule = mod._rule(FakeModels(), _params())
    assert not hasattr(rule, "Uuid")


def test_create_request_wraps_single_rule():
    request = mod.create_request(FakeModels(), _params())
    assert len(request.Rules) == 1
    assert request.Rules[0].SourceContent == "10.0.0.0/8"


def test_update_request_carries_uuid():
    request = mod.update_request(FakeModels(), _params(), 9001)
    assert request.Rules[0].Uuid == 9001
    assert request.Rules[0].Description == "allow-trusted-https"


def test_delete_request_fields():
    request = mod.delete_request(FakeModels(), _params(direction="inbound"), 9001)
    assert request.RuleUuid == [9001]
    assert request.Direction == 1


# ---------------------------------------------------------------------------
# find_rule tests
# ---------------------------------------------------------------------------


def test_find_rule_no_match_returns_none(monkeypatch):
    fake = FakeCfwClient([_rule_item()])
    _make_module(monkeypatch, fake)
    module = FakeModule(_params(description="no-such-rule"))
    assert mod.find_rule(module, fake, FakeModels(), module.params) is None


def test_find_rule_by_description(monkeypatch):
    fake = FakeCfwClient([_rule_item(), _rule_item(Uuid=9002, Description="other")])
    _make_module(monkeypatch, fake)
    module = FakeModule(_params(description="allow-trusted-https"))
    value = mod.find_rule(module, fake, FakeModels(), module.params)
    assert value["Uuid"] == 9001


def test_find_rule_by_uuid(monkeypatch):
    fake = FakeCfwClient([_rule_item(), _rule_item(Uuid=9002, Description="other")])
    _make_module(monkeypatch, fake)
    module = FakeModule(_params(rule_uuid=9002, description=None))
    value = mod.find_rule(module, fake, FakeModels(), module.params)
    assert value["Uuid"] == 9002


def test_find_rule_multiple_matches_fails(monkeypatch):
    fake = FakeCfwClient([_rule_item(Uuid=9001), _rule_item(Uuid=9002)])
    _make_module(monkeypatch, fake)
    module = FakeModule(_params(description="allow-trusted-https"))
    with pytest.raises(AnsibleFailJson) as exc:
        mod.find_rule(module, fake, FakeModels(), module.params)
    assert "Multiple NAT ACL rules matched" in exc.value.args[0]["msg"]


def test_find_rule_paginates_until_match(monkeypatch):
    rules = [_rule_item(Uuid=1000 + i, Description="bulk-%04d" % i) for i in range(150)]
    rules.append(_rule_item(Uuid=9999, Description="allow-trusted-https"))
    fake = FakeCfwClient(rules)
    _make_module(monkeypatch, fake)
    module = FakeModule(_params(description="allow-trusted-https"))
    value = mod.find_rule(module, fake, FakeModels(), module.params)
    assert value["Uuid"] == 9999
    list_calls = [c for c in fake.calls if c[0] == "DescribeNatAcRule"]
    assert len(list_calls) == 2  # page 1 (100) + page 2 (51)
    assert list_calls[0][1].Offset == 0
    assert list_calls[1][1].Offset == 100


# ---------------------------------------------------------------------------
# desired tests
# ---------------------------------------------------------------------------


def test_desired_encodes_api_values():
    value = mod.desired(_params())
    assert value == {
        "SourceContent": "10.0.0.0/8",
        "SourceType": "net",
        "TargetContent": "203.0.113.0/24",
        "TargetType": "net",
        "Protocol": "TCP",
        "Port": "443",
        "RuleAction": "accept",
        "Direction": 0,
        "Enable": "true",
        "Description": "allow-trusted-https",
    }


def test_desired_includes_optional_fields():
    value = mod.desired(_params(order_index=3, scope="internet-1", parameter_template_id="pmt-2"))
    assert value["OrderIndex"] == 3
    assert value["Scope"] == "internet-1"
    assert value["ParamTemplateId"] == "pmt-2"


def test_desired_omits_optional_fields_when_unset():
    value = mod.desired(_params())
    assert "OrderIndex" not in value
    assert "Scope" not in value
    assert "ParamTemplateId" not in value


# ---------------------------------------------------------------------------
# run_module main-path tests
# ---------------------------------------------------------------------------


def test_required_one_of_enforced():
    module_args()  # neither rule_uuid nor description
    with pytest.raises(AnsibleFailJson):
        run(mod.run_module)


def test_present_requires_source_and_destination():
    module_args(state="present", description="x")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "description, source and destination are required" in exc.value.args[0]["msg"]


def test_sdk_error_is_reported(monkeypatch):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(
        mod,
        "_load",
        lambda: (FakeModels(), SimpleNamespace(CfwClient=object)),
    )
    monkeypatch.setattr(
        TencentCloudModule,
        "create_client",
        lambda self, client_class, endpoint: _BoomClient(),
    )
    _run_args(description="x", source="1.2.3.4", destination="5.6.7.8")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert payload["error"] == "service exploded"


def test_present_creates_rule(monkeypatch):
    fake = FakeCfwClient()
    _make_module(monkeypatch, fake)
    module_args(state="present", description="allow-trusted-https", source="10.0.0.0/8",
                destination="203.0.113.0/24", protocol="TCP", ports="443")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["rule"]["Uuid"] == 10001
    assert result["rule"]["Description"] == "allow-trusted-https"
    names = [c[0] for c in fake.calls]
    assert names.count("DescribeNatAcRule") == 2  # find + refetch
    assert names.count("AddNatAcRule") == 1
    add = [c for c in fake.calls if c[0] == "AddNatAcRule"][0][1]
    assert add.Rules[0].RuleAction == "accept"
    assert add.Rules[0].OrderIndex == -1


def test_present_creates_with_drop_and_template(monkeypatch):
    fake = FakeCfwClient()
    _make_module(monkeypatch, fake)
    module_args(state="present", description="block-malware", source="tpl-src", source_type="ip_template",
                destination="example.com", destination_type="domain",
                protocol="ANY", ports="-1/-1", action="block", direction="inbound", order_index=5)
    result = run(mod.run_module)
    assert result["changed"] is True
    rule = result["rule"]
    assert rule["RuleAction"] == "drop"
    assert rule["SourceType"] == "template"
    assert rule["TargetType"] == "domain"
    assert rule["Direction"] == 1
    add = [c for c in fake.calls if c[0] == "AddNatAcRule"][0][1]
    assert add.Rules[0].OrderIndex == 5


def test_present_noop_returns_unchanged(monkeypatch):
    fake = FakeCfwClient([_rule_item()])
    _make_module(monkeypatch, fake)
    module_args(state="present", description="allow-trusted-https", source="10.0.0.0/8",
                destination="203.0.113.0/24", protocol="TCP", ports="443")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["rule"]["Uuid"] == 9001
    names = [c[0] for c in fake.calls]
    assert "AddNatAcRule" not in names
    assert "ModifyNatAcRule" not in names


def test_present_drift_triggers_update(monkeypatch):
    fake = FakeCfwClient([_rule_item()])
    _make_module(monkeypatch, fake)
    module_args(state="present", description="allow-trusted-https", source="10.0.0.0/8",
                destination="203.0.113.0/24", protocol="TCP", ports="8443")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["rule"]["Port"] == "8443"
    names = [c[0] for c in fake.calls]
    assert names.count("ModifyNatAcRule") == 1
    update = [c for c in fake.calls if c[0] == "ModifyNatAcRule"][0][1]
    assert update.Rules[0].Uuid == 9001
    assert update.Rules[0].Port == "8443"
    # order_index not given -> the existing execution order is preserved.
    assert update.Rules[0].OrderIndex == -1


def test_present_update_preserves_existing_order_index(monkeypatch):
    fake = FakeCfwClient([_rule_item(OrderIndex=7)])
    _make_module(monkeypatch, fake)
    module_args(state="present", description="allow-trusted-https", source="10.0.0.0/8",
                destination="203.0.113.0/24", protocol="TCP", ports="8443")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["rule"]["OrderIndex"] == 7
    update = [c for c in fake.calls if c[0] == "ModifyNatAcRule"][0][1]
    assert update.Rules[0].OrderIndex == 7


def test_present_enable_toggle_triggers_update(monkeypatch):
    fake = FakeCfwClient([_rule_item(Enable="false")])
    _make_module(monkeypatch, fake)
    module_args(state="present", description="allow-trusted-https", source="10.0.0.0/8",
                destination="203.0.113.0/24", protocol="TCP", ports="443", enabled=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["rule"]["Enable"] == "true"


def test_present_rule_uuid_referencing_missing_is_create(monkeypatch):
    # A stale rule_uuid is simply ignored and a fresh rule created (the module
    # treats it as "not found" -> create; unlike resource modules it has no
    # explicit stale-id guard).
    fake = FakeCfwClient()
    _make_module(monkeypatch, fake)
    module_args(state="present", rule_uuid=4242, description="allow-trusted-https",
                source="10.0.0.0/8", destination="203.0.113.0/24")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["rule"]["Uuid"] != 4242
    assert "AddNatAcRule" in [c[0] for c in fake.calls]


def test_check_mode_create_is_dry_run(monkeypatch):
    fake = FakeCfwClient()
    _make_module(monkeypatch, fake)
    module_args(_ansible_check_mode=True, state="present", description="allow-trusted-https",
                source="10.0.0.0/8", destination="203.0.113.0/24")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["rule"] is None  # no real rule created in check mode
    assert not any("AddNatAcRule" == c[0] for c in fake.calls)


def test_check_mode_update_is_dry_run(monkeypatch):
    fake = FakeCfwClient([_rule_item()])
    _make_module(monkeypatch, fake)
    module_args(_ansible_check_mode=True, state="present", description="allow-trusted-https",
                source="10.0.0.0/8", destination="203.0.113.0/24", ports="8443")
    result = run(mod.run_module)
    assert result["changed"] is True
    # No write happened, so the reported rule is the pre-change state.
    assert result["rule"]["Port"] == "443"
    assert not any("ModifyNatAcRule" == c[0] for c in fake.calls)


def test_absent_removes_rule(monkeypatch):
    fake = FakeCfwClient([_rule_item()])
    _make_module(monkeypatch, fake)
    module_args(state="absent", description="allow-trusted-https", direction="outbound")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["rule"] is None
    names = [c[0] for c in fake.calls]
    assert names.count("RemoveNatAcRule") == 1
    remove = [c for c in fake.calls if c[0] == "RemoveNatAcRule"][0][1]
    assert remove.RuleUuid == [9001]
    assert fake.rules == []


def test_absent_by_uuid_removes(monkeypatch):
    fake = FakeCfwClient([_rule_item(Uuid=9001, Description="a"), _rule_item(Uuid=9002, Description="b")])
    _make_module(monkeypatch, fake)
    module_args(state="absent", rule_uuid=9002, direction="outbound")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert [r["Uuid"] for r in fake.rules] == [9001]


def test_absent_not_found_is_noop(monkeypatch):
    fake = FakeCfwClient([_rule_item()])
    _make_module(monkeypatch, fake)
    module_args(state="absent", description="no-such-rule")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["rule"] is None
    assert not any("RemoveNatAcRule" == c[0] for c in fake.calls)


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeCfwClient([_rule_item()])
    _make_module(monkeypatch, fake)
    module_args(_ansible_check_mode=True, state="absent", description="allow-trusted-https")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["rule"] is not None  # pre-change state reported
    assert not any("RemoveNatAcRule" == c[0] for c in fake.calls)
    assert len(fake.rules) == 1
