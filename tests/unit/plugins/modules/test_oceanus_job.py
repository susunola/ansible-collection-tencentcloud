from ansible_collections.susunola.tencentcloud.plugins.modules.oceanus_job import _folder_for_job, describe_request


def test_folder_for_job_finds_nested_placement():
    tree={"Id":"root","JobSet":[],"Children":[{"Id":"folder-a","JobSet":[{"JobId":"job-1"}],"Children":[]}]}
    assert _folder_for_job(tree,"job-1")=="folder-a"


def test_folder_for_job_returns_none_for_missing_job():
    assert _folder_for_job({"Id":"root","JobSet":[],"Children":[]},"missing") is None


def test_describe_request_carries_pagination_offset():
    class Request: pass
    class Filter: pass
    Models=type("Models",(),{"DescribeJobsRequest":Request,"Filter":Filter})
    request=describe_request(Models,{"workspace_id":"space-1","name":"job"},200)
    assert (request.Offset,request.Limit,request.WorkSpaceId)==(200,100,"space-1")
