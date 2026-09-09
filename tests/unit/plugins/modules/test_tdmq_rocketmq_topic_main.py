"""Unit tests for the tdmq_rocketmq_topic write module (run_module flows).

Drives ``run_module()`` against an in-memory fake TDMQ client whose create /
modify / delete operations mutate a RocketMQ-topic store so post-write
describes converge immediately.

Scenario matrix:

* absent on a missing topic (idempotent no-op)
* absent with a matching topic (check-mode dry run, real delete)
* creation when missing (happy path, check-mode dry run)
* no-op when the topic already matches (name/type/partition_num/remark)
* remark / partition_num-drift updates through ModifyRocketMQTopic
* immutable ``Type`` drift and decreasing ``partition_num`` guards
* the blanket SDK failure path
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import tdmq_rocketmq_topic as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

TOPIC = {
    "Name": "orders",
    "Type": "PartitionedOrder",
    "PartitionNum": 6,
    "Remark": "Order stream",
}


def _topic(**overrides):
    item = copy.deepcopy(TOPIC)
    item.update(overrides)
    return item


def _config(**overrides):
    params = {"cluster_id": "rocketmq-abc", "namespace": "production", "name": "orders"}
    params.update(overrides)
    return module_args(**params)


class FakeTdmqClient(object):
    """In-memory TDMQ client mutating a small RocketMQ-topic store."""

    def __init__(self, topics=None):
        self.topics = [copy.deepcopy(t) for t in (topics or [])]
        self.calls = []

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def _by_name(self, name):
        for item in self.topics:
            if item.get("Name") == name:
                return item
        return None

    def DescribeRocketMQTopics(self, request):
        self._record("DescribeRocketMQTopics", request)
        return SimpleNamespace(Topics=[FakeResource(t) for t in self.topics], TotalCount=len(self.topics))

    def CreateRocketMQTopic(self, request):
        self._record("CreateRocketMQTopic", request)
        self.topics.append(
            {
                "Name": getattr(request, "Topic", None),
                "Type": getattr(request, "Type", None),
                "PartitionNum": getattr(request, "PartitionNum", None),
                "Remark": getattr(request, "Remark", None) or "",
            }
        )
        return SimpleNamespace(RequestId="req-fake")

    def ModifyRocketMQTopic(self, request):
        self._record("ModifyRocketMQTopic", request)
        item = self._by_name(getattr(request, "Topic", None))
        if item is not None:
            item["PartitionNum"] = getattr(request, "PartitionNum", item.get("PartitionNum"))
            item["Remark"] = getattr(request, "Remark", item.get("Remark"))
        return SimpleNamespace(RequestId="req-fake")

    def DeleteRocketMQTopic(self, request):
        self._record("DeleteRocketMQTopic", request)
        self.topics = [t for t in self.topics if t.get("Name") != getattr(request, "Topic", None)]
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
    fake = FakeTdmqClient(topics=[])
    _make_module(monkeypatch, fake)
    _config(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["topic"] is None
    assert [c for c, unused in fake.calls] == ["DescribeRocketMQTopics"]


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeTdmqClient(topics=[_topic()])
    _make_module(monkeypatch, fake)
    _config(_ansible_check_mode=True, state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["topic"]["Name"] == "orders"
    assert len(fake.topics) == 1
    assert "DeleteRocketMQTopic" not in [c for c, unused in fake.calls]


def test_absent_deletes_topic(monkeypatch):
    fake = FakeTdmqClient(topics=[_topic()])
    _make_module(monkeypatch, fake)
    _config(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["topic"] is None
    assert fake.topics == []
    ops = [c for c, unused in fake.calls]
    assert "DeleteRocketMQTopic" in ops


# ---------------------------------------------------------------------------
# creation flows
# ---------------------------------------------------------------------------


def test_create_topic(monkeypatch):
    fake = FakeTdmqClient(topics=[])
    _make_module(monkeypatch, fake)
    _config(state="present", topic_type="PartitionedOrder", partition_num=6, remark="Order stream")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["topic"]["Name"] == "orders"
    assert result["topic"]["Type"] == "PartitionedOrder"
    assert result["topic"]["PartitionNum"] == 6
    assert len(fake.topics) == 1
    ops = [c for c, unused in fake.calls]
    assert ops[0] == "DescribeRocketMQTopics"
    assert "CreateRocketMQTopic" in ops


def test_create_check_mode_is_dry_run(monkeypatch):
    fake = FakeTdmqClient(topics=[])
    _make_module(monkeypatch, fake)
    _config(_ansible_check_mode=True, state="present", partition_num=3, remark="Preview")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["topic"] is None
    assert fake.topics == []
    assert "CreateRocketMQTopic" not in [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# existing-topic flows
# ---------------------------------------------------------------------------


def test_existing_topic_no_drift_is_idempotent(monkeypatch):
    fake = FakeTdmqClient(topics=[_topic()])
    _make_module(monkeypatch, fake)
    _config(state="present", topic_type="PartitionedOrder", partition_num=6, remark="Order stream")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["topic"]["Name"] == "orders"
    assert "ModifyRocketMQTopic" not in [c for c, unused in fake.calls]


def test_remark_drift_triggers_modify(monkeypatch):
    fake = FakeTdmqClient(topics=[_topic(Remark="Stale remark")])
    _make_module(monkeypatch, fake)
    _config(state="present", topic_type="PartitionedOrder", partition_num=6, remark="Order stream")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["topic"]["Remark"] == "Order stream"
    ops = [c for c, unused in fake.calls]
    assert "ModifyRocketMQTopic" in ops


def test_partition_increase_triggers_modify(monkeypatch):
    fake = FakeTdmqClient(topics=[_topic(PartitionNum=3)])
    _make_module(monkeypatch, fake)
    _config(state="present", topic_type="PartitionedOrder", partition_num=6)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["topic"]["PartitionNum"] == 6


def test_partition_decrease_is_rejected(monkeypatch):
    fake = FakeTdmqClient(topics=[_topic()])
    _make_module(monkeypatch, fake)
    _config(state="present", topic_type="PartitionedOrder", partition_num=2)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "partition_num cannot be decreased" in exc.value.args[0]["msg"]


def test_topic_type_drift_is_immutable(monkeypatch):
    fake = FakeTdmqClient(topics=[_topic(Type="Normal")])
    _make_module(monkeypatch, fake)
    _config(state="present", topic_type="Transaction", partition_num=6, remark="Order stream")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "Immutable fields cannot be changed on an existing RocketMQ topic" in payload["msg"]
    assert payload["immutable_changes"]["Type"]["after"] == "Transaction"


# ---------------------------------------------------------------------------
# failure paths
# ---------------------------------------------------------------------------


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeRocketMQTopics(self, request):
            raise Boom("connection dropped")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    _config(state="present")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]
