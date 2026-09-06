from ansible_collections.susunola.tencentcloud.plugins.modules.dlc_user_vpc_connection import create_request, delete_request, describe_request


class Object:
    pass


class Models:
    DescribeUserVpcConnectionRequest = Object
    CreateUserVpcConnectionRequest = Object
    DeleteUserVpcConnectionRequest = Object


def test_describe_can_filter_by_exact_endpoint_id():
    request = describe_request(Models, "network-1", "vpce-1")
    assert request.EngineNetworkId == "network-1" and request.UserVpcEndpointIds == ["vpce-1"]


def test_create_maps_network_endpoint_contract():
    request = create_request(
        Models, {"engine_network_id": "network-1", "vpc_id": "vpc-1", "subnet_id": "subnet-1", "endpoint_name": "lake", "endpoint_vip": "10.0.0.8"}
    )
    assert request.EngineNetworkId == "network-1" and request.UserVpcId == "vpc-1"
    assert request.UserSubnetId == "subnet-1" and request.UserVpcEndpointVip == "10.0.0.8"


def test_delete_requires_both_network_and_endpoint_identity():
    request = delete_request(Models, "network-1", "vpce-1")
    assert request.EngineNetworkId == "network-1" and request.UserVpcEndpointId == "vpce-1"
