from ansible_collections.susunola.tencentcloud.plugins.modules.tse_gateway_console_network import (
    describe_request, desired, modify_request, readable,
)


class Value(object):
    def from_json_string(self, value): self.json = value
class Models(object):
    DescribeCloudNativeAPIGatewayConfigRequest = Value
    ModifyConsoleNetworkRequest = Value
    NetworkAccessControl = Value


PARAMS = {"gateway_id": "gateway-1", "state": "open", "network_type": "Open",
          "access_control": {"Mode": "Whitelist"}}


def test_console_network_request_and_target_mapping():
    describe = describe_request(Models, "gateway-1")
    modify = modify_request(Models, PARAMS)
    assert describe.GatewayId == "gateway-1"
    assert (modify.NetworkType, modify.Operate) == ("Open", "Open")
    assert desired(PARAMS) == {"NetType": "Open", "Status": "Open", "AccessControl": {"Mode": "Whitelist"}}


def test_readable_removes_console_password():
    assert readable({"ConsoleType": "Konga", "AdminPassword": "secret"}) == {"ConsoleType": "Konga"}
