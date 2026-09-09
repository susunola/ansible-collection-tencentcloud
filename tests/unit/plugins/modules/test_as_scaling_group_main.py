"""Unit tests for the as_scaling_group write module (run_module flows).

Drives ``run_module()`` end to end against an in-memory fake Auto Scaling
client whose write operations mutate the scaling-group store, so the
post-write ``DescribeAutoScalingGroups`` refetch and the ``wait_for_group``
waiter converge on the first poll.

Scenario matrix:

* absent on a missing group (idempotent no-op)
* absent with a matching group (check-mode dry run and the real delete)
* creation when missing (missing required_if parameters, capacity-ordering
  guard, check-mode dry run and the happy path)
* no-op when nothing drifts
* size drift updates (through ModifyAutoScalingGroup) and its check mode
* the capacity range guard (max_size > 2000)
* the invalid-choice guard
* the required_one_of (id vs name) guard
* the ambiguous-name guard
* the blanket ``Tencent Cloud API request failed`` failure path
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import as_scaling_group as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

GROUP_ID = "asg-test1"

# Field values mirror the module defaults so a bare present reference is a
# no-op (idempotence can be asserted without spelling out every option).
GROUP = {
    "AutoScalingGroupId": GROUP_ID,
    "AutoScalingGroupName": "web-fleet",
    "LaunchConfigurationId": "asc-abc",
    "VpcId": "vpc-abc",
    "SubnetIdSet": ["subnet-aaa", "subnet-bbb"],
    "MinSize": 0,
    "MaxSize": 0,
    "DesiredCapacity": 0,
    "DefaultCooldown": 300,
    "TerminationPolicySet": ["OLDEST_INSTANCE"],
    "RetryPolicy": "IMMEDIATE_RETRY",
    "MultiZoneSubnetPolicy": "PRIORITY",
    "HealthCheckType": "CVM",
    "CapacityRebalance": False,
    "ProjectId": 0,
    "AutoScalingGroupStatus": "NORMAL",
}


def _group(**overrides):
    item = copy.deepcopy(GROUP)
    item.update(overrides)
    return item


def _base(**overrides):
    # NOTE: keys carrying ``choices`` (state, termination_policy,
    # retry_policy, subnet_policy, health_check_type) must not be pre-filled
    # with None. scaling_group_id/name are a required_one_of pair so the
    # _name_args/_id_args helpers supply exactly one of them.
    params = {}
    params.update(overrides)
    return module_args(**params)


def _name_args(**overrides):
    params = {"name": "web-fleet"}
    params.update(overrides)
    return module_args(**params)


def _id_args(**overrides):
    params = {"scaling_group_id": GROUP_ID}
    params.update(overrides)
    return module_args(**params)


_PRESENT_REQUIRED = {
    "name": "web-fleet",
    "launch_configuration_id": "asc-abc",
    "vpc_id": "vpc-abc",
    "subnet_ids": ["subnet-aaa", "subnet-bbb"],
}


class FakeAsClient(object):
    """In-memory Auto Scaling client mutating a small scaling-group store."""

    def __init__(self, groups=None):
        self.groups = [copy.deepcopy(t) for t in (groups or [])]
        self.calls = []

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def DescribeAutoScalingGroups(self, request):
        self._record("DescribeAutoScalingGroups", request)
        ids = list(getattr(request, "AutoScalingGroupIds", None) or [])
        if ids:
            wanted = [str(i) for i in ids]
            page = [dict(t) for t in self.groups if str(t.get("AutoScalingGroupId")) in wanted]
        else:
            wanted = None
            for item in (getattr(request, "Filters", None) or []):
                if getattr(item, "Name", None) == "auto-scaling-group-name":
                    values = list(getattr(item, "Values", None) or [])
                    wanted = values[0] if values else None
            if wanted is not None:
                page = [dict(t) for t in self.groups if t.get("AutoScalingGroupName") == wanted]
            else:
                page = [dict(t) for t in self.groups]
        return SimpleNamespace(
            AutoScalingGroupSet=[FakeResource(t) for t in page],
            TotalCount=len(page),
        )

    def CreateAutoScalingGroup(self, request):
        self._record("CreateAutoScalingGroup", request)
        group_id = "asg-new-%d" % (len(self.groups) + 1)
        item = {
            "AutoScalingGroupId": group_id,
            "AutoScalingGroupName": getattr(request, "AutoScalingGroupName", None),
            "LaunchConfigurationId": getattr(request, "LaunchConfigurationId", None),
            "VpcId": getattr(request, "VpcId", None),
            "SubnetIdSet": list(getattr(request, "SubnetIds", None) or []),
            "MinSize": getattr(request, "MinSize", 0),
            "MaxSize": getattr(request, "MaxSize", 0),
            "DesiredCapacity": getattr(request, "DesiredCapacity", 0),
            "DefaultCooldown": getattr(request, "DefaultCooldown", 300),
            "TerminationPolicySet": list(getattr(request, "TerminationPolicies", None) or []),
            "RetryPolicy": getattr(request, "RetryPolicy", None),
            "MultiZoneSubnetPolicy": getattr(request, "MultiZoneSubnetPolicy", None),
            "HealthCheckType": getattr(request, "HealthCheckType", None),
            "CapacityRebalance": bool(getattr(request, "CapacityRebalance", False)),
            "ProjectId": getattr(request, "ProjectId", 0),
            "AutoScalingGroupStatus": "NORMAL",
        }
        self.groups.append(item)
        return SimpleNamespace(AutoScalingGroupId=group_id, RequestId="req-fake")

    def ModifyAutoScalingGroup(self, request):
        self._record("ModifyAutoScalingGroup", request)
        for item in self.groups:
            if item.get("AutoScalingGroupId") == getattr(request, "AutoScalingGroupId", None):
                item.update(
                    {
                        "AutoScalingGroupName": getattr(request, "AutoScalingGroupName", item.get("AutoScalingGroupName")),
                        "LaunchConfigurationId": getattr(request, "LaunchConfigurationId", item.get("LaunchConfigurationId")),
                        "VpcId": getattr(request, "VpcId", item.get("VpcId")),
                        "SubnetIdSet": list(getattr(request, "SubnetIds", item.get("SubnetIdSet")) or []),
                        "MinSize": getattr(request, "MinSize", item.get("MinSize")),
                        "MaxSize": getattr(request, "MaxSize", item.get("MaxSize")),
                        "DesiredCapacity": getattr(request, "DesiredCapacity", item.get("DesiredCapacity")),
                        "DefaultCooldown": getattr(request, "DefaultCooldown", item.get("DefaultCooldown")),
                        "TerminationPolicySet": list(getattr(request, "TerminationPolicies", item.get("TerminationPolicySet")) or []),
                        "RetryPolicy": getattr(request, "RetryPolicy", item.get("RetryPolicy")),
                        "MultiZoneSubnetPolicy": getattr(request, "MultiZoneSubnetPolicy", item.get("MultiZoneSubnetPolicy")),
                        "HealthCheckType": getattr(request, "HealthCheckType", item.get("HealthCheckType")),
                        "CapacityRebalance": bool(getattr(request, "CapacityRebalance", item.get("CapacityRebalance"))),
                        "ProjectId": getattr(request, "ProjectId", item.get("ProjectId")),
                    }
                )
        return SimpleNamespace(RequestId="req-fake")

    def DeleteAutoScalingGroup(self, request):
        self._record("DeleteAutoScalingGroup", request)
        self.groups = [t for t in self.groups if t.get("AutoScalingGroupId") != getattr(request, "AutoScalingGroupId", None)]
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake, models=None):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load_autoscaling", lambda: (models or FakeModels(), SimpleNamespace(AutoscalingClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


# ---------------------------------------------------------------------------
# absent flows
# ---------------------------------------------------------------------------


def test_absent_missing_group_is_idempotent(monkeypatch):
    fake = FakeAsClient(groups=[])
    _make_module(monkeypatch, fake)
    _name_args(state="absent", name="ghost-fleet")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["scaling_group"] is None
    assert result["msg"] == "Auto Scaling group is absent"
    assert [c for c, unused in fake.calls] == ["DescribeAutoScalingGroups"]


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeAsClient(groups=[_group()])
    _make_module(monkeypatch, fake)
    _id_args(_ansible_check_mode=True, state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["msg"] == "Would delete Auto Scaling group"
    assert result["scaling_group"]["AutoScalingGroupId"] == GROUP_ID
    assert len(fake.groups) == 1
    assert "DeleteAutoScalingGroup" not in [c for c, unused in fake.calls]


def test_absent_deletes_group(monkeypatch):
    fake = FakeAsClient(groups=[_group()])
    _make_module(monkeypatch, fake)
    _id_args(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["msg"] == "Auto Scaling group deleted"
    assert result["scaling_group"] is None
    assert fake.groups == []
    assert "DeleteAutoScalingGroup" in [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# creation flows
# ---------------------------------------------------------------------------


def test_create_requires_creation_parameters(monkeypatch):
    fake = FakeAsClient(groups=[])
    _make_module(monkeypatch, fake)
    _name_args(state="present", name="web-fleet")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "missing" in payload["msg"]
    for field in ("launch_configuration_id", "vpc_id", "subnet_ids"):
        assert field in payload["msg"]


def test_create_rejects_invalid_capacity_order(monkeypatch):
    fake = FakeAsClient(groups=[])
    _make_module(monkeypatch, fake)
    _name_args(
        state="present",
        min_size=3,
        desired_capacity=2,
        max_size=5,
        **_PRESENT_REQUIRED,
    )
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "0 <= min_size <= desired_capacity <= max_size <= 2000" in payload["msg"]


def test_create_check_mode_is_dry_run(monkeypatch):
    fake = FakeAsClient(groups=[])
    _make_module(monkeypatch, fake)
    _name_args(_ansible_check_mode=True, state="present", max_size=5, **_PRESENT_REQUIRED)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["msg"] == "Would create Auto Scaling group"
    assert result["scaling_group"] is None
    assert fake.groups == []
    assert "CreateAutoScalingGroup" not in [c for c, unused in fake.calls]


def test_create_group(monkeypatch):
    fake = FakeAsClient(groups=[])
    _make_module(monkeypatch, fake)
    _name_args(
        state="present",
        min_size=0,
        desired_capacity=0,
        max_size=5,
        default_cooldown=120,
        termination_policy="NEWEST_INSTANCE",
        retry_policy="INCREMENTAL_INTERVALS",
        subnet_policy="EQUALITY",
        health_check_type="CLB",
        capacity_rebalance=True,
        project_id=1001,
        **_PRESENT_REQUIRED,
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["msg"] == "Auto Scaling group created"
    group = result["scaling_group"]
    assert group["AutoScalingGroupName"] == "web-fleet"
    assert group["MaxSize"] == 5
    assert group["DefaultCooldown"] == 120
    assert group["TerminationPolicySet"] == ["NEWEST_INSTANCE"]
    assert group["MultiZoneSubnetPolicy"] == "EQUALITY"
    assert group["HealthCheckType"] == "CLB"
    assert group["CapacityRebalance"] is True
    assert group["ProjectId"] == 1001
    assert len(fake.groups) == 1
    ops = [c for c, unused in fake.calls]
    assert ops[0] == "DescribeAutoScalingGroups"
    assert "CreateAutoScalingGroup" in ops


# ---------------------------------------------------------------------------
# existing-group flows
# ---------------------------------------------------------------------------


def test_existing_group_no_drift_is_idempotent(monkeypatch):
    fake = FakeAsClient(groups=[_group()])
    _make_module(monkeypatch, fake)
    _name_args(state="present", **_PRESENT_REQUIRED)
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["msg"] == "Auto Scaling group is up to date"
    assert result["scaling_group"]["AutoScalingGroupId"] == GROUP_ID
    assert "ModifyAutoScalingGroup" not in [c for c, unused in fake.calls]


def test_update_group_size_drift(monkeypatch):
    fake = FakeAsClient(groups=[_group()])
    _make_module(monkeypatch, fake)
    _id_args(state="present", max_size=8, min_size=1, desired_capacity=2, **_PRESENT_REQUIRED)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["msg"] == "Auto Scaling group updated"
    assert result["scaling_group"]["MinSize"] == 1
    assert result["scaling_group"]["DesiredCapacity"] == 2
    assert result["scaling_group"]["MaxSize"] == 8
    assert fake.groups[0]["MaxSize"] == 8
    assert "ModifyAutoScalingGroup" in [c for c, unused in fake.calls]


def test_update_check_mode_is_dry_run(monkeypatch):
    fake = FakeAsClient(groups=[_group()])
    _make_module(monkeypatch, fake)
    _id_args(_ansible_check_mode=True, state="present", max_size=10, **_PRESENT_REQUIRED)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["msg"] == "Would update Auto Scaling group"
    assert fake.groups[0]["MaxSize"] == 0
    assert "ModifyAutoScalingGroup" not in [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# guards / validation / failure paths
# ---------------------------------------------------------------------------


def test_create_rejects_capacity_over_limit(monkeypatch):
    fake = FakeAsClient(groups=[])
    _make_module(monkeypatch, fake)
    _name_args(state="present", max_size=2001, **_PRESENT_REQUIRED)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "0 <= min_size <= desired_capacity <= max_size <= 2000" in exc.value.args[0]["msg"]


def test_missing_identity_fails(monkeypatch):
    fake = FakeAsClient(groups=[])
    _make_module(monkeypatch, fake)
    _base(state="absent")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "scaling_group_id" in exc.value.args[0]["msg"]
    assert "name" in exc.value.args[0]["msg"]


def test_invalid_choice_fails(monkeypatch):
    fake = FakeAsClient(groups=[])
    _make_module(monkeypatch, fake)
    _name_args(state="present", termination_policy="BANANAS", **_PRESENT_REQUIRED)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "value of termination_policy must be one of" in exc.value.args[0]["msg"]


def test_multiple_groups_with_same_name_fail(monkeypatch):
    fake = FakeAsClient(groups=[_group(), _group(AutoScalingGroupId="asg-dup")])
    _make_module(monkeypatch, fake)
    _name_args(state="present", **_PRESENT_REQUIRED)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "Multiple Auto Scaling groups have the requested name" in payload["msg"]
    assert payload["name"] == "web-fleet"


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeAutoScalingGroups(self, request):
            raise Boom("connection dropped")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    _id_args(state="present", **_PRESENT_REQUIRED)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]


# ---------------------------------------------------------------------------
# legacy helper regression tests (folded from test_as_scaling_group.py)
# ---------------------------------------------------------------------------

_PARAMS = {
    "name": "web",
    "launch_configuration_id": "asc-x",
    "vpc_id": "vpc-x",
    "subnet_ids": ["subnet-a", "subnet-b"],
    "min_size": 0,
    "max_size": 10,
    "desired_capacity": 0,
    "default_cooldown": 300,
    "termination_policy": "OLDEST_INSTANCE",
    "retry_policy": "IMMEDIATE_RETRY",
    "subnet_policy": "PRIORITY",
    "health_check_type": "CVM",
    "capacity_rebalance": False,
    "project_id": 0,
}


def test_request_builders():
    models = FakeModels()
    create = mod.build_create_request(models, _PARAMS)
    assert create.DesiredCapacity == 0
    assert create.SubnetIds == ["subnet-a", "subnet-b"]
    update = mod.build_update_request(models, "asg-x", _PARAMS)
    assert update.AutoScalingGroupId == "asg-x"
    assert mod.build_delete_request(models, "asg-x").AutoScalingGroupId == "asg-x"


def test_exact_idempotency():
    desired = mod._desired(_PARAMS)
    assert mod._matches(dict(desired), desired)
    changed = dict(desired)
    changed["DesiredCapacity"] = 1
    assert not mod._matches(changed, desired)
