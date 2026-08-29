"""Tests for cls_logset."""

from ansible_collections.susunola.tencentcloud.plugins.modules import cls_logset
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import FakeModels


def test_request_builders():
    models = FakeModels()
    create = cls_logset.build_create_request(models, "prod", {"env": "prod"})
    assert create.LogsetName == "prod"
    assert create.Tags[0].Key == "env"
    update = cls_logset.build_update_request(models, "logset-1", "prod-v2", {})
    assert update.LogsetId == "logset-1"
    assert cls_logset.build_delete_request(models, "logset-1").LogsetId == "logset-1"
