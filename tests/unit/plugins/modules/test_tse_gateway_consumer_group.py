from ansible_collections.susunola.tencentcloud.plugins.modules.tse_gateway_consumer_group import create_request, update_request


class Value(object): pass
class Models(object):
    CreateCloudNativeAPIGatewayConsumerGroupRequest = Value
    ModifyCloudNativeAPIGatewayConsumerGroupRequest = Value


def test_consumer_group_requests_cover_mutable_fields():
    p = {"gateway_id":"g1", "name":"trusted", "status":"Enable", "description":"apps"}
    assert create_request(Models, p).Status == "Enable"
    request = update_request(Models, p, {"ConsumerGroupId":"cg1"})
    assert request.ConsumerGroupId == "cg1"
    assert request.Description == "apps"
