from ansible_collections.susunola.tencentcloud.plugins.modules.tse_gateway_service import contains, desired, write_request


class Value(object):
    def from_json_string(self,raw): self.raw=raw


def test_gateway_service_payload_and_subset_comparison():
    p={"name":"orders","protocol":"http","timeout":30000,"retries_count":2,"upstream_type":"IPList","upstream_info":{"Targets":[{"Host":"10.0.0.1","Port":80}]},"path":"/"}
    target=desired(p)
    assert contains(dict(target,ID="s1"),target)
    assert '"GatewayId": "g1"' in write_request(Value,p,{"GatewayId":"g1",**target}).raw
