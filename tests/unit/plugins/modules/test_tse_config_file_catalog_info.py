from ansible_collections.susunola.tencentcloud.plugins.modules.tse_config_file_catalog_info import fetch_all, request


class Request(object): pass
class Tag(object):
    def from_json_string(self, value): self.json = value
class Models(object):
    DescribeConfigFilesRequest = Request
    ConfigFileTag = Tag


PARAMS = {"instance_id": "ins-1", "namespace": "prod", "group": "app", "name": None,
          "config_file_id": None, "tags": [{"Key": "team", "Value": "payments"}], "page_size": 2}


def test_catalog_request_maps_filters_and_pagination():
    value = request(Models, PARAMS, 4)
    assert (value.InstanceId, value.Namespace, value.Group, value.Offset, value.Limit) == ("ins-1", "prod", "app", 4, 2)
    assert len(value.Tags) == 1


class Item(object):
    def __init__(self, value): self.value = value
    def _serialize(self, allow_none=False): return {"Name": self.value}
class Response(object):
    def __init__(self, values, total, request_id): self.ConfigFiles, self.TotalCount, self.RequestId = [Item(v) for v in values], total, request_id
class Client(object):
    def __init__(self): self.offsets = []
    def DescribeConfigFiles(self, value):
        self.offsets.append(value.Offset)
        return Response(["a", "b"] if value.Offset == 0 else ["c"], 3, "request-%s" % value.Offset)
class Module(object):
    def sdk_call(self, operation, value): return operation(value)


def test_fetch_all_paginates_catalog():
    client = Client()
    values, total, request_id = fetch_all(Module(), client, Models, PARAMS)
    assert values == [{"Name": "a"}, {"Name": "b"}, {"Name": "c"}]
    assert (total, request_id, client.offsets) == (3, "request-2", [0, 2])
