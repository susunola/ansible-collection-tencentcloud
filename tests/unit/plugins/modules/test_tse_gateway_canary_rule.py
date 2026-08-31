import json
from ansible_collections.susunola.tencentcloud.plugins.modules.tse_gateway_canary_rule import contains, mutation_request


class Value(object):
    def from_json_string(self,value):
        for key,item in json.loads(value).items(): setattr(self,key,item)


def test_canary_request_injects_stable_priority():
    p={"gateway_id":"g1","service_id":"s1","priority":90}
    request=mutation_request(Value,p,{"Enabled":True})
    assert request.Priority==90
    assert request.CanaryRule["Priority"]==90


def test_contains_allows_server_enriched_rule():
    assert contains({"Priority":90,"Enabled":True,"ServiceName":"orders"},{"Priority":90,"Enabled":True})
