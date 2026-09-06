from ansible_collections.susunola.tencentcloud.plugins.modules.dlc_work_group import describe_request, delete_request


class Request:
    pass


class Filter:
    pass


Models = type("Models", (), {"DescribeWorkGroupsRequest": Request, "DeleteWorkGroupRequest": Request, "Filter": Filter})


def test_describe_request_supports_exact_id_and_pagination():
    request = describe_request(Models, {"work_group_id": 42, "name": None}, 200)
    assert (request.WorkGroupId, request.Offset, request.Limit) == (42, 200, 100)


def test_delete_request_is_narrowly_scoped():
    assert delete_request(Models, 42).WorkGroupIds == [42]
