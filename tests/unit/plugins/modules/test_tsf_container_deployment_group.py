from ansible_collections.susunola.tencentcloud.plugins.modules.tsf_container_deployment_group import _ports, comparable, desired

def test_container_group_normalizes_port_order():
    assert _ports([{"Protocol":"TCP","Port":81,"TargetPort":8081,"Name":"z"},{"Protocol":"TCP","Port":80,"TargetPort":8080,"Name":"a"}])[0]["Name"]=="a"

def test_container_group_maps_capacity_and_resources():
    p={"name":"orders","application_id":"app-1","namespace_id":"ns-1","cluster_id":"c-1","replicas":3,"cpu_request":"0.5","cpu_limit":"1","memory_request":"512","memory_limit":"1024","access_type":1,"protocol_ports":None,"update_type":0,"update_interval":None,"subnet_id":None,"alias":None,"resource_type":"DEF"}
    target=desired(p)
    assert target["InstanceNum"]==3 and target["MemLimit"]=="1024"
    assert comparable(dict(target,Status="Running"),target)==target
