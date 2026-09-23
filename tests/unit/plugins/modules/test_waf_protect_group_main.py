"""Unit tests for the waf_protect_group write module (run_module flows).

Drives ``run_module()`` against an in-memory fake WAF client whose create /
modify / delete operations mutate a protection-group store so post-write
describes converge immediately.

Scenario matrix:

* absent on a missing group, identified by name or by ``group_id``
  (idempotent no-op)
* absent with a matching group (check-mode dry run, real delete)
* creation when missing (happy path, check mode, group_id-not-found guard)
* no-op when the group already matches (name/remark/domains)
* domain/remark drift updates and rename by ``group_id``
* rename-by-name-alone actually creates a separate group, the
  ambiguous-match guard and the blanket SDK failure path
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import waf_protect_group as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

GROUP = {
    "ID": 1001,
    "Name": "production-apps",
    "Remark": "Internet-facing applications",
    "Domains": [{"Domain": "api.example.com"}, {"Domain": "www.example.com"}],
}


def _group(**overrides):
    item = copy.deepcopy(GROUP)
    item.update(overrides)
    return item


def _domains(*names):
    return [{"Domain": name} for name in names]


def _name_args(**overrides):
    params = {"name": "production-apps"}
    params.update(overrides)
    return module_args(**params)


def _id_args(**overrides):
    params = {"group_id": 1001, "name": "production-apps"}
    params.update(overrides)
    return module_args(**params)


class FakeWafClient(object):
    """In-memory WAF client mutating a small protection-group store."""

    def __init__(self, groups=None):
        self.groups = [copy.deepcopy(t) for t in (groups or [])]
        self.calls = []
        self._next = 0

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def _by_id(self, group_id):
        for item in self.groups:
            if item.get("ID") == group_id:
                return item
        return None

    def DescribeProtectGroup(self, request):
        self._record("DescribeProtectGroup", request)
        filter_item = (getattr(request, "Filter", None) or [None])[0]
        field = getattr(filter_item, "Name", None) if filter_item is not None else None
        values = getattr(filter_item, "Values", None) or [] if filter_item is not None else []
        if field == "ID" and values:
            matches = [t for t in self.groups if str(t.get("ID")) == values[0]]
        elif field == "Name" and values:
            matches = [t for t in self.groups if t.get("Name") == values[0]]
        else:
            matches = list(self.groups)
        return SimpleNamespace(Data=[FakeResource(t) for t in matches], Total=len(matches))

    def CreateProtectGroup(self, request):
        self._record("CreateProtectGroup", request)
        self._next += 1
        item = {
            "ID": 1000 + self._next,
            "Name": getattr(request, "Name", None),
            "Remark": getattr(request, "Remark", None) or "",
            "Domains": [{"Domain": d} for d in (getattr(request, "Domains", None) or [])],
        }
        self.groups.append(item)
        return SimpleNamespace(RequestId="req-fake")

    def ModifyProtectGroup(self, request):
        self._record("ModifyProtectGroup", request)
        item = self._by_id(getattr(request, "GroupId", None))
        if item is not None:
            item["Name"] = getattr(request, "Name", item.get("Name"))
            item["Remark"] = getattr(request, "Remark", item.get("Remark"))
            item["Domains"] = [{"Domain": d} for d in (getattr(request, "Domains", None) or [])]
        return SimpleNamespace(RequestId="req-fake")

    def DeleteProtectGroup(self, request):
        self._record("DeleteProtectGroup", request)
        ids = list(getattr(request, "GroupIds", None) or [])
        self.groups = [t for t in self.groups if t.get("ID") not in ids]
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake, models=None):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (models or FakeModels(), SimpleNamespace(WafClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


# ---------------------------------------------------------------------------
# absent flows
# ---------------------------------------------------------------------------


def test_absent_missing_by_name_is_idempotent(monkeypatch):
    fake = FakeWafClient(groups=[])
    _make_module(monkeypatch, fake)
    _name_args(state="absent", name="ghost-group")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["protect_group"] is None
    assert [c for c, unused in fake.calls] == ["DescribeProtectGroup"]


def test_absent_missing_by_id_is_idempotent(monkeypatch):
    fake = FakeWafClient(groups=[])
    _make_module(monkeypatch, fake)
    module_args(state="absent", name="production-apps", group_id=9999)
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["protect_group"] is None


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeWafClient(groups=[_group()])
    _make_module(monkeypatch, fake)
    _name_args(_ansible_check_mode=True, state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["protect_group"]["ID"] == 1001
    assert len(fake.groups) == 1
    assert "DeleteProtectGroup" not in [c for c, unused in fake.calls]


def test_absent_deletes_group(monkeypatch):
    fake = FakeWafClient(groups=[_group()])
    _make_module(monkeypatch, fake)
    _id_args(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["protect_group"] is None
    assert fake.groups == []
    ops = [c for c, unused in fake.calls]
    assert "DeleteProtectGroup" in ops


# ---------------------------------------------------------------------------
# creation flows
# ---------------------------------------------------------------------------


def test_group_id_not_found_blocks_creation(monkeypatch):
    fake = FakeWafClient(groups=[])
    _make_module(monkeypatch, fake)
    module_args(state="present", name="production-apps", group_id=9999)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "group_id was not found" in exc.value.args[0]["msg"]


def test_create_group(monkeypatch):
    fake = FakeWafClient(groups=[])
    _make_module(monkeypatch, fake)
    _name_args(
        state="present",
        remark="Internet-facing applications",
        domains=["api.example.com", "www.example.com"],
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["protect_group"]["Name"] == "production-apps"
    assert result["protect_group"]["Domains"] == ["api.example.com", "www.example.com"]
    assert len(fake.groups) == 1
    ops = [c for c, unused in fake.calls]
    assert ops[0] == "DescribeProtectGroup"
    assert "CreateProtectGroup" in ops


def test_create_check_mode_is_dry_run(monkeypatch):
    fake = FakeWafClient(groups=[])
    _make_module(monkeypatch, fake)
    _name_args(_ansible_check_mode=True, state="present", domains=["api.example.com"])
    result = run(mod.run_module)
    assert result["changed"] is True
    assert fake.groups == []
    assert "CreateProtectGroup" not in [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# existing-group flows
# ---------------------------------------------------------------------------


def test_existing_group_no_drift_is_idempotent(monkeypatch):
    fake = FakeWafClient(groups=[_group()])
    _make_module(monkeypatch, fake)
    _name_args(
        state="present",
        remark="Internet-facing applications",
        domains=["api.example.com", "www.example.com"],
    )
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["protect_group"]["ID"] == 1001
    assert "ModifyProtectGroup" not in [c for c, unused in fake.calls]


def test_domain_drift_reconciles_exact_set(monkeypatch):
    fake = FakeWafClient(groups=[_group()])
    _make_module(monkeypatch, fake)
    _name_args(
        state="present",
        remark="Internet-facing applications",
        domains=["api.example.com"],
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["protect_group"]["Domains"] == ["api.example.com"]
    ops = [c for c, unused in fake.calls]
    assert "ModifyProtectGroup" in ops


def test_remark_drift_updates(monkeypatch):
    fake = FakeWafClient(groups=[_group()])
    _make_module(monkeypatch, fake)
    _name_args(
        state="present",
        remark="Updated remark",
        domains=["api.example.com", "www.example.com"],
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["protect_group"]["Remark"] == "Updated remark"


def test_rename_by_group_id(monkeypatch):
    fake = FakeWafClient(groups=[_group()])
    _make_module(monkeypatch, fake)
    _id_args(state="present", name="renamed-apps")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["protect_group"]["Name"] == "renamed-apps"
    ops = [c for c, unused in fake.calls]
    assert "ModifyProtectGroup" in ops


def test_rename_by_name_alone_creates_new_group(monkeypatch):
    # Without group_id the module can only look the group up by its exact
    # name, so handing it a brand-new name reads as a brand-new group.
    fake = FakeWafClient(groups=[_group()])
    _make_module(monkeypatch, fake)
    _name_args(state="present", name="renamed-apps")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["protect_group"]["Name"] == "renamed-apps"
    assert [g["Name"] for g in fake.groups] == ["production-apps", "renamed-apps"]


def test_ambiguous_name_match_fails(monkeypatch):
    fake = FakeWafClient(groups=[_group(), _group(ID=1002)])
    _make_module(monkeypatch, fake)
    _name_args(state="present")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "specify group_id" in exc.value.args[0]["msg"]


# ---------------------------------------------------------------------------
# failure paths
# ---------------------------------------------------------------------------


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeProtectGroup(self, request):
            raise Boom("connection dropped")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    _name_args(state="present")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]
