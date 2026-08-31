from ansible_collections.susunola.tencentcloud.plugins.modules.tse_gateway_certificate import create_payload, metadata_request, modify_payload, scrub


def test_ssl_create_payload_excludes_private_material():
    p={"gateway_id":"g1","name":"api","cert_source":"ssl","ssl_certificate_id":"ssl1","bind_domains":["api.example.com"],"cert_type":"SVR","cert_usage":"SERVER"}
    payload=create_payload(p)
    assert payload["CertId"]=="ssl1" and "Key" not in payload


def test_native_modify_requires_explicit_material_from_params():
    p={"gateway_id":"g1","name":None,"bind_domains":None,"cert_source":None,"ssl_certificate_id":None,"private_key":"private","certificate":"public"}
    payload=modify_payload(p,{"Id":"c1","Name":"api","BindDomains":[],"CertSource":"native","Crt":"old"})
    assert payload["Key"]=="private" and payload["Crt"]=="public"


def test_private_key_is_always_scrubbed():
    assert scrub({"Cert":{"Key":"private","Crt":"public"}})=={"Cert":{"Crt":"public"}}


class Value(object): pass
class Models(object): UpdateCloudNativeAPIGatewayCertificateInfoRequest=Value


def test_metadata_request_does_not_require_certificate_material():
    value=metadata_request(Models,{"gateway_id":"g1","name":"renamed","bind_domains":["api.example.com"]},{"Id":"c1","Name":"old","BindDomains":[]})
    assert (value.GatewayId,value.Id,value.Name,value.BindDomains)==("g1","c1","renamed",["api.example.com"])
