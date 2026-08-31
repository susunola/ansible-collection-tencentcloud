from ansible_collections.susunola.tencentcloud.plugins.modules.tse_cloud_native_gateway import create_request, update_request


class Value(object):
    def from_json_string(self,raw): self.raw=raw
class Models(object):
    CreateCloudNativeAPIGatewayRequest=Value
    ModifyCloudNativeAPIGatewayRequest=Value


def test_gateway_requests_map_creation_and_mutable_fields():
    p={"name":"gw","gateway_type":"kong","gateway_version":"2.5.1","node_config":{"Number":2},"vpc_config":{"VpcId":"v1"},"description":None,"tags":None,"enable_cls":True,"feature_version":"STANDARD","internet_max_bandwidth_out":None,"region":"ap-guangzhou","ingress_class_name":None,"trade_type":0,"internet_config":None,"prometheus_id":None}
    assert '"EngineRegion": "ap-guangzhou"' in create_request(Models,p).raw
    value=update_request(Models,"g1",{"Name":"gw2","Description":"x","EnableCls":True,"InternetPayMode":"TRAFFIC","DeleteProtect":True})
    assert value.GatewayId=="g1" and value.DeleteProtect is True
