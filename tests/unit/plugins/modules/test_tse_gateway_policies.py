from ansible_collections.susunola.tencentcloud.plugins.modules.tse_gateway_cors import request as cors_request, target_config
from ansible_collections.susunola.tencentcloud.plugins.modules.tse_gateway_ip_restriction import request as ip_request


class Value(object): pass


def test_cors_defaults_and_request_identity():
    p={"gateway_id":"g1","scope":"route","resource_id":"r1"}
    target=target_config(p,None)
    request=cors_request(Value,p,target)
    assert request.SourceType=="route" and request.Enabled is True and request.Origins==[]


def test_ip_request_maps_exact_policy():
    p={"gateway_id":"g1","scope":"service","resource_id":"s1"}
    request=ip_request(Value,p,{"Enabled":True,"RestrictionType":"whiteList","AddressList":["10.0.0.0/8"]})
    assert request.SourceId=="s1" and request.AddressList==["10.0.0.0/8"]
