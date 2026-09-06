from ansible_collections.susunola.tencentcloud.plugins.modules.dlc_data_mask_strategy import (
    create_request,
    delete_request,
    describe_request,
    normalize,
    normalize_groups,
    normalize_users,
    update_request,
)


class Object:
    def from_json_string(self, value):
        import json

        for key, item in json.loads(value).items():
            setattr(self, key, item)


class Filter(Object):
    pass


class Models:
    DescribeDataMaskStrategiesRequest = Object
    CreateDataMaskStrategyRequest = Object
    UpdateDataMaskStrategyRequest = Object
    DeleteDataMaskStrategyRequest = Object
    DataMaskStrategyInfo = Object
    Filter = Filter


def target():
    return {
        "StrategyId": "mask-1",
        "StrategyName": "phone",
        "StrategyType": "MASK_SHOW_LAST_4",
        "StrategyDesc": "phone mask",
        "Groups": [{"WorkGroupId": 2, "StrategyType": "MASK_HASH"}],
        "Users": ["10001", "10002"],
    }


def test_normalization_stabilizes_groups_and_users():
    assert normalize_users("10002;10001;10001") == ["10001", "10002"]
    assert normalize_groups([{"WorkGroupId": 2, "StrategyType": "B"}, {"WorkGroupId": 1, "StrategyType": "A"}])[0]["WorkGroupId"] == 1
    assert normalize({**target(), "Users": "10002;10001"}) == target()


def test_describe_uses_name_filter_and_pagination():
    request = describe_request(Models, {"name": "phone"}, 100)
    assert request.Offset == 100 and request.Filters[0].Name == "strategy-name"


def test_mutation_requests_serialize_normalized_users():
    created = create_request(Models, target())
    updated = update_request(Models, target())
    assert created.Strategy.Users == "10001;10002" and updated.Strategy.StrategyId == "mask-1"
    assert delete_request(Models, "mask-1").StrategyId == "mask-1"
