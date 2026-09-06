from ansible_collections.susunola.tencentcloud.plugins.modules.dlc_data_engine_config import (
    _pairs,
    _template,
    describe_request,
    desired,
    engine_request,
    normalize,
    update_request,
)


class Object:
    def from_json_string(self, value):
        import json

        for key, item in json.loads(value).items():
            setattr(self, key, item)


class Models:
    DescribeDataEnginesRequest = DescribeUserDataEngineConfigRequest = UpdateUserDataEngineConfigRequest = Object
    DataEngineConfigPair = SessionResourceTemplate = Filter = Object


def test_requests_filter_exact_engine_identity():
    request = engine_request(Models, "spark-prod", 100)
    assert request.Offset == 100 and request.Filters[0].Name == "data-engine-name"
    assert request.Filters[0].Values == ["spark-prod"]
    request = describe_request(Models, "engine-1", 200)
    assert request.Offset == 200 and request.Filters[0].Name == "engine-id"
    assert request.Filters[0].Values == ["engine-1"]


def test_configuration_normalization_is_order_independent():
    value = normalize(
        {
            "DataEngineId": "engine-1",
            "DataEngineConfigPairs": [{"ConfigItem": "z", "ConfigValue": "2"}, {"ConfigItem": "a", "ConfigValue": "1"}],
            "SessionResourceTemplate": {
                "ExecutorNums": 2,
                "RunningTimeParameters": [{"ConfigItem": "b", "ConfigValue": "2"}, {"ConfigItem": "a", "ConfigValue": "1"}],
            },
        }
    )
    assert value["DataEngineConfigPairs"] == [{"ConfigItem": "a", "ConfigValue": "1"}, {"ConfigItem": "z", "ConfigValue": "2"}]
    assert value["SessionResourceTemplate"]["RunningTimeParameters"][0]["ConfigItem"] == "a"


def test_desired_preserves_omitted_session_template():
    current = {"SessionResourceTemplate": {"DriverSize": "medium"}}
    p = {"config_pairs": [{"key": "spark.sql.adaptive.enabled", "value": "true"}], "session_resource_template": None}
    assert desired(p, "engine-1", current)["SessionResourceTemplate"] == {"DriverSize": "medium"}


def test_update_serializes_complete_configuration():
    target = {
        "DataEngineId": "engine-1",
        "DataEngineConfigPairs": _pairs([{"key": "b", "value": "2"}, {"key": "a", "value": "1"}]),
        "SessionResourceTemplate": _template({"driver_size": "medium", "executor_nums": 2}),
    }
    request = update_request(Models, target)
    assert request.DataEngineId == "engine-1"
    assert [x.ConfigItem for x in request.DataEngineConfigPairs] == ["a", "b"]
    assert request.SessionResourceTemplate.DriverSize == "medium" and request.SessionResourceTemplate.ExecutorNums == 2
