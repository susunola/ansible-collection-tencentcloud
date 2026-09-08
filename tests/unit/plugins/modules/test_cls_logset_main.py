"""Unit tests for the cls_logset write module (run_module flows).

Drives ``run_module()`` end to end against an in-memory fake CLS client whose
write operations mutate the logset store, so the module's post-write
``find_logset`` waiters converge immediately.

Scenario matrix:

* absent on a missing logset (idempotent no-op)
* absent with a matching logset (check-mode dry run and the real delete)
* creation when missing (with/without ``name``, check mode, waiting)
* no-op when nothing drifts (by name and by ``logset_id``)
* drift updates (tag change through ``ModifyLogset``)
* the multiple-match guard and the ``sdk_error_payload`` failure path
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import cls_logset as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

LOGSET = {
    "LogsetId": "logset-0a1b2c3d",
    "LogsetName": "production-logs",
    "Tags": [{"Key": "env", "Value": "prod"}],
}


def _logset(**overrides):
    item = copy.deepcopy(LOGSET)
    item.update(overrides)
    return item


def _base(**overrides):
    params = {"name": "production-logs"}
    params.update(overrides)
    return module_args(**params)


class FakeClsClient(object):
    """In-memory CLS client mutating a small logset store."""

    def __init__(self, logsets=None):
        self.logsets = [copy.deepcopy(t) for t in (logsets or [])]
        self.calls = []
        self._next = 0

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def DescribeLogsets(self, request):
        self._record("DescribeLogsets", request)
        matched = list(self.logsets)
        for item in list(getattr(request, "Filters", None) or []):
            key = item.Key
            value = item.Values[0]
            if key == "logsetId":
                matched = [t for t in matched if t.get("LogsetId") == value]
            elif key == "logsetName":
                matched = [t for t in matched if t.get("LogsetName") == value]
        return SimpleNamespace(
            Logsets=[FakeResource(t) for t in matched],
            TotalCount=len(matched),
        )

    def CreateLogset(self, request):
        self._record("CreateLogset", request)
        self._next += 1
        item = {
            "LogsetId": "logset-new-%03d" % self._next,
            "LogsetName": getattr(request, "LogsetName", None),
        }
        tags = getattr(request, "Tags", None)
        if tags is not None:
            item["Tags"] = [{"Key": t.Key, "Value": t.Value} for t in tags]
        self.logsets.append(item)
        return SimpleNamespace(LogsetId=item["LogsetId"], RequestId="req-fake")

    def ModifyLogset(self, request):
        self._record("ModifyLogset", request)
        item = self._find(getattr(request, "LogsetId", None))
        if item is not None:
            item["LogsetName"] = getattr(request, "LogsetName", item.get("LogsetName"))
            tags = getattr(request, "Tags", None)
            if tags is not None:
                item["Tags"] = [{"Key": t.Key, "Value": t.Value} for t in tags]
        return SimpleNamespace(RequestId="req-fake")

    def DeleteLogset(self, request):
        self._record("DeleteLogset", request)
        logset_id = getattr(request, "LogsetId", None)
        self.logsets = [t for t in self.logsets if t.get("LogsetId") != logset_id]
        return SimpleNamespace(RequestId="req-fake")

    def _find(self, logset_id):
        for item in self.logsets:
            if item.get("LogsetId") == logset_id:
                return item
        return None


def _make_module(monkeypatch, fake, models=None):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load_cls", lambda: (models or FakeModels(), SimpleNamespace(ClsClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


# ---------------------------------------------------------------------------
# absent flows
# ---------------------------------------------------------------------------


def test_absent_missing_logset_is_idempotent(monkeypatch):
    fake = FakeClsClient(logsets=[])
    _make_module(monkeypatch, fake)
    _base(state="absent", name="ghost-logs")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["logset"] is None
    assert [c for c, unused in fake.calls] == ["DescribeLogsets"]


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeClsClient(logsets=[_logset()])
    _make_module(monkeypatch, fake)
    _base(_ansible_check_mode=True, state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["logset"] is not None
    assert len(fake.logsets) == 1
    assert "DeleteLogset" not in [c for c, unused in fake.calls]


def test_absent_deletes_logset_by_id(monkeypatch):
    fake = FakeClsClient(logsets=[_logset()])
    _make_module(monkeypatch, fake)
    _base(state="absent", name=None, logset_id="logset-0a1b2c3d")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["logset"] is None
    assert fake.logsets == []
    ops = [c for c, unused in fake.calls]
    assert "DeleteLogset" in ops


# ---------------------------------------------------------------------------
# creation flows
# ---------------------------------------------------------------------------


def test_create_requires_name_when_missing(monkeypatch):
    fake = FakeClsClient(logsets=[])
    _make_module(monkeypatch, fake)
    _base(state="present", name=None, logset_id="logset-unknown")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "name is required when creating a CLS logset" in exc.value.args[0]["msg"]


def test_create_logset(monkeypatch):
    fake = FakeClsClient(logsets=[])
    _make_module(monkeypatch, fake)
    _base(
        state="present",
        name="production-logs",
        tags={"env": "prod", "team": "sre"},
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["logset"]["LogsetName"] == "production-logs"
    assert result["logset"]["LogsetId"].startswith("logset-new-")
    assert len(fake.logsets) == 1
    assert fake.logsets[0]["LogsetId"] == result["logset"]["LogsetId"]
    ops = [c for c, unused in fake.calls]
    assert ops[0] == "DescribeLogsets"
    assert "CreateLogset" in ops


def test_create_logset_without_tags(monkeypatch):
    fake = FakeClsClient(logsets=[])
    _make_module(monkeypatch, fake)
    _base(state="present", name="bare-logs")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["logset"]["LogsetName"] == "bare-logs"
    assert "Tags" not in result["logset"]


def test_create_check_mode_is_dry_run(monkeypatch):
    fake = FakeClsClient(logsets=[])
    _make_module(monkeypatch, fake)
    _base(
        _ansible_check_mode=True,
        state="present",
        name="production-logs",
        tags={"env": "prod"},
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["logset"] is None
    assert fake.logsets == []
    assert "CreateLogset" not in [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# existing-logset flows
# ---------------------------------------------------------------------------


def test_existing_logset_no_drift_is_idempotent(monkeypatch):
    fake = FakeClsClient(logsets=[_logset()])
    _make_module(monkeypatch, fake)
    _base(state="present", name="production-logs", tags={"env": "prod"})
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["logset"]["LogsetId"] == "logset-0a1b2c3d"


def test_existing_logset_no_drift_by_id(monkeypatch):
    fake = FakeClsClient(logsets=[_logset()])
    _make_module(monkeypatch, fake)
    _base(state="present", name="production-logs", logset_id="logset-0a1b2c3d", tags={"env": "prod"})
    result = run(mod.run_module)
    assert result["changed"] is False


def test_update_tags_drift(monkeypatch):
    fake = FakeClsClient(logsets=[_logset()])
    _make_module(monkeypatch, fake)
    _base(state="present", tags={"env": "staging"})
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["logset"]["Tags"] == [{"Key": "env", "Value": "staging"}]
    ops = [c for c, unused in fake.calls]
    assert "ModifyLogset" in ops


def test_update_removes_tags_when_empty(monkeypatch):
    fake = FakeClsClient(logsets=[_logset()])
    _make_module(monkeypatch, fake)
    _base(state="present", tags={})
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["logset"]["Tags"] == []


# ---------------------------------------------------------------------------
# guards / failure paths
# ---------------------------------------------------------------------------


def test_multiple_matches_fail(monkeypatch):
    fake = FakeClsClient(logsets=[_logset(), _logset(LogsetId="logset-dup")])
    _make_module(monkeypatch, fake)
    _base(state="present")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "Multiple CLS logsets have the requested name" in exc.value.args[0]["msg"]


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeLogsets(self, request):
            raise Boom("connection dropped")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    _base(state="present", name="production-logs")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]
