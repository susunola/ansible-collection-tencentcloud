"""Unit tests for the eb_event_bus write module (run_module flows).

Drives ``run_module()`` against an in-memory fake EventBridge client whose
create / update / delete operations mutate an event-bus store so
post-write describes converge immediately.

Scenario matrix:

* absent on a missing bus (idempotent no-op)
* absent with a matching bus (check-mode dry run, real delete)
* creation when missing (happy path, check mode, missing-name guard)
* no-op when the bus already matches (name/description/retention/storage)
* drift updates through UpdateEventBus, including keeping remote values for
  omitted save_days/enable_store/name, plus the ambiguous-match guard and
  the blanket SDK failure paths
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import eb_event_bus as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

BUS = {
    "EventBusId": "eb-l8q2abcd",
    "EventBusName": "production-events",
    "Description": "Production application events",
    "SaveDays": 7,
    "EnableStore": True,
}


def _bus(**overrides):
    item = copy.deepcopy(BUS)
    item.update(overrides)
    return item


def _present_args(**overrides):
    params = {
        "state": "present",
        "name": "production-events",
        "description": "Production application events",
        "save_days": 7,
        "enable_store": True,
    }
    params.update(overrides)
    return module_args(**params)


class FakeEbClient(object):
    """In-memory EventBridge client mutating a small event-bus store."""

    def __init__(self, buses=None):
        self.buses = [copy.deepcopy(t) for t in (buses or [])]
        self.calls = []
        self._next = 0

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def _by_id(self, bus_id):
        for item in self.buses:
            if item.get("EventBusId") == bus_id:
                return item
        return None

    def ListEventBuses(self, request):
        self._record("ListEventBuses", request)
        return SimpleNamespace(EventBuses=[FakeResource(copy.deepcopy(t)) for t in self.buses])

    def GetEventBus(self, request):
        self._record("GetEventBus", request)
        item = self._by_id(getattr(request, "EventBusId", None))
        if item is None:
            return FakeResource({})
        value = copy.deepcopy(item)
        value["RequestId"] = "req-fake"
        return FakeResource(value)

    def CreateEventBus(self, request):
        self._record("CreateEventBus", request)
        self._next += 1
        item = {
            "EventBusId": "eb-new%04d" % self._next,
            "EventBusName": getattr(request, "EventBusName", None),
            "Description": getattr(request, "Description", None) or "",
            "SaveDays": getattr(request, "SaveDays", None),
            "EnableStore": getattr(request, "EnableStore", None),
        }
        self.buses.append(item)
        return SimpleNamespace(EventBusId=item["EventBusId"], RequestId="req-fake")

    def UpdateEventBus(self, request):
        self._record("UpdateEventBus", request)
        item = self._by_id(getattr(request, "EventBusId", None))
        if item is not None:
            name = getattr(request, "EventBusName", None)
            if name is not None:
                item["EventBusName"] = name
            item["Description"] = getattr(request, "Description", item.get("Description"))
            save_days = getattr(request, "SaveDays", None)
            if save_days is not None:
                item["SaveDays"] = save_days
            enable_store = getattr(request, "EnableStore", None)
            if enable_store is not None:
                item["EnableStore"] = enable_store
        return SimpleNamespace(RequestId="req-fake")

    def DeleteEventBus(self, request):
        self._record("DeleteEventBus", request)
        bus_id = getattr(request, "EventBusId", None)
        self.buses = [t for t in self.buses if t.get("EventBusId") != bus_id]
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake, models=None):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (models or FakeModels(), SimpleNamespace(EbClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


# ---------------------------------------------------------------------------
# absent flows
# ---------------------------------------------------------------------------


def test_absent_missing_bus_is_idempotent(monkeypatch):
    fake = FakeEbClient(buses=[])
    _make_module(monkeypatch, fake)
    module_args(state="absent", name="ghost-bus")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["event_bus"] is None
    assert [c for c, unused in fake.calls] == ["ListEventBuses"]


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeEbClient(buses=[_bus()])
    _make_module(monkeypatch, fake)
    module_args(_ansible_check_mode=True, state="absent", name="production-events")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["event_bus"] is None
    assert len(fake.buses) == 1
    assert "DeleteEventBus" not in [c for c, unused in fake.calls]


def test_absent_deletes_bus(monkeypatch):
    fake = FakeEbClient(buses=[_bus()])
    _make_module(monkeypatch, fake)
    module_args(state="absent", event_bus_id="eb-l8q2abcd")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["event_bus"] is None
    assert fake.buses == []
    assert "DeleteEventBus" in [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# creation flows
# ---------------------------------------------------------------------------


def test_create_bus(monkeypatch):
    fake = FakeEbClient(buses=[])
    _make_module(monkeypatch, fake)
    _present_args()
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["event_bus"]["EventBusId"] == "eb-new0001"
    assert result["event_bus"]["EventBusName"] == "production-events"
    assert result["event_bus"]["EnableStore"] is True
    assert len(fake.buses) == 1
    ops = [c for c, unused in fake.calls]
    assert ops[0] == "ListEventBuses"
    assert "CreateEventBus" in ops
    assert ops[-1] == "GetEventBus"


def test_create_check_mode_returns_target(monkeypatch):
    fake = FakeEbClient(buses=[])
    _make_module(monkeypatch, fake)
    _present_args(_ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["event_bus"] == {
        "EventBusName": "production-events",
        "Description": "Production application events",
        "SaveDays": 7,
        "EnableStore": True,
    }
    assert "diff" in result
    assert fake.buses == []
    assert "CreateEventBus" not in [c for c, unused in fake.calls]


def test_create_without_name_fails(monkeypatch):
    fake = FakeEbClient(buses=[])
    _make_module(monkeypatch, fake)
    module_args(state="present", event_bus_id="eb-l8q2abcd", description="desc")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "name is required when creating an event bus" in exc.value.args[0]["msg"]


# ---------------------------------------------------------------------------
# existing-bus flows
# ---------------------------------------------------------------------------


def test_existing_bus_no_drift_is_idempotent(monkeypatch):
    fake = FakeEbClient(buses=[_bus()])
    _make_module(monkeypatch, fake)
    _present_args()
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["event_bus"]["EventBusId"] == "eb-l8q2abcd"
    assert "UpdateEventBus" not in [c for c, unused in fake.calls]


def test_description_drift_updates(monkeypatch):
    fake = FakeEbClient(buses=[_bus()])
    _make_module(monkeypatch, fake)
    _present_args(description="Updated description")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["event_bus"]["Description"] == "Updated description"
    ops = [c for c, unused in fake.calls]
    assert "UpdateEventBus" in ops
    assert ops[-1] == "GetEventBus"


def test_save_days_drift_updates(monkeypatch):
    fake = FakeEbClient(buses=[_bus()])
    _make_module(monkeypatch, fake)
    _present_args(save_days=30)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["event_bus"]["SaveDays"] == 30
    assert "UpdateEventBus" in [c for c, unused in fake.calls]


def test_omitted_fields_keep_remote_values(monkeypatch):
    # Only description is provided; name/save_days/enable_store fall back to
    # the current values, so the update rewrites description alone.
    fake = FakeEbClient(buses=[_bus()])
    _make_module(monkeypatch, fake)
    module_args(state="present", event_bus_id="eb-l8q2abcd", description="Tweaked")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["event_bus"]["EventBusName"] == "production-events"
    assert result["event_bus"]["SaveDays"] == 7
    assert result["event_bus"]["EnableStore"] is True
    assert result["event_bus"]["Description"] == "Tweaked"


def test_update_check_mode_is_dry_run(monkeypatch):
    fake = FakeEbClient(buses=[_bus()])
    _make_module(monkeypatch, fake)
    _present_args(_ansible_check_mode=True, description="Preview")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["event_bus"]["Description"] == "Production application events"
    assert "diff" in result
    assert "UpdateEventBus" not in [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# guards and failure paths
# ---------------------------------------------------------------------------


def test_multiple_name_matches_fail(monkeypatch):
    fake = FakeEbClient(buses=[_bus(), _bus(EventBusId="eb-other01")])
    _make_module(monkeypatch, fake)
    _present_args()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "specify event_bus_id" in exc.value.args[0]["msg"]


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def ListEventBuses(self, request):
            raise Boom("connection dropped")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    _present_args()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]


def test_delete_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def ListEventBuses(self, request):
            return SimpleNamespace(EventBuses=[FakeResource(copy.deepcopy(_bus()))])

        def GetEventBus(self, request):
            value = copy.deepcopy(_bus())
            value["RequestId"] = "req-fake"
            return FakeResource(value)

        def DeleteEventBus(self, request):
            raise Boom("delete refused")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    module_args(state="absent", name="production-events")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "delete refused" in payload["error"]
