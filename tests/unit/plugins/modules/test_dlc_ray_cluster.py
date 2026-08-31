from ansible_collections.susunola.tencentcloud.plugins.modules.dlc_ray_cluster import delete_request, drift, list_request, make_request, normalize, priority_request


class Object:
    def from_json_string(self, value):
        import json
        for key, item in json.loads(value).items(): setattr(self, key, item)
class Models:
    ListRayClustersRequest = Object
    CreateRayClusterRequest = Object
    UpdateRayClusterRequest = Object
    DeleteRayClusterRequest = Object
    ModifyClusterPriorityRequest = Object


def params():
    return {"name": "analytics-ray", "description": "shared", "group_id": None, "resource_partition_id": "rp-1",
            "queue": "notebooks", "image": "ray:1", "image_pull_policy": "IfNotPresent", "image_pull_type": "BuiltIn",
            "resource_config": None, "resource_config_id": "rc-1", "catalog": '{ "volumes": [] }',
            "advanced_options": '{"spec.x": 1}', "priority": 5, "tags": [{"key": "team", "value": "data"}]}


def test_list_request_is_paginated():
    request = list_request(Models, 2)
    assert request.Page == 2 and request.PageSize == 200


def test_create_normalizes_json_and_tags():
    request = make_request(Models, params())
    assert request.Catalog == '{"volumes":[]}' and request.Tags == [{"TagKey": "team", "TagValue": "data"}]


def test_update_and_delete_use_stable_cluster_id():
    update = make_request(Models, params(), update=True, cluster_id="ray-1")
    assert update.Id == "ray-1" and not hasattr(update, "Priority")
    assert delete_request(Models, "ray-1").Id == "ray-1"
    priority = priority_request(Models, "ray-1", 6)
    assert priority.Id == "ray-1" and priority.Priority == 6


def test_normalized_readback_is_idempotent():
    current = normalize({"Description": "shared", "ResourcePartitionId": "rp-1", "Queue": "notebooks", "Image": "ray:1",
                         "ImagePullPolicy": "IfNotPresent", "ImagePullType": "BuiltIn", "ResourceConfigId": "rc-1",
                         "Catalog": '{"volumes": []}', "AdvancedOptions": '{ "spec.x": 1 }', "Priority": 5,
                         "Tags": [{"TagValue": "data", "TagKey": "team"}]})
    assert drift(params(), current) == {}
