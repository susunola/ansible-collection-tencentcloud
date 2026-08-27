"""Unit tests for the cdb_instance write module helpers."""

from __future__ import absolute_import, division, print_function

__metaclass__ = type
from ansible_collections.susunola.tencentcloud.plugins.modules.cdb_instance import (
    build_describe_request,
    find_instance,
    _create,
    _rename,
    _delete,
)


class FakeRequest(object):
    pass


class FakeTagInfoUnit(object):
    def __init__(self):
        self.TagKey = None
        self.TagValue = None


class FakeModels(object):
    DescribeDBInstancesRequest = FakeRequest
    CreateDBInstanceRequest = FakeRequest
    ModifyDBInstanceNameRequest = FakeRequest
    IsolateDBInstanceRequest = FakeRequest
    TagInfoUnit = FakeTagInfoUnit


class FakeInstance(object):
    def __init__(self, instance_id, name):
        self.InstanceId = instance_id
        self.InstanceName = name
        self.Status = 1
        self.Memory = 8000
        self.Volume = 100
        self.EngineVersion = "8.0"

    def _serialize(self, allow_none=True):
        return {
            "InstanceId": self.InstanceId,
            "InstanceName": self.InstanceName,
            "Status": self.Status,
            "Memory": self.Memory,
            "Volume": self.Volume,
            "EngineVersion": self.EngineVersion,
        }


class FakeDescribeResponse(object):
    def __init__(self, items):
        self.Items = items


class FakeCreateResponse(object):
    def __init__(self, instance_ids):
        self.InstanceIds = instance_ids


class FakeClient(object):
    def __init__(self, describe_response=None, create_response=None, exc=None):
        self.describe_response = describe_response
        self.create_response = create_response
        self.exc = exc
        self.calls = []

    def DescribeDBInstances(self, request):
        self.calls.append(("DescribeDBInstances", request))
        if self.exc:
            raise self.exc
        return self.describe_response

    def CreateDBInstance(self, request):
        self.calls.append(("CreateDBInstance", request))
        return self.create_response

    def ModifyDBInstanceName(self, request):
        self.calls.append(("ModifyDBInstanceName", request))

    def IsolateDBInstance(self, request):
        self.calls.append(("IsolateDBInstance", request))


class FakeModule(object):
    def __init__(self):
        self.params = {"retries": 2}

    def sdk_call(self, operation, request):
        return operation(request)


def test_build_describe_request_by_id():
    request = build_describe_request(FakeModels, "cdb-1", None)
    assert request.InstanceIds == ["cdb-1"]
    assert not hasattr(request, "InstanceNames") or request.InstanceNames is None


def test_build_describe_request_by_name():
    request = build_describe_request(FakeModels, None, "prod-mysql")
    assert request.InstanceNames == ["prod-mysql"]
    assert not hasattr(request, "InstanceIds") or request.InstanceIds is None


def test_find_instance_by_id():
    client = FakeClient(FakeDescribeResponse([FakeInstance("cdb-1", "prod-mysql")]))
    module = FakeModule()
    instance = find_instance(module, client, FakeModels, "cdb-1", None)
    assert instance["InstanceId"] == "cdb-1"
    assert len(client.calls) == 1


def test_find_instance_by_exact_name():
    client = FakeClient(FakeDescribeResponse([
        FakeInstance("cdb-1", "prod-mysql"),
        FakeInstance("cdb-2", "prod-mysql-2"),
    ]))
    module = FakeModule()
    instance = find_instance(module, client, FakeModels, None, "prod-mysql")
    assert instance["InstanceId"] == "cdb-1"


def test_find_instance_returns_none_when_absent():
    client = FakeClient(FakeDescribeResponse([]))
    module = FakeModule()
    assert find_instance(module, client, FakeModels, "cdb-9", None) is None


def test_create_sends_all_fields():
    client = FakeClient(create_response=FakeCreateResponse(["cdb-9"]))
    module = FakeModule()
    created_id = _create(module, client, FakeModels, {
        "name": "prod-mysql",
        "zone": "ap-guangzhou-3",
        "engine_version": "8.0",
        "memory": 8000,
        "volume": 100,
        "password": "s3cret",
        "vpc_id": "vpc-1",
        "subnet_id": "subnet-1",
        "project_id": 5,
        "period_months": 12,
        "auto_renew": 1,
        "security_group": ["sg-1"],
        "tags": {"env": "prod"},
    })
    assert created_id == "cdb-9"
    request = client.calls[-1][1]
    assert request.InstanceName == "prod-mysql"
    assert request.Zone == "ap-guangzhou-3"
    assert request.EngineVersion == "8.0"
    assert request.Memory == 8000
    assert request.Volume == 100
    assert request.GoodsNum == 1
    assert request.Password == "s3cret"
    assert request.UniqVpcId == "vpc-1"
    assert request.UniqSubnetId == "subnet-1"
    assert request.ProjectId == 5
    assert request.Period == 12
    assert request.AutoRenewFlag == 1
    assert request.SecurityGroup == ["sg-1"]
    assert [(t.TagKey, t.TagValue) for t in request.ResourceTags] == [("env", "prod")]


def test_create_omits_optional_fields():
    client = FakeClient(create_response=FakeCreateResponse(["cdb-9"]))
    module = FakeModule()
    _create(module, client, FakeModels, {
        "name": "prod-mysql",
        "zone": "ap-guangzhou-3",
        "engine_version": "5.7",
        "memory": 4000,
        "volume": 50,
        "password": None,
        "vpc_id": None,
        "subnet_id": None,
        "project_id": None,
        "period_months": None,
        "auto_renew": None,
        "security_group": None,
        "tags": {},
    })
    request = client.calls[-1][1]
    assert request.InstanceName == "prod-mysql"
    assert not hasattr(request, "Password")
    assert not hasattr(request, "UniqVpcId")
    assert not hasattr(request, "UniqSubnetId")
    assert not hasattr(request, "ProjectId")
    assert not hasattr(request, "Period")
    assert not hasattr(request, "AutoRenewFlag")
    assert not hasattr(request, "SecurityGroup")
    assert not hasattr(request, "ResourceTags")


def test_rename_sends_id_and_name():
    client = FakeClient()
    module = FakeModule()
    _rename(module, client, FakeModels, "cdb-1", "renamed")
    request = client.calls[-1][1]
    assert request.InstanceId == "cdb-1"
    assert request.InstanceName == "renamed"


def test_delete_isolates_instance():
    client = FakeClient()
    module = FakeModule()
    _delete(module, client, FakeModels, "cdb-1")
    assert [c[0] for c in client.calls] == ["IsolateDBInstance"]
    assert client.calls[-1][1].InstanceId == "cdb-1"
