from ansible_collections.susunola.tencentcloud.plugins.modules.tat_invocation import cancel_request, invoke_request, tasks_request


class Value(object): pass
class Models(object):
    InvokeCommandRequest = Value
    CancelInvocationRequest = Value
    DescribeInvocationTasksRequest = Value
    Filter = Value


def test_invoke_request_is_canonical_and_deduplicates_targets():
    value = invoke_request(Models, {"command_id": "cmd-1", "instance_ids": ["ins-2", "ins-1", "ins-1"], "parameters": {"z": 2, "a": 1}, "username": "deploy", "working_directory": None, "timeout": 60, "output_cos_bucket_url": None, "output_cos_key_prefix": None})
    assert value.InstanceIds == ["ins-1", "ins-2"]
    assert value.Parameters == '{"a":"1","z":"2"}'
    assert value.Username == "deploy"


def test_cancel_can_target_selected_instances():
    value = cancel_request(Models, {"invocation_id": "inv-1", "instance_ids": ["ins-2", "ins-1"]})
    assert value.InvocationId == "inv-1"
    assert value.InstanceIds == ["ins-1", "ins-2"]


def test_task_query_hides_output_by_default():
    value = tasks_request(Models, "inv-1", 100, False)
    assert value.HideOutput is True
    assert value.Filters[0].Name == "invocation-id"
    assert value.Filters[0].Values == ["inv-1"]
