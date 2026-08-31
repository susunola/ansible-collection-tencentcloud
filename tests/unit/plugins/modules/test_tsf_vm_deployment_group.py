from ansible_collections.susunola.tencentcloud.plugins.modules.tsf_vm_deployment_group import comparable, desired

def test_vm_group_maps_scope_and_mutable_metadata():
    p={"name":"orders","application_id":"app-1","namespace_id":"ns-1","cluster_id":"cluster-1","description":"prod","alias":None,"resource_type":"DEF"}
    assert desired(p)=={"GroupName":"orders","ApplicationId":"app-1","NamespaceId":"ns-1","ClusterId":"cluster-1","GroupDesc":"prod","GroupResourceType":"DEF"}

def test_vm_group_comparison_ignores_runtime_and_package_state():
    target={"GroupName":"orders","GroupDesc":"prod"}
    current=dict(target,GroupStatus="Running",PackageVersion="1.2.3",InstanceCount=4)
    assert comparable(current,target)==target
