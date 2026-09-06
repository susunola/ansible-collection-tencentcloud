from ansible_collections.susunola.tencentcloud.plugins.modules.tsf_lane_rule import comparable, desired, normalize_tags


def test_lane_rule_normalizes_tag_order_and_read_only_fields():
    tags = [{"TagName": "z", "TagOperator": "EQUAL", "TagValue": "1", "TagId": "x"}, {"TagName": "a", "TagOperator": "EQUAL", "TagValue": "2"}]
    assert normalize_tags(tags)[0] == {"TagName": "a", "TagOperator": "EQUAL", "TagValue": "2"}


def test_lane_rule_maps_observable_state():
    params = {"name": "canary", "lane_id": "lane-a", "remark": None, "enabled": True, "tag_relationship": "RELEATION_AND", "tags": [{"name": "x-canary", "operator": "EQUAL", "value": "true"}]}
    target = desired(params)
    assert comparable(dict(target, RuleId="rule-a"), target) == target
