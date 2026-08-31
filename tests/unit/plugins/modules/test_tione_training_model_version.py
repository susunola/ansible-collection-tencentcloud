from ansible_collections.susunola.tencentcloud.plugins.modules.tione_training_model_version import create_request, delete_request, conflicts


class Object:
    def from_json_string(self, value): self.value = value
class Models: CreateTrainingModelRequest = DeleteTrainingModelVersionRequest = CosPathInfo = ImageInfo = Object


def params():
    return {"model_id": "m1", "version_id": "mv1", "version": "v2", "import_method": "VERSION", "reasoning_environment_source": "SYSTEM", "training_job_name": None, "training_job_id": "t1", "training_job_version": "i1", "training_model_cos_path": None, "model_output_path": {"Bucket": "out"}, "training_model_source": "JOB", "algorithm_framework": "PYTORCH", "reasoning_environment": None, "reasoning_environment_id": "img1", "reasoning_image_info": None, "training_model_index": None, "model_move_mode": "COPY", "training_preference": None, "model_version_type": "NORMAL", "model_format": "PYTORCH", "auto_clean": "false", "max_reserved_models": 12, "model_clean_period": 60, "is_qat": False, "delete_cos": True}


def test_create_is_scoped_to_existing_parent_and_maps_version_fields():
    request = create_request(Models, params())
    assert request.TrainingModelId == "m1" and request.TrainingModelVersion == "v2" and request.ImportMethod == "VERSION"
    assert request.ModelVersionType == "NORMAL" and request.ModelOutputPath is not None and request.IsQAT is False


def test_delete_uses_only_stable_version_id_and_cos_choice():
    request = delete_request(Models, params())
    assert request.TrainingModelVersionId == "mv1" and request.EnableDeleteCos is True


def test_conflicts_uses_readable_dto_names():
    p = params(); current = {"TrainingModelVersion": "v2", "TrainingModelId": "m1", "TrainingJobId": "t1", "TrainingJobVersion": "i1", "ModelOutputPath": {"Bucket": "out"}, "TrainingModelSource": "JOB", "AlgorithmFramework": "PYTORCH", "ReasoningEnvironmentSource": "SYSTEM", "ReasoningEnvironmentId": "img1", "VersionType": "NORMAL", "TrainingModelFormat": "PYTORCH", "AutoClean": "false", "MaxReservedModels": 12, "ModelCleanPeriod": 60, "IsQAT": False}
    assert conflicts(p, current) == {}
