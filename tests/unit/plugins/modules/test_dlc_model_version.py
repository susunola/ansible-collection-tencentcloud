from ansible_collections.susunola.tencentcloud.plugins.modules.dlc_model_version import conflict, create_request, desired, list_request


class Model:
    def from_json_string(self, value):
        import json

        for key, item in json.loads(value).items():
            setattr(self, key, item)


class Models:
    ListModelVersionsRequest = CreateModelVersionRequest = GooseFSConfig = Model


def params():
    return {
        "model_uid": "model-1",
        "version": "v2",
        "description": "release",
        "storage_uri": "cos://bucket/v2",
        "use_custom_storage": True,
        "storage_type": "COS",
        "goosefs_config": None,
    }


def test_immutable_version_conflict_is_precise():
    p = params()
    current = {"Version": "v2", "Description": "old", "StorageUri": "cos://bucket/v2", "UseCustomStorage": True}
    assert conflict(p, current) == {"Description": ("old", "release")}
    assert desired(p)["Version"] == "v2"


def test_create_and_list_requests_use_parent_and_exact_version():
    p = params()
    create = create_request(Models, p)
    listing = list_request(Models, p, 4)
    assert create.ModelUid == "model-1" and create.ModelVersion == "v2" and create.StorageType == "COS"
    assert listing.ModelUid == "model-1" and listing.Page == 4 and listing.PageSize == 200
