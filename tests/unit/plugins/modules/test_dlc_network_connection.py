from ansible_collections.susunola.tencentcloud.plugins.modules.dlc_network_connection import describe_request, update_request


class Object:
    pass


class Models:
    DescribeNetworkConnectionsRequest = UpdateNetworkConnectionRequest = Object


def params():
    return {"name": "analytics-vpc", "data_engine_name": "spark-prod", "vpc_id": "vpc-1", "connection_type": 2}


def test_describe_scopes_exact_connection_identity_and_paginates():
    request = describe_request(Models, params(), 100)
    assert request.NetworkConnectionName == "analytics-vpc"
    assert request.DataEngineName == "spark-prod" and request.DatasourceConnectionVpcId == "vpc-1"
    assert request.NetworkConnectionType == 2 and request.Offset == 100 and request.Limit == 100


def test_update_only_changes_description_for_exact_name():
    request = update_request(Models, "analytics-vpc", "production route")
    assert request.NetworkConnectionName == "analytics-vpc"
    assert request.NetworkConnectionDesc == "production route"
