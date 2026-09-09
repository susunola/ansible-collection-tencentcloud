"""Unit tests for the clb_target_group write module (run_module flows).

Drives ``run_module()`` end to end against an in-memory fake CLB client whose
write operations mutate a small target-group store (group attributes plus a
per-group backend member set), so the post-write describe refetch and the
``wait_for_group`` waiter converge on the first poll.

Scenario matrix:

* absent on a missing target group (idempotent no-op)
* absent with a matching target group (check-mode dry run and the real
  delete)
* creation when missing (name/vpc creation guard, check-mode dry run, happy
  path with and without backend members)
* no-op when nothing drifts
* member reconciliation (addition, removal, weight change) and attribute
  drift updates (port), plus their check mode
* the ambiguous-name guard, the invalid-choice guard, required_one_of guard
* the blanket ``Tencent Cloud API request failed`` failure path
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import clb_target_group as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

GROUP_ID = "lbtg-abc123"
VPC_ID = "vpc-abc"

GROUP = {
    "TargetGroupId": GROUP_ID,
    "TargetGroupName": "api-backends",
    "VpcId": VPC_ID,
    "Type": "v2",
    "Protocol": "TCP",
    "Port": None,
    "ScheduleAlgorithm": None,
    "Weight": None,
}


def _group(**overrides):
    item = copy.deepcopy(GROUP)
    item.update(overrides)
    return item


def _base(**overrides):
    # NOTE: keys carrying ``choices`` (state, type, protocol,
    # schedule_algorithm) must not be pre-filled with None.
    # target_group_id/name are a required_one_of pair so the _name_args/
    # _id_args helpers supply exactly one of them.
    params = {}
    params.update(overrides)
    return module_args(**params)


def _name_args(**overrides):
    params = {"name": "api-backends"}
    params.update(overrides)
    return module_args(**params)


def _id_args(**overrides):
    params = {"target_group_id": GROUP_ID}
    params.update(overrides)
    return module_args(**params)


def _member(ip, port, weight):
    return {"BindIP": ip, "Port": port, "Weight": weight}


class FakeClbClient(object):
    """In-memory CLB client mutating a small target-group + member store."""

    def __init__(self, groups=None, members=None):
        self.groups = [copy.deepcopy(t) for t in (groups or [])]
        self.members = {}
        for group_id, instances in (members or {}).items():
            self.members[group_id] = [copy.deepcopy(t) for t in instances]
        self.calls = []

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def _group(self, group_id):
        for item in self.groups:
            if item.get("TargetGroupId") == group_id:
                return item
        return None

    def DescribeTargetGroups(self, request):
        self._record("DescribeTargetGroups", request)
        ids = list(getattr(request, "TargetGroupIds", None) or [])
        if ids:
            page = [dict(t) for t in self.groups if t.get("TargetGroupId") in ids]
        else:
            page = [dict(t) for t in self.groups]
            for item in (getattr(request, "Filters", None) or []):
                name = getattr(item, "Name", None)
                values = list(getattr(item, "Values", None) or [])
                if not values:
                    continue
                if name == "TargetGroupName":
                    page = [t for t in page if t.get("TargetGroupName") == values[0]]
                elif name == "VpcId":
                    page = [t for t in page if t.get("VpcId") == values[0]]
        return SimpleNamespace(
            TargetGroupSet=[FakeResource(t) for t in page],
            TotalCount=len(page),
        )

    def DescribeTargetGroupInstances(self, request):
        self._record("DescribeTargetGroupInstances", request)
        group_id = None
        for item in (getattr(request, "Filters", None) or []):
            if getattr(item, "Name", None) == "TargetGroupId":
                values = list(getattr(item, "Values", None) or [])
                group_id = values[0] if values else None
        instances = self.members.get(group_id, [])
        return SimpleNamespace(
            TargetGroupInstanceSet=[FakeResource(dict(t)) for t in instances],
            TotalCount=len(instances),
        )

    def CreateTargetGroup(self, request):
        self._record("CreateTargetGroup", request)
        group_id = "lbtg-new-%d" % (len(self.groups) + 1)
        item = {
            "TargetGroupId": group_id,
            "TargetGroupName": getattr(request, "TargetGroupName", None),
            "VpcId": getattr(request, "VpcId", None),
            "Type": getattr(request, "Type", "v2"),
            "Protocol": getattr(request, "Protocol", "TCP"),
            "Port": getattr(request, "Port", None),
            "ScheduleAlgorithm": getattr(request, "ScheduleAlgorithm", None),
            "Weight": getattr(request, "Weight", None),
        }
        self.groups.append(item)
        self.members.setdefault(group_id, [])
        return SimpleNamespace(TargetGroupId=group_id, RequestId="req-fake")

    def ModifyTargetGroupAttribute(self, request):
        self._record("ModifyTargetGroupAttribute", request)
        item = self._group(getattr(request, "TargetGroupId", None))
        if item is not None:
            for attr in ("TargetGroupName", "Port", "ScheduleAlgorithm", "Weight"):
                value = getattr(request, attr, None)
                if value is not None:
                    item[attr] = value
        return SimpleNamespace(RequestId="req-fake")

    def RegisterTargetGroupInstances(self, request):
        self._record("RegisterTargetGroupInstances", request)
        group_id = getattr(request, "TargetGroupId", None)
        store = self.members.setdefault(group_id, [])
        for value in (getattr(request, "TargetGroupInstances", None) or []):
            store.append(_member(getattr(value, "BindIP", None), getattr(value, "Port", None), getattr(value, "Weight", None)))
        return SimpleNamespace(RequestId="req-fake")

    def DeregisterTargetGroupInstances(self, request):
        self._record("DeregisterTargetGroupInstances", request)
        group_id = getattr(request, "TargetGroupId", None)
        store = self.members.setdefault(group_id, [])
        wanted = []
        for value in (getattr(request, "TargetGroupInstances", None) or []):
            wanted.append(_member(getattr(value, "BindIP", None), getattr(value, "Port", None), getattr(value, "Weight", None)))
        self.members[group_id] = [m for m in store if m not in wanted]
        return SimpleNamespace(RequestId="req-fake")

    def DeleteTargetGroups(self, request):
        self._record("DeleteTargetGroups", request)
        ids = list(getattr(request, "TargetGroupIds", None) or [])
        self.groups = [t for t in self.groups if t.get("TargetGroupId") not in ids]
        for group_id in ids:
            self.members.pop(group_id, None)
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake, models=None):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load_clb", lambda: (models or FakeModels(), SimpleNamespace(ClbClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


# ---------------------------------------------------------------------------
# absent flows
# ---------------------------------------------------------------------------


def test_absent_missing_group_is_idempotent(monkeypatch):
    fake = FakeClbClient(groups=[])
    _make_module(monkeypatch, fake)
    _id_args(state="absent", target_group_id="lbtg-ghost")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["target_group"] is None
    assert result["msg"] == "Target group is absent"
    assert [c for c, unused in fake.calls] == ["DescribeTargetGroups"]


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeClbClient(groups=[_group()])
    _make_module(monkeypatch, fake)
    _id_args(_ansible_check_mode=True, state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["msg"] == "Would delete target group"
    assert result["target_group"]["TargetGroupId"] == GROUP_ID
    assert len(fake.groups) == 1
    assert "DeleteTargetGroups" not in [c for c, unused in fake.calls]


def test_absent_deletes_group(monkeypatch):
    fake = FakeClbClient(groups=[_group()], members={GROUP_ID: [_member("10.0.1.10", 8080, 10)]})
    _make_module(monkeypatch, fake)
    _id_args(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["msg"] == "Target group deleted"
    assert result["target_group"] is None
    assert fake.groups == []
    assert fake.members == {}
    assert "DeleteTargetGroups" in [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# creation flows
# ---------------------------------------------------------------------------


def test_create_requires_name_and_vpc(monkeypatch):
    fake = FakeClbClient(groups=[])
    _make_module(monkeypatch, fake)
    _name_args(state="present", name="ghost-group")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "name and vpc_id are required when creating" in exc.value.args[0]["msg"]


def test_create_check_mode_is_dry_run(monkeypatch):
    fake = FakeClbClient(groups=[])
    _make_module(monkeypatch, fake)
    _name_args(
        _ansible_check_mode=True,
        state="present",
        vpc_id=VPC_ID,
        instances=[{"ip": "10.0.1.10", "port": 8080, "weight": 20}],
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["msg"] == "Would create target group"
    assert result["target_group"] is None
    assert fake.groups == []
    assert "CreateTargetGroup" not in [c for c, unused in fake.calls]


def test_create_group_without_instances(monkeypatch):
    fake = FakeClbClient(groups=[])
    _make_module(monkeypatch, fake)
    _name_args(state="present", vpc_id=VPC_ID, port=8080)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["msg"] == "Target group created"
    group = result["target_group"]
    assert group["TargetGroupName"] == "api-backends"
    assert group["Instances"] == []
    assert len(fake.groups) == 1
    ops = [c for c, unused in fake.calls]
    assert ops[0] == "DescribeTargetGroups"
    assert "CreateTargetGroup" in ops


def test_create_group_with_instances(monkeypatch):
    fake = FakeClbClient(groups=[])
    _make_module(monkeypatch, fake)
    _name_args(
        state="present",
        vpc_id=VPC_ID,
        instances=[
            {"ip": "10.0.1.10", "port": 8080, "weight": 20},
            {"ip": "10.0.1.11", "port": 8080, "weight": 10},
        ],
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["msg"] == "Target group created"
    assert result["target_group"]["Instances"] == [
        {"ip": "10.0.1.10", "port": 8080, "weight": 20},
        {"ip": "10.0.1.11", "port": 8080, "weight": 10},
    ]
    ops = [c for c, unused in fake.calls]
    assert "RegisterTargetGroupInstances" in ops


# ---------------------------------------------------------------------------
# existing-group flows
# ---------------------------------------------------------------------------


def test_existing_no_drift_is_idempotent(monkeypatch):
    fake = FakeClbClient(groups=[_group()])
    _make_module(monkeypatch, fake)
    _name_args(state="present", vpc_id=VPC_ID)
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["msg"] == "Target group is up to date"
    assert result["target_group"]["TargetGroupId"] == GROUP_ID
    assert "ModifyTargetGroupAttribute" not in [c for c, unused in fake.calls]
    assert "RegisterTargetGroupInstances" not in [c for c, unused in fake.calls]


def test_add_members(monkeypatch):
    fake = FakeClbClient(groups=[_group()])
    _make_module(monkeypatch, fake)
    _id_args(state="present", name="api-backends", instances=[{"ip": "10.0.1.10", "port": 8080}])
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["msg"] == "Target group updated"
    assert result["target_group"]["Instances"] == [{"ip": "10.0.1.10", "port": 8080, "weight": 10}]
    ops = [c for c, unused in fake.calls]
    assert "RegisterTargetGroupInstances" in ops
    assert "DeregisterTargetGroupInstances" not in ops


def test_remove_members(monkeypatch):
    fake = FakeClbClient(
        groups=[_group()],
        members={GROUP_ID: [_member("10.0.1.10", 8080, 10), _member("10.0.1.11", 8080, 10)]},
    )
    _make_module(monkeypatch, fake)
    _id_args(state="present", name="api-backends", instances=[{"ip": "10.0.1.10", "port": 8080, "weight": 10}])
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["target_group"]["Instances"] == [{"ip": "10.0.1.10", "port": 8080, "weight": 10}]
    ops = [c for c, unused in fake.calls]
    assert "DeregisterTargetGroupInstances" in ops


def test_member_weight_change(monkeypatch):
    fake = FakeClbClient(groups=[_group()], members={GROUP_ID: [_member("10.0.1.10", 8080, 10)]})
    _make_module(monkeypatch, fake)
    _id_args(state="present", name="api-backends", instances=[{"ip": "10.0.1.10", "port": 8080, "weight": 50}])
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["target_group"]["Instances"] == [{"ip": "10.0.1.10", "port": 8080, "weight": 50}]
    ops = [c for c, unused in fake.calls]
    assert "DeregisterTargetGroupInstances" in ops
    assert "RegisterTargetGroupInstances" in ops


def test_update_port_attribute(monkeypatch):
    fake = FakeClbClient(groups=[_group(Port=80)])
    _make_module(monkeypatch, fake)
    _id_args(state="present", name="api-backends", port=9090)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["msg"] == "Target group updated"
    assert result["target_group"]["Port"] == 9090
    assert fake.groups[0]["Port"] == 9090
    assert "ModifyTargetGroupAttribute" in [c for c, unused in fake.calls]


def test_update_check_mode_is_dry_run(monkeypatch):
    fake = FakeClbClient(groups=[_group(Port=80)], members={GROUP_ID: [_member("10.0.1.10", 8080, 10)]})
    _make_module(monkeypatch, fake)
    _id_args(
        _ansible_check_mode=True,
        state="present",
        name="api-backends",
        port=9090,
        instances=[{"ip": "10.0.1.20", "port": 9090, "weight": 10}],
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["msg"] == "Would update target group"
    assert fake.groups[0]["Port"] == 80
    assert fake.members[GROUP_ID] == [_member("10.0.1.10", 8080, 10)]
    assert "ModifyTargetGroupAttribute" not in [c for c, unused in fake.calls]
    assert "RegisterTargetGroupInstances" not in [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# guards / validation / failure paths
# ---------------------------------------------------------------------------


def test_ambiguous_name_fails(monkeypatch):
    fake = FakeClbClient(groups=[_group(), _group(TargetGroupId="lbtg-dup")])
    _make_module(monkeypatch, fake)
    _name_args(state="present", vpc_id=VPC_ID)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "Ambiguous target group reference" in payload["msg"]
    assert payload["ambiguous"] is True
    assert payload["match_count"] == 2


def test_missing_identity_fails(monkeypatch):
    fake = FakeClbClient(groups=[])
    _make_module(monkeypatch, fake)
    _base(state="absent")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "target_group_id" in payload["msg"]
    assert "name" in payload["msg"]


def test_invalid_protocol_choice_fails(monkeypatch):
    fake = FakeClbClient(groups=[])
    _make_module(monkeypatch, fake)
    _name_args(state="present", vpc_id=VPC_ID, protocol="ICMP")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "value of protocol must be one of" in exc.value.args[0]["msg"]


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeTargetGroups(self, request):
            raise Boom("connection dropped")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    _id_args(state="present", name="api-backends")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]


# ---------------------------------------------------------------------------
# legacy helper regression tests (folded from test_clb_target_group.py)
# ---------------------------------------------------------------------------


def test_builders_and_member_normalization():
    models = FakeModels()
    params = {
        "name": "api",
        "vpc_id": "vpc-1",
        "type": "v2",
        "protocol": "HTTP",
        "port": 8080,
        "schedule_algorithm": "WRR",
        "weight": 10,
        "tags": {"env": "prod"},
    }
    request = mod.build_create_request(models, params)
    assert request.TargetGroupName == "api"
    assert request.Tags[0].TagKey == "env"
    members = mod._members([{"BindIP": "10.0.0.1", "Port": 8080, "Weight": 20}])
    assert members == [{"ip": "10.0.0.1", "port": 8080, "weight": 20}]


def test_create_main_path(monkeypatch):
    models = FakeModels()
    client = SimpleNamespace(CreateTargetGroup=MagicMock(return_value=SimpleNamespace(TargetGroupId="lbtg-1")))
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load_clb", lambda: (models, SimpleNamespace(ClbClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, cls, endpoint: client)
    monkeypatch.setattr(mod, "find_group", lambda *args: None)
    monkeypatch.setattr(mod, "wait_for_group", MagicMock(return_value={"TargetGroupId": "lbtg-1"}))
    module_args(state="present", name="api", vpc_id="vpc-1", protocol="HTTP", port=8080)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["target_group"]["TargetGroupId"] == "lbtg-1"
    client.CreateTargetGroup.assert_called_once()


def test_check_mode_create_does_not_write(monkeypatch):
    models = FakeModels()
    client = SimpleNamespace(CreateTargetGroup=MagicMock())
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load_clb", lambda: (models, SimpleNamespace(ClbClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, cls, endpoint: client)
    monkeypatch.setattr(mod, "find_group", lambda *args: None)
    module_args(state="present", name="api", vpc_id="vpc-1", protocol="HTTP", port=8080, _ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert "diff" in result
    client.CreateTargetGroup.assert_not_called()
