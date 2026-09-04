"""Unit tests for the cfw_vpc_acl_rule write module (helpers + run_module).

Covers the create / drift-update / delete flows of
``plugins/modules/cfw_vpc_acl_rule.py`` with an in-memory fake Cloud Firewall
client whose write operations mutate the rule store, so the module's
post-write ``find_rule`` refetch converges immediately. Rules are matched by
``rule_uuid`` or by ``edge_id`` + ``description`` across the paged
DescribeVpcAcRule list; actions are re-encoded to the API vocabulary
(``log``/``drop``/``accept``), Enable to ``"true"/"false"``, and the
pre-change comparison projects the current rule onto the desired key set so
extra API fields never cause drift.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import cfw_vpc_acl_rule as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

RULE = {
    "Uuid": 9001,
    "SourceContent": "10.0.0.0/16",
    "SourceType": "net",
    "DestContent": "10.20.0.0/16",
    "DestType": "net",
    "Protocol": "ANY",
    "Port": "-1/-1",
    "RuleAction": "accept",
    "Description": "allow-vpc-https",
    "EdgeId": "vpcfw-edge-1",
    "OrderIndex": -1,
    "Enable": "true",
    "IpVersion": 0,
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
        "description": "allow-vpc-https",
        "edge_id": "vpcfw-edge-1",
        "source": "10.0.0.0/16",
        "destination": "10.20.0.0/16",
        "destination_type": "net",
        "protocol": "ANY",
        "ports": "-1/-1",
        "action": "accept",
        "enabled": True,
        "order_index": None,
        "firewall_group_id": None,
        "parameter_template_id": None,
        "ip_version": 0,
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

    Stores API-shaped rule dicts. DescribeVpcAcRule pages over the store
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

    def DescribeVpcAcRule(self, request):
        self._record("DescribeVpcAcRule", request)
        page = self.rules[request.Offset : request.Offset + request.Limit]
        return SimpleNamespace(
            Data=[FakeResource(dict(r)) for r in page],
            Total=len(self.rules),
            RequestId="req-fake",
        )

    def AddVpcAcRule(self, request):
        self._record("AddVpcAcRule", request)
        uuids = []
        for rule in request.Rules:
            self._next_uuid += 1
            uuids.append(self._next_uuid)
            item = self._plain(rule)
            item["Uuid"] = self._next_uuid
            self.rules.append(item)
        return SimpleNamespace(RuleUuids=uuids, RequestId="req-fake")

    def ModifyVpcAcRule(self, request):
        self._record("ModifyVpcAcRule", request)
        for rule in request.Rules:
            item = self._plain(rule)
            uuid = item.pop("Uuid")
            for stored in self.rules:
                if stored.get("Uuid") == uuid:
                    stored.clear()
                    stored.update(item)
                    stored["Uuid"] = uuid
        return SimpleNamespace(RequestId="req-fake")

    def RemoveVpcAcRule(self, request):
        self._record("RemoveVpcAcRule", request)
        uuids = list(request.RuleUuids or [])
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
# request-builder helper tests
# ---------------------------------------------------------------------------


def test_describe_request_fields():
    request = mod.describe_request(FakeModels(), offset=7)
    assert request.Offset == 7
    assert request.Limit == 100


def test_rule_builder_maps_fields():
    rule = mod._rule(FakeModels(), _params())
    assert rule.SourceContent == "10.0.0.0/16"
    assert rule.SourceType == "net"
    assert rule.DestContent == "10.20.0.0/16"
    assert rule.DestType == "net"
    assert rule.Protocol == "ANY"
    assert rule.Port == "-1/-1"
    assert rule.RuleAction == "accept"
    assert rule.Description == "allow-vpc-https"
    assert rule.EdgeId == "vpcfw-edge-1"
    assert rule.OrderIndex == -1  # append-by-default
    assert rule.Enable == "true"
    assert rule.IpVersion == 0


def test_rule_builder_encodes_action_and_enable():
    rule = mod._rule(FakeModels(), _params(action="block", enabled=False, destination_type="domain", destination="example.com"))
    assert rule.RuleAction == "drop"
    assert rule.Enable == "false"
    assert rule.DestType == "domain"
    assert rule.DestContent == "example.com"


def test_rule_builder_optional_fields():
    rule = mod._rule(
        FakeModels(),
        _params(order_index=4, firewall_group_id="vpcfw-group-9", parameter_template_id="pmt-7", ip_version=1),
        rule_uuid=77,
    )
    assert rule.Uuid == 77
    assert rule.OrderIndex == 4
    assert rule.FwGroupId == "vpcfw-group-9"
    assert rule.ParamTemplateId == "pmt-7"
    assert rule.IpVersion == 1


def test_rule_builder_omits_uuid_when_absent():
    rule = mod._rule(FakeModels(), _params())
    assert not hasattr(rule, "Uuid")


def test_create_request_wraps_single_rule():
    request = mod.create_request(FakeModels(), _params())
    assert len(request.Rules) == 1
    assert request.Rules[0].SourceContent == "10.0.0.0/16"


def test_update_request_carries_uuid():
    request = mod.update_request(FakeModels(), _params(), 9001)
    assert request.Rules[0].Uuid == 9001
    assert request.Rules[0].Description == "allow-vpc-https"


def test_delete_request_fields():
    request = mod.delete_request(FakeModels(), _params(ip_version=1), 9001)
    assert request.RuleUuids == [9001]
    assert request.IpVersion == 1


# ---------------------------------------------------------------------------
# desired tests
# ---------------------------------------------------------------------------


def test_desired_encodes_api_values():
    value = mod.desired(_params())
    assert value == {
        "SourceContent": "10.0.0.0/16",
        "SourceType": "net",
        "DestContent": "10.20.0.0/16",
        "DestType": "net",
        "Protocol": "ANY",
        "Port": "-1/-1",
        "RuleAction": "accept",
        "Description": "allow-vpc-https",
        "EdgeId": "vpcfw-edge-1",
        "Enable": "true",
        "IpVersion": 0,
    }


def test_desired_includes_optional_fields():
    value = mod.desired(_params(order_index=3, firewall_group_id="vpcfw-group-1", parameter_template_id="pmt-2", ip_version=1))
    assert value["OrderIndex"] == 3
    assert value["FwGroupId"] == "vpcfw-group-1"
    assert value["ParamTemplateId"] == "pmt-2"
    assert value["IpVersion"] == 1


def test_desired_omits_optional_fields_when_unset():
    value = mod.desired(_params())
    assert "OrderIndex" not in value
    assert "FwGroupId" not in value
    assert "ParamTemplateId" not in value


def test_desired_action_mapping():
    assert mod.desired(_params(action="observe"))["RuleAction"] == "log"
    assert mod.desired(_params(action="block"))["RuleAction"] == "drop"


# ---------------------------------------------------------------------------
# find_rule tests
# ---------------------------------------------------------------------------


def test_find_rule_no_match_returns_none(monkeypatch):
    fake = FakeCfwClient([_rule_item()])
    _make_module(monkeypatch, fake)
    module = FakeModule(_params(description="no-such-rule"))
    assert mod.find_rule(module, fake, FakeModels(), module.params) is None


def test_find_rule_by_edge_and_description(monkeypatch):
    fake = FakeCfwClient([_rule_item(), _rule_item(Uuid=9002, EdgeId="vpcfw-edge-2")])
    _make_module(monkeypatch, fake)
    module = FakeModule(_params(description="allow-vpc-https"))
    value = mod.find_rule(module, fake, FakeModels(), module.params)
    assert value["Uuid"] == 9001


def test_find_rule_ignores_same_description_on_other_edge(monkeypatch):
    fake = FakeCfwClient([_rule_item(Uuid=9002, EdgeId="vpcfw-edge-2")])
    _make_module(monkeypatch, fake)
    module = FakeModule(_params(description="allow-vpc-https"))
    assert mod.find_rule(module, fake, FakeModels(), module.params) is None


def test_find_rule_by_uuid(monkeypatch):
    fake = FakeCfwClient([_rule_item(), _rule_item(Uuid=9002, Description="other")])
    _make_module(monkeypatch, fake)
    module = FakeModule(_params(rule_uuid=9002, description=None))
    value = mod.find_rule(module, fake, FakeModels(), module.params)
    assert value["Uuid"] == 9002


def test_find_rule_multiple_matches_fails(monkeypatch):
    fake = FakeCfwClient([_rule_item(Uuid=9001), _rule_item(Uuid=9002)])
    _make_module(monkeypatch, fake)
    module = FakeModule(_params(description="allow-vpc-https"))
    with pytest.raises(AnsibleFailJson) as exc:
        mod.find_rule(module, fake, FakeModels(), module.params)
    assert "Multiple inter-VPC ACL rules matched" in exc.value.args[0]["msg"]


def test_find_rule_paginates_until_match(monkeypatch):
    rules = [_rule_item(Uuid=1000 + i, Description="bulk-%04d" % i, EdgeId="vpcfw-edge-%d" % i) for i in range(250)]
    rules.append(_rule_item(Uuid=9999, Description="allow-vpc-https"))
    fake = FakeCfwClient(rules)
    _make_module(monkeypatch, fake)
    module = FakeModule(_params(description="allow-vpc-https"))
    value = mod.find_rule(module, fake, FakeModels(), module.params)
    assert value["Uuid"] == 9999
    list_calls = [c for c in fake.calls if c[0] == "DescribeVpcAcRule"]
    assert len(list_calls) == 3  # pages of 100
    assert [c[1].Offset for c in list_calls] == [0, 100, 200]


# ---------------------------------------------------------------------------
# run_module main-path tests
# ---------------------------------------------------------------------------


def test_required_one_of_enforced():
    module_args(state="present", edge_id="vpcfw-edge-1")  # neither rule_uuid nor description
    with pytest.raises(AnsibleFailJson):
        run(mod.run_module)


def test_present_requires_source_and_destination():
    module_args(state="present", edge_id="vpcfw-edge-1", description="x")
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
    _run_args()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert payload["error"] == "service exploded"


def test_present_creates_rule(monkeypatch):
    fake = FakeCfwClient()
    _make_module(monkeypatch, fake)
    _run_args(description="allow-vpc-https", source="10.0.0.0/16", destination="10.20.0.0/16", protocol="TCP", ports="443")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["rule"]["Uuid"] == 10001
    assert result["rule"]["Description"] == "allow-vpc-https"
    names = [c[0] for c in fake.calls]
    assert names.count("DescribeVpcAcRule") == 2  # find + refetch
    assert names.count("AddVpcAcRule") == 1
    add = [c for c in fake.calls if c[0] == "AddVpcAcRule"][0][1]
    assert add.Rules[0].RuleAction == "accept"
    assert add.Rules[0].OrderIndex == -1


def test_present_noop_returns_unchanged(monkeypatch):
    fake = FakeCfwClient([_rule_item()])
    _make_module(monkeypatch, fake)
    _run_args()
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["rule"]["Uuid"] == 9001
    names = [c[0] for c in fake.calls]
    assert "AddVpcAcRule" not in names
    assert "ModifyVpcAcRule" not in names


def test_present_drift_triggers_update(monkeypatch):
    fake = FakeCfwClient([_rule_item()])
    _make_module(monkeypatch, fake)
    _run_args(ports="8443")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["rule"]["Port"] == "8443"
    names = [c[0] for c in fake.calls]
    assert names.count("ModifyVpcAcRule") == 1
    update = [c for c in fake.calls if c[0] == "ModifyVpcAcRule"][0][1]
    assert update.Rules[0].Uuid == 9001
    assert update.Rules[0].Port == "8443"
    # order_index not given -> the existing execution order is preserved.
    assert update.Rules[0].OrderIndex == -1


def test_present_update_preserves_existing_order_index(monkeypatch):
    fake = FakeCfwClient([_rule_item(OrderIndex=7)])
    _make_module(monkeypatch, fake)
    _run_args(ports="8443")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["rule"]["OrderIndex"] == 7
    update = [c for c in fake.calls if c[0] == "ModifyVpcAcRule"][0][1]
    assert update.Rules[0].OrderIndex == 7


def test_present_explicit_order_index_wins(monkeypatch):
    fake = FakeCfwClient([_rule_item(OrderIndex=7)])
    _make_module(monkeypatch, fake)
    _run_args(ports="8443", order_index=2)
    result = run(mod.run_module)
    assert result["changed"] is True
    update = [c for c in fake.calls if c[0] == "ModifyVpcAcRule"][0][1]
    assert update.Rules[0].OrderIndex == 2


def test_present_enable_toggle_triggers_update(monkeypatch):
    fake = FakeCfwClient([_rule_item(Enable="false")])
    _make_module(monkeypatch, fake)
    _run_args(enabled=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["rule"]["Enable"] == "true"


def test_present_rule_uuid_referencing_missing_is_create(monkeypatch):
    # A stale rule_uuid is simply ignored and a fresh rule created (the module
    # treats it as "not found" -> create; unlike resource modules it has no
    # explicit stale-id guard).
    fake = FakeCfwClient()
    _make_module(monkeypatch, fake)
    _run_args(rule_uuid=4242, description="allow-vpc-https", source="10.0.0.0/16", destination="10.20.0.0/16")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["rule"]["Uuid"] != 4242
    assert "AddVpcAcRule" in [c[0] for c in fake.calls]


def test_check_mode_create_is_dry_run(monkeypatch):
    fake = FakeCfwClient()
    _make_module(monkeypatch, fake)
    module_args(_ansible_check_mode=True, **_params())
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["rule"] is None  # no real rule created in check mode
    assert not any("AddVpcAcRule" == c[0] for c in fake.calls)


def test_check_mode_update_is_dry_run(monkeypatch):
    fake = FakeCfwClient([_rule_item()])
    _make_module(monkeypatch, fake)
    module_args(_ansible_check_mode=True, **_params(ports="8443"))
    result = run(mod.run_module)
    assert result["changed"] is True
    # No write happened, so the reported rule is the pre-change state.
    assert result["rule"]["Port"] == "-1/-1"
    assert not any("ModifyVpcAcRule" == c[0] for c in fake.calls)


def test_absent_removes_rule(monkeypatch):
    fake = FakeCfwClient([_rule_item()])
    _make_module(monkeypatch, fake)
    _run_args(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["rule"] is None
    names = [c[0] for c in fake.calls]
    assert names.count("RemoveVpcAcRule") == 1
    remove = [c for c in fake.calls if c[0] == "RemoveVpcAcRule"][0][1]
    assert remove.RuleUuids == [9001]
    assert fake.rules == []


def test_absent_by_uuid_removes(monkeypatch):
    fake = FakeCfwClient([_rule_item(Uuid=9001, Description="a"), _rule_item(Uuid=9002, Description="b")])
    _make_module(monkeypatch, fake)
    _run_args(state="absent", rule_uuid=9002, description=None)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert [r["Uuid"] for r in fake.rules] == [9001]


def test_absent_not_found_is_noop(monkeypatch):
    fake = FakeCfwClient([_rule_item()])
    _make_module(monkeypatch, fake)
    _run_args(state="absent", description="no-such-rule")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["rule"] is None
    assert not any("RemoveVpcAcRule" == c[0] for c in fake.calls)


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeCfwClient([_rule_item()])
    _make_module(monkeypatch, fake)
    module_args(_ansible_check_mode=True, **_params(state="absent"))
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["rule"] is not None  # pre-change state reported
    assert not any("RemoveVpcAcRule" == c[0] for c in fake.calls)
    assert len(fake.rules) == 1
