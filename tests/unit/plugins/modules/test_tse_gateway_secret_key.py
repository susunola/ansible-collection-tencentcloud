from ansible_collections.susunola.tencentcloud.plugins.modules.tse_gateway_secret_key import create_payload, desired_immutable, scrub_secret


def test_create_payload_maps_all_credential_shapes():
    p = {"gateway_id":"g1", "name":"key", "secret_type":"JWT", "generate_type":"Custom", "resource_type":"Consumer", "secret_value":"hidden", "jwt_credential_config":{"Algorithm":"RS256"}, "description":None, "provider":None, "kms_key_name":None, "kms_key_version":None}
    payload = create_payload(p)
    assert payload["JWTCredentialConfig"] == {"Algorithm":"RS256"}
    assert payload["SecretValue"] == "hidden"


def test_scrub_secret_recursively_removes_material():
    value = scrub_secret({"SecretValue":"x", "Nested":{"Token":"y", "ClientSecret":"z", "Name":"safe"}, "Items":[{"Password":"z", "HeaderValue":"h"}]})
    assert value == {"Nested":{"Name":"safe"}, "Items":[{}]}


def test_unspecified_immutable_values_preserve_current():
    p = {"name":"key", "secret_type":None, "generate_type":None, "resource_type":None, "kms_key_name":None, "kms_key_version":None, "description":None, "provider":None}
    current = {"Name":"key", "SecretType":"ApiKey", "GenerateType":"System", "ResourceType":"Consumer"}
    assert desired_immutable(p, current)["SecretType"] == "ApiKey"
