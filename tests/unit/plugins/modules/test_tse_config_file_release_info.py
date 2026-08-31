from ansible_collections.susunola.tencentcloud.plugins.modules.tse_config_file_release_info import (
    fetch_pages, history_request, release_request, version_request,
)


class Request(object): pass
class Models(object):
    DescribeConfigFileReleasesRequest = Request
    DescribeConfigFileReleaseHistoriesRequest = Request
    DescribeConfigFileReleaseVersionsRequest = Request


PARAMS = {"instance_id": "ins-1", "namespace": "prod", "group": "app", "name": "a.yaml",
          "config_file_id": "file-1", "release_name": "stable", "only_in_use": True, "page_size": 2}


def test_audit_requests_map_release_identity():
    release = release_request(Models, PARAMS, 4)
    history = history_request(Models, PARAMS, 6)
    version = version_request(Models, PARAMS)
    assert (release.FileName, release.ReleaseName, release.Offset, release.Limit) == ("a.yaml", "stable", 4, 2)
    assert (history.Name, history.ConfigFileId, history.Offset) == ("a.yaml", "file-1", 6)
    assert (version.FileName, version.ConfigFileId) == ("a.yaml", "file-1")


class Item(object):
    def __init__(self, value): self.value = value
    def _serialize(self, allow_none=False): return {"Value": self.value}


class Response(object):
    def __init__(self, values, total, request_id):
        self.Releases, self.TotalCount, self.RequestId = [Item(v) for v in values], total, request_id


class Module(object):
    def sdk_call(self, operation, request): return operation(request)


def test_fetch_pages_collects_all_releases():
    offsets = []
    def operation(request):
        offsets.append(request.Offset)
        return Response([1, 2] if request.Offset == 0 else [3], 3, "request-%s" % request.Offset)
    values, total, request_id = fetch_pages(
        Module(), operation, lambda offset: release_request(Models, PARAMS, offset), "Releases"
    )
    assert values == [{"Value": 1}, {"Value": 2}, {"Value": 3}]
    assert (total, request_id, offsets) == (3, "request-2", [0, 2])
