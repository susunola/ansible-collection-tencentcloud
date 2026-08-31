from ansible_collections.susunola.tencentcloud.plugins.modules.tse_gateway_model_service import create_payload, modify_payload


def test_create_payload_maps_full_service_identity():
    p={"gateway_id":"g1","name":"openai","config":{"ServiceType":"LLMService","ModelProvider":"OpenAI","ModelProtocol":"OpenAI/v1","ModelSelector":"Specify","DefaultModel":"gpt"}}
    assert create_payload(p)["ModelProvider"]=="OpenAI"


def test_modify_payload_preserves_unspecified_values():
    p={"gateway_id":"g1","name":None,"config":{"ReadTimeout":30000}}
    current={"Id":"ms1","Name":"openai","ReadTimeout":60000,"Retries":2}
    payload=modify_payload(p,current)
    assert payload["ReadTimeout"]==30000 and payload["Retries"]==2
