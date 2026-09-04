"""Unit tests for the as_scaling_policy write module (helpers + run_module).

Creates, updates and deletes Auto Scaling simple or target-tracking
scaling policies within a scaling group. Lookup lists the group's
policies and filters by ``policy_id`` (the API id-filter) or by
``name``; duplicate names within a group fail. ``ScalingPolicyType``
is immutable after creation (require_immutable_unchanged). The same
``name`` parameter drives lookup and the desired name, so renames are
only possible when addressing the policy by ``policy_id``.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import as_scaling_policy as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)


def _policy(**overrides):
    """API-shaped scaling-policy dict; fresh copy per call."""
    item = {
        "AutoScalingPolicyId": "asp-1",
        "AutoScalingGroupId": "asg-1",
        "ScalingPolicyName": "scale-out",
        "ScalingPolicyType": "SIMPLE",
        "AdjustmentType": "CHANGE_IN_CAPACITY",
        "AdjustmentValue": 1,
        "Cooldown": 300,
    }
    item.update(overrides)
    return item


def _tracking_policy(**overrides):
    item = _policy(AutoScalingPolicyId="asp-tt", ScalingPolicyType="TARGET_TRACKING")
    item.update(
        PredefinedMetricType="ASG_AVG_CPU_UTILIZATION",
        TargetValue=60,
        EstimatedInstanceWarmup=300,
        DisableScaleIn=False,
    )
    item.update(overrides)
    return item


def _params(**overrides):
    """Module parameters pre-filled from the argument spec defaults."""
    params = {
        "state": "present",
        "scaling_group_id": "asg-1",
        "policy_id": None,
        "name": None,
        "policy_type": "SIMPLE",
        "adjustment_type": "CHANGE_IN_CAPACITY",
        "adjustment_value": 1,
        "cooldown": 300,
        "predefined_metric_type": None,
        "target_value": None,
        "estimated_instance_warmup": 300,
        "disable_scale_in": False,
    }
    params.update(overrides)
    return params


def _run_args(**extra):
    """module_args() pre-filled with every non-None module parameter."""
    return module_args(**{k: v for k, v in _params(**extra).items() if v is not None})


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


class FakeAsClient(object):
    """In-memory AutoscalingClient stand-in storing policy dicts.

    DescribeScalingPolicies filters by ``AutoScalingPolicyIds`` when
    present (the module trusts the API id-filter and keeps every returned
    item) or by the ``auto-scaling-group-id`` filter otherwise; the module
    applies the name match itself. Create/Modify read the fields the
    module's ``apply`` helper set on the request models.
    """

    def __init__(self, policies=None):
        self.policies = [dict(p) for p in (policies or [])]
        self.calls = []
        self._next_id = 100

    def _record(self, name, request):
        self.calls.append((name, request))
        return request

    def _filtered(self, request):
        if getattr(request, "AutoScalingPolicyIds", None):
            ids = request.AutoScalingPolicyIds
            return [p for p in self.policies if p.get("AutoScalingPolicyId") in ids]
        group_ids = []
        for item in getattr(request, "Filters", []) or []:
            if item.Name == "auto-scaling-group-id":
                group_ids = item.Values or []
        return [p for p in self.policies if not group_ids or p.get("AutoScalingGroupId") in group_ids]

    def DescribeScalingPolicies(self, request):
        self._record("DescribeScalingPolicies", request)
        return SimpleNamespace(
            ScalingPolicySet=[FakeResource(dict(p)) for p in self._filtered(request)],
            RequestId="req-fake",
        )

    def CreateScalingPolicy(self, request):
        self._record("CreateScalingPolicy", request)
        policy_id = "asp-new%d" % self._next_id
        self._next_id += 1
        stored = {
            "AutoScalingPolicyId": policy_id,
            "AutoScalingGroupId": request.AutoScalingGroupId,
            "ScalingPolicyName": request.ScalingPolicyName,
            "ScalingPolicyType": request.ScalingPolicyType,
            "AdjustmentType": request.AdjustmentType,
            "AdjustmentValue": request.AdjustmentValue,
            "Cooldown": request.Cooldown,
        }
        if request.ScalingPolicyType == "TARGET_TRACKING":
            stored.update(
                PredefinedMetricType=request.PredefinedMetricType,
                TargetValue=request.TargetValue,
                EstimatedInstanceWarmup=request.EstimatedInstanceWarmup,
                DisableScaleIn=request.DisableScaleIn,
            )
        self.policies.append(stored)
        return SimpleNamespace(AutoScalingPolicyId=policy_id, RequestId="req-fake")

    def ModifyScalingPolicy(self, request):
        self._record("ModifyScalingPolicy", request)
        for stored in self.policies:
            if stored.get("AutoScalingPolicyId") == request.AutoScalingPolicyId:
                stored["ScalingPolicyName"] = request.ScalingPolicyName
                stored["AdjustmentType"] = request.AdjustmentType
                stored["AdjustmentValue"] = request.AdjustmentValue
                stored["Cooldown"] = request.Cooldown
                if getattr(request, "PredefinedMetricType", None) is not None:
                    stored["PredefinedMetricType"] = request.PredefinedMetricType
                    stored["TargetValue"] = request.TargetValue
                    stored["EstimatedInstanceWarmup"] = request.EstimatedInstanceWarmup
                    stored["DisableScaleIn"] = request.DisableScaleIn
        return SimpleNamespace(RequestId="req-fake")

    def DeleteScalingPolicy(self, request):
        self._record("DeleteScalingPolicy", request)
        self.policies = [p for p in self.policies if p.get("AutoScalingPolicyId") != request.AutoScalingPolicyId]
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake):
    """Wire the shared monkeypatches and return the fake client."""
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(
        mod,
        "_load",
        lambda: (FakeModels(), SimpleNamespace(AutoscalingClient=object)),
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
# wanted / apply helper tests
# ---------------------------------------------------------------------------


def test_wanted_simple_excludes_tracking_fields():
    value = mod.wanted(_params(name="scale-out"))
    assert value == {
        "ScalingPolicyName": "scale-out",
        "ScalingPolicyType": "SIMPLE",
        "AdjustmentType": "CHANGE_IN_CAPACITY",
        "AdjustmentValue": 1,
        "Cooldown": 300,
    }
    assert "PredefinedMetricType" not in value


def test_wanted_tracking_adds_metric_fields():
    value = mod.wanted(_params(name="track-cpu", policy_type="TARGET_TRACKING", predefined_metric_type="ASG_AVG_CPU_UTILIZATION", target_value=60))
    assert value["PredefinedMetricType"] == "ASG_AVG_CPU_UTILIZATION"
    assert value["TargetValue"] == 60
    assert value["EstimatedInstanceWarmup"] == 300
    assert value["DisableScaleIn"] is False


def test_apply_create_sets_group_and_type():
    request = mod.apply(FakeModels().CreateScalingPolicyRequest(), _params(name="scale-out"))
    assert request.AutoScalingGroupId == "asg-1"
    assert request.ScalingPolicyType == "SIMPLE"
    assert request.ScalingPolicyName == "scale-out"
    assert request.AdjustmentValue == 1
    assert request.Cooldown == 300
    assert not hasattr(request, "AutoScalingPolicyId")


def test_apply_modify_sets_only_policy_id():
    request = mod.apply(FakeModels().ModifyScalingPolicyRequest(), _params(name="renamed", adjustment_value=2), "asp-9")
    assert request.AutoScalingPolicyId == "asp-9"
    assert request.ScalingPolicyName == "renamed"
    assert request.AdjustmentValue == 2
    assert not hasattr(request, "AutoScalingGroupId")
    assert not hasattr(request, "ScalingPolicyType")


def test_apply_tracking_adds_metric_fields():
    params = _params(policy_type="TARGET_TRACKING", predefined_metric_type="ASG_AVG_CPU_UTILIZATION", target_value=60, disable_scale_in=True)
    request = mod.apply(FakeModels().CreateScalingPolicyRequest(), params)
    assert request.PredefinedMetricType == "ASG_AVG_CPU_UTILIZATION"
    assert request.TargetValue == 60
    assert request.EstimatedInstanceWarmup == 300
    assert request.DisableScaleIn is True


# ---------------------------------------------------------------------------
# find tests
# ---------------------------------------------------------------------------


def test_find_matches_by_policy_id(monkeypatch):
    fake = FakeAsClient([_policy(), _policy(AutoScalingPolicyId="asp-2", ScalingPolicyName="other")])
    _make_module(monkeypatch, fake)
    module = FakeModule(_params(policy_id="asp-2"))
    value = mod.find(module, fake, FakeModels(), module.params)
    assert value["AutoScalingPolicyId"] == "asp-2"
    assert value["ScalingPolicyName"] == "other"


def test_find_matches_by_name_within_group(monkeypatch):
    fake = FakeAsClient([_policy(), _policy(AutoScalingPolicyId="asp-2", AutoScalingGroupId="asg-other", ScalingPolicyName="scale-out")])
    _make_module(monkeypatch, fake)
    module = FakeModule(_params(name="scale-out"))
    value = mod.find(module, fake, FakeModels(), module.params)
    assert value["AutoScalingPolicyId"] == "asp-1"  # other group filtered out by API


def test_find_no_match_returns_none(monkeypatch):
    fake = FakeAsClient([_policy()])
    _make_module(monkeypatch, fake)
    module = FakeModule(_params(name="ghost"))
    assert mod.find(module, fake, FakeModels(), module.params) is None


def test_find_multiple_name_matches_fails(monkeypatch):
    fake = FakeAsClient([_policy(), _policy(AutoScalingPolicyId="asp-2")])
    _make_module(monkeypatch, fake)
    module = FakeModule(_params(name="scale-out"))
    with pytest.raises(AnsibleFailJson) as exc:
        mod.find(module, fake, FakeModels(), module.params)
    payload = exc.value.args[0]
    assert "Multiple scaling policies have the requested name" in payload["msg"]
    assert payload["name"] == "scale-out"


# ---------------------------------------------------------------------------
# run_module main-path tests
# ---------------------------------------------------------------------------


def test_requires_policy_id_or_name():
    module_args(scaling_group_id="asg-1")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    msg = exc.value.args[0]["msg"]
    assert "policy_id" in msg and "name" in msg


def test_name_required_when_present():
    module_args(scaling_group_id="asg-1", policy_id="asp-1")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "name is required when state=present" in exc.value.args[0]["msg"]


def test_tracking_requires_metric_and_target():
    module_args(scaling_group_id="asg-1", name="x", policy_type="TARGET_TRACKING")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "predefined_metric_type and target_value are required for TARGET_TRACKING" in exc.value.args[0]["msg"]


def test_present_creates_simple_policy(monkeypatch):
    fake = FakeAsClient()
    _make_module(monkeypatch, fake)
    _run_args(name="add-two", adjustment_value=2)
    result = run(mod.run_module)
    assert result["changed"] is True
    policy = result["scaling_policy"]
    assert policy["AutoScalingPolicyId"] == "asp-new100"
    assert policy["ScalingPolicyName"] == "add-two"
    assert policy["AdjustmentValue"] == 2
    assert policy["ScalingPolicyType"] == "SIMPLE"
    assert [c[0] for c in fake.calls].count("DescribeScalingPolicies") == 2  # find + refetch
    create = [c for c in fake.calls if c[0] == "CreateScalingPolicy"][0][1]
    assert create.AutoScalingGroupId == "asg-1"
    assert create.Cooldown == 300


def test_present_creates_tracking_policy(monkeypatch):
    fake = FakeAsClient()
    _make_module(monkeypatch, fake)
    _run_args(
        name="track-cpu",
        policy_type="TARGET_TRACKING",
        predefined_metric_type="ASG_AVG_CPU_UTILIZATION",
        target_value=60,
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    policy = result["scaling_policy"]
    assert policy["ScalingPolicyType"] == "TARGET_TRACKING"
    assert policy["PredefinedMetricType"] == "ASG_AVG_CPU_UTILIZATION"
    assert policy["TargetValue"] == 60
    create = [c for c in fake.calls if c[0] == "CreateScalingPolicy"][0][1]
    assert create.DisableScaleIn is False


def test_present_check_mode_create_is_dry_run(monkeypatch):
    fake = FakeAsClient()
    _make_module(monkeypatch, fake)
    module_args(
        _ansible_check_mode=True,
        **{k: v for k, v in _params(name="add-two", adjustment_value=2).items() if v is not None}
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["scaling_policy"] is None  # nothing was created to report
    assert not any(c[0] == "CreateScalingPolicy" for c in fake.calls)
    assert fake.policies == []


def test_present_noop_returns_unchanged(monkeypatch):
    fake = FakeAsClient([_policy()])
    _make_module(monkeypatch, fake)
    _run_args(name="scale-out")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["scaling_policy"]["AutoScalingPolicyId"] == "asp-1"
    assert not any(c[0] in ("CreateScalingPolicy", "ModifyScalingPolicy") for c in fake.calls)


def test_present_adjustment_drift_triggers_update(monkeypatch):
    fake = FakeAsClient([_policy()])
    _make_module(monkeypatch, fake)
    _run_args(name="scale-out", adjustment_value=2)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["scaling_policy"]["AdjustmentValue"] == 2
    update = [c for c in fake.calls if c[0] == "ModifyScalingPolicy"][0][1]
    assert update.AutoScalingPolicyId == "asp-1"
    assert update.AdjustmentValue == 2
    assert update.ScalingPolicyName == "scale-out"
    assert not hasattr(update, "AutoScalingGroupId")


def test_present_tracking_metric_drift_triggers_update(monkeypatch):
    fake = FakeAsClient([_tracking_policy()])
    _make_module(monkeypatch, fake)
    _run_args(
        policy_id="asp-tt",
        name="track-cpu",
        policy_type="TARGET_TRACKING",
        predefined_metric_type="ASG_AVG_CPU_UTILIZATION",
        target_value=80,
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["scaling_policy"]["TargetValue"] == 80
    update = [c for c in fake.calls if c[0] == "ModifyScalingPolicy"][0][1]
    assert update.TargetValue == 80


def test_present_type_immutable_fails(monkeypatch):
    fake = FakeAsClient([_policy()])
    _make_module(monkeypatch, fake)
    _run_args(
        policy_id="asp-1",
        name="scale-out",
        policy_type="TARGET_TRACKING",
        predefined_metric_type="ASG_AVG_CPU_UTILIZATION",
        target_value=60,
    )
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "Immutable fields cannot be changed" in payload["msg"]
    assert payload["replacement_required"] is True
    assert payload["immutable_changes"] == {"ScalingPolicyType": {"before": "SIMPLE", "after": "TARGET_TRACKING"}}
    assert not any(c[0] == "ModifyScalingPolicy" for c in fake.calls)


def test_check_mode_update_is_dry_run(monkeypatch):
    fake = FakeAsClient([_policy()])
    _make_module(monkeypatch, fake)
    module_args(
        _ansible_check_mode=True,
        **{k: v for k, v in _params(policy_id="asp-1", name="scale-out", adjustment_value=2).items() if v is not None}
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["scaling_policy"]["AdjustmentValue"] == 1  # pre-change reported
    assert not any(c[0] == "ModifyScalingPolicy" for c in fake.calls)


def test_absent_not_found_is_noop(monkeypatch):
    fake = FakeAsClient([_policy()])
    _make_module(monkeypatch, fake)
    _run_args(state="absent", policy_id="ghost")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["scaling_policy"] is None
    assert not any(c[0] == "DeleteScalingPolicy" for c in fake.calls)


def test_absent_deletes_policy(monkeypatch):
    fake = FakeAsClient([_policy(), _policy(AutoScalingPolicyId="asp-2", ScalingPolicyName="other")])
    _make_module(monkeypatch, fake)
    _run_args(state="absent", policy_id="asp-1")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["scaling_policy"] is None
    delete = [c for c in fake.calls if c[0] == "DeleteScalingPolicy"][0][1]
    assert delete.AutoScalingPolicyId == "asp-1"
    assert [p["AutoScalingPolicyId"] for p in fake.policies] == ["asp-2"]


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeAsClient([_policy()])
    _make_module(monkeypatch, fake)
    module_args(
        _ansible_check_mode=True,
        **{k: v for k, v in _params(state="absent", policy_id="asp-1").items() if v is not None}
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["scaling_policy"]["AutoScalingPolicyId"] == "asp-1"  # pre-delete reported
    assert not any(c[0] == "DeleteScalingPolicy" for c in fake.calls)
    assert len(fake.policies) == 1


def test_sdk_error_is_reported(monkeypatch):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(
        mod,
        "_load",
        lambda: (FakeModels(), SimpleNamespace(AutoscalingClient=object)),
    )
    monkeypatch.setattr(
        TencentCloudModule,
        "create_client",
        lambda self, client_class, endpoint: _BoomClient(),
    )
    _run_args(name="add-two", adjustment_value=2)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert payload["error"] == "service exploded"
