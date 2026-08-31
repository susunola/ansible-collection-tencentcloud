import json

from ansible_collections.susunola.tencentcloud.plugins.modules.tse_gateway_server_group import create_request, delete_request, resize_request, update_request


class Value(object):
    def from_json_string(self,raw): self.raw=raw
class Models(object):
    CreateNativeGatewayServerGroupRequest=Value
    ModifyNativeGatewayServerGroupRequest=Value
    UpdateCloudNativeAPIGatewaySpecRequest=Value
    DeleteNativeGatewayServerGroupRequest=Value


def test_server_group_requests_map_full_lifecycle():
    p={"gateway_id":"g1","name":"workers","node_config":{"Specification":"4c8g","Number":3},"subnet_id":"subnet-1","description":"worker pool","internet_max_bandwidth_out":None,"internet_config":None}
    assert json.loads(create_request(Models,p).raw)["SubnetId"]=="subnet-1"
    assert json.loads(update_request(Models,p,"group-1",{"Name":"workers-v2","Description":"new"}).raw)["GroupId"]=="group-1"
    assert json.loads(resize_request(Models,p,"group-1").raw)["NodeConfig"]["Number"]==3
    assert json.loads(delete_request(Models,p,"group-1").raw)=={"GatewayId":"g1","GroupId":"group-1"}
