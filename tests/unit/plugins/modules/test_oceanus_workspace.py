from ansible_collections.susunola.tencentcloud.plugins.modules.oceanus_workspace import describe_request


def test_describe_request_carries_pagination_offset():
    class Filter:
        pass

    class Request:
        pass

    Models = type("Models", (), {"DescribeWorkSpacesRequest": Request, "Filter": Filter})
    request = describe_request(Models, {"name": "production"}, 300)
    assert (request.Offset, request.Limit) == (300, 100)
    assert request.Filters[0].Name == "WorkSpaceName"
