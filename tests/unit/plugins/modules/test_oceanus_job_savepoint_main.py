"""Unit tests for the oceanus_job_savepoint write module (run_module flows).

``run_module()`` is driven end to end against an in-memory fake Oceanus client
whose savepoint store is immediately converged by ``TriggerJobSavepoint``, so
the status poll reports the savepoint as active on the first check. The module
has no delete lifecycle: it triggers a savepoint for a running job and, by
default, waits until it is usable.

Scenario matrix:

* an existing active or in-progress savepoint with the same description is
  reused (idempotent, changed False)
* check-mode dry run reports a trigger without calling the SDK
* a real trigger drives ``TriggerJobSavepoint`` and waits for activation
* ``force=true`` triggers another savepoint even when one exists
* ``wait=false`` skips the status waiter
* trigger rejection fails the module
* argument-validation failure before any SDK call
* the blanket ``sdk_error_payload`` failure path
* legacy helper regression tests (folded from test_oceanus_job_savepoint.py)
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import oceanus_job_savepoint as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

SAVEPOINT = {
    "Id": 1,
    "SerialId": "sp-00000001",
    "Description": "before-release-2026-08-31",
    "Status": 1,
    "RecordType": 1,
    "Path": "cos://savepoint-1250000000/base",
    "CreateTime": 10,
}


def _savepoint(**overrides):
    item = copy.deepcopy(SAVEPOINT)
    item.update(overrides)
    return item


def _base(**overrides):
    params = {
        "job_id": "cql-abcdefgh",
        "workspace_id": "space-abcdefgh",
        "description": "before-release-2026-08-31",
    }
    params.update(overrides)
    return module_args(**params)


class FakeOceanusClient(object):
    """In-memory Oceanus client mutating a per-job savepoint store."""

    def __init__(self, savepoints=None, reject=False):
        self.savepoints = [copy.deepcopy(t) for t in (savepoints or [])]
        self.reject = reject
        self.calls = []
        self._next = 0

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def DescribeJobSavepoint(self, request):
        self._record("DescribeJobSavepoint", request)
        return SimpleNamespace(
            Savepoint=[FakeResource(dict(t)) for t in self.savepoints],
            RunningSavepoint=[],
            TotalNumber=len(self.savepoints),
            RequestId="req-fake",
        )

    def TriggerJobSavepoint(self, request):
        self._record("TriggerJobSavepoint", request)
        if self.reject:
            return SimpleNamespace(SavepointTrigger=False, SavepointId=None, ErrorMsg="job not running")
        self._next += 1
        serial = "sp-new-%08d" % self._next
        self.savepoints.append({
            "Id": len(self.savepoints) + 1,
            "SerialId": serial,
            "Description": request.Description,
            "Status": 1,
            "RecordType": 1,
            "Path": "cos://savepoint-1250000000/%s" % serial,
            "CreateTime": 99,
        })
        return SimpleNamespace(
            SavepointTrigger=True,
            SavepointId=serial,
            FinalSavepointPath="cos://savepoint-1250000000/%s" % serial,
            RequestId="req-fake",
        )


def _make_module(monkeypatch, fake, models=None):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (models or FakeModels(), SimpleNamespace(OceanusClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


def _find_call(fake, operation):
    return next(request for name, request in fake.calls if name == operation)


# ---------------------------------------------------------------------------
# idempotent reuse
# ---------------------------------------------------------------------------


def test_active_savepoint_with_description_is_reused(monkeypatch):
    fake = FakeOceanusClient(savepoints=[_savepoint()])
    _make_module(monkeypatch, fake)
    _base()
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["savepoint"]["SerialId"] == "sp-00000001"
    assert result["savepoint_id"] == "sp-00000001"
    assert result["savepoint_path"] == "cos://savepoint-1250000000/base"
    assert "TriggerJobSavepoint" not in [name for name, unused in fake.calls]


def test_in_progress_savepoint_with_description_is_reused(monkeypatch):
    fake = FakeOceanusClient(savepoints=[_savepoint(Status=3)])
    _make_module(monkeypatch, fake)
    _base()
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["savepoint"]["Status"] == 3


def test_failed_savepoint_is_not_reused(monkeypatch):
    fake = FakeOceanusClient(savepoints=[_savepoint(Status=4)])
    _make_module(monkeypatch, fake)
    _base()
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["savepoint"]["SerialId"].startswith("sp-new-")


# ---------------------------------------------------------------------------
# trigger flows
# ---------------------------------------------------------------------------


def test_trigger_check_mode_is_dry_run(monkeypatch):
    fake = FakeOceanusClient(savepoints=[])
    _make_module(monkeypatch, fake)
    _base(_ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["savepoint"] == {"Description": "before-release-2026-08-31", "Status": 3, "RecordType": 1}
    assert result["savepoint_id"] is None
    assert fake.savepoints == []
    assert "TriggerJobSavepoint" not in [name for name, unused in fake.calls]


def test_trigger_creates_and_waits_for_savepoint(monkeypatch):
    fake = FakeOceanusClient(savepoints=[])
    _make_module(monkeypatch, fake)
    _base(wait=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["savepoint"]["Status"] == 1
    assert result["savepoint_id"].startswith("sp-new-")
    assert result["savepoint_path"].startswith("cos://savepoint-1250000000/")
    assert len(fake.savepoints) == 1
    request = _find_call(fake, "TriggerJobSavepoint")
    assert request.JobId == "cql-abcdefgh"
    assert request.WorkSpaceId == "space-abcdefgh"
    assert request.Description == "before-release-2026-08-31"
    ops = [name for name, unused in fake.calls]
    assert "TriggerJobSavepoint" in ops
    assert "DescribeJobSavepoint" in ops  # status poller


def test_force_triggers_another_savepoint(monkeypatch):
    fake = FakeOceanusClient(savepoints=[_savepoint()])
    _make_module(monkeypatch, fake)
    _base(force=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["savepoint_id"].startswith("sp-new-")
    assert len(fake.savepoints) == 2


def test_wait_false_skips_status_poller(monkeypatch):
    fake = FakeOceanusClient(savepoints=[])
    _make_module(monkeypatch, fake)
    _base(wait=False)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["savepoint_id"].startswith("sp-new-")
    ops = [name for name, unused in fake.calls]
    # One lookup to decide, one post-trigger lookup to find by id, no poll loop.
    assert ops == ["DescribeJobSavepoint", "TriggerJobSavepoint", "DescribeJobSavepoint"]


def test_rejected_trigger_fails_module(monkeypatch):
    fake = FakeOceanusClient(savepoints=[], reject=True)
    _make_module(monkeypatch, fake)
    _base()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "Oceanus rejected the savepoint trigger" in payload["msg"]
    assert payload["error"] == "job not running"


# ---------------------------------------------------------------------------
# argument validation and failure paths
# ---------------------------------------------------------------------------


def test_missing_required_arguments_fail(monkeypatch):
    fake = FakeOceanusClient(savepoints=[])
    _make_module(monkeypatch, fake)
    module_args(workspace_id="space-abcdefgh", description="x")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "job_id" in exc.value.args[0]["msg"]
    assert fake.calls == []


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeJobSavepoint(self, request):
            raise Boom("connection dropped")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    _base()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]


# ---------------------------------------------------------------------------
# legacy helper regression tests (folded from test_oceanus_job_savepoint.py)
# ---------------------------------------------------------------------------


def test_matching_reuses_latest_active_or_running_description():
    values = [
        {"Id": 1, "Description": "release", "Status": 1, "CreateTime": 10},
        {"Id": 2, "Description": "release", "Status": 3, "CreateTime": 20},
        {"Id": 3, "Description": "release", "Status": 4, "CreateTime": 30},
    ]
    assert mod.matching(values, "release")["Id"] == 2


def test_matching_requires_status_and_description():
    values = [{"Id": 1, "Description": "release", "Status": 4, "CreateTime": 10}]
    assert mod.matching(values, "release") is None
    assert mod.matching(values, "other") is None


def test_find_by_id_accepts_serial_or_numeric_identity():
    values = [{"Id": 7, "SerialId": "sp-7"}]
    assert mod.find_by_id(values, "sp-7") == values[0]
    assert mod.find_by_id([{"Id": 7}], 7) == {"Id": 7}
