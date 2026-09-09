"""Main-path (run_module) unit tests for tse_gateway_consumer_group_membership.

Drives ``run_module()`` end to end against an in-memory fake TSE client whose
mutations edit each consumer's group membership so the post-write
``inspect_members`` readback converges.

Scenario matrix:
* list-size and duplicate validation guards
* idempotent no-op when members already belong
* add/remove mutations (check mode and real), resolving names when ids are
  omitted
* consumer-group / consumer name resolution failures and unknown-consumer
  lookup failure
* the blanket ``sdk_error_payload`` failure path
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import tse_gateway_consumer_group_membership as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

GROUPS = [{"ConsumerGroupId": "g1", "Name": "trusted-clients"}]


def _consumer(consumer_id, name, groups=None):
    return {
        "ConsumerId": consumer_id,
        "Name": name,
        "ConsumerGroups": [{"ConsumerGroupId": g} for g in (groups or [])],
    }


def _base(**overrides):
    params = {"gateway_id": "gateway-1", "consumer_group_id": "g1", "consumer_ids": ["c1", "c2"]}
    params.update(overrides)
    return module_args(**params)


def _name_args(**overrides):
    """Args resolved exclusively by name (no group/consumer ids)."""
    params = {"gateway_id": "gateway-1", "consumer_group_name": "trusted-clients", "consumer_names": ["mobile-app", "batch-worker"]}
    params.update(overrides)
    return module_args(**params)


class FakeTseClient(object):
    """In-memory TSE client storing consumer groups and consumer memberships."""

    def __init__(self, groups=None, consumers=None):
        self.groups = [copy.deepcopy(g) for g in (groups or [])]
        self.consumers = [copy.deepcopy(c) for c in (consumers or [])]
        self.calls = []

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def _consumer(self, consumer_id):
        return next((c for c in self.consumers if c.get("ConsumerId") == consumer_id), None)

    def DescribeCloudNativeAPIGatewayConsumerGroupList(self, request):
        self._record("DescribeCloudNativeAPIGatewayConsumerGroupList", request)
        return SimpleNamespace(
            Result=SimpleNamespace(ConsumerGroups=[FakeResource(copy.deepcopy(g)) for g in self.groups], TotalCount=len(self.groups))
        )

    def DescribeCloudNativeAPIGatewayConsumerList(self, request):
        self._record("DescribeCloudNativeAPIGatewayConsumerList", request)
        return SimpleNamespace(
            Result=SimpleNamespace(Consumers=[FakeResource(copy.deepcopy(c)) for c in self.consumers], TotalCount=len(self.consumers))
        )

    def DescribeCloudNativeAPIGatewayConsumer(self, request):
        self._record("DescribeCloudNativeAPIGatewayConsumer", request)
        item = self._consumer(getattr(request, "ConsumerId", None))
        return SimpleNamespace(Result=FakeResource(copy.deepcopy(item)) if item else None)

    def AddCloudNativeAPIGatewayConsumerInGroup(self, request):
        self._record("AddCloudNativeAPIGatewayConsumerInGroup", request)
        group = getattr(request, "ConsumerGroupId", None)
        for consumer_id in getattr(request, "ConsumerIds", None) or []:
            item = self._consumer(consumer_id)
            if item is not None and group not in [g["ConsumerGroupId"] for g in item["ConsumerGroups"]]:
                item["ConsumerGroups"].append({"ConsumerGroupId": group})
        return SimpleNamespace(RequestId="req-fake")

    def RemoveCloudNativeAPIGatewayConsumerInGroup(self, request):
        self._record("RemoveCloudNativeAPIGatewayConsumerInGroup", request)
        group = getattr(request, "ConsumerGroupId", None)
        for consumer_id in getattr(request, "ConsumerIds", None) or []:
            item = self._consumer(consumer_id)
            if item is not None:
                item["ConsumerGroups"] = [g for g in item["ConsumerGroups"] if g["ConsumerGroupId"] != group]
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake, models=None):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (models or FakeModels(), SimpleNamespace(TseClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


def _full_client():
    return FakeTseClient(
        groups=GROUPS,
        consumers=[_consumer("c1", "mobile-app", groups=["g1"]), _consumer("c2", "batch-worker")],
    )


# ---------------------------------------------------------------------------
# validation guards
# ---------------------------------------------------------------------------


def test_empty_consumer_list_fails(monkeypatch):
    fake = _full_client()
    _make_module(monkeypatch, fake)
    _base(consumer_ids=[])
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "between 1 and 10 entries" in exc.value.args[0]["msg"]


def test_duplicate_consumer_ids_fail(monkeypatch):
    fake = _full_client()
    _make_module(monkeypatch, fake)
    _base(consumer_ids=["c1", "c1"])
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "must not contain duplicates" in exc.value.args[0]["msg"]


# ---------------------------------------------------------------------------
# present flows
# ---------------------------------------------------------------------------


def test_membership_no_change_is_idempotent(monkeypatch):
    fake = _full_client()
    _make_module(monkeypatch, fake)
    _base(state="present", consumer_ids=["c1"])
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["membership"]["ConsumerGroupId"] == "g1"
    assert result["membership"]["ConsumerIds"] == ["c1"]


def test_present_adds_missing_consumer(monkeypatch):
    fake = _full_client()
    _make_module(monkeypatch, fake)
    _base(state="present", consumer_ids=["c1", "c2"])
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["membership"]["AffectedConsumerIds"] == ["c2"]
    assert sorted(result["membership"]["ConsumerIds"]) == ["c1", "c2"]
    ops = [c for c, unused in fake.calls]
    assert "AddCloudNativeAPIGatewayConsumerInGroup" in ops


def test_present_add_check_mode_is_dry_run(monkeypatch):
    fake = _full_client()
    _make_module(monkeypatch, fake)
    _base(_ansible_check_mode=True, state="present", consumer_ids=["c1", "c2"])
    result = run(mod.run_module)
    assert result["changed"] is True
    assert "AddCloudNativeAPIGatewayConsumerInGroup" not in [c for c, unused in fake.calls]
    assert sorted(result["membership"]["ConsumerIds"]) == ["c1", "c2"]


def test_present_resolves_names(monkeypatch):
    fake = _full_client()
    _make_module(monkeypatch, fake)
    _name_args(state="present")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["membership"]["ConsumerGroupId"] == "g1"
    assert result["membership"]["AffectedConsumerIds"] == ["c2"]


# ---------------------------------------------------------------------------
# absent flows
# ---------------------------------------------------------------------------


def test_absent_removes_consumer(monkeypatch):
    fake = _full_client()
    _make_module(monkeypatch, fake)
    _base(state="absent", consumer_ids=["c1"])
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["membership"]["AffectedConsumerIds"] == ["c1"]
    assert result["membership"]["ConsumerIds"] == []
    ops = [c for c, unused in fake.calls]
    assert "RemoveCloudNativeAPIGatewayConsumerInGroup" in ops


def test_absent_no_members_is_idempotent(monkeypatch):
    fake = _full_client()
    _make_module(monkeypatch, fake)
    _base(state="absent", consumer_ids=["c2"])
    result = run(mod.run_module)
    assert result["changed"] is False


# ---------------------------------------------------------------------------
# resolution / lookup failures and sdk failure
# ---------------------------------------------------------------------------


def test_unknown_consumer_group_name_fails(monkeypatch):
    fake = _full_client()
    _make_module(monkeypatch, fake)
    _name_args(consumer_group_name="ghost-group")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "consumer group name was not found" in exc.value.args[0]["msg"]


def test_unknown_consumer_names_fail(monkeypatch):
    fake = _full_client()
    _make_module(monkeypatch, fake)
    _name_args(consumer_names=["ghost-app"])
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "consumer names were not found" in exc.value.args[0]["msg"]


def test_unknown_consumer_id_fails(monkeypatch):
    fake = _full_client()
    _make_module(monkeypatch, fake)
    _base(state="present", consumer_ids=["c-ghost"])
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "consumer was not found" in exc.value.args[0]["msg"]


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeCloudNativeAPIGatewayConsumer(self, request):
            raise Boom("connection dropped")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    _base(state="present", consumer_ids=["c1"])
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]


# ---------------------------------------------------------------------------
# legacy helper regression tests (folded from test_tse_gateway_consumer_group_membership.py)
# ---------------------------------------------------------------------------


class LegacyValue(object):
    pass


def test_group_ids_reads_consumer_detail_memberships():
    assert mod.group_ids({"ConsumerGroups": [{"ConsumerGroupId": "cg1"}, {"ConsumerGroupId": "cg2"}]}) == {"cg1", "cg2"}


def test_membership_request_maps_only_delta():
    p = {"gateway_id": "g1", "consumer_group_id": "cg1"}
    request = mod.mutation_request(LegacyValue, p, ["c2"])
    assert request.ConsumerGroupId == "cg1" and request.ConsumerIds == ["c2"]


def test_resolve_ids_reports_unknown_names():
    ids, missing = mod.resolve_ids([{"Name": "mobile", "ConsumerId": "c1"}], ["mobile", "missing"], "ConsumerId")
    assert ids == ["c1"] and missing == ["missing"]
