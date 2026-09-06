from ansible_collections.susunola.tencentcloud.plugins.modules.dlc_engine_resource_group import (
    base_request,
    capacity_request,
    config_delta,
    config_request,
    config_update_request,
    create_request,
    delete_request,
    describe_request,
    drift,
    network_request,
)


class Object:
    pass


class Filter(Object):
    pass


class Models:
    DescribeStandardEngineResourceGroupsRequest = Object
    CreateStandardEngineResourceGroupRequest = Object
    UpdateStandardEngineResourceGroupBaseInfoRequest = Object
    UpdateStandardEngineResourceGroupResourceInfoRequest = Object
    UpdateEngineResourceGroupNetworkConfigInfoRequest = Object
    DeleteStandardEngineResourceGroupRequest = Object
    DescribeStandardEngineResourceGroupConfigInfoRequest = Object
    UpdateStandardEngineResourceGroupConfigInfoRequest = Object
    EngineResourceGroupConfigPair = Object
    UpdateConfContext = Object
    Param = Object
    Filter = Filter


def params():
    return {
        "name": "spark-etl",
        "data_engine_name": "spark-prod",
        "auto_launch": True,
        "auto_pause": True,
        "auto_pause_time": 15,
        "max_concurrency": 8,
        "driver_cu_spec": "medium",
        "executor_cu_spec": "large",
        "min_executors": 2,
        "max_executors": 10,
        "network_config_names": ["data", "base", "data"],
        "launch_now": False,
        "effective_now": True,
    }


def test_describe_uses_unique_name_filter_and_pagination():
    request = describe_request(Models, "spark-etl", 100)
    assert request.Offset == 100 and request.Limit == 100
    assert request.Filters[0].Name == "engine-resource-group-name-unique"


def test_create_maps_boolean_flags_capacity_and_sorted_networks():
    value = params()
    value["static_config"] = {"spark.sql.shuffle.partitions": 200}
    value["dynamic_config"] = {}
    request = create_request(Models, value)
    assert request.AutoLaunch == 0 and request.AutoPause == 0 and request.IsLaunchNow == 1
    assert request.MinExecutorNums == 2 and request.NetworkConfigNames == ["base", "data"]
    assert request.StaticConfigPairs[0].ConfigValue == "200" and request.DynamicConfigPairs == []


def test_update_requests_are_split_by_api_contract():
    p = params()
    base, capacity = base_request(Models, p), capacity_request(Models, p)
    assert base.AutoPauseTime == 15 and not hasattr(base, "DriverCuSpec")
    assert capacity.DriverCuSpec == "medium" and capacity.IsEffectiveNow == 0
    network = network_request(Models, "rg-1", ["z", "a", "z"], False)
    assert network.EngineResourceGroupId == "rg-1" and network.NetworkConfigNames == ["a", "z"] and network.IsEffectiveNow == 1


def test_drift_normalizes_boolean_flags_and_network_order():
    current = {
        "AutoLaunch": 0,
        "AutoPause": 1,
        "AutoPauseTime": 15,
        "MaxConcurrency": 8,
        "DriverCuSpec": "medium",
        "ExecutorCuSpec": "large",
        "MinExecutorNums": 1,
        "MaxExecutorNums": 10,
        "NetworkConfigNames": ["data", "base"],
    }
    value = params()
    value["auto_pause"] = False
    assert drift(value, current) == {"MinExecutorNums": (1, 2)}


def test_delete_uses_exact_name():
    assert delete_request(Models, "spark-etl").EngineResourceGroupName == "spark-etl"


def test_config_query_and_exact_update_operations():
    query = config_request(Models, "rg-1", 100)
    assert query.Offset == 100 and query.Filters[0].Name == "engine-resource-group-id"
    changes = {"StaticConfig": ({"remove": "1", "change": "old"}, {"change": "new", "add": "2"})}
    delta = config_delta(changes)
    request = config_update_request(Models, "spark-etl", delta, True)
    operations = {x.ConfigItem: x.Operate for x in request.UpdateConfContext[0].Params}
    assert operations == {"add": "ADD", "change": "MODIFY", "remove": "DELETE"}
    assert request.IsEffectiveNow == 0
