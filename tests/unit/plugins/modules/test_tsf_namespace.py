from ansible_collections.susunola.tencentcloud.plugins.modules.tsf_namespace import comparable, desired


def test_namespace_converts_high_availability_to_sdk_value():
    params = {"name": "prod", "cluster_id": "cluster-1", "description": "production",
              "resource_type": "DEF", "namespace_type": "DEF", "high_availability": True,
              "create_k8s_namespace": None}
    assert desired(params)["IsHaEnable"] == "1"


def test_namespace_create_only_flag_is_not_compared_after_creation():
    target = {"NamespaceName": "prod", "ClusterId": "cluster-1", "CreateK8sNamespaceFlag": True}
    current = {"NamespaceName": "prod", "ClusterId": "cluster-1", "NamespaceId": "namespace-1"}
    assert comparable(current, target) == {"NamespaceName": "prod", "ClusterId": "cluster-1"}
