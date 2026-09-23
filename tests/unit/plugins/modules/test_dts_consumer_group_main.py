"""Unit tests for the dts_consumer_group write module (run_module flows).

Drives ``run_module()`` end to end against an in-memory fake DTS client whose
write operations mutate the consumer-group store so ``find_group`` and the
module's ``wait_for_group`` loops converge immediately.

Scenario matrix:

* absent on a missing consumer group (idempotent no-op)
* absent with a matching group (check-mode dry run, real delete)
* creation when missing (password guard, check mode, happy path)
* no-op when nothing drifts
* drift updates (description) with and without check mode
* multiple-match guard and the blanket ``sdk_error_payload`` failure path
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import dts_consumer_group as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

GROUP = {
    "SubscribeId": "subs-aaaa",
    "ConsumerGroupName": "analytics",
    "Account": "analytics-reader",
    "Description": "",
    "ConsumerGroupId": "cg-1",
}


def _group(**overrides):
    item = dict(GROUP)
    item.update(overrides)
    return item


def _base(**overrides):
    params = {
        "subscribe_id": "subs-aaaa",
        "consumer_group_name": "analytics",
        "account_name": "analytics-reader",
    }
    params.update(overrides)
    return module_args(**params)


class FakeDtsClient(object):
    """In-memory DTS client mutating a small consumer-group store."""

    def __init__(self, groups=None):
        self.groups = [dict(t) for t in (groups or [])]
        self.calls = []
        self._next = 0

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def DescribeConsumerGroups(self, request):
        self._record("DescribeConsumerGroups", request)
        rows = [g for g in self.groups if g.get("SubscribeId", "subs-aaaa") == getattr(request, "SubscribeId", None)]
        return SimpleNamespace(Items=[FakeResource(g) for g in rows], TotalCount=len(rows), RequestId="req-list")

    def CreateConsumerGroup(self, request):
        self._record("CreateConsumerGroup", request)
        self._next += 1
        self.groups.append(
            {
                "SubscribeId": getattr(request, "SubscribeId", None),
                "ConsumerGroupName": getattr(request, "ConsumerGroupName", None),
                "Account": getattr(request, "AccountName", None),
                "Description": getattr(request, "Description", None) or "",
                "ConsumerGroupId": "cg-new-%d" % self._next,
            }
        )
        return SimpleNamespace(RequestId="req-create")

    def ModifyConsumerGroupDescription(self, request):
        self._record("ModifyConsumerGroupDescription", request)
        for item in self.groups:
            if (
                item.get("SubscribeId") == getattr(request, "SubscribeId", None)
                and item.get("ConsumerGroupName") == getattr(request, "ConsumerGroupName", None)
                and item.get("Account") == getattr(request, "AccountName", None)
            ):
                item["Description"] = getattr(request, "Description", None) or ""
        return SimpleNamespace(RequestId="req-modify")

    def DeleteConsumerGroup(self, request):
        self._record("DeleteConsumerGroup", request)
        self.groups = [
            g for g in self.groups
            if not (
                g.get("ConsumerGroupName") == getattr(request, "ConsumerGroupName", None)
                and g.get("Account") == getattr(request, "AccountName", None)
            )
        ]
        return SimpleNamespace(RequestId="req-delete")


def _make_module(monkeypatch, fake, models=None):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load_dts", lambda: (models or FakeModels(), SimpleNamespace(DtsClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)


# ---------------------------------------------------------------------------
# absent flows
# ---------------------------------------------------------------------------


def test_absent_missing_group_is_idempotent(monkeypatch):
    fake = FakeDtsClient()
    _make_module(monkeypatch, fake)
    _base(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["consumer_group"] is None
    assert [c for c, unused in fake.calls] == ["DescribeConsumerGroups"]


def test_absent_deletes_group(monkeypatch):
    fake = FakeDtsClient(groups=[_group()])
    _make_module(monkeypatch, fake)
    _base(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["consumer_group"] is None
    assert fake.groups == []
    assert "DeleteConsumerGroup" in [c for c, unused in fake.calls]


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeDtsClient(groups=[_group()])
    _make_module(monkeypatch, fake)
    _base(_ansible_check_mode=True, state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert len(fake.groups) == 1
    assert "DeleteConsumerGroup" not in [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# creation flows
# ---------------------------------------------------------------------------


def test_create_requires_password(monkeypatch):
    fake = FakeDtsClient()
    _make_module(monkeypatch, fake)
    _base(state="present")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "password is required when creating" in exc.value.args[0]["msg"]


def test_create_group(monkeypatch):
    fake = FakeDtsClient()
    _make_module(monkeypatch, fake)
    _base(state="present", password="s3cret!", description="Analytics consumers")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["consumer_group"]["ConsumerGroupName"] == "analytics"
    assert result["consumer_group"]["Description"] == "Analytics consumers"
    assert len(fake.groups) == 1
    ops = [c for c, unused in fake.calls]
    assert ops[0] == "DescribeConsumerGroups"
    assert "CreateConsumerGroup" in ops


def test_create_check_mode_is_dry_run(monkeypatch):
    fake = FakeDtsClient()
    _make_module(monkeypatch, fake)
    _base(_ansible_check_mode=True, state="present", password="s3cret!")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["consumer_group"] is None
    assert fake.groups == []
    assert "CreateConsumerGroup" not in [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# existing-group flows
# ---------------------------------------------------------------------------


def test_existing_group_no_drift_is_idempotent(monkeypatch):
    fake = FakeDtsClient(groups=[_group()])
    _make_module(monkeypatch, fake)
    _base(state="present")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["consumer_group"]["ConsumerGroupName"] == "analytics"
    assert "ModifyConsumerGroupDescription" not in [c for c, unused in fake.calls]


def test_update_group_description(monkeypatch):
    fake = FakeDtsClient(groups=[_group()])
    _make_module(monkeypatch, fake)
    _base(state="present", description="ETL consumers")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["consumer_group"]["Description"] == "ETL consumers"
    assert fake.groups[0]["Description"] == "ETL consumers"
    assert "ModifyConsumerGroupDescription" in [c for c, unused in fake.calls]


def test_update_check_mode_is_dry_run(monkeypatch):
    fake = FakeDtsClient(groups=[_group()])
    _make_module(monkeypatch, fake)
    _base(_ansible_check_mode=True, state="present", description="ETL consumers")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert fake.groups[0]["Description"] == ""
    assert "ModifyConsumerGroupDescription" not in [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# guards / failure paths
# ---------------------------------------------------------------------------


def test_multiple_matching_groups_fail(monkeypatch):
    fake = FakeDtsClient(
        groups=[_group(), _group(ConsumerGroupId="cg-2", Description="dup")]
    )
    _make_module(monkeypatch, fake)
    _base(state="present")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "Multiple DTS consumer groups" in exc.value.args[0]["msg"]


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeConsumerGroups(self, request):
            raise Boom("connection dropped")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    _base(state="present", password="s3cret!")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]


# ---------------------------------------------------------------------------
# legacy helper regression tests (folded from test_dts_consumer_group.py)
# ---------------------------------------------------------------------------

_PARAMS = {"subscribe_id": "subs-x", "consumer_group_name": "analytics", "account_name": "reader", "password": "secret", "description": "analytics"}


def test_request_builders():
    models = FakeModels()
    create = mod.build_create_request(models, _PARAMS)
    assert create.SubscribeId == "subs-x"
    assert create.Password == "secret"
    update = mod.build_update_request(models, "subs-x", "consumer-full", "account-full", "new")
    assert update.Description == "new"
    delete = mod.build_delete_request(models, "subs-x", "consumer-full", "account-full")
    assert delete.AccountName == "account-full"


def test_generated_name_matching():
    assert mod._name_matches("consumer-grp-subs-x-analytics", "analytics", "consumer-grp-subs-x")
    assert mod._name_matches("analytics", "analytics", "consumer-grp-subs-x")
    assert not mod._name_matches("other", "analytics", "consumer-grp-subs-x")
