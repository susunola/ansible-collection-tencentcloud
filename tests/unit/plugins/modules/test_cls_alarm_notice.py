"""Unit tests for the cls_alarm_notice write module (run_module flows).

Drives ``run_module()`` end to end against an in-memory fake CLS client that
mutates an alarm-notice store keyed by name, so the module's post-write
``DescribeAlarmNotices`` refetch observes the new state immediately.

Scenario matrix:

* create when missing (real Create + converged refetch)
* idempotent no-op when the notice already exists
* absent when missing (no-op)
* delete when present (real Delete + converged refetch)
* check-mode dry run for create (no Create call)
* check-mode dry run for delete (no Delete call)
* missing notice payload on present fails (required_if)
* SDK failure surfaces via fail_sdk_error
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from types import SimpleNamespace

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import cls_alarm_notice as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    FakeModels,
    FakeResource,
    module_args,
    run,
)


def _notice(aid, name):
    return FakeResource({"AlarmNoticeId": str(aid), "Name": name})


class FakeClsClient(object):
    """In-memory CLS client mutating an alarm-notice store keyed by name."""

    def __init__(self, notices=None):
        self.notices = list(notices or [])
        self._seq = 0
        self.calls = []

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def _name_filter(self, request):
        for flt in getattr(request, "Filters", None) or []:
            if getattr(flt, "Key", None) == "name":
                return list(getattr(flt, "Values", None) or [])
        return []

    def DescribeAlarmNotices(self, request):
        self._record("DescribeAlarmNotices", request)
        wanted = self._name_filter(request)
        if wanted:
            matched = [n for n in self.notices if n.Name in wanted]
        else:
            matched = list(self.notices)
        return SimpleNamespace(AlarmNotices=[FakeResource(dict(n._data)) for n in matched],
                               TotalCount=len(matched), RequestId="req-fake")

    def CreateAlarmNotice(self, request):
        self._record("CreateAlarmNotice", request)
        self._seq += 1
        item = _notice(self._seq, getattr(request, "Name", ""))
        self.notices.append(item)
        return SimpleNamespace(AlarmNoticeId=item.AlarmNoticeId, RequestId="req-fake")

    def DeleteAlarmNotice(self, request):
        self._record("DeleteAlarmNotice", request)
        aid = getattr(request, "AlarmNoticeId", None)
        self.notices = [n for n in self.notices if n.AlarmNoticeId != aid]
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake, models=None):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load_cls", lambda: (models or FakeModels(), SimpleNamespace(ClsClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


NOTICE = {"Type": "All", "NoticeReceivers": [{"ReceiverType": "Person", "ReceiverIds": ["1"], "ReceiverChannels": ["Email"], "Enable": 1}]}


# ---------------------------------------------------------------------------
# create / delete flows
# ---------------------------------------------------------------------------


def test_create_when_missing(monkeypatch):
    fake = FakeClsClient(notices=[])
    _make_module(monkeypatch, fake)
    module_args(name="oncall-email", notice=dict(NOTICE), state="present")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["exists"] is True
    assert result["alarm_notice_id"] is not None
    ops = [c for c, unused in fake.calls]
    assert ops[0] == "DescribeAlarmNotices"
    assert "CreateAlarmNotice" in ops
    assert "DeleteAlarmNotice" not in ops
    created = [r for c, r in fake.calls if c == "CreateAlarmNotice"][0]
    assert created.Name == "oncall-email"


def test_delete_when_present(monkeypatch):
    fake = FakeClsClient(notices=[_notice(1, "oncall-email")])
    _make_module(monkeypatch, fake)
    module_args(name="oncall-email", state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["exists"] is False
    assert "DeleteAlarmNotice" in [c for c, unused in fake.calls]
    assert "CreateAlarmNotice" not in [c for c, unused in fake.calls]
    assert fake.notices == []


# ---------------------------------------------------------------------------
# idempotent no-op flows
# ---------------------------------------------------------------------------


def test_already_present_is_idempotent(monkeypatch):
    fake = FakeClsClient(notices=[_notice(1, "oncall-email")])
    _make_module(monkeypatch, fake)
    module_args(name="oncall-email", notice=dict(NOTICE), state="present")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["alarm_notice_id"] == "1"
    assert [c for c, unused in fake.calls] == ["DescribeAlarmNotices"]
    assert "CreateAlarmNotice" not in [c for c, unused in fake.calls]


def test_absent_when_missing_is_idempotent(monkeypatch):
    fake = FakeClsClient(notices=[])
    _make_module(monkeypatch, fake)
    module_args(name="oncall-email", state="absent")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert "DeleteAlarmNotice" not in [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# check-mode dry runs
# ---------------------------------------------------------------------------


def test_create_check_mode_is_dry_run(monkeypatch):
    fake = FakeClsClient(notices=[])
    _make_module(monkeypatch, fake)
    module_args(name="oncall-email", notice=dict(NOTICE), state="present", _ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert "CreateAlarmNotice" not in [c for c, unused in fake.calls]
    assert fake.notices == []


def test_delete_check_mode_is_dry_run(monkeypatch):
    fake = FakeClsClient(notices=[_notice(1, "oncall-email")])
    _make_module(monkeypatch, fake)
    module_args(name="oncall-email", state="absent", _ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert "DeleteAlarmNotice" not in [c for c, unused in fake.calls]
    assert len(fake.notices) == 1


# ---------------------------------------------------------------------------
# error / validation paths
# ---------------------------------------------------------------------------


def test_missing_notice_payload_on_present_fails(monkeypatch):
    fake = FakeClsClient(notices=[])
    _make_module(monkeypatch, fake)
    module_args(name="oncall-email", state="present")
    try:
        run(mod.run_module)
    except SystemExit as exc:
        payload = getattr(exc, "args", [{}])[0]
        assert payload.get("failed")
    else:
        raise AssertionError("expected required_if notice to fail the module")


def test_sdk_failure_fails(monkeypatch):
    fake = FakeClsClient(notices=[])
    fake.CreateAlarmNotice = lambda request: (_ for _ in ()).throw(RuntimeError("boom"))
    _make_module(monkeypatch, fake)
    module_args(name="oncall-email", notice=dict(NOTICE), state="present")
    try:
        run(mod.run_module)
    except SystemExit as exc:
        payload = getattr(exc, "args", [{}])[0]
        assert payload.get("failed")
    else:
        raise AssertionError("expected SDK failure to fail the module")
