"""Unit tests for the dts_migration_check action module (run_module flows).

This is a one-shot action module: it describes the migration check, starts a
check when the current state implies one is needed, optionally waits for a
conclusive status and fails when the check did not pass. There is no
``state=absent`` lifecycle.

The fake DTS client serves a queue of ``DescribeMigrationCheckJob`` states so
the module observes a real state transition after starting a check.

Scenario matrix:

* an already-passing check is idempotent
* ``notStarted`` starts a check and waits for ``success``
* a ``failed``/``notPass`` check is re-run
* ``wait=false`` returns right after starting (no wait loop)
* check-mode reports a change without starting anything
* a running check is waited on; running in check mode is left alone
* a non-passing result fails the module, unless ``fail_on_check_error=false``
* the waiter times out on a stuck check
* the blanket SDK failure path
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import dts_migration_check as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)


def _check(status, flag):
    return {"Status": status, "CheckFlag": flag}


PASSED = _check("success", "checkPass")


def _args(**overrides):
    params = {"job_id": "dts-abcd1234", "wait": True, "fail_on_check_error": True}
    params.update(overrides)
    return module_args(**params)


class FakeDtsClient(object):
    """In-memory DTS client replaying a queue of check states."""

    def __init__(self, states):
        self.states = [copy.deepcopy(s) for s in states]
        self.calls = []

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def _next_state(self):
        state = self.states[0]
        if len(self.states) > 1:
            self.states.pop(0)
        return state

    def DescribeMigrationCheckJob(self, request):
        self._record("DescribeMigrationCheckJob", request)
        return FakeResource(self._next_state())

    def CreateMigrateCheckJob(self, request):
        self._record("CreateMigrateCheckJob", request)
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (FakeModels(), SimpleNamespace(DtsClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


def test_successful_check_is_idempotent(monkeypatch):
    fake = FakeDtsClient([PASSED])
    _make_module(monkeypatch, fake)
    _args()
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["migration_check"]["Status"] == "success"
    assert [c for c, unused in fake.calls] == ["DescribeMigrationCheckJob"]


def test_not_started_runs_and_waits(monkeypatch):
    fake = FakeDtsClient([_check("notStarted", None), PASSED])
    _make_module(monkeypatch, fake)
    _args()
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["migration_check"]["Status"] == "success"
    ops = [c for c, unused in fake.calls]
    assert ops.count("DescribeMigrationCheckJob") == 2
    assert "CreateMigrateCheckJob" in ops


def test_failed_check_is_rerun(monkeypatch):
    fake = FakeDtsClient([_check("failed", "checkNotPass"), PASSED])
    _make_module(monkeypatch, fake)
    _args()
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["migration_check"]["Status"] == "success"
    ops = [c for c, unused in fake.calls]
    assert "CreateMigrateCheckJob" in ops


def test_no_wait_returns_after_start(monkeypatch):
    fake = FakeDtsClient([_check("notStarted", "checkNotPass"), _check("notStarted", "checkNotPass")])
    _make_module(monkeypatch, fake)
    _args(wait=False)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["migration_check"]["Status"] == "notStarted"
    ops = [c for c, unused in fake.calls]
    assert "CreateMigrateCheckJob" in ops
    # A single post-start describe, no wait loop.
    assert ops.count("DescribeMigrationCheckJob") == 2


def test_check_mode_reports_change_without_starting(monkeypatch):
    fake = FakeDtsClient([_check("notStarted", None)])
    _make_module(monkeypatch, fake)
    _args(_ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["migration_check"]["Status"] == "notStarted"
    assert "CreateMigrateCheckJob" not in [c for c, unused in fake.calls]


def test_running_check_is_waited_on(monkeypatch):
    fake = FakeDtsClient([_check("running", None), PASSED])
    _make_module(monkeypatch, fake)
    _args()
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["migration_check"]["Status"] == "success"
    assert "CreateMigrateCheckJob" not in [c for c, unused in fake.calls]


def test_running_check_in_check_mode_is_left_alone(monkeypatch):
    fake = FakeDtsClient([_check("running", None)])
    _make_module(monkeypatch, fake)
    _args(_ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["migration_check"]["Status"] == "running"
    assert [c for c, unused in fake.calls] == ["DescribeMigrationCheckJob"]


def test_non_passing_result_fails_module(monkeypatch):
    fake = FakeDtsClient([_check("notStarted", None), _check("success", "checkNotPass")])
    _make_module(monkeypatch, fake)
    _args()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "DTS migration check did not pass"
    assert payload["migration_check"]["CheckFlag"] == "checkNotPass"


def test_fail_on_check_error_can_be_disabled(monkeypatch):
    fake = FakeDtsClient([_check("notStarted", None), _check("success", "checkNotPass")])
    _make_module(monkeypatch, fake)
    _args(fail_on_check_error=False)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["migration_check"]["CheckFlag"] == "checkNotPass"


def test_wait_times_out_on_stuck_check(monkeypatch):
    fake = FakeDtsClient([_check("notStarted", None), _check("notStarted", None)])
    _make_module(monkeypatch, fake)
    _args(waiter_timeout=0, waiter_delay=0)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "Timed out waiting for DTS migration check" in payload["msg"]
    assert "migration_check" in payload


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeMigrationCheckJob(self, request):
            raise Boom("connection dropped")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    _args()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]
