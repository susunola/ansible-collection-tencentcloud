"""Unit tests for the tdmq_topic write module (run_module flows).

Drives ``run_module()`` end to end against an in-memory fake TDMQ client
whose write operations mutate the topic store, so the post-write
``DescribeTopics`` refetch and the ``wait_for_topic`` waiter converge on the
first poll.

Scenario matrix:

* absent on a missing topic (idempotent no-op)
* absent with a matching topic (check-mode dry run and the real delete)
* creation when missing (partition range guard, check-mode dry run and the
  happy path)
* no-op when nothing drifts
* attribute drift updates (message TTL / remark / ack timeout / consumer
  isolation / delay policy) and partition expansion
* the partition shrink guard
* the ambiguous-name guard and the invalid-choice guard
* the blanket ``Tencent Cloud API request failed`` failure path
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import tdmq_topic as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

TOPIC = {
    "TopicName": "orders",
    "ClusterId": "pulsar-abc",
    "EnvironmentId": "production",
    "Partitions": 1,
    "PulsarTopicType": 2,
    "Remark": "",
    "MsgTTL": 86400,
    "IsolateConsumerEnable": False,
    "AckTimeOut": 60,
    "DelayMessagePolicy": "defaultPolicy",
}


def _topic(**overrides):
    item = copy.deepcopy(TOPIC)
    item.update(overrides)
    return item


def _args(**overrides):
    # NOTE: keys carrying ``choices`` (state, topic_type,
    # delay_message_policy) must not be pre-filled with None.
    params = {"cluster_id": "pulsar-abc", "environment_id": "production", "name": "orders"}
    params.update(overrides)
    return module_args(**params)


class FakeTdmqClient(object):
    """In-memory TDMQ client mutating a small topic store."""

    def __init__(self, topics=None):
        self.topics = [copy.deepcopy(t) for t in (topics or [])]
        self.calls = []

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def _topic(self, name):
        for item in self.topics:
            if item.get("TopicName") == name:
                return item
        return None

    def DescribeTopics(self, request):
        self._record("DescribeTopics", request)
        wanted = None
        for item in (getattr(request, "Filters", None) or []):
            if getattr(item, "Name", None) == "TopicName":
                values = list(getattr(item, "Values", None) or [])
                wanted = values[0] if values else None
        page = [dict(t) for t in self.topics if t.get("TopicName") == wanted]
        return SimpleNamespace(
            TopicSets=[FakeResource(t) for t in page],
            TotalCount=len(page),
        )

    def CreateTopic(self, request):
        self._record("CreateTopic", request)
        item = {
            "TopicName": getattr(request, "TopicName", None),
            "ClusterId": getattr(request, "ClusterId", None),
            "EnvironmentId": getattr(request, "EnvironmentId", None),
            "Partitions": getattr(request, "Partitions", 1),
            "PulsarTopicType": getattr(request, "PulsarTopicType", 2),
            "Remark": getattr(request, "Remark", ""),
            "MsgTTL": getattr(request, "MsgTTL", 86400),
            "IsolateConsumerEnable": bool(getattr(request, "IsolateConsumerEnable", False)),
            "AckTimeOut": getattr(request, "AckTimeOut", 60),
            "DelayMessagePolicy": getattr(request, "DelayMessagePolicy", "defaultPolicy"),
        }
        self.topics.append(item)
        return SimpleNamespace(RequestId="req-fake")

    def ModifyTopic(self, request):
        self._record("ModifyTopic", request)
        item = self._topic(getattr(request, "TopicName", None))
        if item is not None:
            for attr, field in (
                ("Partitions", "Partitions"),
                ("Remark", "Remark"),
                ("MsgTTL", "MsgTTL"),
                ("IsolateConsumerEnable", "IsolateConsumerEnable"),
                ("AckTimeOut", "AckTimeOut"),
                ("DelayMessagePolicy", "DelayMessagePolicy"),
            ):
                value = getattr(request, attr, None)
                if value is not None:
                    item[field] = bool(value) if attr == "IsolateConsumerEnable" else value
        return SimpleNamespace(RequestId="req-fake")

    def DeleteTopics(self, request):
        self._record("DeleteTopics", request)
        topic_sets = list(getattr(request, "TopicSets", None) or [])
        names = [getattr(t, "TopicName", None) for t in topic_sets]
        self.topics = [t for t in self.topics if t.get("TopicName") not in names]
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake, models=None):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load_tdmq", lambda: (models or FakeModels(), SimpleNamespace(TdmqClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


# ---------------------------------------------------------------------------
# absent flows
# ---------------------------------------------------------------------------


def test_absent_missing_topic_is_idempotent(monkeypatch):
    fake = FakeTdmqClient(topics=[])
    _make_module(monkeypatch, fake)
    _args(state="absent", name="ghost-topic")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["topic"] is None
    assert result["msg"] == "TDMQ topic is absent"
    assert [c for c, unused in fake.calls] == ["DescribeTopics"]


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeTdmqClient(topics=[_topic()])
    _make_module(monkeypatch, fake)
    _args(_ansible_check_mode=True, state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["msg"] == "Would delete TDMQ topic"
    assert result["topic"]["TopicName"] == "orders"
    assert len(fake.topics) == 1
    assert "DeleteTopics" not in [c for c, unused in fake.calls]


def test_absent_deletes_topic(monkeypatch):
    fake = FakeTdmqClient(topics=[_topic()])
    _make_module(monkeypatch, fake)
    _args(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["msg"] == "TDMQ topic deleted"
    assert result["topic"] is None
    assert fake.topics == []
    assert "DeleteTopics" in [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# creation flows
# ---------------------------------------------------------------------------


def test_partition_count_must_be_at_least_one(monkeypatch):
    fake = FakeTdmqClient(topics=[])
    _make_module(monkeypatch, fake)
    _args(state="present", partitions=0)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "partitions must be between 1 and 32" in exc.value.args[0]["msg"]


def test_partition_count_must_be_at_most_thirty_two(monkeypatch):
    fake = FakeTdmqClient(topics=[])
    _make_module(monkeypatch, fake)
    _args(state="present", partitions=33)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "partitions must be between 1 and 32" in exc.value.args[0]["msg"]


def test_create_check_mode_is_dry_run(monkeypatch):
    fake = FakeTdmqClient(topics=[])
    _make_module(monkeypatch, fake)
    _args(_ansible_check_mode=True, state="present", partitions=4)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["msg"] == "Would create TDMQ topic"
    assert result["topic"] is None
    assert fake.topics == []
    assert "CreateTopic" not in [c for c, unused in fake.calls]


def test_create_topic(monkeypatch):
    fake = FakeTdmqClient(topics=[])
    _make_module(monkeypatch, fake)
    _args(
        state="present",
        partitions=4,
        message_ttl=3600,
        remark="orders queue",
        isolate_consumer=True,
        ack_timeout=30,
        delay_message_policy="timingwheelPolicy",
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["msg"] == "TDMQ topic created"
    topic = result["topic"]
    assert topic["TopicName"] == "orders"
    assert topic["Partitions"] == 4
    assert topic["MsgTTL"] == 3600
    assert topic["Remark"] == "orders queue"
    assert topic["IsolateConsumerEnable"] is True
    assert topic["AckTimeOut"] == 30
    assert topic["DelayMessagePolicy"] == "timingwheelPolicy"
    assert len(fake.topics) == 1
    ops = [c for c, unused in fake.calls]
    assert ops[0] == "DescribeTopics"
    assert "CreateTopic" in ops


# ---------------------------------------------------------------------------
# existing-topic flows
# ---------------------------------------------------------------------------


def test_existing_no_drift_is_idempotent(monkeypatch):
    fake = FakeTdmqClient(topics=[_topic()])
    _make_module(monkeypatch, fake)
    _args(state="present")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["msg"] == "TDMQ topic is up to date"
    assert result["topic"]["TopicName"] == "orders"
    assert "ModifyTopic" not in [c for c, unused in fake.calls]


def test_expand_partitions(monkeypatch):
    fake = FakeTdmqClient(topics=[_topic()])
    _make_module(monkeypatch, fake)
    _args(state="present", partitions=8)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["msg"] == "TDMQ topic updated"
    assert result["topic"]["Partitions"] == 8
    assert fake.topics[0]["Partitions"] == 8
    assert "ModifyTopic" in [c for c, unused in fake.calls]


def test_update_message_ttl_and_remark(monkeypatch):
    fake = FakeTdmqClient(topics=[_topic()])
    _make_module(monkeypatch, fake)
    _args(state="present", message_ttl=120, remark="reprioritized", ack_timeout=15)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["topic"]["MsgTTL"] == 120
    assert result["topic"]["Remark"] == "reprioritized"
    assert result["topic"]["AckTimeOut"] == 15
    assert "ModifyTopic" in [c for c, unused in fake.calls]


def test_update_check_mode_is_dry_run(monkeypatch):
    fake = FakeTdmqClient(topics=[_topic()])
    _make_module(monkeypatch, fake)
    _args(_ansible_check_mode=True, state="present", message_ttl=60)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["msg"] == "Would update TDMQ topic"
    assert fake.topics[0]["MsgTTL"] == 86400
    assert "ModifyTopic" not in [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# guards / validation / failure paths
# ---------------------------------------------------------------------------


def test_partitions_cannot_be_decreased(monkeypatch):
    fake = FakeTdmqClient(topics=[_topic(Partitions=4)])
    _make_module(monkeypatch, fake)
    _args(state="present", partitions=1)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "partitions cannot be decreased" in payload["msg"]
    assert payload["current_partitions"] == 4
    assert "ModifyTopic" not in [c for c, unused in fake.calls]


def test_multiple_topics_with_same_name_fail(monkeypatch):
    fake = FakeTdmqClient(topics=[_topic(), _topic()])
    _make_module(monkeypatch, fake)
    _args(state="present")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "Multiple TDMQ topics have the requested name" in payload["msg"]
    assert payload["name"] == "orders"


def test_invalid_topic_type_choice_fails(monkeypatch):
    fake = FakeTdmqClient(topics=[])
    _make_module(monkeypatch, fake)
    _args(state="present", topic_type=9)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "value of topic_type must be one of" in exc.value.args[0]["msg"]


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeTopics(self, request):
            raise Boom("connection dropped")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    _args(state="present")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]


# ---------------------------------------------------------------------------
# legacy helper regression tests (folded from test_tdmq_topic.py)
# ---------------------------------------------------------------------------

PARAMS = {
    "cluster_id": "pulsar-x",
    "environment_id": "prod",
    "name": "orders",
    "partitions": 4,
    "topic_type": 3,
    "remark": "orders",
    "message_ttl": 86400,
    "isolate_consumer": True,
    "ack_timeout": 120,
    "delay_message_policy": "defaultPolicy",
}


def test_request_builders():
    models = FakeModels()
    describe = mod.build_describe_request(models, "pulsar-x", "prod", "orders")
    assert describe.Filters[0].Values == ["orders"]
    create = mod.build_create_request(models, PARAMS)
    assert create.PulsarTopicType == 3
    assert create.Partitions == 4
    update = mod.build_update_request(models, PARAMS)
    assert update.MsgTTL == 86400
    delete = mod.build_delete_request(models, "pulsar-x", "prod", "orders", True)
    assert delete.TopicSets[0].TopicName == "orders"
    assert delete.Force is True


def test_exact_idempotency():
    desired = mod._desired(PARAMS)
    assert mod._matches(dict(desired), desired)
    changed = dict(desired)
    changed["Partitions"] = 2
    assert not mod._matches(changed, desired)
