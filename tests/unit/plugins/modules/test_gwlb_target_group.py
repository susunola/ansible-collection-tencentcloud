"""Unit tests for the gwlb_target_group write module (helpers + run_module).

Covers the create / drift-update / delete flows of
``plugins/modules/gwlb_target_group.py`` with an in-memory fake GWLB client
whose write operations mutate the target-group store, so the module's
post-write ``find`` refetch converges immediately. Target groups are matched
by ``target_group_id`` or by ``TargetGroupName``; VpcId / Port / Protocol /
ScheduleAlgorithm / ForwardingMode are immutable after creation and drift on
them fails with a replacement-required error. The SDK HealthCheck config
sub-object round-trips through ``from_json_string``.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
import json
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import gwlb_target_group as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

GROUP = {
    "TargetGroupId": "gwlb-tg-1",
    "TargetGroupName": "security-appliances",
    "VpcId": "vpc-1",
    "Port": 6081,
    "Protocol": "GENEVE",
    "ScheduleAlgorithm": "WRR",
    "ForwardingMode": "L3",
    "HealthCheck": {"HealthSwitch": True, "Protocol": "TCP", "Port": 80},
    "AllDeadToAlive": False,
}


def _group(**overrides):
    """API-shaped target-group dict isolated from the shared constant."""
    item = copy.deepcopy(GROUP)
    item.update(overrides)
    return item


def _params(**overrides):
    """Module parameters pre-filled from the argument spec."""
    params = {
        "state": "present",
        "target_group_id": None,
        "name": "security-appliances",
        "vpc_id": "vpc-1",
        "port": 6081,
        "protocol": "GENEVE",
        "schedule_algorithm": None,
        "health_check": None,
        "all_dead_to_alive": False,
        "forwarding_mode": None,
        "tags": None,
    }
    params.update(overrides)
    return params


def _run_args(**extra):
    """module_args() pre-filled with every module parameter (None dropped)."""
    args = dict(_params())
    args.update(extra)
    return module_args(**{k: v for k, v in args.items() if v is not None})


class _JsonModel(object):
    """SDK model whose config sub-objects round-trip through from_json_string."""

    def from_json_string(self, payload):
        for key, value in json.loads(payload).items():
            setattr(self, key, value)
        return self


class FakeGwlbModels(FakeModels):
    """FakeModels whose config class implements from_json_string."""

    def __getattr__(self, name):
        if name == "TargetGroupHealthCheck":
            return _JsonModel
        return super(FakeGwlbModels, self).__getattr__(name)


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


class FakeGwlbClient(object):
    """In-memory GwlbClient stand-in.

    Stores API-shaped target-group dicts. DescribeTargetGroups returns the
    whole store (optionally filtered by TargetGroupIds); write operations
    mutate the store so the module's post-write find refetch converges.
    """

    def __init__(self, groups=None):
        self.groups = [copy.deepcopy(g) for g in (groups or [])]
        self.calls = []
        self._next_id = 20000

    def _record(self, name, request):
        self.calls.append((name, request))
        return request

    def _new_id(self):
        self._next_id += 1
        return "gwlb-tg-%05d" % self._next_id

    @staticmethod
    def _as_dict(value):
        return dict(vars(value)) if value is not None else None

    def DescribeTargetGroups(self, request):
        self._record("DescribeTargetGroups", request)
        groups = self.groups
        ids = getattr(request, "TargetGroupIds", None)
        if ids:
            groups = [g for g in groups if g.get("TargetGroupId") in ids]
        return SimpleNamespace(
            TargetGroupSet=[FakeResource(dict(g)) for g in groups],
            TotalCount=len(groups),
            RequestId="req-fake",
        )

    def CreateTargetGroup(self, request):
        self._record("CreateTargetGroup", request)
        group_id = self._new_id()
        self.groups.append(
            {
                "TargetGroupId": group_id,
                "TargetGroupName": request.TargetGroupName,
                "VpcId": request.VpcId,
                "Port": request.Port,
                "Protocol": request.Protocol,
                "ScheduleAlgorithm": request.ScheduleAlgorithm,
                "ForwardingMode": getattr(request, "ForwardingMode", None),
                "HealthCheck": self._as_dict(request.HealthCheck),
                "AllDeadToAlive": bool(request.AllDeadToAlive),
            }
        )
        return SimpleNamespace(TargetGroupId=group_id, RequestId="req-fake")

    def ModifyTargetGroupAttribute(self, request):
        self._record("ModifyTargetGroupAttribute", request)
        for stored in self.groups:
            if stored.get("TargetGroupId") != request.TargetGroupId:
                continue
            stored["TargetGroupName"] = request.TargetGroupName
            stored["HealthCheck"] = self._as_dict(request.HealthCheck)
            stored["AllDeadToAlive"] = bool(request.AllDeadToAlive)
        return SimpleNamespace(RequestId="req-fake")

    def DeleteTargetGroups(self, request):
        self._record("DeleteTargetGroups", request)
        ids = list(request.TargetGroupIds or [])
        self.groups = [g for g in self.groups if g.get("TargetGroupId") not in ids]
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake):
    """Wire the shared monkeypatches and return the fake client."""
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(
        mod,
        "_load",
        lambda: (FakeGwlbModels(), SimpleNamespace(GwlbClient=object)),
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
# request-builder / model helper tests
# ---------------------------------------------------------------------------


def test_model_returns_none_for_none_value():
    assert mod._model(FakeGwlbModels().TargetGroupHealthCheck, None) is None


def test_model_round_trips_payload():
    item = mod._model(FakeGwlbModels().TargetGroupHealthCheck, {"HealthSwitch": True, "Port": 80})
    assert item.HealthSwitch is True
    assert item.Port == 80


def test_describe_request_base_fields():
    request = mod.describe_request(FakeGwlbModels(), _params(target_group_id=None, name="app"))
    assert request.Offset == 0
    assert request.Limit == 100
    assert not hasattr(request, "TargetGroupIds")


def test_describe_request_filters_by_id():
    request = mod.describe_request(FakeGwlbModels(), _params(target_group_id="gwlb-tg-9"))
    assert request.TargetGroupIds == ["gwlb-tg-9"]


def test_tags_builder_sorted():
    items = mod._tags(FakeGwlbModels(), {"z": "2", "a": "1"})
    assert [(x.TagKey, x.TagValue) for x in items] == [("a", "1"), ("z", "2")]


def test_tags_builder_empty_and_none():
    assert mod._tags(FakeGwlbModels(), None) == []
    assert mod._tags(FakeGwlbModels(), {}) == []


def test_create_request_fields():
    request = mod.create_request(FakeGwlbModels(), _params())
    assert request.TargetGroupName == "security-appliances"
    assert request.VpcId == "vpc-1"
    assert request.Port == 6081
    assert request.Protocol == "GENEVE"
    assert request.ScheduleAlgorithm == "WRR"  # defaulted when not given
    assert request.AllDeadToAlive is False
    assert request.HealthCheck is None
    assert request.Tags == []


def test_create_request_with_health_check():
    request = mod.create_request(FakeGwlbModels(), _params(health_check={"HealthSwitch": True, "Port": 80}))
    assert request.HealthCheck.HealthSwitch is True
    assert request.HealthCheck.Port == 80


def test_create_request_with_schedule_and_tags():
    request = mod.create_request(FakeGwlbModels(), _params(schedule_algorithm="IP_HASH", tags={"env": "prod"}))
    assert request.ScheduleAlgorithm == "IP_HASH"
    assert [(x.TagKey, x.TagValue) for x in request.Tags] == [("env", "prod")]


def test_update_request_fields():
    request = mod.update_request(FakeGwlbModels(), _params(name="renamed", health_check={"HealthSwitch": False}), "gwlb-tg-1")
    assert request.TargetGroupId == "gwlb-tg-1"
    assert request.TargetGroupName == "renamed"
    assert request.HealthCheck.HealthSwitch is False
    assert not hasattr(request, "VpcId")
    assert not hasattr(request, "Tags")


def test_delete_request_fields():
    request = mod.delete_request(FakeGwlbModels(), "gwlb-tg-1")
    assert request.TargetGroupIds == ["gwlb-tg-1"]


def test_comparable_normalises_all_dead_to_alive_bool():
    value = mod.comparable(_group(AllDeadToAlive=1))
    assert value["AllDeadToAlive"] is True
    assert value["TargetGroupName"] == "security-appliances"
    assert value["Port"] == 6081
    assert value["HealthCheck"]["Port"] == 80


# ---------------------------------------------------------------------------
# find tests
# ---------------------------------------------------------------------------


def test_find_no_match_returns_none(monkeypatch):
    fake = FakeGwlbClient([_group(TargetGroupName="other")])
    _make_module(monkeypatch, fake)
    module = FakeModule(_params(name="ghost"))
    assert mod.find(module, fake, FakeGwlbModels(), module.params) is None


def test_find_by_name(monkeypatch):
    fake = FakeGwlbClient([_group(TargetGroupName="other"), _group()])
    _make_module(monkeypatch, fake)
    module = FakeModule(_params(name="security-appliances"))
    value = mod.find(module, fake, FakeGwlbModels(), module.params)
    assert value["TargetGroupId"] == "gwlb-tg-1"


def test_find_by_target_group_id(monkeypatch):
    fake = FakeGwlbClient([_group(), _group(TargetGroupId="gwlb-tg-2", TargetGroupName="other")])
    _make_module(monkeypatch, fake)
    module = FakeModule(_params(target_group_id="gwlb-tg-2", name=None))
    value = mod.find(module, fake, FakeGwlbModels(), module.params)
    assert value["TargetGroupId"] == "gwlb-tg-2"


def test_find_multiple_matches_fails(monkeypatch):
    fake = FakeGwlbClient([_group(), _group(TargetGroupId="gwlb-tg-2")])
    _make_module(monkeypatch, fake)
    module = FakeModule(_params(name="security-appliances"))
    with pytest.raises(AnsibleFailJson) as exc:
        mod.find(module, fake, FakeGwlbModels(), module.params)
    assert "Multiple GWLB target groups matched" in exc.value.args[0]["msg"]


# ---------------------------------------------------------------------------
# run_module main-path tests
# ---------------------------------------------------------------------------


def test_required_one_of_enforced():
    module_args(state="present")  # neither target_group_id nor name
    with pytest.raises(AnsibleFailJson):
        run(mod.run_module)


def test_present_creates_target_group(monkeypatch):
    fake = FakeGwlbClient()
    _make_module(monkeypatch, fake)
    _run_args()
    result = run(mod.run_module)
    assert result["changed"] is True
    group = result["target_group"]
    assert group["TargetGroupId"] == "gwlb-tg-20001"
    assert group["TargetGroupName"] == "security-appliances"
    assert group["ScheduleAlgorithm"] == "WRR"
    names = [c[0] for c in fake.calls]
    assert names.count("DescribeTargetGroups") == 2  # find + refetch
    assert names.count("CreateTargetGroup") == 1
    create = [c for c in fake.calls if c[0] == "CreateTargetGroup"][0][1]
    assert create.VpcId == "vpc-1"
    assert create.Port == 6081


def test_present_requires_name_and_vpc_for_new(monkeypatch):
    fake = FakeGwlbClient()
    _make_module(monkeypatch, fake)
    _run_args(target_group_id="gwlb-tg-ghost", name=None, vpc_id=None)  # id given but absent
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "creation parameters are required for a new GWLB target group" in exc.value.args[0]["msg"]


def test_present_noop_returns_unchanged(monkeypatch):
    fake = FakeGwlbClient([_group()])
    _make_module(monkeypatch, fake)
    _run_args()
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["target_group"]["TargetGroupId"] == "gwlb-tg-1"
    names = [c[0] for c in fake.calls]
    assert "ModifyTargetGroupAttribute" not in names
    assert "CreateTargetGroup" not in names


def test_present_rename_by_id_triggers_update(monkeypatch):
    fake = FakeGwlbClient([_group(TargetGroupName="old-name")])
    _make_module(monkeypatch, fake)
    _run_args(target_group_id="gwlb-tg-1", name="renamed-appliances")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["target_group"]["TargetGroupName"] == "renamed-appliances"
    assert len(fake.groups) == 1  # renamed in place
    modify = [c for c in fake.calls if c[0] == "ModifyTargetGroupAttribute"][0][1]
    assert modify.TargetGroupId == "gwlb-tg-1"
    assert modify.TargetGroupName == "renamed-appliances"


def test_present_health_check_drift_triggers_update(monkeypatch):
    fake = FakeGwlbClient([_group()])
    _make_module(monkeypatch, fake)
    _run_args(health_check={"HealthSwitch": False, "Protocol": "TCP", "Port": 8080})
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["target_group"]["HealthCheck"]["Port"] == 8080
    modify = [c for c in fake.calls if c[0] == "ModifyTargetGroupAttribute"][0][1]
    assert modify.HealthCheck.Port == 8080


def test_present_all_dead_to_alive_drift_triggers_update(monkeypatch):
    fake = FakeGwlbClient([_group()])
    _make_module(monkeypatch, fake)
    _run_args(all_dead_to_alive=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["target_group"]["AllDeadToAlive"] is True
    modify = [c for c in fake.calls if c[0] == "ModifyTargetGroupAttribute"][0][1]
    assert modify.AllDeadToAlive is True


def test_present_immutable_vpc_drift_fails(monkeypatch):
    fake = FakeGwlbClient([_group()])
    _make_module(monkeypatch, fake)
    _run_args(vpc_id="vpc-other")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "Immutable fields cannot be changed" in payload["msg"]
    assert payload["replacement_required"] is True
    assert payload["immutable_changes"]["VpcId"]["before"] == "vpc-1"
    assert payload["immutable_changes"]["VpcId"]["after"] == "vpc-other"
    assert not any("ModifyTargetGroupAttribute" == c[0] for c in fake.calls)


def test_present_immutable_port_drift_fails(monkeypatch):
    fake = FakeGwlbClient([_group()])
    _make_module(monkeypatch, fake)
    _run_args(port=8080)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "Immutable fields cannot be changed" in payload["msg"]
    assert payload["immutable_changes"]["Port"]["before"] == 6081


def test_present_protocol_single_choice_is_noop(monkeypatch):
    # GENEVE is the only allowed protocol, so no drift can ever be expressed.
    fake = FakeGwlbClient([_group(Protocol="GENEVE")])
    _make_module(monkeypatch, fake)
    _run_args(protocol="GENEVE", port=6081)
    result = run(mod.run_module)
    assert result["changed"] is False


def test_present_immutable_schedule_algorithm_drift_fails(monkeypatch):
    fake = FakeGwlbClient([_group()])
    _make_module(monkeypatch, fake)
    _run_args(schedule_algorithm="IP_HASH")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "Immutable fields cannot be changed" in payload["msg"]
    assert payload["immutable_changes"]["ScheduleAlgorithm"]["before"] == "WRR"


def test_present_immutable_forwarding_mode_drift_fails(monkeypatch):
    fake = FakeGwlbClient([_group()])
    _make_module(monkeypatch, fake)
    _run_args(forwarding_mode="L4")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "Immutable fields cannot be changed" in payload["msg"]
    assert payload["immutable_changes"]["ForwardingMode"]["before"] == "L3"


def test_sdk_error_is_reported(monkeypatch):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(
        mod,
        "_load",
        lambda: (FakeGwlbModels(), SimpleNamespace(GwlbClient=object)),
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
    fake = FakeGwlbClient()
    _make_module(monkeypatch, fake)
    module_args(_ansible_check_mode=True, **{k: v for k, v in _params().items() if v is not None})
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["target_group"]["TargetGroupName"] == "security-appliances"  # desired reported
    assert not any("CreateTargetGroup" == c[0] for c in fake.calls)


def test_check_mode_update_is_dry_run(monkeypatch):
    fake = FakeGwlbClient([_group()])
    _make_module(monkeypatch, fake)
    module_args(
        _ansible_check_mode=True,
        **{k: v for k, v in _params(target_group_id="gwlb-tg-1", name="renamed").items() if v is not None},
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["target_group"]["TargetGroupName"] == "security-appliances"  # pre-change state
    assert not any("ModifyTargetGroupAttribute" == c[0] for c in fake.calls)


def test_absent_removes_target_group(monkeypatch):
    fake = FakeGwlbClient([_group()])
    _make_module(monkeypatch, fake)
    _run_args(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["target_group"] is None
    delete = [c for c in fake.calls if c[0] == "DeleteTargetGroups"][0][1]
    assert delete.TargetGroupIds == ["gwlb-tg-1"]
    assert fake.groups == []


def test_absent_not_found_is_noop(monkeypatch):
    fake = FakeGwlbClient([_group()])
    _make_module(monkeypatch, fake)
    _run_args(state="absent", name="ghost")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["target_group"] is None
    assert not any("DeleteTargetGroups" == c[0] for c in fake.calls)


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeGwlbClient([_group()])
    _make_module(monkeypatch, fake)
    module_args(_ansible_check_mode=True, **{k: v for k, v in _params(state="absent").items() if v is not None})
    result = run(mod.run_module)
    assert result["changed"] is True
    assert not any("DeleteTargetGroups" == c[0] for c in fake.calls)
    assert len(fake.groups) == 1
