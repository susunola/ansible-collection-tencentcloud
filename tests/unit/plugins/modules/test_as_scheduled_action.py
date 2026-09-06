"""Unit tests for the as_scheduled_action write module (helpers + run_module).

Creates, updates and deletes Auto Scaling scheduled actions. The module
requires action_id or name (required_one_of) and, when state=present, the
full capacity/time plan (name, min_size, desired_capacity, max_size,
start_time) plus a sane capacity ordering — all validated before the SDK
is reached. find() locates actions by ScheduledActionIds when an id is
given, otherwise by an auto-scaling-group-id Filter plus an exact name
match; more than one name match fails. Unlike immutable-config peers, all
eight config fields are mutable through ModifyScheduledAction, and the
module re-finds by the action id after every create/update. Check mode
reports diffs without mutating the store.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import as_scheduled_action as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)


class _SdkError(Exception):
    """Stand-in for TencentCloudSDKException carrying a code/request id."""

    def __init__(self, code, message="", request_id=None):
        super(_SdkError, self).__init__(message)
        self._code = code
        self._request_id = request_id

    def get_code(self):
        return self._code

    def get_request_id(self):
        return self._request_id


def _action(**overrides):
    """API-shaped stored action; fresh copy per call."""
    item = {
        "id": "asa-1001",
        "group_id": "asg-1001",
        "name": "weekday-scale-out",
        "min_size": 2,
        "desired_capacity": 4,
        "max_size": 8,
        "start_time": "2026-09-01T01:00:00+08:00",
        "end_time": None,
        "recurrence": "0 0 9 * * MON-FRI",
        "disable": False,
    }
    item.update(overrides)
    return item


def _params(**overrides):
    """Module parameters pre-filled from the argument spec defaults."""
    params = {
        "state": "present",
        "scaling_group_id": "asg-1001",
        "action_id": None,
        "name": "weekday-scale-out",
        "min_size": 2,
        "desired_capacity": 4,
        "max_size": 8,
        "start_time": "2026-09-01T01:00:00+08:00",
        "end_time": None,
        "recurrence": "0 0 9 * * MON-FRI",
        "disable_update_desired_capacity": False,
    }
    params.update(overrides)
    return params


def _run_args(**extra):
    """module_args() pre-filled with every non-None module parameter."""
    params = _params(**extra)
    args = {k: v for k, v in params.items() if v is not None}
    for key, value in extra.items():
        if key.startswith("_"):
            args[key] = value
    return module_args(**args)


def _serialize_action(a):
    """Map a stored action dict onto its API response shape."""
    return {
        "ScheduledActionId": a["id"],
        "ScheduledActionName": a["name"],
        "AutoScalingGroupId": a["group_id"],
        "MinSize": a["min_size"],
        "DesiredCapacity": a["desired_capacity"],
        "MaxSize": a["max_size"],
        "StartTime": a["start_time"],
        "EndTime": a["end_time"],
        "Recurrence": a["recurrence"],
        "DisableUpdateDesiredCapacity": a["disable"],
    }


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
    """In-memory AutoscalingClient stand-in storing action dicts.

    DescribeScheduledActions honours ScheduledActionIds when present,
    otherwise the auto-scaling-group-id Filter; the module then applies its
    own name filtering on the returned set. CreateScheduledAction
    synthesises sequential asa-NNNN ids; ModifyScheduledAction rewrites the
    eight config fields in place; DeleteScheduledAction removes by id.
    """

    def __init__(self, actions=None):
        self.actions = [dict(a) for a in (actions or [])]
        self.calls = []
        self._seq = 2000

    def _record(self, name, request):
        self.calls.append((name, request))
        return request

    def _next_id(self):
        self._seq += 1
        return "asa-%d" % self._seq

    def DescribeScheduledActions(self, request):
        self._record("DescribeScheduledActions", request)
        ids = getattr(request, "ScheduledActionIds", None) or []
        result = self.actions
        if ids:
            result = [a for a in self.actions if a["id"] in ids]
        else:
            filters = getattr(request, "Filters", None) or []
            if filters:
                groups = filters[0].Values
                result = [a for a in self.actions if a["group_id"] in groups]
        return SimpleNamespace(
            ScheduledActionSet=[FakeResource(_serialize_action(a)) for a in result],
            TotalCount=len(result),
            RequestId="req-fake",
        )

    def ModifyScheduledAction(self, request):
        self._record("ModifyScheduledAction", request)
        target = request.ScheduledActionId
        for action in self.actions:
            if action["id"] == target:
                action["name"] = request.ScheduledActionName
                action["min_size"] = request.MinSize
                action["desired_capacity"] = request.DesiredCapacity
                action["max_size"] = request.MaxSize
                action["start_time"] = request.StartTime
                action["end_time"] = getattr(request, "EndTime", None)
                action["recurrence"] = getattr(request, "Recurrence", None)
                action["disable"] = request.DisableUpdateDesiredCapacity
        return SimpleNamespace(RequestId="req-fake")

    def CreateScheduledAction(self, request):
        self._record("CreateScheduledAction", request)
        action_id = self._next_id()
        self.actions.append({
            "id": action_id,
            "group_id": request.AutoScalingGroupId,
            "name": request.ScheduledActionName,
            "min_size": request.MinSize,
            "desired_capacity": request.DesiredCapacity,
            "max_size": request.MaxSize,
            "start_time": request.StartTime,
            "end_time": getattr(request, "EndTime", None),
            "recurrence": getattr(request, "Recurrence", None),
            "disable": request.DisableUpdateDesiredCapacity,
        })
        return SimpleNamespace(ScheduledActionId=action_id, RequestId="req-fake")

    def DeleteScheduledAction(self, request):
        self._record("DeleteScheduledAction", request)
        self.actions = [a for a in self.actions if a["id"] != request.ScheduledActionId]
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
            raise _SdkError("AuthFailure", "auth rejected", request_id="req-err")

        return boom


# ---------------------------------------------------------------------------
# helper tests
# ---------------------------------------------------------------------------


def test_find_by_action_id_sets_ids():
    fake = FakeAsClient([_action()])
    module = FakeModule(_params(action_id="asa-1001", name="other"))
    value = mod.find(module, fake, FakeModels(), module.params)
    assert value["ScheduledActionId"] == "asa-1001"
    request = module.sdk_calls[0][1]
    assert request.ScheduledActionIds == ["asa-1001"]
    assert request.Offset == 0
    assert request.Limit == 100


def test_find_by_group_and_name_sets_filter():
    fake = FakeAsClient([_action()])
    module = FakeModule(_params())
    value = mod.find(module, fake, FakeModels(), module.params)
    assert value["ScheduledActionName"] == "weekday-scale-out"
    request = module.sdk_calls[0][1]
    assert request.Filters[0].Name == "auto-scaling-group-id"
    assert request.Filters[0].Values == ["asg-1001"]


def test_find_no_match_by_name_returns_none():
    fake = FakeAsClient([_action(name="other-action")])
    module = FakeModule(_params())
    assert mod.find(module, fake, FakeModels(), module.params) is None


def test_find_no_match_by_id_returns_none():
    fake = FakeAsClient()
    module = FakeModule(_params(action_id="asa-missing", name=None))
    assert mod.find(module, fake, FakeModels(), module.params) is None


def test_find_multi_match_fails():
    fake = FakeAsClient([_action(), _action(id="asa-1002")])
    module = FakeModule(_params())
    with pytest.raises(AnsibleFailJson) as exc:
        mod.find(module, fake, FakeModels(), module.params)
    payload = exc.value.args[0]
    assert "Multiple scheduled actions have the requested name" in payload["msg"]
    assert payload["name"] == "weekday-scale-out"


def test_wanted_builds_full_target():
    value = mod.wanted(_params())
    assert value == {
        "ScheduledActionName": "weekday-scale-out",
        "MinSize": 2,
        "DesiredCapacity": 4,
        "MaxSize": 8,
        "StartTime": "2026-09-01T01:00:00+08:00",
        "EndTime": None,
        "Recurrence": "0 0 9 * * MON-FRI",
        "DisableUpdateDesiredCapacity": False,
    }


def test_wanted_includes_end_time_and_disable_flag():
    value = mod.wanted(_params(end_time="2026-12-31T23:59:59+08:00", disable_update_desired_capacity=True))
    assert value["EndTime"] == "2026-12-31T23:59:59+08:00"
    assert value["DisableUpdateDesiredCapacity"] is True


def test_apply_create_sets_scaling_group():
    request = mod.apply(FakeModels().CreateScheduledActionRequest(), _params())
    assert request.AutoScalingGroupId == "asg-1001"
    assert not hasattr(request, "ScheduledActionId")
    assert request.ScheduledActionName == "weekday-scale-out"
    assert request.MinSize == 2
    assert request.DesiredCapacity == 4
    assert request.MaxSize == 8
    assert request.StartTime == "2026-09-01T01:00:00+08:00"
    assert getattr(request, "EndTime", None) is None
    assert request.Recurrence == "0 0 9 * * MON-FRI"
    assert request.DisableUpdateDesiredCapacity is False


def test_apply_update_sets_action_id():
    request = mod.apply(FakeModels().ModifyScheduledActionRequest(), _params(), action_id="asa-7")
    assert request.ScheduledActionId == "asa-7"
    assert not hasattr(request, "AutoScalingGroupId")
    assert request.ScheduledActionName == "weekday-scale-out"


# ---------------------------------------------------------------------------
# run_module main-path tests
# ---------------------------------------------------------------------------


def test_requires_either_action_id_or_name(monkeypatch):
    fake = FakeAsClient()
    _make_module(monkeypatch, fake)
    _run_args(name=None)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "one of the following is required" in exc.value.args[0]["msg"]
    assert fake.calls == []


@pytest.mark.parametrize(
    "overrides",
    [
        {"name": None, "action_id": "asa-x"},
        {"min_size": None},
        {"desired_capacity": None},
        {"max_size": None},
        {"start_time": None},
    ],
)
def test_present_requires_create_fields(monkeypatch, overrides):
    fake = FakeAsClient()
    _make_module(monkeypatch, fake)
    _run_args(**overrides)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "name, min_size, desired_capacity, max_size and start_time are required when state=present" in payload["msg"]
    assert fake.calls == []


def test_present_capacity_order_invalid(monkeypatch):
    fake = FakeAsClient()
    _make_module(monkeypatch, fake)
    _run_args(min_size=8, desired_capacity=4, max_size=8)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "capacity must satisfy min_size <= desired_capacity <= max_size" in exc.value.args[0]["msg"]
    assert fake.calls == []


def test_absent_noop_when_missing(monkeypatch):
    fake = FakeAsClient()
    _make_module(monkeypatch, fake)
    _run_args(state="absent", name="ghost")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["scheduled_action"] is None
    assert [c[0] for c in fake.calls] == ["DescribeScheduledActions"]


def test_absent_check_mode_delete_is_dry_run(monkeypatch):
    fake = FakeAsClient([_action()])
    _make_module(monkeypatch, fake)
    _run_args(state="absent", _ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["scheduled_action"]["ScheduledActionName"] == "weekday-scale-out"
    assert result["diff"]["before"]["ScheduledActionId"] == "asa-1001"
    assert result["diff"]["after"] is None
    assert [c[0] for c in fake.calls] == ["DescribeScheduledActions"]
    assert len(fake.actions) == 1


def test_absent_deletes_action(monkeypatch):
    fake = FakeAsClient([_action()])
    _make_module(monkeypatch, fake)
    _run_args(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["scheduled_action"] is None
    assert [c[0] for c in fake.calls] == ["DescribeScheduledActions", "DeleteScheduledAction"]
    deleted = fake.calls[1][1]
    assert deleted.ScheduledActionId == "asa-1001"
    assert fake.actions == []


def test_present_noop_when_action_matches(monkeypatch):
    fake = FakeAsClient([_action()])
    _make_module(monkeypatch, fake)
    _run_args()
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["scheduled_action"]["ScheduledActionName"] == "weekday-scale-out"
    assert result["scheduled_action"]["DesiredCapacity"] == 4
    assert [c[0] for c in fake.calls] == ["DescribeScheduledActions"]


def test_present_modifies_drift(monkeypatch):
    fake = FakeAsClient([_action()])
    _make_module(monkeypatch, fake)
    _run_args(desired_capacity=6)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["scheduled_action"]["DesiredCapacity"] == 6
    assert [c[0] for c in fake.calls] == [
        "DescribeScheduledActions",
        "ModifyScheduledAction",
        "DescribeScheduledActions",
    ]
    updated = fake.calls[1][1]
    assert updated.ScheduledActionId == "asa-1001"
    assert not hasattr(updated, "AutoScalingGroupId")
    assert updated.DesiredCapacity == 6
    assert fake.actions[0]["desired_capacity"] == 6


def test_present_check_mode_update_is_dry_run(monkeypatch):
    fake = FakeAsClient([_action()])
    _make_module(monkeypatch, fake)
    _run_args(desired_capacity=6, _ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["scheduled_action"]["DesiredCapacity"] == 4
    assert result["diff"]["before"]["DesiredCapacity"] == 4
    assert result["diff"]["after"]["DesiredCapacity"] == 6
    assert [c[0] for c in fake.calls] == ["DescribeScheduledActions"]
    assert fake.actions[0]["desired_capacity"] == 4


def test_present_creates_action(monkeypatch):
    fake = FakeAsClient()
    _make_module(monkeypatch, fake)
    _run_args(end_time="2026-12-31T23:59:59+08:00", disable_update_desired_capacity=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["scheduled_action"]["ScheduledActionId"] == "asa-2001"
    assert result["scheduled_action"]["EndTime"] == "2026-12-31T23:59:59+08:00"
    assert result["scheduled_action"]["DisableUpdateDesiredCapacity"] is True
    assert [c[0] for c in fake.calls] == [
        "DescribeScheduledActions",
        "CreateScheduledAction",
        "DescribeScheduledActions",
    ]
    created = fake.calls[1][1]
    assert created.AutoScalingGroupId == "asg-1001"
    assert created.ScheduledActionName == "weekday-scale-out"
    assert created.DesiredCapacity == 4
    assert created.StartTime == "2026-09-01T01:00:00+08:00"
    assert created.Recurrence == "0 0 9 * * MON-FRI"
    assert created.DisableUpdateDesiredCapacity is True
    assert len(fake.actions) == 1
    assert fake.actions[0]["id"] == "asa-2001"


def test_present_check_mode_create_is_dry_run(monkeypatch):
    fake = FakeAsClient()
    _make_module(monkeypatch, fake)
    _run_args(_ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["scheduled_action"] is None
    assert result["diff"]["before"] is None
    assert result["diff"]["after"]["ScheduledActionName"] == "weekday-scale-out"
    assert [c[0] for c in fake.calls] == ["DescribeScheduledActions"]
    assert fake.actions == []


def test_sdk_failure_reports_error_payload(monkeypatch):
    fake = _BoomClient()
    _make_module(monkeypatch, fake)
    _run_args(state="absent")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert payload["error"] == "auth rejected"
    assert payload["error_code"] == "AuthFailure"
    assert payload["request_id"] == "req-err"


def test_main_entrypoint_runs_module(monkeypatch):
    fake = FakeAsClient()
    _make_module(monkeypatch, fake)
    _run_args(state="absent", name="ghost")
    result = run(mod.main)
    assert result["changed"] is False
    assert result["scheduled_action"] is None
