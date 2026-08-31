from ansible_collections.susunola.tencentcloud.plugins.modules.tsf_microservice import comparable, desired

def test_microservice_maps_managed_fields():
    p={"namespace_id":"ns-1","name":"payments","description":"managed"}
    assert desired(p)=={"NamespaceId":"ns-1","MicroserviceName":"payments","MicroserviceDesc":"managed"}

def test_microservice_comparison_limits_updates_to_supported_fields():
    target={"NamespaceId":"ns-1","MicroserviceName":"orders","MicroserviceDesc":"managed"}
    current=dict(target,MicroserviceId="ms-1",RunInstanceCount=3)
    assert comparable(current,target)=={"NamespaceId":"ns-1","MicroserviceName":"orders","MicroserviceDesc":"managed"}
