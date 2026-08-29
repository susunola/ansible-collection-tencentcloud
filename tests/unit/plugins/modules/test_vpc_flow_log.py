"""Tests for vpc_flow_log."""

from ansible_collections.susunola.tencentcloud.plugins.modules import vpc_flow_log
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import FakeModels


def test_request_builders():
    models = FakeModels()
    params = {"name": "eni-flow", "vpc_id": "vpc-1", "resource_type": "NETWORKINTERFACE", "resource_id": "eni-1", "traffic_type": "ALL", "cls_topic_id": "topic-1", "description": "audit", "cls_region": None, "period": None, "tags": {"env": "prod"}}
    create = vpc_flow_log.build_create_request(models, params)
    assert create.ResourceId == "eni-1"
    assert create.CloudLogId == "topic-1"
    assert create.Tags[0].Key == "env"
    assert vpc_flow_log.build_toggle_request(models, True, "fl-1").FlowLogIds == ["fl-1"]
    assert vpc_flow_log.build_delete_request(models, "vpc-1", "fl-1").FlowLogId == "fl-1"
