"""Unit tests for the ccn write module (run_module flows).

Drives ``run_module()`` end to end against an in-memory fake VPC client
whose write operations mutate the CCN store, so the module's post-write
``find_ccn`` refetch and the converged-state waiter return immediately.

Scenario matrix:

* absent on a missing CCN (idempotent no-op)
* absent with a matching CCN (check-mode dry run and real delete)
* creation when missing (with/without the required name, check mode)
* no-op when nothing drifts
* drift updates on the mutable name / description / routing feature flags
* the multi-match guard and the blanket SDK-failure path
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import ccn as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

CCN = {
    "CcnId": "ccn-8z4b1a2c",
    "CcnName": "global-backbone",
    "CcnDescription": "Production multi-region network",
    "RouteECMPFlag": True,
    "RouteOverlapFlag": False,
    "TrafficMarkingPolicyFlag": False,
}


def _ccn(**overrides):
    item = copy.deepcopy(CCN)
    item.update(overrides)
    return item


def _base(**overrides):
    # ccn_id and name are alternatives (required_one_of); start from the name.
    params = {"name": "global-backbone"}
    params.update(overrides)
    return module_args(**params)


class FakeVpcClient(object):
    """In-memory VPC client mutating a CCN store."""

    def __init__(self, ccns=None):
        self.ccns = [copy.deepcopy(t) for t in (ccns or [])]
        self.calls = []

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def _matches(self, request):
        ids = list(getattr(request, "CcnIds", None) or [])
        wanted = None
        for item in list(getattr(request, "Filters", None) or []):
            if getattr(item, "Name", None) == "ccn-name":
                wanted = (getattr(item, "Values", None) or [None])[0]
        matches = []
        for item in self.ccns:
            if ids and item.get("CcnId") not in ids:
                continue
            if wanted is not None and item.get("CcnName") != wanted:
                continue
            matches.append(dict(item))
        return matches

    def DescribeCcns(self, request):
        self._record("DescribeCcns", request)
        matches = self._matches(request)
        return SimpleNamespace(
            CcnSet=[FakeResource(t) for t in matches],
            TotalCount=len(matches),
        )

    def CreateCcn(self, request):
        self._record("CreateCcn", request)
        item = {
            "CcnId": "ccn-new-%03d" % (len(self.ccns) + 1),
            "CcnName": request.CcnName,
            "CcnDescription": request.CcnDescription,
            "RouteECMPFlag": False,
            "RouteOverlapFlag": False,
            "TrafficMarkingPolicyFlag": False,
        }
        self.ccns.append(item)
        return SimpleNamespace(Ccn=SimpleNamespace(CcnId=item["CcnId"]), RequestId="req-fake")

    def ModifyCcnAttribute(self, request):
        self._record("ModifyCcnAttribute", request)
        for item in self.ccns:
            if item.get("CcnId") != request.CcnId:
                continue
            for attr in ("CcnName", "CcnDescription", "RouteECMPFlag", "RouteOverlapFlag", "TrafficMarkingPolicyFlag"):
                value = getattr(request, attr, None)
                if value is not None:
                    item[attr] = value
        return SimpleNamespace(RequestId="req-fake")

    def DeleteCcn(self, request):
        self._record("DeleteCcn", request)
        self.ccns = [t for t in self.ccns if t.get("CcnId") != request.CcnId]
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake, models=None):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load_vpc", lambda: (models or FakeModels(), SimpleNamespace(VpcClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


# ---------------------------------------------------------------------------
# absent flows
# ---------------------------------------------------------------------------


def test_absent_missing_ccn_is_idempotent(monkeypatch):
    fake = FakeVpcClient(ccns=[])
    _make_module(monkeypatch, fake)
    _base(state="absent", name="ghost-backbone")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["ccn"] is None
    assert [c for c, unused in fake.calls] == ["DescribeCcns"]


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeVpcClient(ccns=[_ccn()])
    _make_module(monkeypatch, fake)
    _base(_ansible_check_mode=True, state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["ccn"]["CcnId"] == "ccn-8z4b1a2c"
    assert "DeleteCcn" not in [c for c, unused in fake.calls]


def test_absent_deletes_ccn(monkeypatch):
    fake = FakeVpcClient(ccns=[_ccn()])
    _make_module(monkeypatch, fake)
    _base(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["ccn"] is None
    assert fake.ccns == []
    assert "DeleteCcn" in [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# creation flows
# ---------------------------------------------------------------------------


def test_create_requires_name(monkeypatch):
    fake = FakeVpcClient(ccns=[])
    _make_module(monkeypatch, fake)
    module_args(state="present", ccn_id="ccn-ghost")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "name is required when creating a CCN" in exc.value.args[0]["msg"]


def test_create_ccn(monkeypatch):
    fake = FakeVpcClient(ccns=[])
    _make_module(monkeypatch, fake)
    _base(state="present", name="global-backbone", description="Production multi-region network")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["ccn"]["CcnName"] == "global-backbone"
    assert result["ccn"]["CcnDescription"] == "Production multi-region network"
    assert len(fake.ccns) == 1
    ops = [c for c, unused in fake.calls]
    assert ops[0] == "DescribeCcns"
    assert "CreateCcn" in ops


def test_create_check_mode_is_dry_run(monkeypatch):
    fake = FakeVpcClient(ccns=[])
    _make_module(monkeypatch, fake)
    _base(_ansible_check_mode=True, state="present", name="global-backbone")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["ccn"] is None
    assert fake.ccns == []
    assert "CreateCcn" not in [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# existing-ccn flows
# ---------------------------------------------------------------------------


def test_existing_ccn_no_drift_is_idempotent(monkeypatch):
    fake = FakeVpcClient(ccns=[_ccn()])
    _make_module(monkeypatch, fake)
    _base(state="present", name="global-backbone", description="Production multi-region network", route_ecmp=True, route_overlap=False)
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["ccn"]["CcnId"] == "ccn-8z4b1a2c"


def test_update_description_drift(monkeypatch):
    fake = FakeVpcClient(ccns=[_ccn()])
    _make_module(monkeypatch, fake)
    _base(state="present", name="global-backbone", description="Expanded backbone")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["ccn"]["CcnDescription"] == "Expanded backbone"
    ops = [c for c, unused in fake.calls]
    assert "ModifyCcnAttribute" in ops


def test_update_route_flags(monkeypatch):
    fake = FakeVpcClient(ccns=[_ccn()])
    _make_module(monkeypatch, fake)
    _base(
        state="present",
        name="global-backbone",
        description="Production multi-region network",
        route_ecmp=True,
        route_overlap=True,
        traffic_marking_policy=True,
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["ccn"]["RouteOverlapFlag"] is True
    assert result["ccn"]["TrafficMarkingPolicyFlag"] is True
    assert "ModifyCcnAttribute" in [c for c, unused in fake.calls]


def test_update_check_mode_is_dry_run(monkeypatch):
    fake = FakeVpcClient(ccns=[_ccn()])
    _make_module(monkeypatch, fake)
    _base(_ansible_check_mode=True, state="present", name="global-backbone", description="Expanded backbone")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["ccn"]["CcnDescription"] == "Production multi-region network"
    assert "ModifyCcnAttribute" not in [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# guards / failure paths
# ---------------------------------------------------------------------------


def test_multiple_name_matches_fail(monkeypatch):
    fake = FakeVpcClient(ccns=[_ccn(), _ccn(CcnId="ccn-dup0000")])
    _make_module(monkeypatch, fake)
    _base(state="present", name="global-backbone", description="Production multi-region network")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "Multiple CCNs have the requested name" in exc.value.args[0]["msg"]


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeCcns(self, request):
            raise Boom("connection dropped")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    _base(state="present", name="global-backbone")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]
