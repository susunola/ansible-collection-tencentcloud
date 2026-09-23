"""Unit tests for the ckafka_topic write module (run_module flows).

Drives ``run_module()`` end to end against an in-memory fake CKafka client
whose writes mutate the topic store so the post-write ``find_topic`` refetch
converges immediately.

Scenario matrix:

* absent on a missing topic (idempotent no-op)
* absent with a matching topic (check-mode dry run and the real delete)
* creation when missing (required params, check mode and the happy path)
* no-op when nothing drifts
* drift updates (partition scale-up, replica/retention/note attributes)
* the partition-shrink guard and the check-mode update preview
* argument-spec validation guards (choice violations, missing required args)
* the blanket ``Tencent Cloud API request failed`` failure path
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import ckafka_topic as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

INSTANCE_ID = "ckafka-abc123"

TOPIC = {
    "TopicName": "orders",
    "PartitionNum": 1,
    "ReplicaNum": 2,
    "RetentionMs": 86400000,
    "CleanUpPolicy": "delete",
    "Note": "Order event stream",
}


def _topic(**overrides):
    item = copy.deepcopy(TOPIC)
    item.update(overrides)
    return item


def _base(**overrides):
    # NOTE: keys carrying ``choices`` (state, clean_up_policy,
    # message_timestamp_type) must not be pre-filled with None.
    params = {"instance_id": INSTANCE_ID, "topic_name": "orders"}
    params.update(overrides)
    return module_args(**params)


class FakeCkafkaClient(object):
    """In-memory CKafka client mutating a small topic store."""

    def __init__(self, topics=None):
        self.topics = [copy.deepcopy(t) for t in (topics or [])]
        self.calls = []

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def _topic(self, instance_id, topic_name):
        for item in self.topics:
            if item.get("TopicName") == topic_name:
                return item
        return None

    def DescribeTopic(self, request):
        self._record("DescribeTopic", request)
        search = getattr(request, "SearchWord", None)
        matches = [dict(t) for t in self.topics if search in t.get("TopicName", "")]
        return SimpleNamespace(Result=[FakeResource(t) for t in matches], TotalCount=len(matches))

    def DescribeTopicAttributes(self, request):
        self._record("DescribeTopicAttributes", request)
        item = self._topic(getattr(request, "InstanceId", None), getattr(request, "TopicName", None))
        return SimpleNamespace(Result=FakeResource(item or {}))

    def CreateTopic(self, request):
        self._record("CreateTopic", request)
        item = {"TopicName": getattr(request, "TopicName", None)}
        for attr in (
            "PartitionNum", "ReplicaNum", "RetentionMs", "RetentionBytes",
            "CleanUpPolicy", "Note", "MaxMessageBytes", "MinInsyncReplicas",
            "UncleanLeaderElectionEnable", "LogMsgTimestampType",
        ):
            value = getattr(request, attr, None)
            if value is not None:
                item[attr] = value
        item.setdefault("PartitionNum", 1)
        item.setdefault("ReplicaNum", 2)
        self.topics.append(item)
        return SimpleNamespace(TopicId="topic-fake", RequestId="req-fake")

    def CreatePartition(self, request):
        self._record("CreatePartition", request)
        item = self._topic(getattr(request, "InstanceId", None), getattr(request, "TopicName", None))
        if item is not None:
            item["PartitionNum"] = item.get("PartitionNum", 1) + int(getattr(request, "PartitionNum", 0))
        return SimpleNamespace(RequestId="req-fake")

    def ModifyTopicAttributes(self, request):
        self._record("ModifyTopicAttributes", request)
        item = self._topic(getattr(request, "InstanceId", None), getattr(request, "TopicName", None))
        if item is None:
            return SimpleNamespace(RequestId="req-fake")
        for attr in (
            "ReplicaNum", "RetentionMs", "RetentionBytes", "CleanUpPolicy", "Note",
            "MaxMessageBytes", "MinInsyncReplicas", "UncleanLeaderElectionEnable",
            "QuotaProducerByteRate", "QuotaConsumerByteRate", "LogMsgTimestampType",
        ):
            value = getattr(request, attr, None)
            if value is not None:
                item[attr] = value
        return SimpleNamespace(RequestId="req-fake")

    def DeleteTopic(self, request):
        self._record("DeleteTopic", request)
        name = getattr(request, "TopicName", None)
        self.topics = [t for t in self.topics if t.get("TopicName") != name]
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake, models=None):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load_ckafka", lambda: (models or FakeModels(), SimpleNamespace(CkafkaClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


# ---------------------------------------------------------------------------
# absent flows
# ---------------------------------------------------------------------------


def test_absent_missing_topic_is_idempotent(monkeypatch):
    fake = FakeCkafkaClient(topics=[])
    _make_module(monkeypatch, fake)
    _base(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["msg"] == "Topic already absent"
    assert [c for c, unused in fake.calls] == ["DescribeTopic"]


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeCkafkaClient(topics=[_topic()])
    _make_module(monkeypatch, fake)
    _base(_ansible_check_mode=True, state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["msg"] == "Would delete topic"
    assert len(fake.topics) == 1
    assert "DeleteTopic" not in [c for c, unused in fake.calls]


def test_absent_deletes_topic(monkeypatch):
    fake = FakeCkafkaClient(topics=[_topic()])
    _make_module(monkeypatch, fake)
    _base(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["msg"] == "Topic deleted"
    assert result["topic"] is None
    assert fake.topics == []
    assert "DeleteTopic" in [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# creation flows
# ---------------------------------------------------------------------------


def test_create_topic(monkeypatch):
    fake = FakeCkafkaClient(topics=[])
    _make_module(monkeypatch, fake)
    _base(
        state="present",
        partition_num=3,
        replica_num=2,
        retention_ms=86400000,
        note="Order event stream",
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["msg"] == "Topic created"
    assert result["topic"]["TopicName"] == "orders"
    assert result["topic"]["PartitionNum"] == 3
    assert len(fake.topics) == 1
    ops = [c for c, unused in fake.calls]
    assert ops[0] == "DescribeTopic"
    assert "CreateTopic" in ops


def test_create_applies_quota_update(monkeypatch):
    fake = FakeCkafkaClient(topics=[])
    _make_module(monkeypatch, fake)
    _base(state="present", producer_quota_mb=-1, consumer_quota_mb=-1)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["topic"]["QuotaProducerByteRate"] == -1
    ops = [c for c, unused in fake.calls]
    assert "CreateTopic" in ops
    assert "ModifyTopicAttributes" in ops


def test_create_check_mode_is_dry_run(monkeypatch):
    fake = FakeCkafkaClient(topics=[])
    _make_module(monkeypatch, fake)
    _base(_ansible_check_mode=True, state="present", partition_num=3, note="Order event stream")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["msg"] == "Would create topic"
    assert fake.topics == []
    assert "CreateTopic" not in [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# existing-topic flows
# ---------------------------------------------------------------------------


def test_existing_topic_no_drift_is_idempotent(monkeypatch):
    fake = FakeCkafkaClient(topics=[_topic()])
    _make_module(monkeypatch, fake)
    _base(state="present")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["msg"] == "Topic is up to date"
    assert result["topic"]["TopicName"] == "orders"


def test_update_scale_partitions_up(monkeypatch):
    fake = FakeCkafkaClient(topics=[_topic(PartitionNum=2)])
    _make_module(monkeypatch, fake)
    _base(state="present", partition_num=4)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["topic"]["PartitionNum"] == 4
    ops = [c for c, unused in fake.calls]
    assert "CreatePartition" in ops
    assert "ModifyTopicAttributes" in ops


def test_shrink_partitions_fails(monkeypatch):
    fake = FakeCkafkaClient(topics=[_topic(PartitionNum=3)])
    _make_module(monkeypatch, fake)
    _base(state="present", partition_num=1)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "CKafka cannot reduce partitions" in exc.value.args[0]["msg"]
    assert "currently has 3" in exc.value.args[0]["msg"]


def test_update_replica_and_retention(monkeypatch):
    fake = FakeCkafkaClient(topics=[_topic()])
    _make_module(monkeypatch, fake)
    _base(state="present", replica_num=3, retention_ms=172800000, note="scaled note")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["msg"] == "Topic updated"
    assert result["topic"]["ReplicaNum"] == 3
    assert result["topic"]["RetentionMs"] == 172800000
    assert result["topic"]["Note"] == "scaled note"


def test_update_check_mode_is_dry_run(monkeypatch):
    fake = FakeCkafkaClient(topics=[_topic(Note="old note")])
    _make_module(monkeypatch, fake)
    _base(_ansible_check_mode=True, state="present", note="new note")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["msg"] == "Would update topic"
    assert fake.topics[0]["Note"] == "old note"
    assert "ModifyTopicAttributes" not in [c for c, unused in fake.calls]


def test_unclean_leader_election_drift(monkeypatch):
    fake = FakeCkafkaClient(topics=[_topic(UncleanLeaderElectionEnable=0)])
    _make_module(monkeypatch, fake)
    _base(state="present", unclean_leader_election=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["topic"]["UncleanLeaderElectionEnable"] == 1


# ---------------------------------------------------------------------------
# guards / validation / failure paths
# ---------------------------------------------------------------------------


def test_invalid_clean_up_policy_fails_argument_spec(monkeypatch):
    fake = FakeCkafkaClient(topics=[])
    _make_module(monkeypatch, fake)
    _base(state="present", clean_up_policy="nonsense")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "clean_up_policy" in exc.value.args[0]["msg"]
    assert "nonsense" in exc.value.args[0]["msg"]


def test_missing_topic_name_fails_argument_spec(monkeypatch):
    fake = FakeCkafkaClient(topics=[])
    _make_module(monkeypatch, fake)
    module_args(instance_id=INSTANCE_ID)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "topic_name" in exc.value.args[0]["msg"]


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeTopic(self, request):
            raise Boom("connection dropped")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    _base(state="present")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]
