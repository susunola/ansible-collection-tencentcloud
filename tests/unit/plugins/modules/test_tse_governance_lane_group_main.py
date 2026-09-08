"""Unit tests for the tse_governance_lane_group write module (run_module flows).

Drives ``run_module()`` end to end against an in-memory fake TSE client whose
create/modify/delete operations mutate a lane-group store so the post-write
``wait`` reconciliation converges immediately.

Scenario matrix:

* absent on a missing group (idempotent no-op)
* absent with a matching group (check-mode dry run and the real delete)
* creation when missing (missing-name guard, check mode, waiting)
* no-op when the group already matches
* drift updates (rename, description) through ``ModifyGovernanceLaneGroups``
* unsuccessful-operation responses and the multiple-match guard
* the blanket ``sdk_error_payload`` failure path
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import tse_governance_lane_group as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

LANE_GROUP = {
    "ID": "lane-1a2b3c4d",
    "Name": "checkout-gray",
    "Description": "gray release",
    "TrafficEntries": [{"Namespace": "production", "Service": "edge-gateway"}],
    "Destinations": [{"Namespace": "production", "Service": "checkout"}],
    "Rules": [{"Name": "gray", "Enable": True}],
}


def _lane(**overrides):
    item = copy.deepcopy(LANE_GROUP)
    item.update(overrides)
    return item


def _base(**overrides):
    params = {"instance_id": "ins-abc123"}
    params.update(overrides)
    return module_args(**params)


class FakeTseLaneClient(object):
    """In-memory TSE governance lane-group client."""

    def __init__(self, groups=None):
        self.groups = [copy.deepcopy(t) for t in (groups or [])]
        self.calls = []
        self._next = 0
        self.result = True

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def DescribeGovernanceLaneGroups(self, request):
        self._record("DescribeGovernanceLaneGroups", request)
        return SimpleNamespace(LaneGroups=[FakeResource(t) for t in self.groups], Total=len(self.groups))

    def _lane_data(self, request):
        first = (getattr(request, "LaneGroups", None) or [None])[0]
        return copy.deepcopy(dict(getattr(first, "__dict__", {}) or {}))

    def CreateGovernanceLaneGroups(self, request):
        self._record("CreateGovernanceLaneGroups", request)
        self._next += 1
        item = self._lane_data(request)
        item["ID"] = "lane-new-%03d" % self._next
        self.groups.append(item)
        return SimpleNamespace(Result=self.result, RequestId="req-fake")

    def ModifyGovernanceLaneGroups(self, request):
        self._record("ModifyGovernanceLaneGroups", request)
        data = self._lane_data(request)
        lane_id = data.get("ID")
        for item in self.groups:
            if item.get("ID") == lane_id:
                item.update(data)
        return SimpleNamespace(Result=self.result, RequestId="req-fake")

    def DeleteGovernanceLaneGroups(self, request):
        self._record("DeleteGovernanceLaneGroups", request)
        data = self._lane_data(request)
        lane_id = data.get("ID")
        self.groups = [t for t in self.groups if t.get("ID") != lane_id]
        return SimpleNamespace(Result=self.result, RequestId="req-fake")


def _make_module(monkeypatch, fake, models=None):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (models or FakeModels(), SimpleNamespace(TseClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


# ---------------------------------------------------------------------------
# absent flows
# ---------------------------------------------------------------------------


def test_absent_missing_group_is_idempotent(monkeypatch):
    fake = FakeTseLaneClient(groups=[])
    _make_module(monkeypatch, fake)
    _base(state="absent", lane_group_id="lane-ghost")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["lane_group"] is None
    assert [c for c, unused in fake.calls] == ["DescribeGovernanceLaneGroups"]


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeTseLaneClient(groups=[_lane()])
    _make_module(monkeypatch, fake)
    _base(_ansible_check_mode=True, state="absent", lane_group_id="lane-1a2b3c4d")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["lane_group"] is None
    assert len(fake.groups) == 1
    assert "DeleteGovernanceLaneGroups" not in [c for c, unused in fake.calls]


def test_absent_deletes_group(monkeypatch):
    fake = FakeTseLaneClient(groups=[_lane()])
    _make_module(monkeypatch, fake)
    _base(state="absent", lane_group_id="lane-1a2b3c4d")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["lane_group"] is None
    assert fake.groups == []
    ops = [c for c, unused in fake.calls]
    assert "DeleteGovernanceLaneGroups" in ops


def test_absent_deletes_by_name(monkeypatch):
    fake = FakeTseLaneClient(groups=[_lane()])
    _make_module(monkeypatch, fake)
    _base(state="absent", name="checkout-gray")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert fake.groups == []


# ---------------------------------------------------------------------------
# creation flows
# ---------------------------------------------------------------------------


def test_create_requires_name_when_missing(monkeypatch):
    fake = FakeTseLaneClient(groups=[])
    _make_module(monkeypatch, fake)
    _base(state="present", lane_group_id="lane-unknown")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "name is required to create a TSE governance lane group" in exc.value.args[0]["msg"]


def test_create_group(monkeypatch):
    fake = FakeTseLaneClient(groups=[])
    _make_module(monkeypatch, fake)
    _base(
        state="present",
        name="checkout-gray",
        traffic_entries=[{"Namespace": "production", "Service": "edge-gateway"}],
        destinations=[{"Namespace": "production", "Service": "checkout"}],
        rules=[{"Name": "gray", "Enable": True}],
        description="gray release",
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["lane_group"]["Name"] == "checkout-gray"
    assert result["lane_group"]["ID"].startswith("lane-new-")
    assert len(fake.groups) == 1
    ops = [c for c, unused in fake.calls]
    assert ops[0] == "DescribeGovernanceLaneGroups"
    assert "CreateGovernanceLaneGroups" in ops


def test_create_check_mode_is_dry_run(monkeypatch):
    fake = FakeTseLaneClient(groups=[])
    _make_module(monkeypatch, fake)
    _base(
        _ansible_check_mode=True,
        state="present",
        name="checkout-gray",
        traffic_entries=[{"Namespace": "production", "Service": "edge-gateway"}],
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["lane_group"]["Name"] == "checkout-gray"
    assert "ID" not in result["lane_group"]
    assert fake.groups == []
    assert "CreateGovernanceLaneGroups" not in [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# existing-group flows
# ---------------------------------------------------------------------------


def test_existing_group_no_drift_is_idempotent(monkeypatch):
    fake = FakeTseLaneClient(groups=[_lane()])
    _make_module(monkeypatch, fake)
    _base(
        state="present",
        lane_group_id="lane-1a2b3c4d",
        name="checkout-gray",
        traffic_entries=[{"Namespace": "production", "Service": "edge-gateway"}],
        destinations=[{"Namespace": "production", "Service": "checkout"}],
        rules=[{"Name": "gray", "Enable": True}],
        description="gray release",
    )
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["lane_group"]["ID"] == "lane-1a2b3c4d"


def test_update_description(monkeypatch):
    fake = FakeTseLaneClient(groups=[_lane()])
    _make_module(monkeypatch, fake)
    _base(state="present", lane_group_id="lane-1a2b3c4d", name="checkout-gray", description="renamed description")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["lane_group"]["Description"] == "renamed description"
    ops = [c for c, unused in fake.calls]
    assert "ModifyGovernanceLaneGroups" in ops


def test_rename_group_by_id(monkeypatch):
    fake = FakeTseLaneClient(groups=[_lane()])
    _make_module(monkeypatch, fake)
    _base(state="present", lane_group_id="lane-1a2b3c4d", name="checkout-blue")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["lane_group"]["Name"] == "checkout-blue"
    ops = [c for c, unused in fake.calls]
    assert "ModifyGovernanceLaneGroups" in ops


def test_update_check_mode_is_dry_run(monkeypatch):
    fake = FakeTseLaneClient(groups=[_lane()])
    _make_module(monkeypatch, fake)
    _base(_ansible_check_mode=True, state="present", lane_group_id="lane-1a2b3c4d", name="checkout-blue")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["lane_group"]["Name"] == "checkout-blue"
    assert "ModifyGovernanceLaneGroups" not in [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# guards / failure paths
# ---------------------------------------------------------------------------


def test_unsuccessful_operation_fails(monkeypatch):
    fake = FakeTseLaneClient(groups=[])
    fake.result = False
    _make_module(monkeypatch, fake)
    _base(state="present", name="checkout-gray")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "TSE governance lane group operation returned an unsuccessful result"
    assert payload["operation"] == "CreateGovernanceLaneGroups"


def test_multiple_matches_fail(monkeypatch):
    fake = FakeTseLaneClient(groups=[_lane(), _lane(ID="lane-dup")])
    _make_module(monkeypatch, fake)
    _base(state="present", name="checkout-gray")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "Multiple TSE governance lane groups matched; specify lane_group_id" in exc.value.args[0]["msg"]


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeGovernanceLaneGroups(self, request):
            raise Boom("connection dropped")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    _base(state="present", name="checkout-gray")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]
