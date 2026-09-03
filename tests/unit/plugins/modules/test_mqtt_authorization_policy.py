"""Unit tests for the mqtt_authorization_policy write module (helpers + run_module).

Covers the create / drift-update / delete flows of
``plugins/modules/mqtt_authorization_policy.py`` with an in-memory fake MQTT
client whose write operations mutate the policy store, so the module's
post-write ``find`` refetch converges immediately. Policies are matched by
``policy_id`` (``Id``) or by ``PolicyName``; CSV-encoded SDK list fields
(Actions / Resources / Qos) are split back into sorted lists for drift
comparison. ``effect`` / ``retain`` / ``qos`` are no-default choices params,
so tests drop explicit ``None`` values before injecting module args.
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
    "Id": 101,
    "InstanceId": "mqtt-1",
    "PolicyName": "app-publish",
    "Priority": 10,
    "Effect": "allow",
    "Actions": "connect,pub",
    "Resources": "orders/#",
    "Username": "",
    "ClientId": "",
    "Ip": "",
    "Retain": None,
    "Qos": "",
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
        "instance_id": "mqtt-1",
        "policy_id": None,
        "name": "app-publish",
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
    """_params() with None-valued keys removed (no-default choices params)."""
    return {k: v for k, v in _params(**overrides).items() if v is not None}


def _run_args(**extra):
    """module_args() pre-filled with every module parameter (None dropped)."""
    return module_args(**dict(_clean_params(**extra)))


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

    Stores API-shaped policy dicts; DescribeAuthorizationPolicies returns the
    whole store. Write operations mutate the store so post-write refetches
    converge.
    """

    def __init__(self, policies=None):
        self.policies = [copy.deepcopy(p) for p in (policies or [])]
        self.calls = []
        self._next_id = 1000

    def _record(self, name, request):
        self.calls.append((name, request))
        return request

    def _new_id(self):
        self._next_id += 1
        return self._next_id

    def DescribeAuthorizationPolicies(self, request):
        self._record("DescribeAuthorizationPolicies", request)
        return SimpleNamespace(Data=[FakeResource(dict(p)) for p in self.policies], RequestId="req-fake")

    def CreateAuthorizationPolicy(self, request):
        self._record("CreateAuthorizationPolicy", request)
        policy_id = self._new_id()
        self.policies.append(
            {
                "Id": policy_id,
                "InstanceId": request.InstanceId,
                "PolicyName": request.PolicyName,
                "Priority": request.Priority,
                "Effect": request.Effect,
                "Actions": request.Actions or "",
                "Resources": request.Resources or "",
                "Username": request.Username or "",
                "ClientId": request.ClientId or "",
                "Ip": request.Ip or "",
                "Retain": request.Retain,
                "Qos": request.Qos or "",
                "Remark": request.Remark or "",
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
            stored["Actions"] = request.Actions or ""
            stored["Resources"] = request.Resources or ""
            stored["Username"] = request.Username or ""
            stored["ClientId"] = request.ClientId or ""
            stored["Ip"] = request.Ip or ""
            stored["Retain"] = request.Retain
            stored["Qos"] = request.Qos or ""
            stored["Remark"] = request.Remark or ""
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
    assert request.InstanceId == "mqtt-1"


def test_csv_builder():
    assert mod._csv(["a", "b"]) == "a,b"
    assert mod._csv([1, 2]) == "1,2"
    assert mod._csv(None) == ""
    assert mod._csv([]) == ""


def test_create_request_fields():
    request = mod.create_request(FakeModels(), _clean_params(qos=[0, 1], retain=2, remark="pol"))
    assert request.InstanceId == "mqtt-1"
    assert request.PolicyName == "app-publish"
    assert request.PolicyVersion == 1
    assert request.Priority == 10
    assert request.Effect == "allow"
    assert request.Actions == "connect,pub"
    assert request.Resources == "orders/#"
    assert request.Qos == "0,1"
    assert request.Retain == 2
    assert request.Username == ""
    assert request.Remark == "pol"


def test_update_request_fields():
    request = mod.update_request(FakeModels(), _clean_params(priority=20), 101)
    assert request.Id == 101
    assert request.InstanceId == "mqtt-1"
    assert request.PolicyName == "app-publish"
    assert request.PolicyVersion == 1
    assert request.Priority == 20


def test_delete_request_fields():
    request = mod.delete_request(FakeModels(), _params(), 101)
    assert request.InstanceId == "mqtt-1"
    assert request.Id == 101


def test_comparable_splits_csv_fields():
    value = mod.comparable(_policy(Qos="0,2,1", Actions="pub,connect"))
    assert value["Actions"] == ["connect", "pub"]
    assert value["Resources"] == ["orders/#"]
    assert value["Qos"] == ["0", "1", "2"]
    assert value["Priority"] == 10
    assert value["Effect"] == "allow"
    assert value["Username"] == ""
    assert value["Remark"] == ""


def test_desired_uses_params_and_old_state():
    value = mod.desired(_params(effect=None, priority=None, actions=None, resources=None, retain=None, qos=None), _policy())
    assert value["PolicyName"] == "app-publish"
    assert value["Priority"] == 10  # falls back to remote
    assert value["Effect"] == "allow"  # falls back to remote
    assert value["Actions"] == ["connect", "pub"]  # falls back to remote
    assert value["Resources"] == ["orders/#"]
    assert value["Retain"] is None


def test_desired_sorts_provided_lists():
    value = mod.desired(_params(actions=["sub", "pub"], resources=["b", "a"], qos=[2, 0]), None)
    assert value["Actions"] == ["pub", "sub"]
    assert value["Resources"] == ["a", "b"]
    assert value["Qos"] == ["0", "2"]
    assert value["Priority"] == 10


# ---------------------------------------------------------------------------
# find tests
# ---------------------------------------------------------------------------


def test_find_no_match_returns_none(monkeypatch):
    fake = FakeMqttClient([_policy(PolicyName="other")])
    _make_module(monkeypatch, fake)
    module = FakeModule(_params(name="ghost"))
    assert mod.find(module, fake, FakeModels(), module.params) is None


def test_find_by_name(monkeypatch):
    fake = FakeMqttClient([_policy(PolicyName="other"), _policy()])
    _make_module(monkeypatch, fake)
    module = FakeModule(_params())
    value = mod.find(module, fake, FakeModels(), module.params)
    assert value["Id"] == 101


def test_find_by_policy_id(monkeypatch):
    fake = FakeMqttClient([_policy(), _policy(Id=102, PolicyName="other")])
    _make_module(monkeypatch, fake)
    module = FakeModule(_params(policy_id=102, name=None))
    value = mod.find(module, fake, FakeModels(), module.params)
    assert value["Id"] == 102


def test_find_multiple_matches_fails(monkeypatch):
    fake = FakeMqttClient([_policy(), _policy(Id=102)])
    _make_module(monkeypatch, fake)
    module = FakeModule(_params())
    with pytest.raises(AnsibleFailJson) as exc:
        mod.find(module, fake, FakeModels(), module.params)
    assert "Multiple MQTT authorization policies matched" in exc.value.args[0]["msg"]


# ---------------------------------------------------------------------------
# run_module main-path tests
# ---------------------------------------------------------------------------


def test_required_one_of_enforced():
    _run_args(name=None, policy_id=None)
    with pytest.raises(AnsibleFailJson):
        run(mod.run_module)


def test_present_creates_policy(monkeypatch):
    fake = FakeMqttClient()
    _make_module(monkeypatch, fake)
    _run_args()
    result = run(mod.run_module)
    assert result["changed"] is True
    policy = result["policy"]
    assert policy["Id"] == 1001
    assert policy["PolicyName"] == "app-publish"
    assert policy["Effect"] == "allow"
    names = [c[0] for c in fake.calls]
    assert names.count("DescribeAuthorizationPolicies") == 2  # find + refetch
    assert names.count("CreateAuthorizationPolicy") == 1
    create = [c for c in fake.calls if c[0] == "CreateAuthorizationPolicy"][0][1]
    assert create.Actions == "connect,pub"


def test_present_requires_creation_params(monkeypatch):
    fake = FakeMqttClient()
    _make_module(monkeypatch, fake)
    _run_args(policy_id=999, name=None, priority=None, effect=None, actions=None, resources=None)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "creation parameters are required for a new MQTT authorization policy" in exc.value.args[0]["msg"]


def test_present_noop_returns_unchanged(monkeypatch):
    fake = FakeMqttClient([_policy()])
    _make_module(monkeypatch, fake)
    _run_args()
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["policy"]["Id"] == 101
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
    assert modify.Id == 101
    assert modify.Priority == 20


def test_present_actions_drift_triggers_update(monkeypatch):
    fake = FakeMqttClient([_policy()])
    _make_module(monkeypatch, fake)
    _run_args(actions=["sub"])
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["policy"]["Actions"] == "sub"
    modify = [c for c in fake.calls if c[0] == "ModifyAuthorizationPolicy"][0][1]
    assert modify.Actions == "sub"


def test_present_qos_drift_triggers_update(monkeypatch):
    fake = FakeMqttClient([_policy(Qos="0")])
    _make_module(monkeypatch, fake)
    _run_args(qos=[1, 2])
    result = run(mod.run_module)
    assert result["changed"] is True
    assert sorted(result["policy"]["Qos"].split(",")) == ["1", "2"]
    modify = [c for c in fake.calls if c[0] == "ModifyAuthorizationPolicy"][0][1]
    assert sorted(modify.Qos.split(",")) == ["1", "2"]


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
    module_args(_ansible_check_mode=True, **dict(_clean_params()))
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["policy"]["PolicyName"] == "app-publish"  # desired reported
    assert not any("CreateAuthorizationPolicy" == c[0] for c in fake.calls)


def test_check_mode_update_is_dry_run(monkeypatch):
    fake = FakeMqttClient([_policy()])
    _make_module(monkeypatch, fake)
    module_args(_ansible_check_mode=True, **dict(_clean_params(priority=20)))
    result = run(mod.run_module)
    assert result["changed"] is True
    assert not any("ModifyAuthorizationPolicy" == c[0] for c in fake.calls)


def test_absent_removes_policy(monkeypatch):
    fake = FakeMqttClient([_policy()])
    _make_module(monkeypatch, fake)
    _run_args(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["policy"] is None
    delete = [c for c in fake.calls if c[0] == "DeleteAuthorizationPolicy"][0][1]
    assert delete.Id == 101
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
    module_args(_ansible_check_mode=True, **dict(_clean_params(state="absent")))
    result = run(mod.run_module)
    assert result["changed"] is True
    assert not any("DeleteAuthorizationPolicy" == c[0] for c in fake.calls)
    assert len(fake.policies) == 1
