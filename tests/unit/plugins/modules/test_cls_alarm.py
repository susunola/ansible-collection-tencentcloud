"""Unit tests for the cls_alarm write module (run_module flows).

Drives ``run_module()`` end to end against an in-memory fake CLS client that
mutates an alarm store keyed by name, so the module's post-write
``DescribeAlarms`` refetch observes the new state immediately.

Scenario matrix:

* create when missing (real Create + converged refetch)
* idempotent no-op when the alarm already exists
* absent when missing (no-op)
* delete when present (real Delete + converged refetch)
* check-mode dry run for create (no Create call)
* check-mode dry run for delete (no Delete call)
* missing alarm payload on present fails (required_if)
* SDK failure surfaces via fail_sdk_error
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from types import SimpleNamespace

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import cls_alarm as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    FakeModels,
    FakeResource,
    module_args,
    run,
)


def _alarm(aid, name):
    return FakeResource({"AlarmId": str(aid), "Name": name, "Enable": True, "Condition": "$1 > 1"})


class FakeClsClient(object):
    """In-memory CLS client mutating an alarm store keyed by name."""

    def __init__(self, alarms=None):
        self.alarms = list(alarms or [])
        self._seq = 0
        self.calls = []

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def _name_filter(self, request):
        for flt in getattr(request, "Filters", None) or []:
            if getattr(flt, "Key", None) == "name":
                return list(getattr(flt, "Values", None) or [])
        return []

    def DescribeAlarms(self, request):
        self._record("DescribeAlarms", request)
        wanted = self._name_filter(request)
        if wanted:
            matched = [a for a in self.alarms if a.Name in wanted]
        else:
            matched = list(self.alarms)
        return SimpleNamespace(Alarms=[FakeResource(dict(a._data)) for a in matched],
                               TotalCount=len(matched), RequestId="req-fake")

    def CreateAlarm(self, request):
        self._record("CreateAlarm", request)
        self._seq += 1
        item = _alarm(self._seq, getattr(request, "Name", ""))
        self.alarms.append(item)
        return SimpleNamespace(AlarmId=item.AlarmId, RequestId="req-fake")

    def DeleteAlarm(self, request):
        self._record("DeleteAlarm", request)
        aid = getattr(request, "AlarmId", None)
        self.alarms = [a for a in self.alarms if a.AlarmId != aid]
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake, models=None):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load_cls", lambda: (models or FakeModels(), SimpleNamespace(ClsClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


ALARM = {"MonitorObjectType": "log", "Condition": "$1.error_count > 10", "TriggerCount": 1}


# ---------------------------------------------------------------------------
# create / delete flows
# ---------------------------------------------------------------------------


def test_create_when_missing(monkeypatch):
    fake = FakeClsClient(alarms=[])
    _make_module(monkeypatch, fake)
    module_args(name="error-spike", alarm=dict(ALARM), state="present")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["exists"] is True
    assert result["alarm_id"] is not None
    ops = [c for c, unused in fake.calls]
    assert ops[0] == "DescribeAlarms"
    assert "CreateAlarm" in ops
    assert "DeleteAlarm" not in ops
    created = [r for c, r in fake.calls if c == "CreateAlarm"][0]
    assert created.Name == "error-spike"


def test_delete_when_present(monkeypatch):
    fake = FakeClsClient(alarms=[_alarm(1, "error-spike")])
    _make_module(monkeypatch, fake)
    module_args(name="error-spike", state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["exists"] is False
    assert "DeleteAlarm" in [c for c, unused in fake.calls]
    assert "CreateAlarm" not in [c for c, unused in fake.calls]
    assert fake.alarms == []


# ---------------------------------------------------------------------------
# idempotent no-op flows
# ---------------------------------------------------------------------------


def test_already_present_is_idempotent(monkeypatch):
    fake = FakeClsClient(alarms=[_alarm(1, "error-spike")])
    _make_module(monkeypatch, fake)
    module_args(name="error-spike", alarm=dict(ALARM), state="present")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["alarm_id"] == "1"
    assert [c for c, unused in fake.calls] == ["DescribeAlarms"]
    assert "CreateAlarm" not in [c for c, unused in fake.calls]


def test_absent_when_missing_is_idempotent(monkeypatch):
    fake = FakeClsClient(alarms=[])
    _make_module(monkeypatch, fake)
    module_args(name="error-spike", state="absent")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert "DeleteAlarm" not in [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# check-mode dry runs
# ---------------------------------------------------------------------------


def test_create_check_mode_is_dry_run(monkeypatch):
    fake = FakeClsClient(alarms=[])
    _make_module(monkeypatch, fake)
    module_args(name="error-spike", alarm=dict(ALARM), state="present", _ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert "CreateAlarm" not in [c for c, unused in fake.calls]
    assert fake.alarms == []


def test_delete_check_mode_is_dry_run(monkeypatch):
    fake = FakeClsClient(alarms=[_alarm(1, "error-spike")])
    _make_module(monkeypatch, fake)
    module_args(name="error-spike", state="absent", _ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert "DeleteAlarm" not in [c for c, unused in fake.calls]
    assert len(fake.alarms) == 1


# ---------------------------------------------------------------------------
# error / validation paths
# ---------------------------------------------------------------------------


def test_missing_alarm_payload_on_present_fails(monkeypatch):
    fake = FakeClsClient(alarms=[])
    _make_module(monkeypatch, fake)
    module_args(name="error-spike", state="present")
    try:
        run(mod.run_module)
    except SystemExit as exc:
        payload = getattr(exc, "args", [{}])[0]
        assert payload.get("failed")
    else:
        raise AssertionError("expected required_if alarm to fail the module")


def test_sdk_failure_fails(monkeypatch):
    fake = FakeClsClient(alarms=[])

    def _raise_error(request):
        raise RuntimeError("boom")
    fake.CreateAlarm = _raise_error
    _make_module(monkeypatch, fake)
    module_args(name="error-spike", alarm=dict(ALARM), state="present")
    try:
        run(mod.run_module)
    except SystemExit as exc:
        payload = getattr(exc, "args", [{}])[0]
        assert payload.get("failed")
    else:
        raise AssertionError("expected SDK failure to fail the module")
