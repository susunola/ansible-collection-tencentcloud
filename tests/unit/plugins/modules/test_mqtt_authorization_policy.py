"""Unit tests for the mqtt_authorization_policy write module (helpers + run_module).

Covers the create / drift-update / delete flows of
``plugins/modules/mqtt_authorization_policy.py`` with an in-memory fake MQTT
client whose write operations mutate the policy store, so the module's
post-write ``find`` refetch converges immediately. Policies are matched by
``policy_id`` (field ``Id``) or by ``PolicyName`` across the Describe
response; CSV-encoded action/resource/qos fields are compared as sorted
lists.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import mqtt_authorization_policy as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

POLICY = {
    "Id": 7,
    "PolicyName": "application-publish",
    "Priority": 10,
    "Effect": "allow",
    "Actions": "connect,pub",
    "Resources": "orders/#",
    "Username": "",
    "ClientId": "",
    "Ip": "",
    "Retain": None,
    "Qos": "0,1",
    "Remark": "",
}


def _policy(**overrides):
    """API-shaped policy dict isolated from the shared constant."""
    item = copy.deepcopy(POLICY)
    item.update(overrides)
    return item


def _params(**overrides):
    """Module parameters pre-filled from the argument spec."""
    params = {
        "state": "present",
        "instance_id": "mqtt-inst-1",
        "policy_id": None,
        "name": "application-publish",
        "priority": 10,
        "effect": "allow",
        "actions": ["connect", "pub"],
        "resources": ["orders/#"],
        "username": "",
        "client_id": "",
        "ip": "",
        "retain": None,
        "qos": None,
        "remark": "",
    }
    params.update(overrides)
    return params


def _clean_params(**overrides):
    """Drop None-valued params — Ansible validates explicit None against choices."""
    return {k: v for k, v in _params(**overrides).items() if v is not None}


def _run_args(**extra):
    """module_args() pre-filled with valid (non-None) module parameters."""
    args = dict(_clean_params())
    args.update({k: v for k, v in extra.items() if v is not None})
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


class FakeMqttClient(object):
    """In-memory MqttClient stand-in.

    Stores API-shaped policy dicts. DescribeAuthorizationPolicies returns the
    whole store; write operations mutate the store so the module's post-write
    find refetch converges.
    """

    def __init__(self, policies=None):
        self.policies = [copy.deepcopy(p) for p in (policies or [])]
        self.calls = []
        self._next_id = 100

    def _record(self, name, request):
        self.calls.append((name, request))
        return request

    def _new_id(self):
        self._next_id += 1
        return self._next_id

    def DescribeAuthorizationPolicies(self, request):
        self._record("DescribeAuthorizationPolicies", request)
        return SimpleNamespace(
            Data=[FakeResource(dict(p)) for p in self.policies],
            TotalCount=len(self.policies),
            RequestId="req-fake",
        )

    def CreateAuthorizationPolicy(self, request):
        self._record("CreateAuthorizationPolicy", request)
        policy_id = self._new_id()
        self.policies.append(
            {
                "Id": policy_id,
                "PolicyName": request.PolicyName,
                "Priority": request.Priority,
                "Effect": request.Effect,
                "Actions": request.Actions,
                "Resources": request.Resources,
                "Username": request.Username,
                "ClientId": request.ClientId,
                "Ip": request.Ip,
                "Retain": getattr(request, "Retain", None),
                "Qos": request.Qos,
                "Remark": request.Remark,
            }
        )
        return SimpleNamespace(Id=policy_id, RequestId="req-fake")

    def ModifyAuthorizationPolicy(self, request):
        self._record("ModifyAuthorizationPolicy", request)
        for stored in self.policies:
            if stored.get("Id") != request.Id:
                continue
            stored["PolicyName"] = request.PolicyName
            stored["Priority"] = request.Priority
            stored["Effect"] = request.Effect
            stored["Actions"] = request.Actions
            stored["Resources"] = request.Resources
            stored["Username"] = request.Username
            stored["ClientId"] = request.ClientId
            stored["Ip"] = request.Ip
            stored["Retain"] = getattr(request, "Retain", None)
            stored["Qos"] = request.Qos
            stored["Remark"] = request.Remark
        return SimpleNamespace(RequestId="req-fake")

    def DeleteAuthorizationPolicy(self, request):
        self._record("DeleteAuthorizationPolicy", request)
        self.policies = [p for p in self.policies if p.get("Id") != request.Id]
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake):
    """Wire the shared monkeypatches and return the fake client."""
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(
        mod,
        "_load",
        lambda: (FakeModels(), SimpleNamespace(MqttClient=object)),
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
    assert request.InstanceId == "mqtt-inst-1"


def test_csv_joins_values():
    assert mod._csv(["connect", "pub"]) == "connect,pub"
    assert mod._csv([0, 1, 2]) == "0,1,2"
    assert mod._csv(None) == ""
    assert mod._csv([]) == ""


def test_create_request_fields():
    request = mod.create_request(FakeModels(), _clean_params(qos=[0, 1], retain=1))
    assert request.InstanceId == "mqtt-inst-1"
    assert request.PolicyName == "application-publish"
    assert request.PolicyVersion == 1
    assert request.Priority == 10
    assert request.Effect == "allow"
    assert request.Actions == "connect,pub"
    assert request.Resources == "orders/#"
    assert request.Qos == "0,1"
    assert request.Username == ""
    assert request.Retain == 1


def test_create_request_qos_defaults_to_empty():
    request = mod.create_request(FakeModels(), _clean_params())
    assert request.Qos == ""
    assert request.Retain is None


def test_update_request_fields():
    request = mod.update_request(FakeModels(), _clean_params(name="renamed", priority=20), 42)
    assert request.Id == 42
    assert request.InstanceId == "mqtt-inst-1"
    assert request.PolicyName == "renamed"
    assert request.PolicyVersion == 1
    assert request.Priority == 20


def test_delete_request_fields():
    request = mod.delete_request(FakeModels(), _params(), 42)
    assert request.InstanceId == "mqtt-inst-1"
    assert request.Id == 42


def test_comparable_splits_csv_fields():
    value = mod.comparable(_policy(Actions="pub,connect", Qos="2,0,1"))
    assert value["Actions"] == ["connect", "pub"]
    assert value["Qos"] == ["0", "1", "2"]
    assert value["Priority"] == 10
    assert value["Effect"] == "allow"


def test_comparable_handles_empty_and_none_csv():
    value = mod.comparable(_policy(Actions="", Qos=None, Retain=None))
    assert value["Actions"] == []
    assert value["Qos"] == []
    assert value["Retain"] is None


def test_desired_uses_params_and_old_state():
    value = mod.desired(_clean_params(qos=None, retain=None), _policy())
    assert value["PolicyName"] == "application-publish"
    assert value["Priority"] == 10
    assert value["Actions"] == ["connect", "pub"]
    assert value["Resources"] == ["orders/#"]
    # unset choices fall back to remote state
    assert value["Qos"] == ["0", "1"]
    assert value["Retain"] is None


def test_desired_sorts_input_lists():
    value = mod.desired(_clean_params(actions=["sub", "connect"], resources=["b/#", "a/#"], qos=[2, 0]), _policy())
    assert value["Actions"] == ["connect", "sub"]
    assert value["Resources"] == ["a/#", "b/#"]
    assert value["Qos"] == ["0", "2"]


# ---------------------------------------------------------------------------
# find tests
# ---------------------------------------------------------------------------


def test_find_no_match_returns_none(monkeypatch):
    fake = FakeMqttClient([_policy(PolicyName="other")])
    _make_module(monkeypatch, fake)
    module = FakeModule(_params(name="ghost"))
    assert mod.find(module, fake, FakeModels(), module.params) is None


def test_find_by_name(monkeypatch):
    fake = FakeMqttClient([_policy(PolicyName="other", Id=1), _policy()])
    _make_module(monkeypatch, fake)
    module = FakeModule(_params(name="application-publish"))
    value = mod.find(module, fake, FakeModels(), module.params)
    assert value["Id"] == 7


def test_find_by_policy_id(monkeypatch):
    fake = FakeMqttClient([_policy(), _policy(Id=9, PolicyName="other")])
    _make_module(monkeypatch, fake)
    module = FakeModule(_params(policy_id=9, name=None))
    value = mod.find(module, fake, FakeModels(), module.params)
    assert value["Id"] == 9


def test_find_multiple_matches_fails(monkeypatch):
    fake = FakeMqttClient([_policy(), _policy(Id=8)])
    _make_module(monkeypatch, fake)
    module = FakeModule(_params(name="application-publish"))
    with pytest.raises(AnsibleFailJson) as exc:
        mod.find(module, fake, FakeModels(), module.params)
    assert "Multiple MQTT authorization policies matched" in exc.value.args[0]["msg"]


# ---------------------------------------------------------------------------
# run_module main-path tests
# ---------------------------------------------------------------------------


def test_required_one_of_enforced():
    module_args(state="present", instance_id="mqtt-inst-1")  # neither policy_id nor name
    with pytest.raises(AnsibleFailJson):
        run(mod.run_module)


def test_present_creates_policy(monkeypatch):
    fake = FakeMqttClient()
    _make_module(monkeypatch, fake)
    _run_args(qos=[0, 1], retain=1)
    result = run(mod.run_module)
    assert result["changed"] is True
    policy = result["policy"]
    assert policy["Id"] == 101
    assert policy["PolicyName"] == "application-publish"
    assert policy["Priority"] == 10
    names = [c[0] for c in fake.calls]
    assert names.count("DescribeAuthorizationPolicies") == 2  # find + refetch
    assert names.count("CreateAuthorizationPolicy") == 1
    create = [c for c in fake.calls if c[0] == "CreateAuthorizationPolicy"][0][1]
    assert create.PolicyVersion == 1


def test_present_creation_requires_all_fields(monkeypatch):
    fake = FakeMqttClient()
    _make_module(monkeypatch, fake)
    # policy_id identifies nothing; name/priority omitted -> creation guard fires
    module_args(**{k: v for k, v in _clean_params(policy_id=7, name=None, priority=None).items() if v is not None})
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "creation parameters are required" in payload["msg"]
    assert "name" in payload["missing"]


def test_present_noop_returns_unchanged(monkeypatch):
    fake = FakeMqttClient([_policy()])
    _make_module(monkeypatch, fake)
    _run_args(qos=[0, 1])
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["policy"]["Id"] == 7
    names = [c[0] for c in fake.calls]
    assert "ModifyAuthorizationPolicy" not in names
    assert "CreateAuthorizationPolicy" not in names


def test_present_priority_drift_triggers_update(monkeypatch):
    fake = FakeMqttClient([_policy()])
    _make_module(monkeypatch, fake)
    _run_args(priority=20)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["policy"]["Priority"] == 20
    modify = [c for c in fake.calls if c[0] == "ModifyAuthorizationPolicy"][0][1]
    assert modify.Id == 7
    assert modify.Priority == 20


def test_present_rename_by_policy_id(monkeypatch):
    fake = FakeMqttClient([_policy(PolicyName="old-name")])
    _make_module(monkeypatch, fake)
    _run_args(policy_id=7, name="new-name")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["policy"]["PolicyName"] == "new-name"
    assert len(fake.policies) == 1  # renamed in place


def test_present_effect_drift_triggers_update(monkeypatch):
    fake = FakeMqttClient([_policy(Effect="deny")])
    _make_module(monkeypatch, fake)
    _run_args(effect="allow")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["policy"]["Effect"] == "allow"


def test_sdk_error_is_reported(monkeypatch):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(
        mod,
        "_load",
        lambda: (FakeModels(), SimpleNamespace(MqttClient=object)),
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
    fake = FakeMqttClient()
    _make_module(monkeypatch, fake)
    module_args(_ansible_check_mode=True, **_clean_params())
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["policy"]["PolicyName"] == "application-publish"  # desired reported
    assert not any("CreateAuthorizationPolicy" == c[0] for c in fake.calls)


def test_check_mode_update_is_dry_run(monkeypatch):
    fake = FakeMqttClient([_policy()])
    _make_module(monkeypatch, fake)
    module_args(_ansible_check_mode=True, **_clean_params(priority=20))
    result = run(mod.run_module)
    assert result["changed"] is True
    assert not any("ModifyAuthorizationPolicy" == c[0] for c in fake.calls)


def test_absent_removes_policy(monkeypatch):
    fake = FakeMqttClient([_policy()])
    _make_module(monkeypatch, fake)
    _run_args(state="absent", name="application-publish")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["policy"] is None
    delete = [c for c in fake.calls if c[0] == "DeleteAuthorizationPolicy"][0][1]
    assert delete.Id == 7
    assert fake.policies == []


def test_absent_not_found_is_noop(monkeypatch):
    fake = FakeMqttClient([_policy()])
    _make_module(monkeypatch, fake)
    _run_args(state="absent", name="ghost")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["policy"] is None
    assert not any("DeleteAuthorizationPolicy" == c[0] for c in fake.calls)


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeMqttClient([_policy()])
    _make_module(monkeypatch, fake)
    module_args(_ansible_check_mode=True, **_clean_params(state="absent", name="application-publish"))
    result = run(mod.run_module)
    assert result["changed"] is True
    assert not any("DeleteAuthorizationPolicy" == c[0] for c in fake.calls)
    assert len(fake.policies) == 1
