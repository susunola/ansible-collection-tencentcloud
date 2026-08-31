from ansible_collections.susunola.tencentcloud.plugins.modules.dlc_engine_resource_group import (
    base_request, capacity_request, create_request, delete_request, describe_request, drift, network_request,
)


class Object: pass
class Filter(Object): pass
class Models:
    DescribeStandardEngineResourceGroupsRequest = Object
    CreateStandardEngineResourceGroupRequest = Object
    UpdateStandardEngineResourceGroupBaseInfoRequest = Object
    UpdateStandardEngineResourceGroupResourceInfoRequest = Object
    UpdateEngineResourceGroupNetworkConfigInfoRequest = Object
    DeleteStandardEngineResourceGroupRequest = Object
    Filter = Filter


def params():
    return {"name": "spark-etl", "data_engine_name": "spark-prod", "auto_launch": True, "auto_pause": True,
            "auto_pause_time": 15, "max_concurrency": 8, "driver_cu_spec": "medium", "executor_cu_spec": "large",
            "min_executors": 2, "max_executors": 10, "network_config_names": ["data", "base", "data"],
            "launch_now": False, "effective_now": True}


def test_describe_uses_unique_name_filter_and_pagination():
    request = describe_request(Models, "spark-etl", 100)
    assert request.Offset == 100 and request.Limit == 100
    assert request.Filters[0].Name == "engine-resource-group-name-unique"


def test_create_maps_boolean_flags_capacity_and_sorted_networks():
    request = create_request(Models, params())
    assert request.AutoLaunch == 0 and request.AutoPause == 0 and request.IsLaunchNow == 1
    assert request.MinExecutorNums == 2 and request.NetworkConfigNames == ["base", "data"]


def test_update_requests_are_split_by_api_contract():
    p = params(); base, capacity = base_request(Models, p), capacity_request(Models, p)
    assert base.AutoPauseTime == 15 and not hasattr(base, "DriverCuSpec")
    assert capacity.DriverCuSpec == "medium" and capacity.IsEffectiveNow == 0
    network = network_request(Models, "rg-1", ["z", "a", "z"], False)
    assert network.EngineResourceGroupId == "rg-1" and network.NetworkConfigNames == ["a", "z"] and network.IsEffectiveNow == 1


def test_drift_normalizes_boolean_flags_and_network_order():
    current = {"AutoLaunch": 0, "AutoPause": 1, "AutoPauseTime": 15, "MaxConcurrency": 8,
               "DriverCuSpec": "medium", "ExecutorCuSpec": "large", "MinExecutorNums": 1,
               "MaxExecutorNums": 10, "NetworkConfigNames": ["data", "base"]}
    value = params(); value["auto_pause"] = False
    assert drift(value, current) == {"MinExecutorNums": (1, 2)}


def test_delete_uses_exact_name():
    assert delete_request(Models, "spark-etl").EngineResourceGroupName == "spark-etl"
