from ansible_collections.susunola.tencentcloud.plugins.modules.tdmysql_parameter import (
    describe_request,
    flow_request,
    modify_request,
    read_parameters,
    selected,
)


class Object:
    pass


class Models:
    DescribeDBParametersRequest = DescribeFlowRequest = ModifyDBParametersRequest = DBParamValue = Object


def test_requests_map_instance_task_and_sorted_values():
    assert describe_request(Models, "db1").InstanceId == "db1" and flow_request(Models, 42).FlowId == 42
    request = modify_request(Models, "db1", {"z": 2, "a": True})
    assert [(x.Param, x.Value) for x in request.Params] == [("a", "True"), ("z", "2")]


class Item:
    def __init__(self, name, value):
        self.Param, self.value = name, value

    def _serialize(self, allow_none=True):
        return {"Param": self.Param, "Value": self.value, "NeedRestart": False}


class Response:
    Params = [Item("b", "2"), Item("a", "1")]


class Client:
    def DescribeDBParameters(self, request):
        return Response()


class Module:
    def sdk_call(self, fn, request):
        return fn(request)


def test_read_and_select_parameters_are_name_keyed_and_stable():
    values = read_parameters(Module(), Client(), Models, "db1")
    assert selected(values, ["a"])["a"]["Value"] == "1" and list(selected(values, ["b", "a"])) == ["a", "b"]
