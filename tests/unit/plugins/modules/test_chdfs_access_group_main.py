"""Unit tests for the chdfs_access_group write module (run_module flows).

Drives ``run_module()`` against an in-memory fake CHDFS client whose
create / modify / delete operations mutate an access-group store so
post-write describes converge immediately.

Scenario matrix:

* absent on a missing group, identified by name or by ``access_group_id``
  (idempotent no-op)
* absent with a matching group (check-mode dry run, real delete)
* creation when missing (happy path, check mode, missing-parameter guard)
* no-op when the group already matches (name/description)
* description drift triggers an update; VpcType/VpcId drift is immutable
* paginated lookups and the ambiguous-name-match guard
* the blanket SDK failure path
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import chdfs_access_group as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

ACCESS_GROUP = {
    "AccessGroupId": "ag-1001",
    "AccessGroupName": "analytics-access",
    "VpcType": 1,
    "VpcId": "vpc-etl",
    "Description": "ETL pipeline readers",
}


def _group(**overrides):
    item = copy.deepcopy(ACCESS_GROUP)
    item.update(overrides)
    return item


def _create_params(**overrides):
    params = {
        "state": "present",
        "name": "analytics-access",
        "vpc_type": 1,
        "vpc_id": "vpc-etl",
        "description": "ETL pipeline readers",
    }
    params.update(overrides)
    return module_args(**params)


def _id_args(**overrides):
    params = {"access_group_id": "ag-1001", "name": "analytics-access"}
    params.update(overrides)
    return module_args(**params)


class FakeChdfsClient(object):
    """In-memory CHDFS client mutating a small access-group store."""

    def __init__(self, groups=None, page_size=None):
        self.groups = [copy.deepcopy(t) for t in (groups or [])]
        self.calls = []
        self.page_size = page_size
        self._next = 0

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def _next_id(self):
        self._next += 1
        return "ag-%d" % (1000 + self._next)

    def DescribeAccessGroups(self, request):
        self._record("DescribeAccessGroups", request)
        marker = getattr(request, "AccessGroupIdMarker", None)
        if self.page_size and marker is None:
            page = self.groups[: self.page_size]
            return SimpleNamespace(
                AccessGroups=[FakeResource(t) for t in page],
                IsOver=False,
                NextAccessGroupIdMarker="page-2",
            )
        page = self.groups[self.page_size:] if self.page_size else self.groups
        return SimpleNamespace(
            AccessGroups=[FakeResource(t) for t in page],
            IsOver=True,
            NextAccessGroupIdMarker=None,
        )

    def CreateAccessGroup(self, request):
        self._record("CreateAccessGroup", request)
        item = {
            "AccessGroupId": self._next_id(),
            "AccessGroupName": getattr(request, "AccessGroupName", None),
            "VpcType": getattr(request, "VpcType", None),
            "VpcId": getattr(request, "VpcId", None),
            "Description": getattr(request, "Description", None),
        }
        self.groups.append(item)
        return SimpleNamespace(AccessGroup=SimpleNamespace(AccessGroupId=item["AccessGroupId"]))

    def ModifyAccessGroup(self, request):
        self._record("ModifyAccessGroup", request)
        group_id = getattr(request, "AccessGroupId", None)
        for item in self.groups:
            if item.get("AccessGroupId") == group_id:
                item["AccessGroupName"] = getattr(request, "AccessGroupName", item.get("AccessGroupName"))
                item["Description"] = getattr(request, "Description", item.get("Description"))
        return SimpleNamespace(RequestId="req-fake")

    def DeleteAccessGroup(self, request):
        self._record("DeleteAccessGroup", request)
        group_id = getattr(request, "AccessGroupId", None)
        self.groups = [t for t in self.groups if t.get("AccessGroupId") != group_id]
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake, models=None):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (models or FakeModels(), SimpleNamespace(ChdfsClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


# ---------------------------------------------------------------------------
# absent flows
# ---------------------------------------------------------------------------


def test_absent_missing_by_name_is_idempotent(monkeypatch):
    fake = FakeChdfsClient(groups=[])
    _make_module(monkeypatch, fake)
    module_args(state="absent", name="ghost-group")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["access_group"] is None
    assert [c for c, unused in fake.calls] == ["DescribeAccessGroups"]


def test_absent_missing_by_id_is_idempotent(monkeypatch):
    fake = FakeChdfsClient(groups=[])
    _make_module(monkeypatch, fake)
    module_args(state="absent", access_group_id="ag-9999")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["access_group"] is None


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeChdfsClient(groups=[_group()])
    _make_module(monkeypatch, fake)
    module_args(_ansible_check_mode=True, state="absent", name="analytics-access")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["access_group"] is None
    assert len(fake.groups) == 1
    assert "DeleteAccessGroup" not in [c for c, unused in fake.calls]


def test_absent_deletes_group(monkeypatch):
    fake = FakeChdfsClient(groups=[_group()])
    _make_module(monkeypatch, fake)
    module_args(state="absent", access_group_id="ag-1001")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["access_group"] is None
    assert fake.groups == []
    assert "DeleteAccessGroup" in [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# creation flows
# ---------------------------------------------------------------------------


def test_create_requires_creation_parameters(monkeypatch):
    fake = FakeChdfsClient(groups=[])
    _make_module(monkeypatch, fake)
    module_args(state="present", name="analytics-access")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "creation parameters are required for a CHDFS access group"
    assert payload["missing"] == ["vpc_type", "vpc_id"]


def test_create_group(monkeypatch):
    fake = FakeChdfsClient(groups=[])
    _make_module(monkeypatch, fake)
    _create_params()
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["access_group"]["AccessGroupName"] == "analytics-access"
    assert result["access_group"]["VpcType"] == 1
    assert result["access_group"]["VpcId"] == "vpc-etl"
    assert result["access_group"]["Description"] == "ETL pipeline readers"
    assert len(fake.groups) == 1
    ops = [c for c, unused in fake.calls]
    assert ops[0] == "DescribeAccessGroups"
    assert "CreateAccessGroup" in ops
    assert ops[-1] == "DescribeAccessGroups"  # follow-up find after create


def test_create_check_mode_is_dry_run(monkeypatch):
    fake = FakeChdfsClient(groups=[])
    _make_module(monkeypatch, fake)
    _create_params(_ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["access_group"] == {
        "AccessGroupName": "analytics-access",
        "Description": "ETL pipeline readers",
        "VpcType": 1,
        "VpcId": "vpc-etl",
    }
    assert fake.groups == []
    assert "CreateAccessGroup" not in [c for c, unused in fake.calls]


def test_create_uses_id_lookup_after_create(monkeypatch):
    # Two groups with identical names: creation keys the follow-up find on
    # access_group_id, so the fresh group is reported rather than an ambiguity.
    fake = FakeChdfsClient(groups=[])
    _make_module(monkeypatch, fake)
    module_args(state="present", name="dup", vpc_type=1, vpc_id="vpc-a")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["access_group"]["AccessGroupName"] == "dup"


# ---------------------------------------------------------------------------
# existing-group flows
# ---------------------------------------------------------------------------


def test_existing_group_no_drift_is_idempotent(monkeypatch):
    fake = FakeChdfsClient(groups=[_group()])
    _make_module(monkeypatch, fake)
    _create_params()
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["access_group"]["AccessGroupId"] == "ag-1001"
    assert "ModifyAccessGroup" not in [c for c, unused in fake.calls]


def test_description_drift_updates(monkeypatch):
    fake = FakeChdfsClient(groups=[_group()])
    _make_module(monkeypatch, fake)
    _create_params(description="Updated description")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["access_group"]["Description"] == "Updated description"
    assert "ModifyAccessGroup" in [c for c, unused in fake.calls]


def test_name_drift_updates(monkeypatch):
    fake = FakeChdfsClient(groups=[_group()])
    _make_module(monkeypatch, fake)
    _id_args(state="present", name="renamed-access")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["access_group"]["AccessGroupName"] == "renamed-access"


def test_vpc_type_drift_is_immutable(monkeypatch):
    fake = FakeChdfsClient(groups=[_group()])
    _make_module(monkeypatch, fake)
    _create_params(vpc_type=2)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "Immutable fields cannot be changed" in payload["msg"]
    assert payload["replacement_required"] is True
    assert payload["immutable_changes"]["VpcType"] == {"before": 1, "after": 2}


def test_vpc_id_drift_is_immutable(monkeypatch):
    fake = FakeChdfsClient(groups=[_group()])
    _make_module(monkeypatch, fake)
    _id_args(state="present", vpc_id="vpc-other")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "Immutable fields cannot be changed" in payload["msg"]
    assert set(payload["immutable_changes"].keys()) == {"VpcId"}


def test_find_paginates_until_group_found(monkeypatch):
    fake = FakeChdfsClient(groups=[_group(AccessGroupId="ag-1", AccessGroupName="first"), _group(AccessGroupId="ag-2", AccessGroupName="second")], page_size=1)
    _make_module(monkeypatch, fake)
    module_args(state="present", name="second", vpc_type=1, vpc_id="vpc-etl")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["access_group"]["AccessGroupId"] == "ag-2"
    describes = [r for c, r in fake.calls if c == "DescribeAccessGroups"]
    assert len(describes) == 2


def test_ambiguous_name_match_fails(monkeypatch):
    fake = FakeChdfsClient(groups=[_group(), _group(AccessGroupId="ag-1002")])
    _make_module(monkeypatch, fake)
    module_args(state="present", name="analytics-access")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "specify access_group_id" in exc.value.args[0]["msg"]


# ---------------------------------------------------------------------------
# failure paths
# ---------------------------------------------------------------------------


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeAccessGroups(self, request):
            raise Boom("connection dropped")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    _create_params()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]
