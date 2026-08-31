from ansible_collections.susunola.tencentcloud.plugins.modules.tse_gateway_model_api import create_payload, modify_payload, service_ids


def test_service_ids_normalizes_direct_and_routed_services():
    value={"ModelServiceId":"s1","ModelServiceRoute":{"WeightedConfig":[{"ModelServiceId":"s2"}],"ModelNameConfig":[{"ModelServiceId":"s1"}]}}
    assert service_ids(value)==["s1","s2"]


def test_modify_payload_preserves_resolved_service_links():
    p={"gateway_id":"g1","name":None,"config":{"BasePath":"/v2"}}
    current={"Id":"api1","Name":"chat","BasePath":"/v1","ModelServiceId":"s1"}
    payload=modify_payload(p,current)
    assert payload["ListModelServiceId"]==["s1"] and payload["BasePath"]=="/v2"


def test_create_payload_keeps_routing_config():
    p={"gateway_id":"g1","name":"chat","config":{"SceneType":"Chat","RequestProtocol":"OpenAI","ListModelServiceId":["s1"]}}
    assert create_payload(p)["ListModelServiceId"]==["s1"]
