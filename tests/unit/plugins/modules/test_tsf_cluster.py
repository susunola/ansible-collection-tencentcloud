from ansible_collections.susunola.tencentcloud.plugins.modules.tsf_cluster import comparable, desired

def test_cluster_desired_maps_creation_and_mutable_fields():
    p={"name":"prod","cluster_type":"C","description":"main","remark_name":None,"vpc_id":"vpc-1","subnet_id":"subnet-1","cluster_cidr":None,"tsf_region_id":None,"tsf_zone_id":None,"cluster_version":None,"max_node_pods":64,"max_cluster_services":None,"enable_log_collection":True}
    assert desired(p)=={"ClusterName":"prod","ClusterType":"C","ClusterDesc":"main","VpcId":"vpc-1","SubnetId":"subnet-1","MaxNodePodNum":64,"EnableLogCollection":True}

def test_cluster_does_not_compare_create_only_capacity_fields():
    target={"ClusterName":"prod","MaxNodePodNum":64}
    assert comparable({"ClusterName":"prod","ClusterId":"c1"},target)=={"ClusterName":"prod"}
