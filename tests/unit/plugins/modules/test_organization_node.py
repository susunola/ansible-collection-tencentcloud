"""Tests for organization_node."""

from ansible_collections.susunola.tencentcloud.plugins.modules import organization_node
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import FakeModels


PARAMS = {"parent_node_id": 1001, "name": "Production", "remark": "Production units", "tags": {"env": "prod"}}


def test_request_builders():
    models = FakeModels()
    create = organization_node.build_create_request(models, PARAMS)
    assert create.ParentNodeId == 1001
    assert create.Tags[0].TagKey == "env"
    update = organization_node.build_update_request(models, 1002, PARAMS)
    assert update.NodeId == 1002
    assert organization_node.build_delete_request(models, 1002).NodeId == [1002]


def test_exact_idempotency_normalizes_tags():
    desired = organization_node._desired(PARAMS)
    current = dict(desired)
    current["Tags"] = [{"TagKey": "env", "TagValue": "prod"}]
    assert organization_node._matches(current, desired)
    current["Remark"] = "changed"
    assert not organization_node._matches(current, desired)
