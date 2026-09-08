"""Unit tests for the tsf_lane write module (run_module flows).

Drives ``run_module()`` against an in-memory fake TSF client whose create /
modify / delete operations mutate a small traffic-lane store so the
post-write ``DescribeLanes`` re-read converges immediately.

Scenario matrix:

* absent on a missing lane, by name and by ``lane_id`` (idempotent no-op)
* absent check-mode dry run, real delete, and a rejected-delete failure
* creation guard (``deployment_groups`` required), create happy path and
  check mode
* no-op when the lane already matches (name/remark/groups)
* remark/name drift updates and a rejected-update failure
* immutable deployment-group membership drift
* multiple exact-name matches fail
* blanket SDK failure envelope
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import tsf_lane as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

LANE = {
    "LaneId": "lane-00000001",
    "LaneName": "checkout-canary",
    "Remark": "Canary request path",
    "LaneGroupList": [
        {"GroupId": "group-a", "Entrance": True},
        {"GroupId": "group-b", "Entrance": False},
    ],
}


def _lane(**overrides):
    item = copy.deepcopy(LANE)
    item.update(overrides)
    return item


def _args(**overrides):
    params = {"name": "checkout-canary"}
    params.update(overrides)
    return module_args(**params)


def _groups(*pairs):
    return [{"group_id": group_id, "entrance": entrance} for group_id, entrance in pairs]


class FakeTsfClient(object):
    """In-memory TSF client mutating a small traffic-lane store."""

    def __init__(self, lanes=None):
        self.lanes = [copy.deepcopy(t) for t in (lanes or [])]
        self.calls = []
        self._seq = 0

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def DescribeLanes(self, request):
        self._record("DescribeLanes", request)
        lane_ids = list(getattr(request, "LaneIdList", None) or [])
        if lane_ids:
            matches = [t for t in self.lanes if t.get("LaneId") in lane_ids]
        else:
            word = getattr(request, "SearchWord", None)
            if word is not None:
                matches = [t for t in self.lanes if t.get("LaneName") == word]
            else:
                matches = list(self.lanes)
        return SimpleNamespace(Result=SimpleNamespace(Content=[FakeResource(t) for t in matches]))

    def CreateLane(self, request):
        self._record("CreateLane", request)
        self._seq += 1
        stored_groups = [
            {"GroupId": g.GroupId, "Entrance": bool(g.Entrance)}
            for g in (getattr(request, "LaneGroupList", None) or [])
        ]
        item = {
            "LaneId": "lane-fake%04d" % self._seq,
            "LaneName": getattr(request, "LaneName", None),
            "Remark": getattr(request, "Remark", None),
            "LaneGroupList": stored_groups,
        }
        self.lanes.append(item)
        return SimpleNamespace(Result=item["LaneId"])

    def ModifyLane(self, request):
        self._record("ModifyLane", request)
        item = next((t for t in self.lanes if t.get("LaneId") == getattr(request, "LaneId", None)), None)
        if item is not None:
            item["LaneName"] = getattr(request, "LaneName", item.get("LaneName"))
            remark = getattr(request, "Remark", None)
            if remark is not None:
                item["Remark"] = remark
        return SimpleNamespace(Result=True, RequestId="req-fake")

    def DeleteLane(self, request):
        self._record("DeleteLane", request)
        lane_id = getattr(request, "LaneId", None)
        self.lanes = [t for t in self.lanes if t.get("LaneId") != lane_id]
        return SimpleNamespace(Result=True, RequestId="req-fake")


def _make_module(monkeypatch, fake):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (FakeModels(), SimpleNamespace(TsfClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


# ---------------------------------------------------------------------------
# absent flows
# ---------------------------------------------------------------------------


def test_absent_missing_by_name_is_idempotent(monkeypatch):
    fake = FakeTsfClient(lanes=[])
    _make_module(monkeypatch, fake)
    _args(state="absent", name="ghost-lane")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["lane"] is None
    assert [c for c, unused in fake.calls] == ["DescribeLanes"]


def test_absent_missing_by_id_is_idempotent(monkeypatch):
    fake = FakeTsfClient(lanes=[])
    _make_module(monkeypatch, fake)
    module_args(state="absent", name="checkout-canary", lane_id="lane-nope")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["lane"] is None


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeTsfClient(lanes=[_lane()])
    _make_module(monkeypatch, fake)
    _args(_ansible_check_mode=True, state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["lane"] is None
    assert len(fake.lanes) == 1
    assert "DeleteLane" not in [c for c, unused in fake.calls]


def test_absent_deletes_lane(monkeypatch):
    fake = FakeTsfClient(lanes=[_lane()])
    _make_module(monkeypatch, fake)
    _args(state="absent", lane_id="lane-00000001")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["lane"] is None
    assert fake.lanes == []
    delete = next(request for op, request in fake.calls if op == "DeleteLane")
    assert delete.LaneId == "lane-00000001"


def test_absent_rejected_delete_fails(monkeypatch):
    fake = FakeTsfClient(lanes=[_lane()])
    fake.DeleteLane = lambda request: (unused for unused in ()).throw(
        AssertionError("must patch result")
    )

    class RejectingClient(object):
        def __init__(self, inner):
            self.inner = inner

        def DescribeLanes(self, request):
            return self.inner.DescribeLanes(request)

        def DeleteLane(self, request):
            self.inner.calls.append(("DeleteLane", request))
            return SimpleNamespace(Result=False, RequestId="req-reject")

    _make_module(monkeypatch, RejectingClient(fake))
    _args(state="absent", lane_id="lane-00000001")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "rejected the TSF lane deletion" in exc.value.args[0]["msg"]


# ---------------------------------------------------------------------------
# creation flows
# ---------------------------------------------------------------------------


def test_create_requires_deployment_groups(monkeypatch):
    fake = FakeTsfClient(lanes=[])
    _make_module(monkeypatch, fake)
    _args(state="present")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "deployment_groups is required when creating" in exc.value.args[0]["msg"]


def test_create_lane_happy_path(monkeypatch):
    fake = FakeTsfClient(lanes=[])
    _make_module(monkeypatch, fake)
    _args(
        state="present",
        remark="Canary request path",
        deployment_groups=_groups(("group-a", True), ("group-b", False)),
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["lane"]["LaneName"] == "checkout-canary"
    assert result["lane"]["Remark"] == "Canary request path"
    assert [(g["GroupId"], g["Entrance"]) for g in result["lane"]["LaneGroupList"]] == [
        ("group-a", True),
        ("group-b", False),
    ]
    assert len(fake.lanes) == 1
    ops = [c for c, unused in fake.calls]
    assert ops[0] == "DescribeLanes"
    assert "CreateLane" in ops
    create = next(request for op, request in fake.calls if op == "CreateLane")
    assert create.LaneName == "checkout-canary"
    assert create.Remark == "Canary request path"
    assert sorted((g.GroupId, bool(g.Entrance)) for g in create.LaneGroupList) == [
        ("group-a", True),
        ("group-b", False),
    ]


def test_create_check_mode_is_dry_run(monkeypatch):
    fake = FakeTsfClient(lanes=[])
    _make_module(monkeypatch, fake)
    _args(
        _ansible_check_mode=True,
        state="present",
        remark="Canary request path",
        deployment_groups=_groups(("group-a", True), ("group-b", False)),
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["lane"]["LaneName"] == "checkout-canary"
    assert fake.lanes == []
    assert "CreateLane" not in [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# existing-lane flows
# ---------------------------------------------------------------------------


def test_existing_lane_no_drift_is_idempotent(monkeypatch):
    fake = FakeTsfClient(lanes=[_lane()])
    _make_module(monkeypatch, fake)
    _args(
        state="present",
        remark="Canary request path",
        deployment_groups=_groups(("group-a", True), ("group-b", False)),
    )
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["lane"]["LaneId"] == "lane-00000001"
    assert "ModifyLane" not in [c for c, unused in fake.calls]


def test_remark_drift_updates(monkeypatch):
    fake = FakeTsfClient(lanes=[_lane()])
    _make_module(monkeypatch, fake)
    _args(
        state="present",
        remark="Updated remark",
        deployment_groups=_groups(("group-a", True), ("group-b", False)),
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["lane"]["Remark"] == "Updated remark"
    modify = next(request for op, request in fake.calls if op == "ModifyLane")
    assert modify.LaneId == "lane-00000001"
    assert modify.LaneName == "checkout-canary"
    assert modify.Remark == "Updated remark"


def test_name_drift_updates_by_lane_id(monkeypatch):
    fake = FakeTsfClient(lanes=[_lane()])
    _make_module(monkeypatch, fake)
    _args(state="present", lane_id="lane-00000001", name="checkout-canary-v2")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["lane"]["LaneName"] == "checkout-canary-v2"
    assert result["lane"]["Remark"] == "Canary request path"  # untouched
    modify = next(request for op, request in fake.calls if op == "ModifyLane")
    assert modify.LaneName == "checkout-canary-v2"


def test_immutable_deployment_groups_drift_fails(monkeypatch):
    fake = FakeTsfClient(lanes=[_lane()])
    _make_module(monkeypatch, fake)
    _args(
        state="present",
        deployment_groups=_groups(("group-z", True)),
    )
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "Immutable fields cannot be changed" in payload["msg"]
    assert "LaneGroupList" in payload["immutable_changes"]
    assert payload["replacement_required"] is True


def test_update_rejected_result_fails(monkeypatch):
    fake = FakeTsfClient(lanes=[_lane()])

    class RejectingClient(object):
        def __init__(self, inner):
            self.inner = inner

        def DescribeLanes(self, request):
            return self.inner.DescribeLanes(request)

        def ModifyLane(self, request):
            self.inner.calls.append(("ModifyLane", request))
            return SimpleNamespace(Result=False, RequestId="req-reject")

    _make_module(monkeypatch, RejectingClient(fake))
    _args(state="present", remark="Updated remark")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "rejected the TSF lane update" in exc.value.args[0]["msg"]


# ---------------------------------------------------------------------------
# ambiguity and failure paths
# ---------------------------------------------------------------------------


def test_multiple_exact_name_matches_fail(monkeypatch):
    fake = FakeTsfClient(lanes=[_lane(), _lane(LaneId="lane-00000002")])
    _make_module(monkeypatch, fake)
    _args(state="present")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "Multiple TSF lanes matched the exact name" in exc.value.args[0]["msg"]


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        def get_code(self):
            # Not classified as retryable so sdk_call does not sleep through
            # its backoff curve before the module builds the error payload.
            return "AuthFailure.SignatureFailure"

    class ExplodingClient(object):
        def DescribeLanes(self, request):
            raise Boom("connection dropped")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    _args(state="present")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]
    assert payload["error_code"] == "AuthFailure.SignatureFailure"
