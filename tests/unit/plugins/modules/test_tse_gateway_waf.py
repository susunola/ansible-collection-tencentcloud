from ansible_collections.susunola.tencentcloud.plugins.modules.tse_gateway_waf_protection import enabled_value, status_map
from ansible_collections.susunola.tencentcloud.plugins.modules.tse_gateway_waf_domains import request


class Value(object):
    pass


def test_waf_status_normalizes_sdk_strings():
    assert enabled_value("open") is True
    assert enabled_value("close") is False
    assert status_map({"ServicesStatus": [{"Id": "s1", "Status": "enabled"}]}, "Service") == {"s1": True}


def test_waf_domain_request_maps_delta():
    r = request(Value, {"gateway_id": "g1"}, ["api.example.com"])
    assert r.GatewayId == "g1" and r.Domains == ["api.example.com"]
