from ansible_collections.susunola.tencentcloud.plugins.modules.tse_gateway_consumer import create_request, update_request


class Value(object): pass
class Models(object):
    CreateCloudNativeAPIGatewayConsumerRequest=Value
    ModifyCloudNativeAPIGatewayConsumerRequest=Value


def test_consumer_requests_use_stable_identity_and_priority():
    p={"gateway_id":"g1","name":"mobile","priority":"High","description":"app"}
    assert create_request(Models,p).Priority=="High"
    assert update_request(Models,p,{"ConsumerId":"c1"}).ConsumerId=="c1"
