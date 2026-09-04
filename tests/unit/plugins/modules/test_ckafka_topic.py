"""Unit tests for the ckafka_topic write module helpers."""

from __future__ import absolute_import, division, print_function

__metaclass__ = type
from ansible_collections.susunola.tencentcloud.plugins.modules.ckafka_topic import (
    _create,
    _delete,
    _scale_partitions,
    _update,
    _validate_partition_scale,
    find_topic,
)


class FakeRequest(object):
    pass


class FakeModels(object):
    DescribeTopicRequest = FakeRequest
    DescribeTopicAttributesRequest = FakeRequest
    CreateTopicRequest = FakeRequest
    CreatePartitionRequest = FakeRequest
    ModifyTopicAttributesRequest = FakeRequest
    DeleteTopicRequest = FakeRequest


class FakeTopic(object):
    def __init__(self, name, partitions=1, replicas=2, note=None):
        self.TopicName = name
        self.PartitionNum = partitions
        self.ReplicaNum = replicas
        self.Note = note
        self.RetentionMs = 86400000
        self.RetentionBytes = None
        self.CleanUpPolicy = "delete"

    def _serialize(self, allow_none=True):
        return {
            "TopicName": self.TopicName,
            "PartitionNum": self.PartitionNum,
            "ReplicaNum": self.ReplicaNum,
            "Note": self.Note,
            "RetentionMs": self.RetentionMs,
            "RetentionBytes": self.RetentionBytes,
            "CleanUpPolicy": self.CleanUpPolicy,
        }


class FakeResponse(object):
    def __init__(self, topics=None, result=None):
        self.Result = topics


class FakeClient(object):
    def __init__(self, response=None, exc=None):
        self.response = response
        self.exc = exc
        self.calls = []

    def DescribeTopic(self, request):
        self.calls.append(request)
        if self.exc:
            raise self.exc
        return self.response

    def DescribeTopicAttributes(self, request):
        self.calls.append(request)
        response = FakeResponse()
        response.Result = None
        return response

    def CreateTopic(self, request):
        self.calls.append(request)
        if self.exc:
            raise self.exc
        return self.response

    def CreatePartition(self, request):
        self.calls.append(request)
        if self.exc:
            raise self.exc
        return self.response

    def ModifyTopicAttributes(self, request):
        self.calls.append(request)
        if self.exc:
            raise self.exc
        return self.response

    def DeleteTopic(self, request):
        self.calls.append(request)
        if self.exc:
            raise self.exc
        return self.response


class FakeModule(object):
    def __init__(self):
        self.params = {"retries": 2}

    def sdk_call(self, operation, request):
        return operation(request)


def test_find_topic_matches_by_name():
    client = FakeClient(FakeResponse([FakeTopic("order-events", 3, 2, "orders")]))
    module = FakeModule()
    topic = find_topic(module, client, FakeModels, "ckafka-1", "order-events")
    assert topic["TopicName"] == "order-events"
    assert topic["PartitionNum"] == 3
    assert len(client.calls) == 2
    assert client.calls[0].SearchWord == "order-events"


def test_find_topic_returns_none_when_missing():
    client = FakeClient(FakeResponse([FakeTopic("other")]))
    module = FakeModule()
    assert find_topic(module, client, FakeModels, "ckafka-1", "missing") is None


def test_find_topic_handles_none_result():
    client = FakeClient(FakeResponse(None))
    module = FakeModule()
    assert find_topic(module, client, FakeModels, "ckafka-1", "x") is None


def test_create_sends_all_provided_fields():
    client = FakeClient(FakeResponse())
    module = FakeModule()
    _create(module, client, FakeModels, {
        "instance_id": "ckafka-1",
        "topic_name": "order-events",
        "partition_num": 3,
        "replica_num": 2,
        "retention_ms": 172800000,
        "retention_bytes": 1073741824,
        "clean_up_policy": "delete",
        "note": "orders",
        "max_message_bytes": 1048576,
        "min_insync_replicas": 2,
        "unclean_leader_election": False,
        "producer_quota_mb": 20,
        "consumer_quota_mb": 30,
        "message_timestamp_type": "LogAppendTime",
    })
    request = client.calls[-1]
    assert request.InstanceId == "ckafka-1"
    assert request.TopicName == "order-events"
    assert request.PartitionNum == 3
    assert request.ReplicaNum == 2
    assert request.RetentionMs == 172800000
    assert request.RetentionBytes == 1073741824
    assert request.CleanUpPolicy == "delete"
    assert request.Note == "orders"
    assert request.MaxMessageBytes == 1048576
    assert request.MinInsyncReplicas == 2
    assert request.UncleanLeaderElectionEnable == 0
    assert request.LogMsgTimestampType == "LogAppendTime"


def test_create_omits_optional_fields():
    client = FakeClient(FakeResponse())
    module = FakeModule()
    _create(module, client, FakeModels, {
        "instance_id": "ckafka-1",
        "topic_name": "order-events",
        "partition_num": 1,
        "replica_num": 2,
        "retention_ms": None,
        "retention_bytes": None,
        "clean_up_policy": None,
        "note": None,
        "max_message_bytes": None,
    })
    request = client.calls[-1]
    assert request.InstanceId == "ckafka-1"
    assert not hasattr(request, "RetentionMs")
    assert not hasattr(request, "Note")
    assert not hasattr(request, "MaxMessageBytes")


def test_update_sends_changed_fields():
    client = FakeClient(FakeResponse())
    module = FakeModule()
    _update(module, client, FakeModels, "ckafka-1", "order-events", 3, {
        "partition_num": 6,
        "replica_num": 3,
        "retention_ms": 86400000,
        "retention_bytes": None,
        "clean_up_policy": "compact",
        "note": "scaled",
        "max_message_bytes": 1048576,
    })
    request = client.calls[-1]
    assert request.InstanceId == "ckafka-1"
    assert request.TopicName == "order-events"
    assert not hasattr(request, "PartitionNum")
    assert request.ReplicaNum == 3
    assert request.CleanUpPolicy == "compact"
    assert request.Note == "scaled"
    assert request.MaxMessageBytes == 1048576
    assert not hasattr(request, "RetentionBytes")


def test_run_module_sequence_scales_then_modifies():
    # run_module orchestrates partition scaling before attribute changes;
    # assert the two builders compose to exactly two requests.
    client = FakeClient(FakeResponse())
    module = FakeModule()
    _scale_partitions(module, client, FakeModels, "ckafka-1", "order-events", 3, 6)
    _update(module, client, FakeModels, "ckafka-1", "order-events", 3, {
        "partition_num": 6,
        "replica_num": 3,
        "retention_ms": 86400000,
        "retention_bytes": None,
        "clean_up_policy": "delete",
        "note": "scaled",
        "max_message_bytes": None,
    })
    assert len(client.calls) == 2
    scale_request, modify_request = client.calls
    assert scale_request.PartitionNum == 3  # 6 - 3 new partitions
    assert modify_request.ReplicaNum == 3
    assert not hasattr(modify_request, "PartitionNum")


def test_update_with_unchanged_partitions_skips_scaling():
    client = FakeClient(FakeResponse())
    module = FakeModule()
    _update(module, client, FakeModels, "ckafka-1", "order-events", 6, {
        "partition_num": 6,
        "replica_num": 2,
        "retention_ms": None,
        "retention_bytes": None,
        "clean_up_policy": None,
        "note": "same",
        "max_message_bytes": None,
    })
    assert len(client.calls) == 1
    assert not hasattr(client.calls[-1], "PartitionNum")


def test_scale_partitions_requests_only_the_delta():
    client = FakeClient(FakeResponse())
    module = FakeModule()
    _scale_partitions(module, client, FakeModels, "ckafka-1", "order-events", 3, 8)
    request = client.calls[-1]
    assert request.InstanceId == "ckafka-1"
    assert request.TopicName == "order-events"
    assert request.PartitionNum == 5


def test_scale_partitions_is_noop_at_same_count():
    client = FakeClient(FakeResponse())
    module = FakeModule()
    _scale_partitions(module, client, FakeModels, "ckafka-1", "order-events", 3, 3)
    assert client.calls == []


def test_scale_partitions_rejects_shrink():
    client = FakeClient(FakeResponse())
    module = FakeModule()
    module.fail_json = lambda **kwargs: (_empty for _empty in ()).throw(
        AssertionError(kwargs["msg"]))
    try:
        _scale_partitions(module, client, FakeModels, "ckafka-1", "order-events", 3, 2)
        raise AssertionError("expected fail_json on shrink")
    except AssertionError as exc:
        assert "cannot reduce partitions" in str(exc)
    assert client.calls == []


def test_validate_partition_scale_allows_grow_and_equal():
    module = FakeModule()
    module.fail_json = lambda **kwargs: (_empty for _empty in ()).throw(
        AssertionError(kwargs["msg"]))
    _validate_partition_scale(module, "order-events", 3, 5)
    _validate_partition_scale(module, "order-events", 3, 3)


def test_delete_sends_instance_and_topic():
    client = FakeClient(FakeResponse())
    module = FakeModule()
    _delete(module, client, FakeModels, "ckafka-1", "order-events")
    request = client.calls[-1]
    assert request.InstanceId == "ckafka-1"
    assert request.TopicName == "order-events"
