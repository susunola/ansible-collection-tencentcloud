"""Tests for tdmq_topic."""

from ansible_collections.susunola.tencentcloud.plugins.modules import tdmq_topic
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import FakeModels


PARAMS = {"cluster_id": "pulsar-x", "environment_id": "prod", "name": "orders", "partitions": 4, "topic_type": 3, "remark": "orders", "message_ttl": 86400, "isolate_consumer": True, "ack_timeout": 120, "delay_message_policy": "defaultPolicy"}


def test_request_builders():
    models = FakeModels()
    describe = tdmq_topic.build_describe_request(models, "pulsar-x", "prod", "orders")
    assert describe.Filters[0].Values == ["orders"]
    create = tdmq_topic.build_create_request(models, PARAMS)
    assert create.PulsarTopicType == 3
    assert create.Partitions == 4
    update = tdmq_topic.build_update_request(models, PARAMS)
    assert update.MsgTTL == 86400
    delete = tdmq_topic.build_delete_request(models, "pulsar-x", "prod", "orders", True)
    assert delete.TopicSets[0].TopicName == "orders"
    assert delete.Force is True


def test_exact_idempotency():
    desired = tdmq_topic._desired(PARAMS)
    assert tdmq_topic._matches(dict(desired), desired)
    changed = dict(desired)
    changed["Partitions"] = 2
    assert not tdmq_topic._matches(changed, desired)
