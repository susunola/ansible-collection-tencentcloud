from ansible_collections.susunola.tencentcloud.plugins.modules.tse_gateway_route import contains, desired, write_request


class Value(object):
    def from_json_string(self,raw): self.raw=raw


def test_gateway_route_payload_and_subset_comparison():
    p={"name":"orders","service_id":"s1","methods":["GET"],"hosts":None,"paths":["/orders"],"protocols":["https"],"preserve_host":None,"https_redirect_status_code":None,"strip_path":True,"force_https":None,"destination_ports":None,"headers":None,"request_buffering":None,"response_buffering":None,"regex_priority":None,"query_string_parameters":None}
    target=desired(p)
    assert contains(dict(target,ID="r1"),target)
    assert '"RouteName": "orders"' in write_request(Value,{"GatewayId":"g1","RouteName":"orders"}).raw
