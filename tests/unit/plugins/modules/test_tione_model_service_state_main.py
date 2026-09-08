"""Unit tests for the tione_model_service_state write module (run_module flows).

Drives ``run_module()`` end to end against an in-memory fake TIONE client
whose lifecycle operations (RESUME/STOP/delete) mutate a service store so the
``wait_for_state`` pollers converge on the first poll. Transitional stores
hand out statuses from a per-service sequence so a "creating" service can
converge to "normal".

Scenario matrix:

* absent on a missing service (idempotent) and the allow_delete guard
* absent with a live service (check-mode dry run, real delete, wait toggles)
* running/stopped guards (missing service, failed state, positive waiters)
* no-op when the service already matches the desired state
* resume/stop through ModifyModelService (check mode and real transitions)
* transitional states (wait converges, wait=false fails)
* the blanket ``sdk_error_payload`` failure path
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import tione_model_service_state as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

MS_ID = "ms-1a2b3c4d"


def _svc(**overrides):
    item = {
        "ServiceId": MS_ID,
        "Status": "normal",
        "ServiceName": "bert-classifier",
        "Version": "v1",
    }
    item.update(overrides)
    return item


def _base(**overrides):
    params = {"service_id": MS_ID}
    params.update(overrides)
    return module_args(**params)


class FakeTioneClient(object):
    """In-memory TIONE (tione.v20211111) model-service client."""

    def __init__(self, entries=None):
        self.entries = [copy.deepcopy(t) for t in (entries or [])]
        self.calls = []
        # service_id -> statuses handed out one per DescribeModelService call
        # (and persisted), so transitional stores converge on the waiter poll.
        self.status_seq = {}

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def _entry(self, service_id):
        for entry in self.entries:
            if entry.get("ServiceId") == service_id:
                return entry
        return None

    def DescribeModelService(self, request):
        self._record("DescribeModelService", request)
        entry = self._entry(request.ServiceId)
        if entry is None:
            return SimpleNamespace(Service=None)
        seq = self.status_seq.get(request.ServiceId)
        if seq:
            entry["Status"] = seq.pop(0)
        return SimpleNamespace(Service=FakeResource(copy.deepcopy(entry)))

    def ModifyModelService(self, request):
        self._record("ModifyModelService", request)
        entry = self._entry(request.ServiceId)
        if entry is not None:
            if getattr(request, "ServiceAction", None) == "RESUME":
                entry["Status"] = "normal"
            elif getattr(request, "ServiceAction", None) == "STOP":
                entry["Status"] = "stopped"
        return SimpleNamespace()

    def DeleteModelService(self, request):
        self._record("DeleteModelService", request)
        self.entries = [e for e in self.entries if e.get("ServiceId") != request.ServiceId]
        return SimpleNamespace()


def _make_module(monkeypatch, fake):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (FakeModels(), SimpleNamespace(TioneClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


def _ops(fake):
    return [c for c, unused in fake.calls]


def _request(fake, op_name):
    for op, request in fake.calls:
        if op == op_name:
            return request
    return None


# ---------------------------------------------------------------------------
# absent flows
# ---------------------------------------------------------------------------


def test_absent_missing_service_is_idempotent(monkeypatch):
    fake = FakeTioneClient()
    _make_module(monkeypatch, fake)
    _base(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["service"] is None
    assert result["service_id"] == MS_ID
    assert _ops(fake) == ["DescribeModelService"]


def test_absent_requires_allow_delete(monkeypatch):
    fake = FakeTioneClient(entries=[_svc()])
    _make_module(monkeypatch, fake)
    _base(state="absent")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "allow_delete=true is required" in exc.value.args[0]["msg"]


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeTioneClient(entries=[_svc()])
    _make_module(monkeypatch, fake)
    _base(_ansible_check_mode=True, state="absent", allow_delete=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["service"] is None
    assert len(fake.entries) == 1
    assert "DeleteModelService" not in _ops(fake)


def test_absent_deletes_service(monkeypatch):
    fake = FakeTioneClient(entries=[_svc()])
    _make_module(monkeypatch, fake)
    _base(state="absent", allow_delete=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["service"] is None
    assert fake.entries == []
    assert "DeleteModelService" in _ops(fake)
    assert _request(fake, "DeleteModelService").ServiceId == MS_ID


def test_absent_delete_without_wait(monkeypatch):
    fake = FakeTioneClient(entries=[_svc()])
    _make_module(monkeypatch, fake)
    _base(state="absent", allow_delete=True, wait=False)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert fake.entries == []
    assert "DeleteModelService" in _ops(fake)


def test_absent_delete_request_carries_project_id(monkeypatch):
    fake = FakeTioneClient(entries=[_svc()])
    _make_module(monkeypatch, fake)
    _base(state="absent", allow_delete=True, project_id="prj-xyz")
    run(mod.run_module)
    request = _request(fake, "DeleteModelService")
    assert request.TiProjectId == "prj-xyz"


# ---------------------------------------------------------------------------
# running / stopped guards
# ---------------------------------------------------------------------------


def test_present_missing_service_fails(monkeypatch):
    fake = FakeTioneClient()
    _make_module(monkeypatch, fake)
    _base(state="running")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "does not exist" in payload["msg"]
    assert payload["service_id"] == MS_ID


def test_failed_state_fails(monkeypatch):
    fake = FakeTioneClient(entries=[_svc(Status="abnormal")])
    _make_module(monkeypatch, fake)
    _base(state="running")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "failed state" in exc.value.args[0]["msg"]


def test_non_positive_waiter_parameters_fail(monkeypatch):
    fake = FakeTioneClient()
    _make_module(monkeypatch, fake)
    _base(state="running", waiter_delay=0)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "waiter_delay and waiter_timeout must be positive" in exc.value.args[0]["msg"]


# ---------------------------------------------------------------------------
# no-op states
# ---------------------------------------------------------------------------


def test_running_service_is_noop(monkeypatch):
    fake = FakeTioneClient(entries=[_svc()])
    _make_module(monkeypatch, fake)
    _base(state="running")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["service"]["Status"] == "normal"
    assert "ModifyModelService" not in _ops(fake)


def test_stopped_service_is_noop(monkeypatch):
    fake = FakeTioneClient(entries=[_svc(Status="stopped")])
    _make_module(monkeypatch, fake)
    _base(state="stopped")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["service"]["Status"] == "stopped"


# ---------------------------------------------------------------------------
# lifecycle transitions
# ---------------------------------------------------------------------------


def test_resume_stopped_service(monkeypatch):
    fake = FakeTioneClient(entries=[_svc(Status="stopped")])
    _make_module(monkeypatch, fake)
    _base(state="running")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["service"]["Status"] == "normal"
    request = _request(fake, "ModifyModelService")
    assert request.ServiceId == MS_ID
    assert request.ServiceAction == "RESUME"


def test_resume_without_wait(monkeypatch):
    fake = FakeTioneClient(entries=[_svc(Status="stopped")])
    _make_module(monkeypatch, fake)
    _base(state="running", wait=False)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["service"]["Status"] == "normal"
    assert _request(fake, "ModifyModelService").ServiceAction == "RESUME"


def test_stop_running_service(monkeypatch):
    fake = FakeTioneClient(entries=[_svc()])
    _make_module(monkeypatch, fake)
    _base(state="stopped")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["service"]["Status"] == "stopped"
    request = _request(fake, "ModifyModelService")
    assert request.ServiceAction == "STOP"


def test_stop_request_carries_project_id(monkeypatch):
    fake = FakeTioneClient(entries=[_svc()])
    _make_module(monkeypatch, fake)
    _base(state="stopped", project_id="prj-xyz")
    run(mod.run_module)
    assert _request(fake, "ModifyModelService").TiProjectId == "prj-xyz"


def test_state_change_check_mode_is_dry_run(monkeypatch):
    fake = FakeTioneClient(entries=[_svc()])
    _make_module(monkeypatch, fake)
    _base(_ansible_check_mode=True, state="stopped")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["service"]["Status"] == "normal"
    assert "ModifyModelService" not in _ops(fake)


# ---------------------------------------------------------------------------
# transitional states
# ---------------------------------------------------------------------------


def test_transitional_with_wait_converges(monkeypatch):
    fake = FakeTioneClient(entries=[_svc(Status="creating")])
    fake.status_seq[MS_ID] = ["creating", "normal"]
    _make_module(monkeypatch, fake)
    _base(state="running")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["service"]["Status"] == "normal"


def test_transitional_without_wait_fails(monkeypatch):
    fake = FakeTioneClient(entries=[_svc(Status="creating")])
    _make_module(monkeypatch, fake)
    _base(state="running", wait=False)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "transitioning; enable wait" in exc.value.args[0]["msg"]


# ---------------------------------------------------------------------------
# guards / failure paths
# ---------------------------------------------------------------------------


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        def get_code(self):
            return "UnsupportedOperation"

        def get_request_id(self):
            return "req-xyz"

    class ExplodingClient(object):
        def DescribeModelService(self, request):
            raise Boom("connection dropped")

    _make_module(monkeypatch, ExplodingClient())
    _base(state="running")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]
