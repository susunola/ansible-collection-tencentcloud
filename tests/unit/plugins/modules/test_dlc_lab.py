from ansible_collections.susunola.tencentcloud.plugins.modules.dlc_lab import delete_request, desired, drift, list_request, make_request, normalize


class Object:
    def from_json_string(self, value):
        import json
        for key, item in json.loads(value).items(): setattr(self, key, item)
class Models:
    ListLabsRequest = Object
    CreateLabRequest = Object
    UpdateLabRequest = Object
    DeleteLabRequest = Object


def params():
    return {"name": "analytics-lab", "resource_partition_id": "rp-1", "queue": "default", "lab_image": "image:1",
            "image": None, "description": "team lab", "image_pull_policy": "IfNotPresent", "lab_image_pull_policy": None,
            "image_pull_type": "BuiltIn", "lab_image_pull_type": "BuiltIn", "resource_config_id": "rc-1", "group_id": None,
            "priority": 5, "enable_token": True, "example_id": None, "code_archive_url": None,
            "tags": [{"key": "team", "value": "data"}], "persistent_work_dir": None,
            "resource_config": '{ "worker": 2 }', "catalog": None, "advanced_options": None}


def test_list_request_is_one_based_and_bounded():
    request = list_request(Models, 3)
    assert request.Page == 3 and request.PageSize == 200


def test_create_normalizes_tags_and_json():
    request = make_request(Models, params())
    assert request.Name == "analytics-lab" and request.Tags == [{"TagKey": "team", "TagValue": "data"}]
    assert request.ResourceConfig == '{"worker":2}'


def test_update_excludes_creation_only_contracts():
    request = make_request(Models, params(), update=True)
    assert request.Description == "team lab" and not hasattr(request, "ResourceConfig")


def test_normalization_makes_order_and_json_whitespace_idempotent():
    current = normalize({"Tags": [{"TagValue": "data", "TagKey": "team"}], "ResourceConfig": '{"worker": 2}'})
    target = desired(params(), current)
    assert drift(params(), target, {"resource_config": "ResourceConfig", "tags": "Tags"}) == {}


def test_delete_uses_stable_lab_id():
    assert delete_request(Models, "lab-1").Id == "lab-1"
