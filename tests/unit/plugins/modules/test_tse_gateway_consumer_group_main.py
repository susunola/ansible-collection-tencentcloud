"""Unit tests for the tse_gateway_consumer_group write module (run_module flows).

Drives ``run_module()`` end to end against an in-memory fake TSE client whose
write operations mutate the consumer-group store, so the post-write list/detail
refetch converges immediately.

Scenario matrix:

* argument validation (missing consumer_group_id and name)
* absent on a missing group (idempotent) / check-mode dry run / real delete
* creation when missing (real create and check mode)
* no-op when nothing drifts
* drift updates (status and description changes)
* the multiple-match guard
* the blanket ``sdk_error_payload`` failure path
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import tse_gateway_consumer_group as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

GROUP = {
    "ConsumerGroupId": "cg-8b0a1c2d",
    "Name": "trusted-clients",
    "Status": "Enable",
    "Description": "trusted api clients",
}


def _group(**overrides):
    item = copy.deepcopy(GROUP)
    item.update(overrides)
    return item


def _base(**overrides):
    params = {"gateway_id": "gateway-1", "name": "trusted-clients"}
    params.update(overrides)
    return module_args(**params)


class FakeTseClient(object):
    """In-memory TSE client mutating a consumer-group store."""

    def __init__(self, groups=None):
        self.groups = [copy.deepcopy(t) for t in (groups or [])]
        self.calls = []
        self._next = 0

    def _find(self, group_id):
        for item in self.groups:
            if item.get("ConsumerGroupId") == group_id:
                return item
        return None

    def DescribeCloudNativeAPIGatewayConsumerGroupList(self, request):
        self.calls.append("DescribeCloudNativeAPIGatewayConsumerGroupList")
        result = SimpleNamespace(ConsumerGroups=[FakeResource(t) for t in self.groups], TotalCount=len(self.groups))
        return SimpleNamespace(Result=result, RequestId="req-fake")

    def DescribeCloudNativeAPIGatewayConsumerGroup(self, request):
        self.calls.append("DescribeCloudNativeAPIGatewayConsumerGroup")
        item = self._find(getattr(request, "ConsumerGroupId", None))
        result = FakeResource(dict(item)) if item is not None else None
        return SimpleNamespace(Result=result, RequestId="req-fake")

    def CreateCloudNativeAPIGatewayConsumerGroup(self, request):
        self.calls.append("CreateCloudNativeAPIGatewayConsumerGroup")
        self._next += 1
        item = {
            "ConsumerGroupId": "cg-new-%03d" % self._next,
            "Name": getattr(request, "Name", None),
            "Status": getattr(request, "Status", None),
            "Description": getattr(request, "Description", None),
        }
        self.groups.append(item)
        return SimpleNamespace(Result=SimpleNamespace(ID=item["ConsumerGroupId"]), RequestId="req-fake")

    def ModifyCloudNativeAPIGatewayConsumerGroup(self, request):
        self.calls.append("ModifyCloudNativeAPIGatewayConsumerGroup")
        item = self._find(getattr(request, "ConsumerGroupId", None))
        if item is not None:
            item["Name"] = getattr(request, "Name", None)
            item["Status"] = getattr(request, "Status", None)
            item["Description"] = getattr(request, "Description", None)
        return SimpleNamespace(RequestId="req-fake")

    def DeleteCloudNativeAPIGatewayConsumerGroup(self, request):
        self.calls.append("DeleteCloudNativeAPIGatewayConsumerGroup")
        self.groups = [t for t in self.groups if t.get("ConsumerGroupId") != getattr(request, "ConsumerGroupId", None)]
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake, models=None):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (models or FakeModels(), SimpleNamespace(TseClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


# ---------------------------------------------------------------------------
# argument validation
# ---------------------------------------------------------------------------


def test_name_or_consumer_group_id_required(monkeypatch):
    fake = FakeTseClient()
    _make_module(monkeypatch, fake)
    module_args(gateway_id="gateway-1")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "one of the following is required" in exc.value.args[0]["msg"]


# ---------------------------------------------------------------------------
# absent flows
# ---------------------------------------------------------------------------


def test_absent_missing_group_is_idempotent(monkeypatch):
    fake = FakeTseClient()
    _make_module(monkeypatch, fake)
    _base(state="absent", name="ghost")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["consumer_group"] is None


def test_absent_deletes_group(monkeypatch):
    fake = FakeTseClient(groups=[_group()])
    _make_module(monkeypatch, fake)
    _base(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert fake.groups == []
    ops = list(fake.calls)
    assert "DeleteCloudNativeAPIGatewayConsumerGroup" in ops


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeTseClient(groups=[_group()])
    _make_module(monkeypatch, fake)
    _base(_ansible_check_mode=True, state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert len(fake.groups) == 1
    assert "DeleteCloudNativeAPIGatewayConsumerGroup" not in fake.calls


# ---------------------------------------------------------------------------
# creation flows
# ---------------------------------------------------------------------------


def test_create_group(monkeypatch):
    fake = FakeTseClient()
    _make_module(monkeypatch, fake)
    _base(status="Enable", description="trusted api clients")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["consumer_group"]["ConsumerGroupId"].startswith("cg-new-")
    assert result["consumer_group"]["Name"] == "trusted-clients"
    assert result["consumer_group"]["Status"] == "Enable"
    assert len(fake.groups) == 1
    ops = list(fake.calls)
    assert ops[0] == "DescribeCloudNativeAPIGatewayConsumerGroupList"
    assert "CreateCloudNativeAPIGatewayConsumerGroup" in ops


def test_create_check_mode_is_dry_run(monkeypatch):
    fake = FakeTseClient()
    _make_module(monkeypatch, fake)
    _base(_ansible_check_mode=True, status="Enable")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["consumer_group"]["Name"] == "trusted-clients"
    assert result["consumer_group"]["Status"] == "Enable"
    assert fake.groups == []
    assert "CreateCloudNativeAPIGatewayConsumerGroup" not in fake.calls


# ---------------------------------------------------------------------------
# existing-group flows
# ---------------------------------------------------------------------------


def test_existing_group_no_drift_is_idempotent(monkeypatch):
    fake = FakeTseClient(groups=[_group()])
    _make_module(monkeypatch, fake)
    _base(status="Enable", description="trusted api clients")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["consumer_group"]["ConsumerGroupId"] == "cg-8b0a1c2d"
    ops = list(fake.calls)
    assert "ModifyCloudNativeAPIGatewayConsumerGroup" not in ops


def test_update_group(monkeypatch):
    fake = FakeTseClient(groups=[_group()])
    _make_module(monkeypatch, fake)
    _base(status="Disable", description="revoked")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["consumer_group"]["Status"] == "Disable"
    assert result["consumer_group"]["Description"] == "revoked"
    ops = list(fake.calls)
    assert "ModifyCloudNativeAPIGatewayConsumerGroup" in ops


def test_update_check_mode_is_dry_run(monkeypatch):
    fake = FakeTseClient(groups=[_group()])
    _make_module(monkeypatch, fake)
    _base(_ansible_check_mode=True, status="Disable")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["consumer_group"]["Status"] == "Disable"
    assert "ModifyCloudNativeAPIGatewayConsumerGroup" not in fake.calls


def test_multiple_matches_fail(monkeypatch):
    fake = FakeTseClient(groups=[_group(), _group(ConsumerGroupId="cg-dup")])
    _make_module(monkeypatch, fake)
    _base()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "Multiple TSE gateway consumer groups matched" in exc.value.args[0]["msg"]


# ---------------------------------------------------------------------------
# failure paths
# ---------------------------------------------------------------------------


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeCloudNativeAPIGatewayConsumerGroupList(self, request):
            raise Boom("connection dropped")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    _base()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]


# ---------------------------------------------------------------------------
# legacy helper regression tests (folded from test_tse_gateway_consumer_group.py)
# ---------------------------------------------------------------------------


class LegacyValue(object):
    pass


class LegacyModels(object):
    CreateCloudNativeAPIGatewayConsumerGroupRequest = LegacyValue
    ModifyCloudNativeAPIGatewayConsumerGroupRequest = LegacyValue


def test_consumer_group_requests_cover_mutable_fields():
    p = {"gateway_id": "g1", "name": "trusted", "status": "Enable", "description": "apps"}
    assert mod.create_request(LegacyModels, p).Status == "Enable"
    request = mod.update_request(LegacyModels, p, {"ConsumerGroupId": "cg1"})
    assert request.ConsumerGroupId == "cg1"
    assert request.Description == "apps"
