"""Unit tests for the mongodb_instance write module helpers."""

from __future__ import absolute_import, division, print_function

__metaclass__ = type
from ansible_collections.susunola.tencentcloud.plugins.modules.mongodb_instance import (
    _create,
    _delete,
    _rename,
    build_create_request,
    build_describe_request,
    find_instance,
)


class FakeRequest(object):
    pass


class FakeTag(object):
    def __init__(self):
        self.TagKey = None
        self.TagValue = None


class FakeModels(object):
    DescribeDBInstancesRequest = FakeRequest
    CreateDBInstanceRequest = FakeRequest
    CreateDBInstanceHourRequest = FakeRequest
    RenameInstanceRequest = FakeRequest
    IsolateDBInstanceRequest = FakeRequest
    TagInfo = FakeTag


class FakeInstance(object):
    def __init__(self, instance_id, name):
        self.InstanceId = instance_id
        self.InstanceName = name

    def _serialize(self, allow_none=True):
        return {"InstanceId": self.InstanceId, "InstanceName": self.InstanceName}


class FakeResponse(object):
    def __init__(self, instances):
        self.InstanceDetails = instances


class FakeCreateResponse(object):
    def __init__(self, instance_ids):
        self.InstanceIds = instance_ids


class FakeClient(object):
    def __init__(self, response=None, exc=None):
        self.response = response
        self.exc = exc
        self.calls = []

    def DescribeDBInstances(self, request):
        self.calls.append(request)
        if self.exc:
            raise self.exc
        return self.response

    def CreateDBInstance(self, request):
        self.calls.append(("CreateDBInstance", request))
        if self.exc:
            raise self.exc
        return self.response

    def CreateDBInstanceHour(self, request):
        self.calls.append(("CreateDBInstanceHour", request))
        if self.exc:
            raise self.exc
        return self.response

    def RenameInstance(self, request):
        self.calls.append(request)
        if self.exc:
            raise self.exc
        return self.response

    def IsolateDBInstance(self, request):
        self.calls.append(request)
        if self.exc:
            raise self.exc
        return self.response


class FakeModule(object):
    def __init__(self):
        self.params = {"retries": 2}

    def sdk_call(self, operation, request):
        return operation(request)


BASE_PARAMS = {
    "name": "prod-mongo",
    "memory": 8,
    "volume": 100,
    "mongo_version": "5.0",
    "zone": "ap-guangzhou-3",
    "cluster_type": "REPLSET",
    "node_num": 3,
    "replicate_set_num": None,
    "password": "secret",
    "vpc_id": "vpc-xxxxxxxx",
    "subnet_id": "subnet-xxxxxxxx",
    "project_id": None,
    "period_months": None,
    "auto_renew": None,
    "security_group": None,
    "tags": {},
}


def test_build_describe_request_by_id():
    request = build_describe_request(FakeModels, "cmgo-123", None)
    assert request.InstanceIds == ["cmgo-123"]
    assert request.Limit == 100
    assert not hasattr(request, "SearchKey") or request.SearchKey is None


def test_build_describe_request_by_name():
    request = build_describe_request(FakeModels, None, "prod-mongo")
    assert request.SearchKey == "prod-mongo"
    assert not hasattr(request, "InstanceIds") or request.InstanceIds is None


def test_find_instance_by_id_returns_first():
    client = FakeClient(FakeResponse([FakeInstance("cmgo-1", "prod-mongo")]))
    module = FakeModule()
    instance = find_instance(module, client, FakeModels, "cmgo-1", None)
    assert instance["InstanceId"] == "cmgo-1"
    assert len(client.calls) == 1


def test_find_instance_by_name_matches_name():
    client = FakeClient(FakeResponse([
        FakeInstance("cmgo-1", "other"),
        FakeInstance("cmgo-2", "prod-mongo"),
    ]))
    module = FakeModule()
    instance = find_instance(module, client, FakeModels, None, "prod-mongo")
    assert instance["InstanceId"] == "cmgo-2"


def test_find_instance_returns_none_when_absent():
    client = FakeClient(FakeResponse([]))
    module = FakeModule()
    assert find_instance(module, client, FakeModels, "cmgo-9", None) is None


def test_build_create_request_sends_core_fields():
    request = build_create_request(FakeModels, BASE_PARAMS)
    assert request.Memory == 8
    assert request.Volume == 100
    assert request.MongoVersion == "5.0"
    assert request.Zone == "ap-guangzhou-3"
    assert request.ClusterType == "REPLSET"
    assert request.NodeNum == 3
    assert request.GoodsNum == 1
    assert request.InstanceName == "prod-mongo"
    assert request.Password == "secret"
    assert request.VpcId == "vpc-xxxxxxxx"
    assert request.SubnetId == "subnet-xxxxxxxx"


def test_build_create_request_shard_sends_replicate_set_num():
    params = dict(BASE_PARAMS, cluster_type="SHARD", replicate_set_num=3, node_num=None)
    request = build_create_request(FakeModels, params)
    assert request.ReplicateSetNum == 3
    assert request.ClusterType == "SHARD"
    assert not hasattr(request, "NodeNum")


def test_build_create_request_omits_optional_fields():
    params = dict(BASE_PARAMS, name=None, password=None, vpc_id=None, subnet_id=None)
    request = build_create_request(FakeModels, params)
    assert not hasattr(request, "InstanceName")
    assert not hasattr(request, "Password")
    assert not hasattr(request, "VpcId")
    assert not hasattr(request, "SubnetId")


def test_build_create_request_tags():
    params = dict(BASE_PARAMS, tags={"env": "prod", "team": "ops"})
    request = build_create_request(FakeModels, params)
    assert [t.TagKey for t in request.Tags] == ["env", "team"]


def test_create_prepaid_uses_create_db_instance():
    client = FakeClient(FakeCreateResponse(["cmgo-1"]))
    module = FakeModule()
    params = dict(BASE_PARAMS, period_months=1)
    created = _create(module, client, FakeModels, params)
    assert created == "cmgo-1"
    assert client.calls[-1][0] == "CreateDBInstance"


def test_create_postpaid_uses_create_db_instance_hour():
    client = FakeClient(FakeCreateResponse(["cmgo-1"]))
    module = FakeModule()
    created = _create(module, client, FakeModels, BASE_PARAMS)
    assert created == "cmgo-1"
    assert client.calls[-1][0] == "CreateDBInstanceHour"


def test_rename_sends_new_name():
    client = FakeClient(FakeResponse(None))
    module = FakeModule()
    _rename(module, client, FakeModels, "cmgo-1", "prod-mongo-v2")
    request = client.calls[-1]
    assert request.InstanceId == "cmgo-1"
    assert request.NewName == "prod-mongo-v2"


def test_delete_isolates_instance():
    client = FakeClient(FakeResponse(None))
    module = FakeModule()
    _delete(module, client, FakeModels, "cmgo-1")
    assert client.calls[-1].InstanceId == "cmgo-1"
