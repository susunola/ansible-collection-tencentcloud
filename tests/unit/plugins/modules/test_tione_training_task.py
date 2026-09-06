from ansible_collections.susunola.tencentcloud.plugins.modules.tione_training_task import create_request, conflicts, task_status


class Object:
    def from_json_string(self, value):
        self.value = value


class Models:
    CreateTrainingTaskRequest = ResourceConfigInfo = Tag = ImageInfo = CosPathInfo = StartCmdInfo = EncodedStartCmdInfo = DataConfig = LogConfig = (
        CodeRepoConfig
    ) = ExposeNetworkConfig = EnvVar = TrainToolConfig = ResourceSupplyAttribute = Object


def params():
    return {
        "name": "job",
        "project_id": "p1",
        "charge_type": "POSTPAID_BY_HOUR",
        "resource_configs": [{"Role": "WORKER"}],
        "framework_name": "PYTORCH",
        "framework_version": "2.4",
        "framework_environment": "torch",
        "resource_group_id": None,
        "tags": [{"TagKey": "env", "TagValue": "prod"}],
        "image_info": None,
        "code_package_path": {"Bucket": "code"},
        "start_cmd_info": {"StartCmd": "python train.py"},
        "encoded_start_cmd_info": None,
        "training_mode": "DDP",
        "data_configs": [{"MappingPath": "/data"}],
        "data_source": "DATASET",
        "vpc_id": "vpc-1",
        "subnet_id": "subnet-1",
        "output": {"Bucket": "out"},
        "log_config": None,
        "tuning_parameters": None,
        "log_enable": True,
        "remark": "sft",
        "callback_url": None,
        "code_repos": None,
        "expose_network_config": None,
        "envs": [{"Name": "A", "Value": "B"}],
        "train_tool_config": None,
        "resource_supply_attribute": None,
        "queues": ["q1"],
    }


def test_create_maps_full_training_configuration():
    request = create_request(Models, params())
    assert request.Name == "job" and request.TiProjectId == "p1" and request.ChargeType == "POSTPAID_BY_HOUR"
    assert len(request.ResourceConfigInfos) == 1 and len(request.DataConfigs) == 1 and len(request.Envs) == 1 and request.Queues == ["q1"]


def test_conflicts_only_compares_readable_fields_and_normalizes_tags():
    p = params()
    current = {
        "Name": "job",
        "ChargeType": "POSTPAID_BY_HOUR",
        "ResourceConfigInfos": p["resource_configs"],
        "FrameworkName": "PYTORCH",
        "FrameworkVersion": "2.4",
        "FrameworkEnvironment": "torch",
        "Tags": p["tags"],
        "CodePackagePath": p["code_package_path"],
        "StartCmdInfo": p["start_cmd_info"],
        "TrainingMode": "DDP",
        "DataConfigs": p["data_configs"],
        "DataSource": "DATASET",
        "VpcId": "vpc-1",
        "SubnetId": "subnet-1",
        "Output": p["output"],
        "LogEnable": True,
        "Remark": "sft",
    }
    assert conflicts(p, current) == {}


def test_unreadable_creation_fields_do_not_create_permanent_drift():
    p = params()
    p["name"] = None
    assert "Envs" not in conflicts(p, {}) and "Queues" not in conflicts(p, {})


def test_status_normalization_covers_terminal_values():
    assert task_status({"Status": "SUBMIT_FAILED"}) == "submit_failed" and task_status({"Status": "SUCCEED"}) == "succeed"
