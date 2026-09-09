"""Unit tests for the dnspod_line_group write module (run_module flows).

Drives ``run_module()`` against an in-memory fake DNSPod client whose custom
line-group store is mutated by create / modify / delete so post-write
describes converge immediately.

Scenario matrix:

* absent on a missing group (idempotent no-op)
* absent with a matching group (check-mode dry run, real delete)
* creation when missing (happy path, check mode, group_id-not-found guard)
* no-op when the group already matches (name and exact line membership)
* line membership drift reconciles the exact set
* rename by ``line_group_id``; rename-by-name-alone creates a new group
* an ambiguous name match fails
* the blanket SDK failure path
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import dnspod_line_group as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

GROUP = {
    "Id": 1001,
    "Name": "corporate-networks",
    "Lines": ["office-network", "vpn-network"],
}


def _group(**overrides):
    item = copy.deepcopy(GROUP)
    item.update(overrides)
    return item


def _name_args(**overrides):
    params = {
        "domain": "example.com",
        "name": "corporate-networks",
        "lines": ["office-network", "vpn-network"],
    }
    params.update(overrides)
    return module_args(**params)


def _id_args(**overrides):
    params = {
        "domain": "example.com",
        "line_group_id": 1001,
        "name": "corporate-networks",
        "lines": ["office-network", "vpn-network"],
    }
    params.update(overrides)
    return module_args(**params)


class FakeDnspodClient(object):
    """In-memory DNSPod client mutating a custom line-group store."""

    def __init__(self, groups=None):
        self.groups = [copy.deepcopy(t) for t in (groups or [])]
        self.calls = []
        self._next = 0

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def _by_id(self, group_id):
        for item in self.groups:
            if item.get("Id") == group_id:
                return item
        return None

    def DescribeLineGroupList(self, request):
        self._record("DescribeLineGroupList", request)
        return SimpleNamespace(
            LineGroups=[FakeResource(t) for t in self.groups],
            Info=SimpleNamespace(Total=len(self.groups)),
        )

    def CreateLineGroup(self, request):
        self._record("CreateLineGroup", request)
        self._next += 1
        self.groups.append(
            {
                "Id": 1000 + self._next,
                "Name": getattr(request, "Name", None),
                "Lines": (getattr(request, "Lines", "") or "").split(",") if getattr(request, "Lines", "") else [],
            }
        )
        return SimpleNamespace(RequestId="req-fake")

    def ModifyLineGroup(self, request):
        self._record("ModifyLineGroup", request)
        item = self._by_id(getattr(request, "LineGroupId", None))
        if item is not None:
            item["Name"] = getattr(request, "Name", item.get("Name"))
            item["Lines"] = (getattr(request, "Lines", "") or "").split(",") if getattr(request, "Lines", "") else []
        return SimpleNamespace(RequestId="req-fake")

    def DeleteLineGroup(self, request):
        self._record("DeleteLineGroup", request)
        group_id = getattr(request, "LineGroupId", None)
        self.groups = [t for t in self.groups if t.get("Id") != group_id]
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (FakeModels(), SimpleNamespace(DnspodClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


# ---------------------------------------------------------------------------
# absent flows
# ---------------------------------------------------------------------------


def test_absent_missing_group_is_idempotent(monkeypatch):
    fake = FakeDnspodClient(groups=[])
    _make_module(monkeypatch, fake)
    _name_args(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["line_group"] is None
    assert [c for c, unused in fake.calls] == ["DescribeLineGroupList"]


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeDnspodClient(groups=[_group()])
    _make_module(monkeypatch, fake)
    _name_args(_ansible_check_mode=True, state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["line_group"]["Id"] == 1001
    assert len(fake.groups) == 1
    assert "DeleteLineGroup" not in [c for c, unused in fake.calls]


def test_absent_deletes_group(monkeypatch):
    fake = FakeDnspodClient(groups=[_group()])
    _make_module(monkeypatch, fake)
    _name_args(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["line_group"] is None
    assert fake.groups == []
    ops = [c for c, unused in fake.calls]
    assert "DeleteLineGroup" in ops


# ---------------------------------------------------------------------------
# creation flows
# ---------------------------------------------------------------------------


def test_create_line_group(monkeypatch):
    fake = FakeDnspodClient(groups=[])
    _make_module(monkeypatch, fake)
    _name_args(state="present")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["line_group"]["Name"] == "corporate-networks"
    assert result["line_group"]["Lines"] == ["office-network", "vpn-network"]
    assert len(fake.groups) == 1
    ops = [c for c, unused in fake.calls]
    assert ops[0] == "DescribeLineGroupList"
    assert "CreateLineGroup" in ops


def test_create_check_mode_is_dry_run(monkeypatch):
    fake = FakeDnspodClient(groups=[])
    _make_module(monkeypatch, fake)
    _name_args(_ansible_check_mode=True, state="present")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert fake.groups == []
    assert "CreateLineGroup" not in [c for c, unused in fake.calls]


def test_group_id_not_found_blocks_creation(monkeypatch):
    fake = FakeDnspodClient(groups=[])
    _make_module(monkeypatch, fake)
    module_args(domain="example.com", line_group_id=9999, name="ghost-group", lines=["x"])
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "line_group_id was not found" in exc.value.args[0]["msg"]


# ---------------------------------------------------------------------------
# existing-group flows
# ---------------------------------------------------------------------------


def test_existing_group_no_drift_is_idempotent(monkeypatch):
    fake = FakeDnspodClient(groups=[_group()])
    _make_module(monkeypatch, fake)
    _name_args(state="present")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["line_group"]["Id"] == 1001
    assert "ModifyLineGroup" not in [c for c, unused in fake.calls]


def test_line_drift_reconciles_exact_set(monkeypatch):
    fake = FakeDnspodClient(groups=[_group()])
    _make_module(monkeypatch, fake)
    _name_args(state="present", lines=["office-network"])
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["line_group"]["Lines"] == ["office-network"]
    ops = [c for c, unused in fake.calls]
    assert "ModifyLineGroup" in ops


def test_rename_by_line_group_id(monkeypatch):
    fake = FakeDnspodClient(groups=[_group()])
    _make_module(monkeypatch, fake)
    _id_args(state="present", name="renamed-networks")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["line_group"]["Name"] == "renamed-networks"
    ops = [c for c, unused in fake.calls]
    assert "ModifyLineGroup" in ops


def test_rename_by_name_alone_creates_new_group(monkeypatch):
    fake = FakeDnspodClient(groups=[_group()])
    _make_module(monkeypatch, fake)
    _name_args(state="present", name="partner-networks", lines=["partner-vpn"])
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["line_group"]["Name"] == "partner-networks"
    assert [g["Name"] for g in fake.groups] == ["corporate-networks", "partner-networks"]


def test_ambiguous_name_match_fails(monkeypatch):
    fake = FakeDnspodClient(groups=[_group(), _group(Id=1002)])
    _make_module(monkeypatch, fake)
    _name_args(state="present")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "specify line_group_id" in exc.value.args[0]["msg"]


# ---------------------------------------------------------------------------
# failure paths
# ---------------------------------------------------------------------------


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeLineGroupList(self, request):
            raise Boom("connection dropped")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    _name_args(state="present")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]
