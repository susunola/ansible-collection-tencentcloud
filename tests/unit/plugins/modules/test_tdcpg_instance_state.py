from ansible_collections.susunola.tencentcloud.plugins.modules.tdcpg_instance_state import action_request, recover_request


class Value(object):
    pass


class Models(object):
    RecoverClusterInstancesRequest = Value


def test_instance_action_requests_map_exact_set_and_period():
    p = {"cluster_id": "c1", "instance_ids": ["i1", "i2"], "period_months": 3}
    assert action_request(Value, p).InstanceIdSet == ["i1", "i2"]
    assert recover_request(Models, p).Period == 3
