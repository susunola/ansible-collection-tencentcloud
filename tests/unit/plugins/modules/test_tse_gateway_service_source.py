import json

from ansible_collections.susunola.tencentcloud.plugins.modules.tse_gateway_service_source import create_request, delete_request, desired, readable, update_request


class Value(object):
    def from_json_string(self,raw): self.raw=raw
class Models(object):
    CreateNativeGatewayServiceSourceRequest=Value
    ModifyNativeGatewayServiceSourceRequest=Value
    DeleteNativeGatewayServiceSourceRequest=Value


def test_service_source_requests_map_full_lifecycle():
    p={"gateway_id":"g1","source_id":"nacos-1","source_name":"registry","source_type":"Customer-Nacos","source_info":{"Addresses":["10.0.0.2:8848"],"Auth":{"Username":"reader","Password":"secret"}}}
    assert json.loads(create_request(Models,p).raw)["GatewayID"]=="g1"
    current={"SourceID":"nacos-1","SourceName":"old","SourceInfo":{}}
    assert json.loads(update_request(Models,p,current).raw)["SourceName"]=="registry"
    without_info=dict(p,source_info=None)
    assert "SourceInfo" not in json.loads(update_request(Models,without_info,current).raw)
    assert json.loads(delete_request(Models,p,"nacos-1").raw)["SourceID"]=="nacos-1"


def test_service_source_comparison_removes_write_only_credentials():
    value={"SourceInfo":{"Addresses":["10.0.0.2:8848"],"Auth":{"Username":"reader","Password":"secret","AccessToken":"token"}}}
    assert readable(value)=={"SourceInfo":{"Addresses":["10.0.0.2:8848"],"Auth":{"Username":"reader"}}}
    p={"source_name":"registry","source_type":"Customer-Nacos","source_info":value["SourceInfo"]}
    assert desired(p)["SourceInfo"]["Auth"]=={"Username":"reader"}
