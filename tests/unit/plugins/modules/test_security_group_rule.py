"""Unit tests for the security_group_rule write module helpers."""

from __future__ import absolute_import, division, print_function
__metaclass__ = type
from ansible_collections.susunola.tencentcloud.plugins.modules.security_group_rule import (
    build_describe_request,
    build_policy_set,
    delete_rules,
    find_rules,
    normalize_current_rule,
    normalize_desired_rule,
    reconcile_rules,
)


class FakeRequest(object):
    pass


class FakePolicy(object):
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)

    def _serialize(self, allow_none=True):
        return dict(self.__dict__)


class FakeModels(object):
    SecurityGroupPolicy = FakePolicy
    SecurityGroupPolicySet = FakeRequest
    DescribeSecurityGroupPoliciesRequest = FakeRequest
    CreateSecurityGroupPoliciesRequest = FakeRequest
    DeleteSecurityGroupPoliciesRequest = FakeRequest


class FakePolicySet(object):
    def __init__(self, ingress=None, egress=None):
        self.Ingress = ingress
        self.Egress = egress


class FakeResponse(object):
    def __init__(self, policy_set):
        self.SecurityGroupPolicySet = policy_set


class FakeClient(object):
    def __init__(self, response=None, exc=None, delete_exc=None):
        self.response = response
        self.exc = exc
        self.delete_exc = delete_exc
        self.deleted = []

    def DescribeSecurityGroupPolicies(self, request):
        if self.exc:
            raise self.exc
        return self.response

    def DeleteSecurityGroupPolicies(self, request):
        self.deleted.append(request)
        if self.delete_exc:
            raise self.delete_exc


class FakeModule(object):
    def __init__(self):
        self.params = {"retries": 2}

    def sdk_call(self, operation, request):
        return operation(request)


def _policy(**kwargs):
    defaults = {
        "Protocol": "TCP",
        "Port": "443",
        "CidrBlock": "0.0.0.0/0",
        "Action": "ACCEPT",
        "PolicyDescription": "",
    }
    defaults.update(kwargs)
    return FakePolicy(**defaults)


def _rule(**kwargs):
    defaults = {
        "protocol": "TCP",
        "port": "443",
        "cidr_block": "0.0.0.0/0",
        "action": "ACCEPT",
        "policy_description": "",
        "direction": "ingress",
    }
    defaults.update(kwargs)
    return defaults


def test_build_describe_request():
    request = build_describe_request(FakeModels, "sg-123")
    assert request.SecurityGroupId == "sg-123"


def test_normalize_desired_rule_applies_defaults():
    rule = normalize_desired_rule({"protocol": "tcp", "cidr_block": "10.0.0.0/8"})
    assert rule == {
        "protocol": "TCP",
        "port": "all",
        "cidr_block": "10.0.0.0/8",
        "action": "ACCEPT",
        "policy_description": "",
        "direction": "ingress",
    }


def test_normalize_desired_rule_maps_any_cidr():
    rule = normalize_desired_rule({"protocol": "ALL", "cidr_block": "0.0.0.0/8"})
    assert rule["cidr_block"] == "0.0.0.0/0"


def test_normalize_current_rule_uppercases_and_tags_direction():
    rule = normalize_current_rule(
        _policy(Protocol="tcp", Port=None, CidrBlock="0.0.0.0/12")._serialize(),
        "egress",
    )
    assert rule["protocol"] == "TCP"
    assert rule["port"] == "all"
    assert rule["cidr_block"] == "0.0.0.0/0"
    assert rule["direction"] == "egress"


def test_find_rules_flattens_ingress_and_egress():
    policy_set = FakePolicySet(ingress=[_policy(Port="443")], egress=[_policy(Port="80")])
    client = FakeClient(FakeResponse(policy_set))
    rules = find_rules(FakeModule(), client, FakeModels, "sg-1")
    assert [rule["direction"] for rule in rules] == ["ingress", "egress"]
    assert rules[1]["port"] == "80"


def test_find_rules_handles_none_policy_set():
    client = FakeClient(FakeResponse(None))
    assert find_rules(FakeModule(), client, FakeModels, "sg-1") == []


def test_find_rules_handles_none_lists():
    client = FakeClient(FakeResponse(FakePolicySet()))
    assert find_rules(FakeModule(), client, FakeModels, "sg-1") == []


def test_find_rules_surfaces_sdk_exceptions():
    class Boom(Exception):
        def get_code(self):
            return "InvalidSecurityGroupId.NotFound"

    client = FakeClient(exc=Boom("gone"))
    try:
        find_rules(FakeModule(), client, FakeModels, "sg-1")
        raise AssertionError("expected exception")
    except Boom:
        pass


def test_reconcile_no_changes():
    current = [_rule(), _rule(port="80", direction="egress")]
    desired = [_rule(port="80", direction="egress"), _rule()]
    to_create, to_delete = reconcile_rules(desired, current, purge=True)
    assert to_create == []
    assert to_delete == []


def test_reconcile_creates_only_the_delta():
    current = [_rule()]
    desired = [_rule(), _rule(port="22", cidr_block="10.0.0.0/8")]
    to_create, to_delete = reconcile_rules(desired, current, purge=True)
    assert to_create == [_rule(port="22", cidr_block="10.0.0.0/8")]
    assert to_delete == []


def test_reconcile_purge_deletes_surplus():
    current = [_rule(), _rule(port="22")]
    desired = [_rule()]
    to_create, to_delete = reconcile_rules(desired, current, purge=True)
    assert to_create == []
    assert to_delete == [_rule(port="22")]


def test_reconcile_purge_false_never_deletes():
    current = [_rule(), _rule(port="22")]
    desired = [_rule(port="80")]
    to_create, to_delete = reconcile_rules(desired, current, purge=False)
    assert to_create == [_rule(port="80")]
    assert to_delete == []


def test_reconcile_description_change_replaces_rule():
    current = [_rule(policy_description="old")]
    desired = [_rule(policy_description="new")]
    to_create, to_delete = reconcile_rules(desired, current, purge=True)
    assert to_create == [_rule(policy_description="new")]
    assert to_delete == [_rule(policy_description="old")]


def test_reconcile_matches_duplicate_rules_one_to_one():
    current = [_rule(), _rule()]
    desired = [_rule()]
    to_create, to_delete = reconcile_rules(desired, current, purge=True)
    assert to_create == []
    assert to_delete == [_rule()]


def test_build_policy_set_splits_directions():
    policy_set = build_policy_set(
        FakeModels,
        [_rule(direction="ingress"), _rule(port="80", direction="egress")],
    )
    assert len(policy_set.Ingress) == 1
    assert len(policy_set.Egress) == 1
    policy = policy_set.Egress[0]
    assert policy.Protocol == "TCP"
    assert policy.Port == "80"
    assert policy.CidrBlock == "0.0.0.0/0"
    assert policy.Action == "ACCEPT"


def test_build_policy_set_includes_description_for_create():
    policy_set = build_policy_set(FakeModels, [_rule(policy_description="web")])
    assert policy_set.Ingress[0].PolicyDescription == "web"


def test_build_policy_set_omits_description_for_delete():
    policy_set = build_policy_set(
        FakeModels, [_rule(policy_description="web")], include_description=False
    )
    assert not hasattr(policy_set.Ingress[0], "PolicyDescription")


def test_delete_rules_sends_one_request_per_direction():
    client = FakeClient()
    delete_rules(
        FakeModule(), client, FakeModels, "sg-1",
        [_rule(), _rule(port="80"), _rule(port="53", protocol="UDP", direction="egress")],
    )
    assert len(client.deleted) == 2
    ingress_request = client.deleted[0]
    egress_request = client.deleted[1]
    assert ingress_request.SecurityGroupId == "sg-1"
    assert len(ingress_request.SecurityGroupPolicySet.Ingress) == 2
    assert egress_request.SecurityGroupPolicySet.Egress[0].Protocol == "UDP"


def test_delete_rules_treats_not_found_as_success():
    class Gone(Exception):
        def get_code(self):
            return "InvalidSecurityGroupId.NotFound"

    client = FakeClient(delete_exc=Gone("gone"))
    delete_rules(FakeModule(), client, FakeModels, "sg-1", [_rule()])


def test_delete_rules_raises_other_errors():
    class Boom(Exception):
        def get_code(self):
            return "InternalError"

    client = FakeClient(delete_exc=Boom("broken"))
    try:
        delete_rules(FakeModule(), client, FakeModels, "sg-1", [_rule()])
        raise AssertionError("expected exception")
    except Boom:
        pass
