from ansible_collections.susunola.tencentcloud.plugins.modules.tione_data_source import create_request, delete_request, find, conflict


class Object:
    def from_json_string(self, value): self.value = value
class Models:
    CreateDataSourceRequest = DeleteDataSourceRequest = DescribeDataSourceRequest = DescribeDataSourcesRequest = Filter = MountConfigureInfo = Tag = Object


def params():
    return {"name": "training", "data_source_id": None, "project_id": "p1", "source_type": "CFS", "permission": "RW", "storage_id": "cfs-1", "mount_config": {"WorkDir": "/train"}, "tags": [{"TagKey": "env", "TagValue": "prod"}]}


def test_create_maps_storage_mount_and_tags():
    request = create_request(Models, params())
    assert request.Name == "training" and request.Type == "CFS" and request.Permission == "RW" and request.StorageId == "cfs-1"
    assert request.MountConfigure is not None and len(request.Tags) == 1


def test_delete_uses_stable_id_and_workspace():
    p = params(); p["data_source_id"] = "ds-1"
    request = delete_request(Models, p)
    assert request.Id == "ds-1" and request.TiProjectId == "p1"


class Item:
    def __init__(self, value): self.value = value; self.Name = value.get("Name")
    def _serialize(self, allow_none=True): return dict(self.value)
class Response:
    def __init__(self, values, total): self.DataSourceInfos, self.TotalCount = [Item(x) for x in values], total
class Client:
    def __init__(self): self.responses = [Response([{"Id": "ds-1", "Name": "training"}], 1)]
    def DescribeDataSources(self, request): return self.responses.pop(0)
class Module:
    def sdk_call(self, fn, request): return fn(request)
    def fail_json(self, **kwargs): raise AssertionError(kwargs)


def test_find_by_name_is_exact_and_paginated():
    value = find(Module(), Client(), Models, params())
    assert value == {"Id": "ds-1", "Name": "training"}


def test_conflict_normalizes_tag_order():
    p = params(); p["tags"] = [{"TagKey": "b", "TagValue": "2"}, {"TagKey": "a", "TagValue": "1"}]
    current = {"Name": "training", "Type": "CFS", "Permission": "RW", "StorageId": "cfs-1", "MountConfigure": {"WorkDir": "/train"}, "Tags": list(reversed(p["tags"]))}
    assert conflict(p, current) == {}
