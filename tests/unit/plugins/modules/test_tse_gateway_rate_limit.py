from ansible_collections.susunola.tencentcloud.plugins.modules.tse_gateway_rate_limit import contains, request


class Value(object):
    def from_json_string(self,raw): self.raw=raw


def test_rate_limit_request_maps_scope_specific_resource_key():
    config={"Enabled":True,"QpsThresholds":[{"Unit":"second","Max":100}]}
    route=request(Value,None,{"gateway_id":"g1","scope":"route","resource":"r1"},config)
    service=request(Value,None,{"gateway_id":"g1","scope":"service","resource":"s1"},config)
    assert '"Id": "r1"' in route.raw and '"Name": "s1"' in service.raw
    assert contains(dict(config,Policy="local"),config)
