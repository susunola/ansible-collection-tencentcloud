"""Unit tests for the vpc_address_template_group write module.

Drives ``run_module()`` against an in-memory fake VPC client whose
create / modify / delete operations mutate an address-template-group store
so post-write describes converge immediately.

Scenario matrix:

* the state=present parameter guard (name + member template_ids)
* absent on a missing group (idempotent no-op)
* absent with a matching group (check-mode dry run, real delete)
* creation when missing (happy path, check mode, create-refind via the nested
  ``AddressTemplateGroup`` response)
* no-op when the group already matches (order-invariant member-id set)
* member-set drift and rename through ModifyAddressTemplateGroupAttribute
* the ambiguous-match guard and the blanket SDK failure paths
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import vpc_address_template_group as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

GROUP = {
    "AddressTemplateGroupId": "ipmg-aaaa",
    "AddressTemplateGroupName": "trusted-sources",
    "AddressTemplateIdSet": ["ipm-1001", "ipm-1002"],
}


def _group(**overrides):
    item = copy.deepcopy(GROUP)
    item.update(overrides)
    return item


def _present_args(**overrides):
    params = {"state": "present", "name": "trusted-sources", "template_ids": ["ipm-1002", "ipm-1001"]}
    params.update(overrides)
    return module_args(**params)


class FakeVpcClient(object):
    """In-memory VPC client mutating a small template-group store."""

    def __init__(self, groups=None):
        self.groups = [copy.deepcopy(t) for t in (groups or [])]
        self.calls = []
        self._next = 0

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def _by_id(self, group_id):
        for item in self.groups:
            if item.get("AddressTemplateGroupId") == group_id:
                return item
        return None

    def DescribeAddressTemplateGroups(self, request):
        self._record("DescribeAddressTemplateGroups", request)
        return SimpleNamespace(
            AddressTemplateGroupSet=[FakeResource(copy.deepcopy(t)) for t in self.groups],
            TotalCount=len(self.groups),
        )

    def CreateAddressTemplateGroup(self, request):
        self._record("CreateAddressTemplateGroup", request)
        self._next += 1
        item = {
            "AddressTemplateGroupId": "ipmg-n%04d" % self._next,
            "AddressTemplateGroupName": getattr(request, "AddressTemplateGroupName", None),
            "AddressTemplateIdSet": list(getattr(request, "AddressTemplateIds", None) or []),
        }
        self.groups.append(item)
        return SimpleNamespace(AddressTemplateGroup=SimpleNamespace(AddressTemplateGroupId=item["AddressTemplateGroupId"]), RequestId="req-fake")

    def ModifyAddressTemplateGroupAttribute(self, request):
        self._record("ModifyAddressTemplateGroupAttribute", request)
        item = self._by_id(getattr(request, "AddressTemplateGroupId", None))
        if item is not None:
            item["AddressTemplateGroupName"] = getattr(request, "AddressTemplateGroupName", item.get("AddressTemplateGroupName"))
            item["AddressTemplateIdSet"] = list(getattr(request, "AddressTemplateIds", None) or [])
        return SimpleNamespace(RequestId="req-fake")

    def DeleteAddressTemplateGroup(self, request):
        self._record("DeleteAddressTemplateGroup", request)
        group_id = getattr(request, "AddressTemplateGroupId", None)
        self.groups = [t for t in self.groups if t.get("AddressTemplateGroupId") != group_id]
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake, models=None):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (models or FakeModels(), SimpleNamespace(VpcClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


# ---------------------------------------------------------------------------
# guards / absent flows
# ---------------------------------------------------------------------------


def test_present_requires_template_ids(monkeypatch):
    fake = FakeVpcClient(groups=[])
    _make_module(monkeypatch, fake)
    module_args(state="present", name="trusted-sources", template_ids=[])
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "name and template_ids are required" in exc.value.args[0]["msg"]


def test_absent_missing_group_is_idempotent(monkeypatch):
    fake = FakeVpcClient(groups=[])
    _make_module(monkeypatch, fake)
    module_args(state="absent", name="ghost-group")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["address_template_group"] is None
    assert [c for c, unused in fake.calls] == ["DescribeAddressTemplateGroups"]


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeVpcClient(groups=[_group()])
    _make_module(monkeypatch, fake)
    module_args(_ansible_check_mode=True, state="absent", name="trusted-sources")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["address_template_group"]["AddressTemplateGroupId"] == "ipmg-aaaa"
    assert len(fake.groups) == 1
    assert "DeleteAddressTemplateGroup" not in [c for c, unused in fake.calls]


def test_absent_deletes_group(monkeypatch):
    fake = FakeVpcClient(groups=[_group()])
    _make_module(monkeypatch, fake)
    module_args(state="absent", group_id="ipmg-aaaa")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["address_template_group"] is None
    assert fake.groups == []
    assert "DeleteAddressTemplateGroup" in [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# creation flows
# ---------------------------------------------------------------------------


def test_create_group(monkeypatch):
    fake = FakeVpcClient(groups=[])
    _make_module(monkeypatch, fake)
    _present_args()  # template_ids given in reverse order
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["address_template_group"]["AddressTemplateGroupId"] == "ipmg-n0001"
    assert result["address_template_group"]["AddressTemplateIdSet"] == ["ipm-1001", "ipm-1002"]
    assert len(fake.groups) == 1
    ops = [c for c, unused in fake.calls]
    assert ops[0] == "DescribeAddressTemplateGroups"
    assert "CreateAddressTemplateGroup" in ops
    assert ops[-1] == "DescribeAddressTemplateGroups"


def test_create_check_mode_is_dry_run(monkeypatch):
    fake = FakeVpcClient(groups=[])
    _make_module(monkeypatch, fake)
    _present_args(_ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["address_template_group"] is None
    assert "diff" in result
    assert fake.groups == []
    assert "CreateAddressTemplateGroup" not in [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# existing-group flows
# ---------------------------------------------------------------------------


def test_existing_group_no_drift_is_idempotent(monkeypatch):
    fake = FakeVpcClient(groups=[_group()])
    _make_module(monkeypatch, fake)
    _present_args()
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["address_template_group"]["AddressTemplateGroupId"] == "ipmg-aaaa"
    assert "ModifyAddressTemplateGroupAttribute" not in [c for c, unused in fake.calls]


def test_member_set_drift_updates(monkeypatch):
    fake = FakeVpcClient(groups=[_group()])
    _make_module(monkeypatch, fake)
    _present_args(template_ids=["ipm-1001"])
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["address_template_group"]["AddressTemplateIdSet"] == ["ipm-1001"]
    assert fake.groups[0]["AddressTemplateIdSet"] == ["ipm-1001"]
    assert "ModifyAddressTemplateGroupAttribute" in [c for c, unused in fake.calls]


def test_rename_by_group_id(monkeypatch):
    fake = FakeVpcClient(groups=[_group()])
    _make_module(monkeypatch, fake)
    _present_args(group_id="ipmg-aaaa", name="renamed-sources")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["address_template_group"]["AddressTemplateGroupName"] == "renamed-sources"
    assert "ModifyAddressTemplateGroupAttribute" in [c for c, unused in fake.calls]


def test_update_check_mode_is_dry_run(monkeypatch):
    fake = FakeVpcClient(groups=[_group()])
    _make_module(monkeypatch, fake)
    _present_args(_ansible_check_mode=True, template_ids=["ipm-1001"])
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["address_template_group"]["AddressTemplateIdSet"] == ["ipm-1001", "ipm-1002"]
    assert "diff" in result
    assert fake.groups[0]["AddressTemplateIdSet"] == ["ipm-1001", "ipm-1002"]
    assert "ModifyAddressTemplateGroupAttribute" not in [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# guards and failure paths
# ---------------------------------------------------------------------------


def test_multiple_name_matches_fail(monkeypatch):
    fake = FakeVpcClient(groups=[_group(), _group(AddressTemplateGroupId="ipmg-bbbb")])
    _make_module(monkeypatch, fake)
    _present_args()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "specify group_id" in exc.value.args[0]["msg"]


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeAddressTemplateGroups(self, request):
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
        def DescribeAddressTemplateGroups(self, request):
            return SimpleNamespace(AddressTemplateGroupSet=[FakeResource(copy.deepcopy(_group()))], TotalCount=1)

        def DeleteAddressTemplateGroup(self, request):
            raise Boom("delete refused")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    module_args(state="absent", name="trusted-sources")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "delete refused" in payload["error"]
