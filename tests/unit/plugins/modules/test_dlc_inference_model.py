from ansible_collections.susunola.tencentcloud.plugins.modules.dlc_inference_model import create_request, immutable_drift, list_request, mutable_drift, normalize, resource_tags, update_request


class Model:
    def from_json_string(self, value):
        import json
        for key, item in json.loads(value).items(): setattr(self, key, item)


class Models:
    CreateInferenceModelRequest = UpdateInferenceModelRequest = GooseFSConfig = Tag = ListInferenceModelsRequest = Model


def params(): return {"name": "bge", "model_uid": "model-1", "model_type": "Embedding", "initial_version": "v1", "provider": "BAAI", "description": "managed", "parameter_size": "1.5B", "tags": ["prod", "embedding"], "tasks": ["Embedding"], "storage_uri": "cos://bucket/bge", "use_custom_storage": True, "storage_type": "COS", "goosefs_config": None, "resource_tags": [{"key": "env", "value": "prod"}]}


def test_normalization_and_drift_split_mutable_and_immutable_fields():
    p = params(); current = normalize({"Name": "bge", "ModelUid": "model-1", "ModelType": "Embedding", "Provider": "BAAI", "Description": "old", "ParameterSize": "1.5B", "Tags": ["embedding", "prod"], "Tasks": ["Embedding"], "StorageType": "cos", "HasCustomStorage": True, "ResourceTags": [{"TagValue": "prod", "TagKey": "env"}]})
    assert mutable_drift(p, current) == {"Description": ("old", "managed")}
    assert immutable_drift(p, current) == {}
    assert resource_tags(p["resource_tags"])[0]["TagKey"] == "env"


def test_create_update_and_paging_requests_use_stable_uid():
    p = params(); create = create_request(Models, p); update = update_request(Models, p, "model-1"); listing = list_request(Models, 3)
    assert create.ModelUid == "model-1" and create.InitialVersion == "v1"
    assert create.Tags == ["embedding", "prod"] and create.ResourceTags[0].TagKey == "env"
    assert update.ModelUid == "model-1" and update.Description == "managed"
    assert listing.Page == 3 and listing.PageSize == 200
