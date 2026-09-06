from ansible_collections.susunola.tencentcloud.plugins.modules.tsf_lane import comparable, desired, normalize_groups


def test_lane_normalizes_group_order_and_ignores_read_only_fields():
    groups = [
        {"GroupId": "group-b", "Entrance": False, "GroupName": "b"},
        {"GroupId": "group-a", "Entrance": True, "LaneGroupId": "lane-group-a"},
    ]
    assert normalize_groups(groups) == [
        {"GroupId": "group-a", "Entrance": True},
        {"GroupId": "group-b", "Entrance": False},
    ]


def test_lane_maps_observable_state():
    params = {"name": "canary", "remark": "checkout", "deployment_groups": [{"group_id": "group-a", "entrance": True}]}
    target = desired(params)
    assert target["LaneGroupList"] == [{"GroupId": "group-a", "Entrance": True}]
    assert comparable(dict(target, LaneId="lane-a"), target) == target
