from ansible_collections.susunola.tencentcloud.plugins.modules.dlc_data_engine import (
    create_request, delete_request, describe_request, drift, image_switch_request, image_versions_request, operation_request, update_request,
)


class Object:
    def from_json_string(self, value):
        import json
        for key, item in json.loads(value).items(): setattr(self, key, item)


class Filter(Object): pass
class Models:
    DescribeDataEnginesRequest = Object
    CreateDataEngineRequest = Object
    UpdateDataEngineRequest = Object
    SuspendResumeDataEngineRequest = Object
    DeleteDataEngineRequest = Object
    DescribeDataEngineImageVersionsRequest = Object
    SwitchDataEngineImageRequest = Object
    Filter = Filter


def params():
    return {"name": "spark-prod", "engine_type": "spark", "cluster_type": "spark_cu", "mode": 1,
            "pay_mode": 0, "size": 16, "min_clusters": 1, "max_clusters": 3, "auto_resume": True,
            "auto_suspend": None, "auto_suspend_time": None, "max_concurrency": 5,
            "tolerable_queue_time": None, "description": "production", "cidr_block": None,
            "engine_network_id": "network-1", "engine_exec_type": "SQL", "resource_type": "Standard_CU",
            "engine_generation": "SuperSQL", "image_version_name": None}


def test_describe_uses_exact_name_filter_and_pagination():
    request = describe_request(Models, "spark-prod", 100)
    assert request.Offset == 100 and request.Limit == 100 and request.ExcludePublicEngine is True
    assert request.Filters[0].Name == "data-engine-name" and request.Filters[0].Values == ["spark-prod"]


def test_create_maps_readable_contract():
    request = create_request(Models, params())
    assert request.DataEngineName == "spark-prod" and request.EngineType == "spark"
    assert request.Size == 16 and request.EngineNetworkId == "network-1" and request.Message == "production"
    assert not hasattr(request, "ImageVersionName")


def test_update_only_maps_mutable_values():
    request = update_request(Models, params())
    assert request.DataEngineName == "spark-prod" and request.Size == 16 and request.MaxClusters == 3
    assert not hasattr(request, "EngineType")


def test_lifecycle_requests_are_explicit():
    assert operation_request(Models, "spark-prod", "suspend").Operate == "suspend"
    assert delete_request(Models, "spark-prod").DataEngineNames == ["spark-prod"]


def test_image_switch_uses_catalog_lookup_and_stable_ids():
    request = image_versions_request(Models, "SparkSQL")
    assert request.EngineType == "SparkSQL" and request.Sort == "UpdateTime" and request.Asc is False
    request = image_switch_request(Models, "engine-1", "image-2")
    assert request.DataEngineId == "engine-1" and request.NewImageVersionId == "image-2"


def test_drift_ignores_omitted_values():
    value = params(); value["size"] = None
    assert drift(value, {"Size": 8, "MinClusters": 2, "MaxClusters": 3, "AutoResume": True, "MaxConcurrency": 4}) == {
        "MinClusters": (2, 1), "MaxConcurrency": (4, 5)
    }
