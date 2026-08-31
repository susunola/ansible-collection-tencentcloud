from ansible_collections.susunola.tencentcloud.plugins.modules.tse_gateway_autoscaler_strategy import mutation_payload, target
from ansible_collections.susunola.tencentcloud.plugins.modules.tse_gateway_autoscaler_binding import groups_request, mutation_request, strategy_request


class Value(object): pass
class Models(object):
    DescribeAutoScalerResourceStrategiesRequest=Value
    DescribeNativeGatewayServerGroupsRequest=Value


def test_strategy_target_preserves_unspecified_config():
    p={"gateway_id":"g1","name":None,"description":None,"metric_config":{"Enabled":True},"cron_config":None,"max_replicas":None}
    current={"StrategyId":"st1","StrategyName":"elastic","Description":"prod","CronConfig":{"Enabled":False},"MaxReplicas":8}
    value=target(p,current)
    assert value["Config"]=={"Enabled":True} and value["CronConfig"]=={"Enabled":False}
    assert mutation_payload(p,current)["StrategyId"]=="st1"


def test_binding_request_maps_group_delta():
    p={"gateway_id":"g1","strategy_id":"st1"}
    request=mutation_request(Value,p,["group2"])
    assert request.StrategyId=="st1" and request.GroupIds==["group2"]
    assert strategy_request(Models,p).GatewayId=="g1"
    group_request=groups_request(Models,p)
    assert group_request.GatewayId=="g1" and group_request.Limit==100
