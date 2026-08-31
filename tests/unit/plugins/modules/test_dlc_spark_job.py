from ansible_collections.susunola.tencentcloud.plugins.modules.dlc_spark_job import delete_request, describe_request, drift, make_request


class Object:
    def from_json_string(self, value):
        import json
        for key, item in json.loads(value).items():
            setattr(self, key, item)


class Models:
    DescribeSparkAppJobRequest = Object
    CreateSparkAppRequest = Object
    ModifySparkAppRequest = Object
    DeleteSparkAppRequest = Object


def params():
    return {"name": "daily-etl", "app_type": 1, "data_engine": "spark-prod", "app_file": "cosn://jobs/etl.jar",
            "role_arn": 10001, "driver_size": "medium", "executor_size": "large", "executor_nums": 2,
            "executor_max_nums": 8, "main_class": "com.example.Etl", "app_conf": "spark.x=y", "cmd_args": "--day today",
            "max_retries": None, "data_source": None, "package_source": "cos", "jars": "cosn://jobs/lib.jar",
            "files": None, "python_files": None, "archives": None, "spark_image": None, "spark_image_version": None,
            "inherit_engine_config": True, "session_id": None, "session_started": None}


def test_describe_prefers_stable_id_over_name():
    assert describe_request(Models, "daily-etl").JobName == "daily-etl"
    request = describe_request(Models, "ignored", "job-1")
    assert request.JobId == "job-1" and request.JobName is None


def test_create_maps_definition_and_dependency_source():
    request = make_request(Models, params())
    assert request.AppName == "daily-etl" and request.AppType == 1 and request.AppExecutorMaxNumbers == 8
    assert request.IsInherit == 1 and request.IsLocal == "cos" and request.IsLocalJars == "cos"


def test_modify_includes_stable_job_id():
    request = make_request(Models, params(), update=True, job_id="job-1")
    assert request.SparkAppId == "job-1" and request.AppName == "daily-etl"


def test_drift_maps_api_read_names_and_ignores_omitted_values():
    current = {"JobType": 1, "DataEngine": "spark-prod", "JobFile": "cosn://jobs/etl.jar", "RoleArn": 10001,
               "JobDriverSize": "small", "JobExecutorSize": "large", "JobExecutorNums": 2, "JobExecutorMaxNumbers": 8,
               "MainClass": "com.example.Etl", "JobConf": "spark.x=y", "CmdArgs": "--day today", "IsLocal": "cos",
               "JobJars": "cosn://jobs/lib.jar", "IsLocalJars": "cos", "IsInherit": 1}
    assert drift(params(), current) == {"JobDriverSize": ("small", "medium")}


def test_delete_uses_exact_job_name():
    assert delete_request(Models, "daily-etl").AppName == "daily-etl"
