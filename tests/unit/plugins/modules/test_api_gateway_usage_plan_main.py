"""Unit tests for the api_gateway_usage_plan write module (run_module flows).

Drives ``run_module()`` against an in-memory fake API Gateway client whose
create / modify / delete operations mutate a usage-plan store so post-write
describes converge immediately.

Scenario matrix:

* absent on a missing plan, identified by name or by ``usage_plan_id``
  (idempotent no-op; the id path exercises the not-found guard)
* absent with a matching plan (check-mode dry run, real delete)
* creation when missing (happy path with a follow-up describe, check mode)
* existing plan without drift (idempotent no-op)
* qps drift triggers an update (real modify + describe read-back)
* the duplicate-name guard, the ``name``-for-``present`` guard and the
  blanket SDK failure path
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import api_gateway_usage_plan as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

PLAN = {
    "UsagePlanId": "usagePlan-1001",
    "UsagePlanName": "production-clients",
    "UsagePlanDesc": "Primary production plan",
    "MaxRequestNumPreSec": 100,
    "MaxRequestNum": 1000000,
    "CreatedTime": "2026-01-01T00:00:00Z",
}


def _plan(**overrides):
    item = copy.deepcopy(PLAN)
    item.update(overrides)
    return item


def _name_args(**overrides):
    params = {
        "name": "production-clients",
        "description": "Primary production plan",
        "qps": 100,
        "max_request_num": 1000000,
    }
    params.update(overrides)
    return module_args(**params)


class NotFoundError(Exception):
    def get_code(self):
        return "ResourceNotFound"

    def get_request_id(self):
        return "req-err"


class FakeApigatewayClient(object):
    """In-memory API Gateway client mutating a usage-plan store."""

    def __init__(self, plans=None):
        self.plans = [copy.deepcopy(t) for t in (plans or [])]
        self.calls = []
        self._next = 0

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def _by_id(self, plan_id):
        for item in self.plans:
            if item.get("UsagePlanId") == plan_id:
                return item
        return None

    def DescribeUsagePlan(self, request):
        self._record("DescribeUsagePlan", request)
        item = self._by_id(getattr(request, "UsagePlanId", None))
        if item is None:
            raise NotFoundError("usage plan not found")
        return SimpleNamespace(Result=FakeResource(item))

    def DescribeUsagePlansStatus(self, request):
        self._record("DescribeUsagePlansStatus", request)
        return SimpleNamespace(
            Result=SimpleNamespace(UsagePlanStatusSet=[FakeResource(t) for t in self.plans], Total=len(self.plans))
        )

    def CreateUsagePlan(self, request):
        self._record("CreateUsagePlan", request)
        self._next += 1
        plan_id = "usagePlan-%d" % (2000 + self._next)
        item = {
            "UsagePlanId": plan_id,
            "UsagePlanName": getattr(request, "UsagePlanName", None),
            "UsagePlanDesc": getattr(request, "UsagePlanDesc", None) or "",
            "MaxRequestNumPreSec": getattr(request, "MaxRequestNumPreSec", None),
            "MaxRequestNum": getattr(request, "MaxRequestNum", None),
            "CreatedTime": "2026-01-01T00:00:00Z",
        }
        self.plans.append(item)
        return SimpleNamespace(Result=SimpleNamespace(UsagePlanId=plan_id), RequestId="req-fake")

    def ModifyUsagePlan(self, request):
        self._record("ModifyUsagePlan", request)
        item = self._by_id(getattr(request, "UsagePlanId", None))
        if item is not None:
            item["UsagePlanName"] = getattr(request, "UsagePlanName", item.get("UsagePlanName"))
            item["UsagePlanDesc"] = getattr(request, "UsagePlanDesc", item.get("UsagePlanDesc"))
            item["MaxRequestNumPreSec"] = getattr(request, "MaxRequestNumPreSec", item.get("MaxRequestNumPreSec"))
            item["MaxRequestNum"] = getattr(request, "MaxRequestNum", item.get("MaxRequestNum"))
        return SimpleNamespace(RequestId="req-fake")

    def DeleteUsagePlan(self, request):
        self._record("DeleteUsagePlan", request)
        self.plans = [t for t in self.plans if t.get("UsagePlanId") != getattr(request, "UsagePlanId", None)]
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake, models=None):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (models or FakeModels(), SimpleNamespace(ApigatewayClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


def _names(fake):
    return [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# absent flows
# ---------------------------------------------------------------------------


def test_absent_missing_by_name_is_idempotent(monkeypatch):
    fake = FakeApigatewayClient(plans=[])
    _make_module(monkeypatch, fake)
    module_args(state="absent", name="ghost-plan")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["usage_plan"] is None
    assert _names(fake) == ["DescribeUsagePlansStatus"]


def test_absent_missing_by_plan_id_is_idempotent(monkeypatch):
    fake = FakeApigatewayClient(plans=[])
    _make_module(monkeypatch, fake)
    module_args(state="absent", usage_plan_id="usagePlan-ghost")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["usage_plan"] is None
    assert _names(fake) == ["DescribeUsagePlan"]


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeApigatewayClient(plans=[_plan()])
    _make_module(monkeypatch, fake)
    module_args(_ansible_check_mode=True, state="absent", usage_plan_id="usagePlan-1001")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["usage_plan"]["UsagePlanId"] == "usagePlan-1001"
    assert len(fake.plans) == 1
    assert "DeleteUsagePlan" not in _names(fake)


def test_absent_deletes_plan(monkeypatch):
    fake = FakeApigatewayClient(plans=[_plan()])
    _make_module(monkeypatch, fake)
    module_args(state="absent", name="production-clients")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["usage_plan"] is None
    assert fake.plans == []
    assert "DeleteUsagePlan" in _names(fake)


# ---------------------------------------------------------------------------
# creation flows
# ---------------------------------------------------------------------------


def test_present_without_name_fails(monkeypatch):
    fake = FakeApigatewayClient(plans=[])
    _make_module(monkeypatch, fake)
    module_args(state="present", usage_plan_id="usagePlan-1001")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert exc.value.args[0]["msg"] == "name is required when state=present"


def test_create_usage_plan(monkeypatch):
    fake = FakeApigatewayClient(plans=[])
    _make_module(monkeypatch, fake)
    _name_args(state="present")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["usage_plan"]["UsagePlanName"] == "production-clients"
    assert result["usage_plan"]["UsagePlanId"]
    assert result["usage_plan"]["MaxRequestNumPreSec"] == 100
    assert len(fake.plans) == 1
    ops = _names(fake)
    assert ops[0] == "DescribeUsagePlansStatus"
    assert "CreateUsagePlan" in ops
    assert "DescribeUsagePlan" in ops


def test_create_check_mode_is_dry_run(monkeypatch):
    fake = FakeApigatewayClient(plans=[])
    _make_module(monkeypatch, fake)
    _name_args(_ansible_check_mode=True, state="present")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert fake.plans == []
    assert "CreateUsagePlan" not in _names(fake)


def test_duplicate_name_match_fails(monkeypatch):
    fake = FakeApigatewayClient(plans=[_plan(), _plan(UsagePlanId="usagePlan-1002")])
    _make_module(monkeypatch, fake)
    module_args(state="present", name="production-clients")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "Multiple usage plans have the requested name" in exc.value.args[0]["msg"]


# ---------------------------------------------------------------------------
# existing-plan flows
# ---------------------------------------------------------------------------


def test_existing_plan_no_drift_is_idempotent(monkeypatch):
    fake = FakeApigatewayClient(plans=[_plan()])
    _make_module(monkeypatch, fake)
    _name_args(state="present")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["usage_plan"]["UsagePlanId"] == "usagePlan-1001"
    assert "ModifyUsagePlan" not in _names(fake)


def test_qps_drift_updates_plan(monkeypatch):
    fake = FakeApigatewayClient(plans=[_plan()])
    _make_module(monkeypatch, fake)
    _name_args(state="present", qps=250)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["usage_plan"]["MaxRequestNumPreSec"] == 250
    assert fake.plans[0]["MaxRequestNumPreSec"] == 250
    ops = _names(fake)
    assert "ModifyUsagePlan" in ops
    assert "DescribeUsagePlan" in ops


def test_max_request_num_drift_updates_plan(monkeypatch):
    fake = FakeApigatewayClient(plans=[_plan()])
    _make_module(monkeypatch, fake)
    _name_args(state="present", max_request_num=5000000)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["usage_plan"]["MaxRequestNum"] == 5000000


def test_update_check_mode_is_dry_run(monkeypatch):
    fake = FakeApigatewayClient(plans=[_plan()])
    _make_module(monkeypatch, fake)
    _name_args(_ansible_check_mode=True, state="present", qps=250)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert fake.plans[0]["MaxRequestNumPreSec"] == 100
    assert "ModifyUsagePlan" not in _names(fake)


# ---------------------------------------------------------------------------
# failure paths
# ---------------------------------------------------------------------------


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeUsagePlansStatus(self, request):
            raise Boom("connection dropped")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    _name_args(state="present")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]
