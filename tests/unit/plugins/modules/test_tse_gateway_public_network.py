from ansible_collections.susunola.tencentcloud.plugins.modules.tse_gateway_public_network import contains, create_request, desired


class Value(object):
    def from_json_string(self,raw): self.raw=raw
class Models(object): CreateCloudNativeAPIGatewayPublicNetworkRequest=Value


def test_public_network_payload_and_access_control_comparison():
    p={"gateway_id":"g1","group_id":"grp1","config":{"InternetMaxBandwidthOut":20,"MultiZoneFlag":True},"access_control":{"Mode":"Whitelist","CidrWhiteList":["10.0.0.0/8"]}}
    assert '"GroupId": "grp1"' in create_request(Models,p).raw
    target=desired(p)
    assert contains(dict(target,Status="Open"),target)
