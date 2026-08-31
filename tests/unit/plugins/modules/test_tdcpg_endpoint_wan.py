from ansible_collections.susunola.tencentcloud.plugins.modules.tdcpg_endpoint_wan import is_open, update_request


class Value(object): pass
class Models(object): ModifyClusterEndpointWanStatusRequest=Value


def test_endpoint_request_and_observed_state():
    request=update_request(Models,{"cluster_id":"c1","endpoint_id":"e1","state":"closed"})
    assert request.WanStatus=="CLOSE"
    assert is_open({"WanDomain":"db.example.com"})
    assert not is_open({"WanIp":None,"WanDomain":None})
