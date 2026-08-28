"""Unit tests for the cdb_instance write module helpers."""

from __future__ import absolute_import, division, print_function

__metaclass__ = type
import pytest

from ansible_collections.susunola.tencentcloud.plugins.modules.cdb_instance import (
    build_describe_request,
    build_restart_request,
    build_task_status_request,
    find_instance,
    _create,
    _rename,
    _delete,
    _restart,
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
    RestartDBInstancesRequest = FakeRequest
    DescribeAsyncRequestInfoRequest = FakeRequest
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


class FakeRestartResponse(object):
    def __init__(self, async_request_id):
        self.AsyncRequestId = async_request_id


class FakeTaskResponse(object):
    def __init__(self, status, info=None):
        self.Status = status
        self.Info = info


class FakeClient(object):
    def __init__(self, describe_response=None, create_response=None, exc=None):
        self.describe_response = describe_response
        self.create_response = create_response
        self.exc = exc
        self.restart_response = None
        self.task_responses = []
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

    def RestartDBInstances(self, request):
        self.calls.append(("RestartDBInstances", request))
        return self.restart_response

    def DescribeAsyncRequestInfo(self, request):
        self.calls.append(("DescribeAsyncRequestInfo", request))
        return self.task_responses.pop(0)


class FakeModule(object):
    def __init__(self):
        self.params = {"retries": 2, "waiter_timeout": 10, "waiter_delay": 1}
        self.check_mode = False

    def sdk_call(self, operation, request):
        return operation(request)

    def fail_json(self, *args, **kwargs):
        if args:
            kwargs["msg"] = args[0]
        kwargs["failed"] = True
        raise SystemExit(kwargs)


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


def test_build_restart_request_sends_instance_ids_array():
    request = build_restart_request(FakeModels, "cdb-1")
    assert request.InstanceIds == ["cdb-1"]


def test_build_task_status_request_sends_async_request_id():
    request = build_task_status_request(FakeModels, "task-1")
    assert request.AsyncRequestId == "task-1"


def test_restart_polls_async_task_until_success():
    client = FakeClient()
    client.restart_response = FakeRestartResponse("task-1")
    client.task_responses = [
        FakeTaskResponse("RUNNING"),
        FakeTaskResponse("INITIAL"),
        FakeTaskResponse("SUCCESS", "restart ok"),
    ]
    module = FakeModule()
    _restart(module, client, FakeModels, "cdb-1")
    names = [c[0] for c in client.calls]
    assert names == [
        "RestartDBInstances",
        "DescribeAsyncRequestInfo",
        "DescribeAsyncRequestInfo",
        "DescribeAsyncRequestInfo",
    ]
    assert client.calls[0][1].InstanceIds == ["cdb-1"]
    assert all(
        request.AsyncRequestId == "task-1"
        for name, request in client.calls[1:]
    )


def test_restart_fails_fast_on_task_failure():
    client = FakeClient()
    client.restart_response = FakeRestartResponse("task-1")
    client.task_responses = [FakeTaskResponse("FAILED", "restart rejected")]
    module = FakeModule()
    with pytest.raises(SystemExit) as excinfo:
        _restart(module, client, FakeModels, "cdb-1")
    assert "restart rejected" in excinfo.value.args[0]["msg"]
    assert [c[0] for c in client.calls] == ["RestartDBInstances", "DescribeAsyncRequestInfo"]


def test_restart_fails_when_no_async_request_id():
    client = FakeClient()
    client.restart_response = FakeRestartResponse(None)
    module = FakeModule()
    with pytest.raises(SystemExit) as excinfo:
        _restart(module, client, FakeModels, "cdb-1")
    assert "no AsyncRequestId" in excinfo.value.args[0]["msg"]
    assert [c[0] for c in client.calls] == ["RestartDBInstances"]
