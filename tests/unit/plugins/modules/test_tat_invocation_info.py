from ansible_collections.susunola.tencentcloud.plugins.modules.tat_invocation_info import invocation_request, scrub, task_request


class Value(object): pass
class Models(object):
    DescribeInvocationsRequest = Value
    DescribeInvocationTasksRequest = Value
    Filter = Value


def params(): return {"invocation_id": "inv-1", "command_id": None, "instance_kind": None, "include_output": False, "page_size": 100}


def test_exact_requests_are_bounded_and_hide_task_output():
    p = params(); invocation = invocation_request(Models, p, 0); tasks = task_request(Models, p, 100)
    assert invocation.InvocationIds == ["inv-1"]
    assert tasks.HideOutput is True
    assert tasks.Offset == 100


def test_scrub_removes_command_and_parameter_material():
    value = scrub({"Parameters": '{"password":"x"}', "DefaultParameters": "x", "CommandContent": "base64", "CommandDocument": {"Content": "x"}, "TaskResult": {"Output": "secret", "ExitCode": 0}})
    assert value["Parameters"] == "<redacted>"
    assert value["TaskResult"] == {"Output": "<redacted>"}
    assert "CommandDocument" not in value
