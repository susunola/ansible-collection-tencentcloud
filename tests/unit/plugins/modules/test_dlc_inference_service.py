from ansible_collections.susunola.tencentcloud.plugins.modules.dlc_inference_service import create_request, get_request, list_request, readable_conflict, state_request


class Model:
    def from_json_string(self, value):
        import json
        for key, item in json.loads(value).items(): setattr(self, key, item)


class Models:
    CreateInferenceServiceRequest = GetInferenceServiceRequest = ListInferenceServicesRequest = StopInferenceServiceRequest = RestartInferenceServiceRequest = Tag = Model


def params(): return {"name": "bge", "model_uid": "model-1", "model_version": "v2", "engine": "vllm", "replicas": 2, "resource_partition_id": "rp-1", "image": "image", "model_identifier": "bge-prod", "queue": "inference", "deployment_name": None, "head_high_availability_enabled": True, "advanced_params": '{"b":2,"a":1}', "image_pull_policy": "IfNotPresent", "autoscaling_enabled": True, "min_replicas": 1, "max_replicas": 4, "autoscaler_options": None, "api_key_ids": ["key-1"], "advanced_options": None, "is_custom": False, "runtime_env": None, "resource_tags": [{"key": "env", "value": "prod"}]}


def test_create_payload_normalizes_json_and_tags():
    p = params(); request = create_request(Models, p)
    assert request.ModelUid == "model-1" and request.ModelVersion == "v2"
    assert request.AdvancedParams == '{"a":1,"b":2}' and request.ResourceTags[0].TagKey == "env"


def test_identity_state_and_conflict_requests():
    p = params(); current = {"ModelUid": "model-1", "ModelVersion": "v1", "ModelIdentifier": "bge-prod", "IsCustom": False, "ResourceTags": [{"TagKey": "env", "TagValue": "prod"}]}
    assert readable_conflict(p, current) == {"ModelVersion": ("v1", "v2")}
    assert list_request(Models, 2).Page == 2 and get_request(Models, "svc-1").ServiceId == "svc-1"
    assert state_request(Models.StopInferenceServiceRequest, "svc-1").ServiceId == "svc-1"
