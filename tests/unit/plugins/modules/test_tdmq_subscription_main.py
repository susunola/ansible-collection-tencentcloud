"""Unit tests for the tdmq_subscription write module (run_module flows).

Drives ``run_module()`` against an in-memory fake TDMQ client whose create /
delete operations mutate a Pulsar-subscription store so post-write describes
converge immediately.

Scenario matrix:

* absent on a missing subscription (idempotent no-op)
* absent with a matching subscription (check-mode dry run, real delete)
* creation when missing (happy path, check-mode dry run)
* no-op when the existing subscription already carries the desired remark
* remark drift on an existing subscription fails: TDMQ exposes no Pulsar
  subscription update API, so the module asks for a recreate
* two subscriptions sharing the requested name fail the find
* the blanket SDK failure path
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import tdmq_subscription as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

SUBSCRIPTION = {
    "SubscriptionName": "order-workers",
    "Remark": "",
}


def _subscription(**overrides):
    item = copy.deepcopy(SUBSCRIPTION)
    item.update(overrides)
    return item


def _config(**overrides):
    params = {
        "cluster_id": "pulsar-abc",
        "environment_id": "production",
        "topic_name": "orders",
        "name": "order-workers",
    }
    params.update(overrides)
    return module_args(**params)


class FakeTdmqClient(object):
    """In-memory TDMQ client mutating a small Pulsar-subscription store."""

    def __init__(self, subscriptions=None):
        self.subscriptions = [copy.deepcopy(t) for t in (subscriptions or [])]
        self.calls = []

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def DescribeSubscriptions(self, request):
        self._record("DescribeSubscriptions", request)
        return SimpleNamespace(
            SubscriptionSets=[FakeResource(t) for t in self.subscriptions],
            TotalCount=len(self.subscriptions),
        )

    def CreateSubscription(self, request):
        self._record("CreateSubscription", request)
        self.subscriptions.append(
            {
                "SubscriptionName": getattr(request, "SubscriptionName", None),
                "Remark": getattr(request, "Remark", None) or "",
            }
        )
        return SimpleNamespace(RequestId="req-fake")

    def DeleteSubscriptions(self, request):
        self._record("DeleteSubscriptions", request)
        topics = list(getattr(request, "SubscriptionTopicSets", None) or [])
        names = [t.SubscriptionName for t in topics]
        self.subscriptions = [t for t in self.subscriptions if t.get("SubscriptionName") not in names]
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake, models=None):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (models or FakeModels(), SimpleNamespace(TdmqClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


# ---------------------------------------------------------------------------
# absent flows
# ---------------------------------------------------------------------------


def test_absent_missing_is_idempotent(monkeypatch):
    fake = FakeTdmqClient(subscriptions=[])
    _make_module(monkeypatch, fake)
    _config(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["subscription"] is None
    assert [c for c, unused in fake.calls] == ["DescribeSubscriptions"]


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeTdmqClient(subscriptions=[_subscription()])
    _make_module(monkeypatch, fake)
    _config(_ansible_check_mode=True, state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["subscription"]["SubscriptionName"] == "order-workers"
    assert len(fake.subscriptions) == 1
    assert "DeleteSubscriptions" not in [c for c, unused in fake.calls]


def test_absent_deletes_subscription(monkeypatch):
    fake = FakeTdmqClient(subscriptions=[_subscription()])
    _make_module(monkeypatch, fake)
    _config(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["subscription"] is None
    assert fake.subscriptions == []
    ops = [c for c, unused in fake.calls]
    assert "DeleteSubscriptions" in ops


# ---------------------------------------------------------------------------
# creation flows
# ---------------------------------------------------------------------------


def test_create_subscription(monkeypatch):
    fake = FakeTdmqClient(subscriptions=[])
    _make_module(monkeypatch, fake)
    _config(state="present", remark="Consumer group")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["subscription"]["SubscriptionName"] == "order-workers"
    assert result["subscription"]["Remark"] == "Consumer group"
    assert len(fake.subscriptions) == 1
    ops = [c for c, unused in fake.calls]
    assert ops[0] == "DescribeSubscriptions"
    assert "CreateSubscription" in ops


def test_create_check_mode_is_dry_run(monkeypatch):
    fake = FakeTdmqClient(subscriptions=[])
    _make_module(monkeypatch, fake)
    _config(_ansible_check_mode=True, state="present", remark="Preview")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["subscription"] is None
    assert fake.subscriptions == []
    assert "CreateSubscription" not in [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# existing-subscription flows
# ---------------------------------------------------------------------------


def test_existing_subscription_no_drift_is_idempotent(monkeypatch):
    fake = FakeTdmqClient(subscriptions=[_subscription(Remark="Consumer group")])
    _make_module(monkeypatch, fake)
    _config(state="present", remark="Consumer group")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["subscription"]["SubscriptionName"] == "order-workers"
    assert "CreateSubscription" not in [c for c, unused in fake.calls]


def test_remark_drift_requires_recreate(monkeypatch):
    # TDMQ has no Pulsar subscription update API, so changing the remark of an
    # existing subscription is reported as an unrecoverable drift.
    fake = FakeTdmqClient(subscriptions=[_subscription(Remark="Old remark")])
    _make_module(monkeypatch, fake)
    _config(state="present", remark="Consumer group")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "recreate it to change remark" in payload["msg"]
    assert payload["subscription"]["SubscriptionName"] == "order-workers"


def test_duplicate_subscription_name_fails(monkeypatch):
    fake = FakeTdmqClient(
        subscriptions=[_subscription(), _subscription(Remark="second copy")]
    )
    _make_module(monkeypatch, fake)
    _config(state="present")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "Multiple TDMQ subscriptions have the requested name" in exc.value.args[0]["msg"]


# ---------------------------------------------------------------------------
# failure paths
# ---------------------------------------------------------------------------


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeSubscriptions(self, request):
            raise Boom("connection dropped")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    _config(state="present")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]
