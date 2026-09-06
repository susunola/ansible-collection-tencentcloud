from ansible_collections.susunola.tencentcloud.plugins.modules.tione_training_model_version_info import detail_request, list_request


class Object:
    pass


class Models:
    DescribeTrainingModelVersionRequest = DescribeTrainingModelVersionsRequest = Filter = Object


def test_detail_request_uses_stable_version_id():
    request = detail_request(Models, "mv-1")
    assert request.TrainingModelVersionId == "mv-1"


def test_list_request_is_parent_scoped_and_stably_filtered():
    request = list_request(Models, "model-1", {"ModelVersionType": "NORMAL", "AlgorithmFramework": ["PYTORCH"]})
    assert request.TrainingModelId == "model-1"
    assert [(x.Name, x.Values) for x in request.Filters] == [("AlgorithmFramework", ["PYTORCH"]), ("ModelVersionType", ["NORMAL"])]
