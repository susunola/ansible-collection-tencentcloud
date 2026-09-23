"""Unit tests for the tse_gateway_server_group write module (run_module flows).

Drives ``run_module()`` end to end against an in-memory fake TSE client whose
write operations mutate the gateway-group store, so the module's post-write
``find`` refetch and custom wait loops converge on the first poll.

Scenario matrix:

* absent on a missing group (idempotent no-op)
* absent on the default (``IsFirstGroup``) group (guard failure)
* absent delete (check-mode dry run and the real delete)
* creation when missing (missing creation parameters, happy path, check mode)
* no-op when nothing drifts
* metadata updates (name / description) and node resize
* the network-placement immutability guard (subnet / bandwidth)
* the multiple-match guard and the blanket SDK failure path
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
import json
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import tse_gateway_server_group as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

GROUP = {
    "GroupId": "group-sec-001",
    "Name": "production-secondary",
    "Status": "Running",
    "IsFirstGroup": 0,
    "SubnetIds": "subnet-1",
    "InternetMaxBandwidthOut": 2,
    "Description": "secondary production pool",
    "NodeConfig": {"Specification": "4c8g", "Number": 3},
}


def _group(**overrides):
    item = copy.deepcopy(GROUP)
    item.update(overrides)
    return item


def _base(**overrides):
    params = {"gateway_id": "gateway-1"}
    params.update(overrides)
    return module_args(**params)


class FakeTseClient(object):
    """In-memory TSE gateway server-group store."""

    def __init__(self, groups=None):
        self.groups = [copy.deepcopy(t) for t in (groups or [])]
        self.calls = []
        self._next = 0

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def _group(self, group_id):
        for item in self.groups:
            if item.get("GroupId") == group_id:
                return item
        return None

    def DescribeNativeGatewayServerGroups(self, request):
        self._record("DescribeNativeGatewayServerGroups", request)
        return SimpleNamespace(
            Result=SimpleNamespace(GatewayGroupList=[FakeResource(t) for t in self.groups]),
            RequestId="req-fake",
        )

    def CreateNativeGatewayServerGroup(self, request):
        self._record("CreateNativeGatewayServerGroup", request)
        self._next += 1
        self.groups.append({
            "GroupId": "group-new-%03d" % self._next,
            "Name": getattr(request, "Name", None),
            "NodeConfig": getattr(request, "NodeConfig", None),
            "SubnetIds": getattr(request, "SubnetId", None),
            "Description": getattr(request, "Description", None),
            "Status": "Running",
            "IsFirstGroup": 0,
        })
        item = self.groups[-1]
        return SimpleNamespace(Result=SimpleNamespace(GroupId=item["GroupId"], TaskId="task-1"))

    def ModifyNativeGatewayServerGroup(self, request):
        self._record("ModifyNativeGatewayServerGroup", request)
        item = self._group(getattr(request, "GroupId", None))
        if item is not None:
            if getattr(request, "Name", None) is not None:
                item["Name"] = request.Name
            if getattr(request, "Description", None) is not None:
                item["Description"] = request.Description
        return SimpleNamespace(Result=SimpleNamespace(TaskId="task-1"))

    def UpdateCloudNativeAPIGatewaySpec(self, request):
        self._record("UpdateCloudNativeAPIGatewaySpec", request)
        item = self._group(getattr(request, "GroupId", None))
        if item is not None:
            item["NodeConfig"] = getattr(request, "NodeConfig", None)
        return SimpleNamespace(Result=SimpleNamespace(TaskId="task-1"))

    def DeleteNativeGatewayServerGroup(self, request):
        self._record("DeleteNativeGatewayServerGroup", request)
        self.groups = [t for t in self.groups if t.get("GroupId") != getattr(request, "GroupId", None)]
        return SimpleNamespace(Result=SimpleNamespace(TaskId="task-1"))


def _make_module(monkeypatch, fake, models=None):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (models or FakeModels(), SimpleNamespace(TseClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


# ---------------------------------------------------------------------------
# absent flows
# ---------------------------------------------------------------------------


def test_absent_missing_group_is_idempotent(monkeypatch):
    fake = FakeTseClient(groups=[])
    _make_module(monkeypatch, fake)
    _base(state="absent", name="ghost")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["group"] is None
    assert [c for c, unused in fake.calls] == ["DescribeNativeGatewayServerGroups"]


def test_absent_default_group_fails(monkeypatch):
    fake = FakeTseClient(groups=[_group(IsFirstGroup=1)])
    _make_module(monkeypatch, fake)
    _base(state="absent", name="production-secondary")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "cannot be deleted" in exc.value.args[0]["msg"]


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeTseClient(groups=[_group()])
    _make_module(monkeypatch, fake)
    _base(_ansible_check_mode=True, state="absent", name="production-secondary")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["group"] is None
    assert len(fake.groups) == 1
    assert "DeleteNativeGatewayServerGroup" not in [c for c, unused in fake.calls]


def test_absent_deletes_group(monkeypatch):
    fake = FakeTseClient(groups=[_group()])
    _make_module(monkeypatch, fake)
    _base(state="absent", name="production-secondary")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["group"] is None
    assert fake.groups == []
    ops = [c for c, unused in fake.calls]
    assert "DeleteNativeGatewayServerGroup" in ops


def test_absent_by_group_id(monkeypatch):
    fake = FakeTseClient(groups=[_group()])
    _make_module(monkeypatch, fake)
    _base(state="absent", group_id="group-sec-001")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert fake.groups == []


# ---------------------------------------------------------------------------
# creation flows
# ---------------------------------------------------------------------------


def test_create_requires_creation_parameters(monkeypatch):
    fake = FakeTseClient(groups=[])
    _make_module(monkeypatch, fake)
    _base(state="present", name="new-group")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "creation parameters are required" in payload["msg"]
    assert payload["missing"] == ["node_config", "subnet_id"]


def test_create_group(monkeypatch):
    fake = FakeTseClient(groups=[])
    _make_module(monkeypatch, fake)
    _base(
        state="present",
        name="production-secondary",
        node_config={"Specification": "4c8g", "Number": 3},
        subnet_id="subnet-1",
        description="secondary production pool",
        internet_max_bandwidth_out=2,
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["group"]["Name"] == "production-secondary"
    assert result["group"]["NodeConfig"]["Number"] == 3
    assert fake.groups[0]["GroupId"].startswith("group-new-")
    ops = [c for c, unused in fake.calls]
    assert ops[0] == "DescribeNativeGatewayServerGroups"
    assert "CreateNativeGatewayServerGroup" in ops


def test_create_check_mode_is_dry_run(monkeypatch):
    fake = FakeTseClient(groups=[])
    _make_module(monkeypatch, fake)
    _base(
        _ansible_check_mode=True,
        state="present",
        name="production-secondary",
        node_config={"Specification": "4c8g", "Number": 3},
        subnet_id="subnet-1",
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["group"]["Name"] == "production-secondary"
    assert fake.groups == []
    assert "CreateNativeGatewayServerGroup" not in [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# existing-group flows
# ---------------------------------------------------------------------------


def test_existing_group_no_drift_is_idempotent(monkeypatch):
    fake = FakeTseClient(groups=[_group()])
    _make_module(monkeypatch, fake)
    _base(
        state="present",
        group_id="group-sec-001",
        name="production-secondary",
        description="secondary production pool",
        node_config={"Specification": "4c8g", "Number": 3},
    )
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["group"]["GroupId"] == "group-sec-001"


def test_rename_group(monkeypatch):
    fake = FakeTseClient(groups=[_group()])
    _make_module(monkeypatch, fake)
    _base(state="present", group_id="group-sec-001", name="production-secondary-v2")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["group"]["Name"] == "production-secondary-v2"
    ops = [c for c, unused in fake.calls]
    assert "ModifyNativeGatewayServerGroup" in ops
    assert "UpdateCloudNativeAPIGatewaySpec" not in ops


def test_update_description(monkeypatch):
    fake = FakeTseClient(groups=[_group()])
    _make_module(monkeypatch, fake)
    _base(state="present", group_id="group-sec-001", description="updated pool")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["group"]["Description"] == "updated pool"


def test_resize_group(monkeypatch):
    fake = FakeTseClient(groups=[_group()])
    _make_module(monkeypatch, fake)
    _base(state="present", group_id="group-sec-001", node_config={"Specification": "8c16g", "Number": 5})
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["group"]["NodeConfig"] == {"Specification": "8c16g", "Number": 5}
    ops = [c for c, unused in fake.calls]
    assert "UpdateCloudNativeAPIGatewaySpec" in ops
    assert "ModifyNativeGatewayServerGroup" not in ops


def test_metadata_and_resize_check_mode(monkeypatch):
    fake = FakeTseClient(groups=[_group()])
    _make_module(monkeypatch, fake)
    _base(
        _ansible_check_mode=True,
        state="present",
        group_id="group-sec-001",
        name="renamed",
        node_config={"Specification": "8c16g", "Number": 5},
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["group"]["Name"] == "renamed"
    assert "ModifyNativeGatewayServerGroup" not in [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# guards / failure paths
# ---------------------------------------------------------------------------


def test_subnet_immutable_fails(monkeypatch):
    fake = FakeTseClient(groups=[_group(SubnetIds="subnet-1")])
    _make_module(monkeypatch, fake)
    _base(state="present", group_id="group-sec-001", subnet_id="subnet-2")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "network placement is immutable" in payload["msg"]
    assert "SubnetIds" in payload["immutable_drift"]


def test_bandwidth_immutable_fails(monkeypatch):
    fake = FakeTseClient(groups=[_group(InternetMaxBandwidthOut=2)])
    _make_module(monkeypatch, fake)
    _base(state="present", group_id="group-sec-001", internet_max_bandwidth_out=5)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "network placement is immutable" in payload["msg"]
    assert "InternetMaxBandwidthOut" in payload["immutable_drift"]


def test_multiple_matches_fail(monkeypatch):
    fake = FakeTseClient(groups=[_group(), _group(GroupId="group-sec-002")])
    _make_module(monkeypatch, fake)
    _base(state="present", name="production-secondary")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "specify group_id" in exc.value.args[0]["msg"]


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class ExplodingClient(object):
        def DescribeNativeGatewayServerGroups(self, request):
            raise RuntimeError("connection dropped")

    _make_module(monkeypatch, ExplodingClient())
    _base(state="present", name="production-secondary")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]


# ---------------------------------------------------------------------------
# legacy helper regression tests (folded from test_tse_gateway_server_group.py)
# ---------------------------------------------------------------------------


class LegacyValue(object):
    def from_json_string(self, raw):
        self.raw = raw


class LegacyModels(object):
    CreateNativeGatewayServerGroupRequest = LegacyValue
    ModifyNativeGatewayServerGroupRequest = LegacyValue
    UpdateCloudNativeAPIGatewaySpecRequest = LegacyValue
    DeleteNativeGatewayServerGroupRequest = LegacyValue


def test_server_group_requests_map_full_lifecycle():
    p = {
        "gateway_id": "g1",
        "name": "workers",
        "node_config": {"Specification": "4c8g", "Number": 3},
        "subnet_id": "subnet-1",
        "description": "worker pool",
        "internet_max_bandwidth_out": None,
        "internet_config": None,
    }
    assert json.loads(mod.create_request(LegacyModels, p).raw)["SubnetId"] == "subnet-1"
    assert json.loads(mod.update_request(LegacyModels, p, "group-1", {"Name": "workers-v2", "Description": "new"}).raw)["GroupId"] == "group-1"
    assert json.loads(mod.resize_request(LegacyModels, p, "group-1").raw)["NodeConfig"]["Number"] == 3
    assert json.loads(mod.delete_request(LegacyModels, p, "group-1").raw) == {"GatewayId": "g1", "GroupId": "group-1"}
