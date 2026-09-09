"""Unit tests for the havip_association write module (run_module flows).

``havip_association`` binds or unbinds one CVM/ENI resource to a HAVIP
drift scope. The fake VPC client stores each HAVIP with its association
set and mutates it on Associate/Disassociate.

Scenario matrix:

* absent on an unassociated HAVIP (no-op) and missing-HAVIP guard
* absent on an existing association (check-mode dry run, real disassociate)
* present on an already associated resource (no-op)
* present on a free resource (check-mode dry run, real associate)
* blanket SDK failure path
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import havip_association as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

ASSOCIATION = {
    "HaVipId": "havip-abc123",
    "InstanceId": "ins-abc123",
    "InstanceType": "CVM",
}

HAVIP = {"HaVipId": "havip-abc123", "HaVipAssociationSet": [dict(ASSOCIATION)]}


def _association(**overrides):
    item = copy.deepcopy(ASSOCIATION)
    item.update(overrides)
    return item


def _havip(*associations):
    return {"HaVipId": "havip-abc123", "HaVipAssociationSet": [dict(a) for a in associations]}


def _a_args(**overrides):
    params = {"havip_id": "havip-abc123", "instance_id": "ins-abc123", "instance_type": "CVM"}
    params.update(overrides)
    return module_args(**params)


class FakeVpcClient(object):
    """In-memory VPC client mutating HAVIP association sets."""

    def __init__(self, havips=None):
        self.havips = [copy.deepcopy(h) for h in (havips or [])]
        self.calls = []

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def DescribeHaVips(self, request):
        self._record("DescribeHaVips", request)
        ids = list(request.HaVipIds or [])
        matches = [h for h in self.havips if h["HaVipId"] in ids]
        return SimpleNamespace(HaVipSet=[
            FakeResource({
                "HaVipId": h["HaVipId"],
                "HaVipAssociationSet": [FakeResource(dict(a)) for a in h["HaVipAssociationSet"]],
            })
            for h in matches
        ])

    def AssociateHaVipInstance(self, request):
        self._record("AssociateHaVipInstance", request)
        for item in request.HaVipAssociationSet:
            havip = next(h for h in self.havips if h["HaVipId"] == item.HaVipId)
            association = {"HaVipId": item.HaVipId, "InstanceId": item.InstanceId, "InstanceType": item.InstanceType}
            if association not in havip["HaVipAssociationSet"]:
                havip["HaVipAssociationSet"].append(association)
        return SimpleNamespace()

    def DisassociateHaVipInstance(self, request):
        self._record("DisassociateHaVipInstance", request)
        for item in request.HaVipAssociationSet:
            havip = next(h for h in self.havips if h["HaVipId"] == item.HaVipId)
            havip["HaVipAssociationSet"] = [
                a for a in havip["HaVipAssociationSet"]
                if not (a["InstanceId"] == item.InstanceId and a["InstanceType"] == item.InstanceType)
            ]
        return SimpleNamespace()


def _make_module(monkeypatch, fake):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (FakeModels(), SimpleNamespace(VpcClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


# ---------------------------------------------------------------------------
# absent flows
# ---------------------------------------------------------------------------


def test_absent_on_free_havip_is_idempotent(monkeypatch):
    fake = FakeVpcClient(havips=[_havip()])
    _make_module(monkeypatch, fake)
    _a_args(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["association"] is None
    assert [c for c, unused in fake.calls] == ["DescribeHaVips"]


def test_absent_missing_havip_fails(monkeypatch):
    fake = FakeVpcClient(havips=[])
    _make_module(monkeypatch, fake)
    _a_args(state="absent")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "HAVIP was not found" in exc.value.args[0]["msg"]


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeVpcClient(havips=[_havip(ASSOCIATION)])
    _make_module(monkeypatch, fake)
    _a_args(_ansible_check_mode=True, state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["association"] == ASSOCIATION
    assert len(fake.havips[0]["HaVipAssociationSet"]) == 1
    assert "DisassociateHaVipInstance" not in [c for c, unused in fake.calls]


def test_absent_disassociates(monkeypatch):
    fake = FakeVpcClient(havips=[_havip(ASSOCIATION)])
    _make_module(monkeypatch, fake)
    _a_args(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["association"] is None
    assert fake.havips[0]["HaVipAssociationSet"] == []
    ops = [c for c, unused in fake.calls]
    assert "DisassociateHaVipInstance" in ops


# ---------------------------------------------------------------------------
# present flows
# ---------------------------------------------------------------------------


def test_present_already_associated_is_idempotent(monkeypatch):
    fake = FakeVpcClient(havips=[_havip(ASSOCIATION)])
    _make_module(monkeypatch, fake)
    _a_args(state="present")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["association"] == ASSOCIATION
    ops = [c for c, unused in fake.calls]
    assert "AssociateHaVipInstance" not in ops


def test_present_associates_when_free(monkeypatch):
    fake = FakeVpcClient(havips=[_havip()])
    _make_module(monkeypatch, fake)
    _a_args(state="present")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["association"] == ASSOCIATION
    assert fake.havips[0]["HaVipAssociationSet"] == [ASSOCIATION]
    ops = [c for c, unused in fake.calls]
    assert ops[0] == "DescribeHaVips"
    assert "AssociateHaVipInstance" in ops


def test_present_check_mode_is_dry_run(monkeypatch):
    fake = FakeVpcClient(havips=[_havip()])
    _make_module(monkeypatch, fake)
    _a_args(_ansible_check_mode=True, state="present")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert fake.havips[0]["HaVipAssociationSet"] == []
    assert "AssociateHaVipInstance" not in [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# failure paths
# ---------------------------------------------------------------------------


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeHaVips(self, request):
            raise Boom("connection dropped")

    _make_module(monkeypatch, ExplodingClient())
    _a_args(state="present")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]
