"""Tests for the cls_topic resource module."""

from ansible_collections.susunola.tencentcloud.plugins.modules import cls_topic
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import FakeModels


def test_request_builders():
    models = FakeModels()
    params = {"logset_id": "logset-1", "name": "network", "partition_count": 2, "period": 30, "hot_period": None, "storage_type": "hot", "auto_split": True, "max_split_partitions": 50, "description": "flow", "tags": {"env": "prod"}}
    create = cls_topic.build_create_request(models, params)
    assert create.LogsetId == "logset-1"
    assert create.PartitionCount == 2
    update = cls_topic.build_update_request(models, "topic-1", params)
    assert update.TopicId == "topic-1"
    assert cls_topic.build_delete_request(models, "topic-1").TopicId == "topic-1"
