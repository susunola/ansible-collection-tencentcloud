"""Unit tests for the organization_node write module (run_module flows).

Drives ``run_module()`` end to end against an in-memory fake Organization
client whose write operations mutate the node store so the post-write
``find_node`` waiter converges immediately.

Scenario matrix:

* absent on a missing node (idempotent no-op)
* absent with a matching node (check-mode dry run and the real delete)
* creation when missing (check-mode dry run, waiting)
* no-op when nothing drifts
* drift updates (rename, remark through ``UpdateOrganizationNode``)
* the parent-move and tag-change guards
* the multiple-match guard and the blanket ``sdk_error_payload`` path
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import organization_node as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

NODE = {
    "NodeId": 101,
    "ParentNodeId": 1001,
    "Name": "Production",
    "Remark": "",
    "Tags": [],
}


def _node(**overrides):
    item = copy.deepcopy(NODE)
    item.update(overrides)
    return item


def _base(**overrides):
    params = {"name": "Production", "parent_node_id": 1001}
    params.update(overrides)
    return module_args(**params)


class FakeOrganizationClient(object):
    """In-memory Organization client mutating a small node store."""

    def __init__(self, nodes=None):
        self.nodes = [copy.deepcopy(t) for t in (nodes or [])]
        self.calls = []
        self._next = 0

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def _find(self, node_id):
        for item in self.nodes:
            if item.get("NodeId") == node_id:
                return item
        return None

    def DescribeOrganizationNodes(self, request):
        self._record("DescribeOrganizationNodes", request)
        return SimpleNamespace(Items=[FakeResource(t) for t in self.nodes], Total=len(self.nodes))

    def AddOrganizationNode(self, request):
        self._record("AddOrganizationNode", request)
        self._next += 1
        item = {
            "NodeId": 200 + self._next,
            "ParentNodeId": getattr(request, "ParentNodeId", None),
            "Name": getattr(request, "Name", None),
            "Remark": getattr(request, "Remark", ""),
            "Tags": [{"TagKey": tag.TagKey, "TagValue": tag.TagValue} for tag in (getattr(request, "Tags", None) or [])],
        }
        self.nodes.append(item)
        return SimpleNamespace(NodeId=item["NodeId"], RequestId="req-fake")

    def UpdateOrganizationNode(self, request):
        self._record("UpdateOrganizationNode", request)
        item = self._find(getattr(request, "NodeId", None))
        if item is not None:
            item["Name"] = getattr(request, "Name", item.get("Name"))
            item["Remark"] = getattr(request, "Remark", item.get("Remark"))
        return SimpleNamespace(RequestId="req-fake")

    def DeleteOrganizationNodes(self, request):
        self._record("DeleteOrganizationNodes", request)
        node_ids = set(getattr(request, "NodeId", None) or [])
        self.nodes = [t for t in self.nodes if t.get("NodeId") not in node_ids]
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake, models=None):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load_organization", lambda: (models or FakeModels(), SimpleNamespace(OrganizationClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


# ---------------------------------------------------------------------------
# absent flows
# ---------------------------------------------------------------------------


def test_absent_missing_node_is_idempotent(monkeypatch):
    fake = FakeOrganizationClient(nodes=[])
    _make_module(monkeypatch, fake)
    _base(state="absent", name="ghost-node")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["node"] is None
    assert [c for c, unused in fake.calls] == ["DescribeOrganizationNodes"]


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeOrganizationClient(nodes=[_node()])
    _make_module(monkeypatch, fake)
    _base(_ansible_check_mode=True, state="absent", name=None, node_id=101)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["node"] is not None
    assert len(fake.nodes) == 1
    assert "DeleteOrganizationNodes" not in [c for c, unused in fake.calls]


def test_absent_deletes_node(monkeypatch):
    fake = FakeOrganizationClient(nodes=[_node()])
    _make_module(monkeypatch, fake)
    _base(state="absent", name=None, node_id=101)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["node"] is None
    assert fake.nodes == []
    ops = [c for c, unused in fake.calls]
    assert "DeleteOrganizationNodes" in ops


# ---------------------------------------------------------------------------
# creation flows
# ---------------------------------------------------------------------------


def test_present_requires_name_and_parent(monkeypatch):
    fake = FakeOrganizationClient(nodes=[])
    _make_module(monkeypatch, fake)
    module_args(state="present", node_id=101)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    msg = exc.value.args[0]["msg"]
    assert "parent_node_id" in msg and "name" in msg


def test_create_node(monkeypatch):
    fake = FakeOrganizationClient(nodes=[])
    _make_module(monkeypatch, fake)
    _base(
        state="present",
        name="New Business Unit",
        parent_node_id=1001,
        remark="new bu",
        tags={"env": "prod"},
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["node"]["Name"] == "New Business Unit"
    assert result["node"]["Remark"] == "new bu"
    assert result["node"]["Tags"] == [{"TagKey": "env", "TagValue": "prod"}]
    assert len(fake.nodes) == 1
    ops = [c for c, unused in fake.calls]
    assert ops[0] == "DescribeOrganizationNodes"
    assert "AddOrganizationNode" in ops


def test_create_check_mode_is_dry_run(monkeypatch):
    fake = FakeOrganizationClient(nodes=[])
    _make_module(monkeypatch, fake)
    _base(_ansible_check_mode=True, state="present", name="New Business Unit", parent_node_id=1001)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["node"] is None
    assert fake.nodes == []
    assert "AddOrganizationNode" not in [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# existing-node flows
# ---------------------------------------------------------------------------


def test_existing_node_no_drift_is_idempotent(monkeypatch):
    fake = FakeOrganizationClient(nodes=[_node()])
    _make_module(monkeypatch, fake)
    _base(state="present", name="Production", parent_node_id=1001)
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["node"]["NodeId"] == 101


def test_rename_node(monkeypatch):
    fake = FakeOrganizationClient(nodes=[_node()])
    _make_module(monkeypatch, fake)
    _base(state="present", node_id=101, name="Renamed BU", parent_node_id=1001)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["node"]["Name"] == "Renamed BU"
    ops = [c for c, unused in fake.calls]
    assert "UpdateOrganizationNode" in ops


def test_update_remark(monkeypatch):
    fake = FakeOrganizationClient(nodes=[_node()])
    _make_module(monkeypatch, fake)
    _base(state="present", node_id=101, name="Production", parent_node_id=1001, remark="core business")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["node"]["Remark"] == "core business"
    ops = [c for c, unused in fake.calls]
    assert "UpdateOrganizationNode" in ops


def test_update_check_mode_is_dry_run(monkeypatch):
    fake = FakeOrganizationClient(nodes=[_node()])
    _make_module(monkeypatch, fake)
    _base(_ansible_check_mode=True, state="present", node_id=101, name="Renamed BU", parent_node_id=1001)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["node"]["Name"] == "Production"
    assert "UpdateOrganizationNode" not in [c for c, unused in fake.calls]


def test_parent_move_fails(monkeypatch):
    fake = FakeOrganizationClient(nodes=[_node()])
    _make_module(monkeypatch, fake)
    _base(state="present", node_id=101, name="Production", parent_node_id=2002)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "parent cannot be changed" in payload["msg"]
    assert payload["current_parent_node_id"] == 1001


def test_tag_change_fails(monkeypatch):
    fake = FakeOrganizationClient(nodes=[_node(Tags=[{"TagKey": "env", "TagValue": "prod"}])])
    _make_module(monkeypatch, fake)
    _base(state="present", node_id=101, name="Production", parent_node_id=1001, tags={"env": "dev"})
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "tags cannot be changed" in payload["msg"]
    assert payload["current_tags"] == {"env": "prod"}


def test_multiple_matches_fail(monkeypatch):
    fake = FakeOrganizationClient(nodes=[_node(), _node(NodeId=102)])
    _make_module(monkeypatch, fake)
    _base(state="present", name="Production", parent_node_id=1001)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "Multiple Organization nodes have the requested name under the parent" in exc.value.args[0]["msg"]


# ---------------------------------------------------------------------------
# failure paths
# ---------------------------------------------------------------------------


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeOrganizationNodes(self, request):
            raise Boom("connection dropped")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    _base(state="present", name="Production", parent_node_id=1001)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]
