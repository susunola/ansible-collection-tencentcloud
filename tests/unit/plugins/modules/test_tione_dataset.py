from ansible_collections.susunola.tencentcloud.plugins.modules.tione_dataset import create_request, delete_request, find, conflict


class Object:
    def from_json_string(self, value): self.value = value
class Models:
    CreateDatasetRequest = DeleteDatasetRequest = DescribeDatasetsRequest = Filter = CosPathInfo = Tag = SchemaInfo = CFSConfig = Object


def params():
    return {"name": "sft", "dataset_id": None, "project_id": "p1", "dataset_type": "TYPE_DATASET_LLM", "storage_data_path": {"Bucket": "b"}, "storage_label_path": None, "dataset_tags": [{"TagKey": "env", "TagValue": "prod"}], "annotation_status": None, "annotation_type": None, "annotation_format": None, "schema_infos": None, "is_schema_existed": None, "content_type": "TYPE_TEXT_LINE", "dataset_scene": "LLM", "scene_tags": ["z", "a"], "cfs_config": None, "delete_label_files": False}


def test_create_maps_nested_immutable_fields():
    request = create_request(Models, params())
    assert request.DatasetName == "sft" and request.TiProjectId == "p1" and request.DatasetType == "TYPE_DATASET_LLM"
    assert len(request.DatasetTags) == 1 and request.SceneTags == ["z", "a"]


def test_delete_uses_only_stable_id_and_explicit_label_choice():
    p = params(); p["dataset_id"] = "ds-1"; p["delete_label_files"] = True
    request = delete_request(Models, p)
    assert request.DatasetId == "ds-1" and request.DeleteLabelEnable is True and request.TiProjectId == "p1"


class Item:
    def __init__(self, value): self.value = value
    def _serialize(self, allow_none=True): return dict(self.value)
class Response:
    def __init__(self, values, total): self.DatasetGroups, self.TotalCount = [Item(x) for x in values], total
class Client:
    def __init__(self, responses): self.responses = list(responses); self.requests = []
    def DescribeDatasets(self, request): self.requests.append(request); return self.responses.pop(0)
class Module:
    def sdk_call(self, fn, request): return fn(request)
    def fail_json(self, **kwargs): raise AssertionError(kwargs)


def test_find_uses_dataset_id_as_strong_identity():
    p = params(); p["dataset_id"] = "ds-2"
    client = Client([Response([{"DatasetId": "ds-2", "DatasetName": "sft"}], 1)])
    value = find(Module(), client, Models, p)
    assert value["DatasetId"] == "ds-2" and client.requests[0].DatasetIds == ["ds-2"]


def test_conflict_normalizes_unordered_tags_and_scene_tags():
    p = params()
    current = {"DatasetName": "sft", "DatasetType": "TYPE_DATASET_LLM", "StorageDataPath": {"Bucket": "b"}, "DatasetTags": [{"TagValue": "prod", "TagKey": "env"}], "ContentType": "TYPE_TEXT_LINE", "DatasetScene": "LLM", "SceneTags": ["a", "z"]}
    assert conflict(p, current) == {}
