from ansible_collections.susunola.tencentcloud.plugins.modules.tse_gateway_ip_lookup_info import request


class Value(object):
    pass


class Models(object):
    DescribeCloudNativeAPIGatewayInfoByIpRequest = Value


def test_ip_lookup_request_maps_public_ip():
    value = request(Models, "203.0.113.10")
    assert value.PublicNetworkIP == "203.0.113.10"
