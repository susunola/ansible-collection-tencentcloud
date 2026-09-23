"""Unit tests for the cvm_instance_action_timer write module (run_module flows).

Drives ``run_module()`` against an in-memory fake CVM client whose
import/delete operations mutate an action-timer store so post-write
describes converge immediately.

Scenario matrix:

* absent with no matching unexecuted timer (idempotent no-op)
* absent with a matching timer (check-mode dry run, real delete)
* creating a new termination timer (happy path, check mode)
* no-op when the existing timer already matches action_time
* replacing a stale timer deletes the old one and imports a new one
* the multiple-matching-timers guard and the blanket SDK failure paths
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import cvm_instance_action_timer as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

TIMER = {
    "InstanceId": "ins-123456",
    "ActionTimerId": "atm-1001",
    "TimerAction": "TerminateInstances",
    "ActionTime": "2026-09-01T12:00:00Z",
    "Status": "UNDO",
}


def _timer(**overrides):
    item = copy.deepcopy(TIMER)
    item.update(overrides)
    return item


def _present_args(**overrides):
    params = {"state": "present", "instance_id": "ins-123456", "action_time": "2026-09-01T12:00:00Z"}
    params.update(overrides)
    return module_args(**params)


class FakeCvmClient(object):
    """In-memory CVM client mutating a small action-timer store."""

    def __init__(self, timers=None):
        self.timers = [copy.deepcopy(t) for t in (timers or [])]
        self.calls = []
        self._next = 0

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def _by_id(self, timer_id):
        for item in self.timers:
            if item.get("ActionTimerId") == timer_id:
                return item
        return None

    def DescribeInstancesActionTimer(self, request):
        self._record("DescribeInstancesActionTimer", request)
        ids = list(getattr(request, "InstanceIds", None) or [])
        timer_ids = list(getattr(request, "ActionTimerIds", None) or [])
        statuses = list(getattr(request, "StatusList", None) or [])
        action = getattr(request, "TimerAction", None)
        values = []
        for item in self.timers:
            if item.get("InstanceId") not in ids:
                continue
            if action and item.get("TimerAction") != action:
                continue
            if statuses and item.get("Status") not in statuses:
                continue
            if timer_ids and item.get("ActionTimerId") not in timer_ids:
                continue
            values.append(item)
        return SimpleNamespace(ActionTimers=[FakeResource(copy.deepcopy(t)) for t in values])

    def ImportInstancesActionTimer(self, request):
        self._record("ImportInstancesActionTimer", request)
        self._next += 1
        timer = getattr(request, "ActionTimer", None)
        timer_id = "atm-2%03d" % self._next
        item = {
            "InstanceId": (getattr(request, "InstanceIds", None) or [None])[0],
            "ActionTimerId": timer_id,
            "TimerAction": getattr(timer, "TimerAction", None),
            "ActionTime": getattr(timer, "ActionTime", None),
            "Status": "UNDO",
        }
        self.timers.append(item)
        return SimpleNamespace(ActionTimerIds=[timer_id], RequestId="req-fake")

    def DeleteInstancesActionTimer(self, request):
        self._record("DeleteInstancesActionTimer", request)
        timer_ids = list(getattr(request, "ActionTimerIds", None) or [])
        self.timers = [t for t in self.timers if t.get("ActionTimerId") not in timer_ids]
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake, models=None):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (models or FakeModels(), SimpleNamespace(CvmClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


# ---------------------------------------------------------------------------
# absent flows
# ---------------------------------------------------------------------------


def test_absent_missing_timer_is_idempotent(monkeypatch):
    fake = FakeCvmClient(timers=[])
    _make_module(monkeypatch, fake)
    module_args(state="absent", instance_id="ins-123456")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["action_timer"] is None
    assert [c for c, unused in fake.calls] == ["DescribeInstancesActionTimer"]


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeCvmClient(timers=[_timer()])
    _make_module(monkeypatch, fake)
    module_args(_ansible_check_mode=True, state="absent", instance_id="ins-123456")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["action_timer"]["ActionTimerId"] == "atm-1001"
    assert len(fake.timers) == 1
    assert "DeleteInstancesActionTimer" not in [c for c, unused in fake.calls]


def test_absent_deletes_timer(monkeypatch):
    fake = FakeCvmClient(timers=[_timer()])
    _make_module(monkeypatch, fake)
    module_args(state="absent", instance_id="ins-123456")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["action_timer"] is None
    assert fake.timers == []
    ops = [c for c, unused in fake.calls]
    assert ops == ["DescribeInstancesActionTimer", "DeleteInstancesActionTimer"]


# ---------------------------------------------------------------------------
# creation / replacement flows
# ---------------------------------------------------------------------------


def test_create_timer(monkeypatch):
    fake = FakeCvmClient(timers=[])
    _make_module(monkeypatch, fake)
    _present_args()
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["action_timer"]["ActionTimerId"] == "atm-2001"
    assert result["action_timer"]["ActionTime"] == "2026-09-01T12:00:00Z"
    assert len(fake.timers) == 1
    ops = [c for c, unused in fake.calls]
    assert ops[0] == "DescribeInstancesActionTimer"
    assert "ImportInstancesActionTimer" in ops
    assert ops[-1] == "DescribeInstancesActionTimer"


def test_create_check_mode_is_dry_run(monkeypatch):
    fake = FakeCvmClient(timers=[])
    _make_module(monkeypatch, fake)
    _present_args(_ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["action_timer"] is None
    assert fake.timers == []
    assert "ImportInstancesActionTimer" not in [c for c, unused in fake.calls]


def test_existing_matching_timer_is_idempotent(monkeypatch):
    fake = FakeCvmClient(timers=[_timer()])
    _make_module(monkeypatch, fake)
    _present_args()
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["action_timer"]["ActionTimerId"] == "atm-1001"
    ops = [c for c, unused in fake.calls]
    assert ops == ["DescribeInstancesActionTimer"]


def test_present_with_timer_id_scopes_lookup(monkeypatch):
    # Two timers exist but timer_id restricts the lookup to one of them.
    fake = FakeCvmClient(timers=[_timer(), _timer(ActionTimerId="atm-2000")])
    _make_module(monkeypatch, fake)
    _present_args(timer_id="atm-2000")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["action_timer"]["ActionTimerId"] == "atm-2000"
    ops = [c for c, unused in fake.calls]
    assert ops == ["DescribeInstancesActionTimer"]


def test_action_time_drift_replaces_timer(monkeypatch):
    fake = FakeCvmClient(timers=[_timer()])
    _make_module(monkeypatch, fake)
    _present_args(action_time="2026-10-01T00:00:00Z")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["action_timer"]["ActionTimerId"] == "atm-2001"
    assert result["action_timer"]["ActionTime"] == "2026-10-01T00:00:00Z"
    assert [t["ActionTimerId"] for t in fake.timers] == ["atm-2001"]
    ops = [c for c, unused in fake.calls]
    assert "DeleteInstancesActionTimer" in ops
    assert "ImportInstancesActionTimer" in ops


def test_drift_check_mode_reports_without_replacing(monkeypatch):
    fake = FakeCvmClient(timers=[_timer()])
    _make_module(monkeypatch, fake)
    _present_args(_ansible_check_mode=True, action_time="2026-10-01T00:00:00Z")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["action_timer"]["ActionTimerId"] == "atm-1001"
    assert "diff" in result
    assert [t["ActionTimerId"] for t in fake.timers] == ["atm-1001"]
    ops = [c for c, unused in fake.calls]
    assert "DeleteInstancesActionTimer" not in ops
    assert "ImportInstancesActionTimer" not in ops


def test_absent_ignores_timer_id(monkeypatch):
    # timer_id scopes present lookups; absent still removes by matched timer.
    fake = FakeCvmClient(timers=[_timer()])
    _make_module(monkeypatch, fake)
    module_args(state="absent", instance_id="ins-123456", timer_id="atm-1001")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["action_timer"] is None
    assert fake.timers == []


# ---------------------------------------------------------------------------
# guards and failure paths
# ---------------------------------------------------------------------------


def test_multiple_matching_timers_fails(monkeypatch):
    fake = FakeCvmClient(timers=[_timer(), _timer(ActionTimerId="atm-2000", ActionTime="2026-10-01T00:00:00Z")])
    _make_module(monkeypatch, fake)
    _present_args()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "specify timer_id" in payload["msg"]
    assert payload["timer_ids"] == ["atm-1001", "atm-2000"]


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeInstancesActionTimer(self, request):
            raise Boom("connection dropped")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    _present_args()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]


def test_import_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeInstancesActionTimer(self, request):
            return SimpleNamespace(ActionTimers=[])

        def ImportInstancesActionTimer(self, request):
            raise Boom("import refused")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    _present_args()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "import refused" in payload["error"]
