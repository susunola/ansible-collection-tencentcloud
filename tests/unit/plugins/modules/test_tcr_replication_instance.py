from ansible_collections.susunola.tencentcloud.plugins.modules import tcr_replication_instance as m
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import FakeModels

P = {"registry_id": "tcr-x", "replication_region_id": 1, "replication_region_name": "ap-shanghai", "sync_tag": False}


def test_builders():
    models = FakeModels()
    assert m.build_describe_request(models, "tcr-x").Limit == 100
    assert m.build_create_request(models, P).ReplicationRegionId == 1
    assert m.build_delete_request(models, "tcr-x", "tcr-y", 1).ReplicationRegistryId == "tcr-y"
